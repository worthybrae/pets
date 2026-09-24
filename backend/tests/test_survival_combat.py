import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.carrying import CARRY_STACKS
from backend.survival.creatures import combat
from backend.survival.creatures.combat import ATTACK_REACH, LUNGE, blow, drops_of, weapon
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def meadow():
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def animal(grid, kind="cow", cell=(2, 1, 0), health=None):
    creature = grid.herd.add(kind, cell, KINDS[kind].health if health is None else health, 0.0, 0.0,
                             {"home": list(cell), "chunk": [0, 0], "turn": 0})
    grid.herd.note_chunk((0, 0), 1, 1, 0.0)
    return creature


def attack(creature):
    return {"kind": "attack", "creature": creature["id"]}


class BlowTests(unittest.TestCase):
    def test_a_bare_hand_or_the_best_sword_carried(self):
        self.assertEqual((weapon({}), blow(None)), (None, (1.0, 0.6)))
        self.assertEqual(weapon({"wooden_sword": 1, "stone_sword": 1}), "stone_sword")
        self.assertEqual([blow(sword)[0] for sword in ("wooden_sword", "stone_sword", "iron_sword")], [4.0, 5.0, 6.0])
        self.assertEqual(blow("iron_sword")[1], 0.5)

    def test_drops_are_rolled_from_the_seed_and_stay_in_their_ranges(self):
        cows = [drops_of("5", {"id": number}, KINDS["cow"]) for number in range(60)]
        self.assertEqual(cows, [drops_of("5", {"id": number}, KINDS["cow"]) for number in range(60)])
        self.assertTrue(all(1 <= found["raw_beef"] <= 3 and found.get("leather", 0) <= 2 for found in cows))
        self.assertEqual({found.get("leather", 0) for found in cows}, {0, 1, 2})
        rabbits = [drops_of("5", {"id": number}, KINDS["rabbit"]) for number in range(60)]
        self.assertTrue(all(found["raw_rabbit"] == 1 for found in rabbits))
        self.assertEqual({found.get("rabbit_hide", 0) for found in rabbits}, {0, 1})
        self.assertEqual(drops_of("5", {"id": 1}, KINDS["fish"]), {})


class AttackStepTests(unittest.TestCase):
    def test_a_swing_takes_longer_by_hand_and_needs_the_animal_within_reach(self):
        grid, state = meadow(), pet()
        cow = animal(grid)
        step = start_step(attack(cow), state, grid, 10.0)
        self.assertEqual((step["ends_at"], step["target"], step["creature"]),
                         (10.6, {"x": 2, "y": 1, "z": 0}, cow["id"]))
        armed = start_step(attack(cow), pet(inventory={"wooden_sword": 1}), grid, 10.0, scale=10.0)
        self.assertEqual((armed["ends_at"], armed["weapon"]), (10.05, "wooden_sword"))
        far = animal(grid, cell=(3, 1, 0))
        self.assertGreater(3.0, ATTACK_REACH)
        with self.assertRaisesRegex(StepFailed, "out of reach"):
            start_step(attack(far), state, grid, 10.0)
        with self.assertRaisesRegex(StepFailed, "got away"):
            start_step({"kind": "attack", "creature": 999}, state, grid, 10.0)
        with self.assertRaisesRegex(StepFailed, "bad step: creature"):
            start_step({"kind": "attack", "creature": "cow"}, state, grid, 10.0)
        with self.assertRaisesRegex(StepFailed, "got away"):
            start_step(attack(cow), state, Grid(lambda x, y, z: "air"), 10.0)

    def test_a_hit_hurts_the_animal_and_it_runs_away_from_mimo(self):
        grid, state = meadow(), pet()
        cow = animal(grid)
        step = start_step(attack(cow), state, grid, 10.0)
        self.assertIsNone(finish_step(step, state, grid, 10.6))
        hurt = grid.herd.get(cow["id"])
        self.assertEqual((hurt["health"], hurt["state"]["hurt_at"], hurt["state"]["pose"]), (9.0, 10.6, "fleeing"))
        path = hurt["state"]["path"]
        self.assertEqual(path[0]["at"], 10.6)
        self.assertGreater(math.hypot(path[-1]["x"], path[-1]["z"]), 6)

    def test_an_animal_that_ran_off_before_the_swing_landed_is_missed_and_no_failure(self):
        grid, state = meadow(), pet()
        cow = animal(grid)
        state["queue"] = [attack(cow)]
        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])
        advance_actions(state, context, 0.3)
        self.assertEqual((state["action"]["kind"], state["action"]["ends_at"]), ("attack", 0.6))
        away = grid.herd.get(cow["id"])
        away["x"] = ATTACK_REACH + LUNGE + 1.0  # it walked off while Mimo wound up
        grid.herd.save(away)
        advance_actions(state, context, 1.0)
        missed = grid.herd.get(cow["id"])
        self.assertEqual((missed["health"], missed["state"].get("hurt_at")), (KINDS["cow"].health, None))
        self.assertEqual(state["recent_actions"][-1]["result"], "done")
        self.assertIsNone(state.get("last_failure"))
        self.assertNotIn("hunted_at", state)
        self.assertEqual(context.events, [])

    def test_a_blow_acts_in_a_scene_that_reports_into_the_ticks_events(self):
        grid, state = meadow(), pet()
        cow = animal(grid)
        state["queue"] = [attack(cow)]
        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])
        scenes = []

        def strike(scene, *args):
            scenes.append(scene)
            return real(scene, *args)

        real = combat.strike
        with patch("backend.survival.creatures.combat.strike", strike):
            advance_actions(state, context, 1.0)
        self.assertEqual(len(scenes), 1)
        self.assertIs(scenes[0].events, context.events)

    def test_the_killing_blow_puts_the_drops_in_mimos_arms(self):
        grid, state = meadow(), pet(inventory={"stone_sword": 1})
        cow = animal(grid, health=5.0)
        step = start_step(attack(cow), state, grid, 10.0)
        event = finish_step(step, state, grid, 10.5)
        self.assertEqual(event, ("hunt", "Pip hunted a cow."))
        found = drops_of("5", cow, KINDS["cow"])
        self.assertEqual(state["inventory"], {"stone_sword": 1, **found})
        body = grid.herd.get(cow["id"])
        self.assertTrue(dead(body))
        self.assertEqual((body["health"], body["state"]["dead_at"], body["state"]["drops"]), (0.0, 10.5, sorted(found)))
        self.assertEqual(state["hunted_at"], 10.5)
        self.assertEqual(grid.herd.chunks((0, 0), (0, 0))[(0, 0)]["animals"], 0)
        with self.assertRaisesRegex(StepFailed, "got away"):
            start_step(attack(cow), state, grid, 11.0)

    def test_what_does_not_fit_in_full_arms_stays_behind_and_meat_pushes_out_dirt(self):
        grid = meadow()
        filler = {f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}
        state = pet(inventory={**filler, "dirt": 3})
        cow = animal(grid, health=1.0)
        state["queue"] = [attack(cow)]
        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])
        advance_actions(state, context, 1.0)
        found = drops_of("5", cow, KINDS["cow"])
        self.assertIn("leather", found)  # left behind: it is not worth more than the dirt
        self.assertEqual(state["inventory"], {**filler, "raw_beef": found["raw_beef"]})
        self.assertIsNotNone(state["full_at"])
        self.assertIn((0.6, "hunt", "Pip hunted a cow."), context.events)


if __name__ == "__main__":
    unittest.main()

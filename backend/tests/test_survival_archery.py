import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import craft
from backend.survival import nature
from backend.survival.actions import ActionContext, advance_actions, ensure_actions, record
from backend.survival.carrying import valuable
from backend.survival.creatures import hostiles  # noqa: F401  (registers the gloomling and the skitter)
from backend.survival.creatures.archery import SHOOT_RANGE, hit_chance
from backend.survival.creatures.combat import drops_of
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.snapshot import action_view
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(inventory=None):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
             "inventory": {"bow": 1, "arrow": 4} if inventory is None else inventory, "vitals": dict(START_VITALS),
             "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    ensure_actions(state)
    return state


def creature(grid, kind="gloomling", cell=(10, 1, 0), health=None):
    return grid.herd.add(kind, cell, KINDS[kind].health if health is None else health, 0.0, 0.0,
                         {"home": list(cell), "turn": 0, "pose": "idle"})


def shoot(target):
    return {"kind": "shoot", "creature": target["id"]}


class BowTests(unittest.TestCase):
    def test_a_bow_and_arrows_are_made_at_a_crafting_table_and_are_worth_carrying(self):
        self.assertEqual(craft({"sticks": 3, "string": 3}, "bow", {"crafting_table"}), {"bow": 1})
        self.assertEqual(craft({"flint": 1, "sticks": 1, "feather": 1}, "arrow", {"crafting_table"}), {"arrow": 4})
        with self.assertRaisesRegex(ValueError, "crafting_table"):
            craft({"sticks": 3, "string": 3}, "bow", set())
        self.assertTrue(valuable("bow") and valuable("arrow"))

    def test_one_mined_gravel_in_eight_gives_flint(self):
        found = sum("flint" in nature.chance_drops("5", (x, 1, z), "gravel") for x in range(20) for z in range(20))
        self.assertTrue(30 <= found <= 70, found)
        grid, state = meadow({(1, 1, 0): "gravel"}), pet({})
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)
            finish_step(step, state, grid, step["ends_at"])
        self.assertEqual(state["inventory"], {"gravel": 1, "flint": 1})

    def test_the_chance_of_a_hit_falls_with_distance(self):
        self.assertEqual([hit_chance(distance) for distance in (2.0, 4.0, 10.0, 16.0)], [1.0, 1.0, 0.75, 0.5])


class ShootStepTests(unittest.TestCase):
    def test_it_needs_a_bow_an_arrow_and_the_creature_in_range(self):
        grid = meadow()
        gloom = creature(grid)
        step = start_step(shoot(gloom), pet(), grid, 10.0)
        self.assertEqual({key: step[key] for key in ("ends_at", "target", "creature", "hit")},
                         {"ends_at": 11.0, "target": {"x": 10, "y": 1, "z": 0}, "creature": gloom["id"], "hit": True})
        self.assertEqual(start_step(shoot(gloom), pet(), grid, 10.0, scale=10.0)["ends_at"], 10.1)
        for inventory, words in (({"arrow": 4}, "no bow"), ({"bow": 1}, "no arrows")):
            with self.assertRaisesRegex(StepFailed, words) as failed:
                start_step(shoot(gloom), pet(inventory), grid, 10.0)
            self.assertEqual(failed.exception.code, "missing_item")
        far = creature(grid, cell=(int(SHOOT_RANGE) + 2, 1, 0))
        with self.assertRaisesRegex(StepFailed, "out of range"):
            start_step(shoot(far), pet(), grid, 10.0)

    def test_a_hit_spends_the_arrow_hurts_the_creature_and_turns_a_hostile_on_mimo(self):
        grid, state = meadow(), pet()
        gloom = creature(grid, cell=(3, 1, 0))
        step = start_step(shoot(gloom), state, grid, 10.0)
        self.assertIsNone(finish_step(step, state, grid, 11.0))
        hurt = grid.herd.get(gloom["id"])
        self.assertEqual((hurt["health"], hurt["state"]["hurt_at"], hurt["state"]["chasing"]), (15.0, 11.0, True))
        self.assertEqual(state["inventory"], {"bow": 1, "arrow": 3})

    def test_a_miss_or_a_creature_gone_spends_the_arrow_and_nothing_else(self):
        grid, state = meadow(), pet()
        gloom = creature(grid, cell=(15, 1, 0))
        with patch("backend.survival.creatures.archery.roll", lambda *args: 0.99):
            step = start_step(shoot(gloom), state, grid, 10.0)
        self.assertFalse(step["hit"])
        self.assertIsNone(finish_step(step, state, grid, 11.0))
        self.assertEqual(grid.herd.get(gloom["id"])["health"], 20.0)
        gone = start_step(shoot(gloom), state, grid, 12.0)
        grid.herd.remove(gloom["id"])
        self.assertIsNone(finish_step(gone, state, grid, 13.0))
        self.assertEqual(state["inventory"], {"bow": 1, "arrow": 2})

    def test_a_kill_brings_its_drops_a_hunt_for_an_animal_a_fight_for_a_hostile(self):
        grid, state = meadow(), pet()
        rabbit, skitter = creature(grid, "rabbit", (2, 1, 0)), creature(grid, "skitter", (0, 1, 3), health=4.0)
        self.assertEqual(finish_step(start_step(shoot(rabbit), state, grid, 10.0), state, grid, 11.0),
                         ("hunt", "Pip hunted a rabbit."))
        self.assertEqual(finish_step(start_step(shoot(skitter), state, grid, 12.0), state, grid, 13.0),
                         ("fight", "Pip fought off a skitter."))
        self.assertTrue(dead(grid.herd.get(skitter["id"])))
        expected = {"bow": 1, "arrow": 2}
        for body, kind in ((rabbit, "rabbit"), (skitter, "skitter")):
            for item, count in drops_of("5", body, KINDS[kind]).items():
                expected[item] = expected.get(item, 0) + count
        self.assertEqual(state["inventory"], expected)

    def test_in_the_tick_the_viewer_sees_whether_the_arrow_flies_true(self):
        grid, state = meadow(), pet()
        gloom = creature(grid, cell=(5, 1, 0))
        state["queue"] = [shoot(gloom)]
        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])
        advance_actions(state, context, 0.5)
        self.assertEqual(action_view(state["action"])["hit"], True)
        self.assertNotIn("creature", action_view(state["action"]))
        advance_actions(state, context, 1.5)
        self.assertEqual({key: state["recent_actions"][-1][key] for key in ("kind", "result", "hit")},
                         {"kind": "shoot", "result": "done", "hit": True})
        record(state, {"kind": "walk", "started_at": 2.0}, 2.5, "done")
        self.assertNotIn("hit", state["recent_actions"][-1])


if __name__ == "__main__":
    unittest.main()

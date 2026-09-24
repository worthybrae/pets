import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.creatures.hunting import HUNT_BATCHES, prey
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import simulate
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.foraging import hunger_score
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
HUNT = PURPOSES["hunt"]


def meadow():
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "status": "idle", "last_thought": "", "last_tick_at": 0.0,
             "born_at": 0.0, "brain": new_brain(0.0)}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(grid, state=None, clock=DAY, at=100.0):
    return Situation(state or pet(), grid, clock, at, grid.herd.db)


def animal(grid, kind="rabbit", cell=(5, 1, 0), **state):
    return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 1e9, {"home": list(cell), "turn": 0, **state})


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=brain_plan, events=[], db=grid.herd.db)


class PreyTests(unittest.TestCase):
    def test_the_nearest_living_land_animal_within_32_blocks_away_from_failed_steps(self):
        grid = meadow()
        far, near = animal(grid, cell=(20, 1, 0)), animal(grid, "cow", (8, 1, 3))
        animal(grid, "fish", (3, 0, 0))
        animal(grid, cell=(4, 1, 0), pose="dead")
        animal(grid, cell=(40, 1, 0))
        self.assertEqual([found["id"] for found in prey(situation(grid))], [near["id"], far["id"]])
        failed = pet(recent_actions=[{"kind": "walk", "started_at": 1.0, "ended_at": 2.0, "result": "failed",
                                      "target": {"x": 8, "y": 1, "z": 2}}])
        self.assertEqual([found["id"] for found in prey(situation(grid, failed))], [far["id"]])
        self.assertEqual(prey(Situation(pet(), Grid(lambda x, y, z: "air"), DAY, 0.0)), [])

    def test_an_animal_more_than_2_below_its_columns_natural_surface_is_left_alone(self):
        """L3 final fix wave: a hunt after a cave chicken took the seed-11 pet down its own stairs
        and into a pocket it could not climb out of. Cave animals (more than 2 below the top of
        their column's natural ground) are not prey; one on the surface, or 1 or 2 down in a dug
        hole, still is."""
        grid = meadow()
        on_top, dug, cave = animal(grid, cell=(4, 9, 0)), animal(grid, cell=(6, 6, 0)), animal(grid, cell=(8, 5, 0))
        with patch("backend.survival.creatures.hunting.terrain_height", lambda x, z, seed: 8):
            self.assertCountEqual([found["id"] for found in prey(situation(grid))], [on_top["id"], dug["id"]])


class HuntValidityTests(unittest.TestCase):
    def test_offered_by_day_with_prey_near_when_food_is_needed_or_after_a_day_without_a_kill(self):
        grid = meadow()
        animal(grid)
        self.assertTrue(HUNT.valid(situation(grid)))
        self.assertFalse(HUNT.valid(situation(grid, clock=NIGHT)))
        self.assertFalse(HUNT.valid(situation(meadow())))
        fed = {"cooked_beef": 2}
        self.assertTrue(HUNT.valid(situation(grid, pet(inventory=fed))))  # never hunted yet
        self.assertFalse(HUNT.valid(situation(grid, pet(inventory=fed, hunted_at=50.0), at=100.0)))
        self.assertTrue(HUNT.valid(situation(grid, pet(inventory=fed, hunted_at=50.0), at=50.0 + 3600.0)))
        self.assertTrue(HUNT.valid(situation(grid, pet(hunted_at=50.0), at=100.0)))  # hungry for more

    def test_scores_like_food_work_and_bold_pets_hunt_a_little_more(self):
        grid = meadow()
        animal(grid)
        plain = situation(grid)
        self.assertEqual(HUNT.score(plain), hunger_score(plain, 30.0))
        bold = situation(grid, pet(traits={"bravery": 90}))
        self.assertEqual(HUNT.score(bold), HUNT.score(plain) + 4.0)
        hungry = situation(grid, pet(vitals={**START_VITALS, "hunger": 30.0}))
        fed = situation(grid, pet(inventory={"cooked_beef": 2}))
        self.assertGreater(HUNT.score(hungry), HUNT.score(plain))
        self.assertLess(HUNT.score(fed), HUNT.score(plain))
        self.assertIn("rabbit 5 blocks away", HUNT.facts(plain))


class HuntPlanTests(unittest.TestCase):
    def test_walks_to_where_the_animal_is_going_then_attacks_it_within_reach(self):
        grid = meadow()
        rabbit = animal(grid, cell=(9, 1, 0))
        s = situation(grid)
        self.assertEqual(HUNT.plan(s, context(grid)),
                         [{"kind": "walk", "target": [9, 1, 0], "reach": 2.0, "whole": True}])
        self.assertEqual(s.brain["prey"], rabbit["id"])
        close = situation(grid, pet(position={"x": 7.0, "y": 1.0, "z": 0.0}))
        self.assertEqual(HUNT.plan(close, context(grid)),
                         [{"kind": "attack", "creature": rabbit["id"], "target": [9, 1, 0]}])

    def test_keeps_after_the_same_animal_and_stops_when_it_is_gone_or_after_forty_batches(self):
        grid = meadow()
        first, second = animal(grid, cell=(9, 1, 0)), animal(grid, cell=(4, 1, 0))
        state = pet()
        state["brain"].update(purpose="hunt", batches=3, prey=first["id"])
        self.assertEqual(HUNT.plan(situation(grid, state), context(grid))[0]["target"], [9, 1, 0])
        grid.herd.remove(first["id"])
        self.assertEqual(HUNT.plan(situation(grid, state), context(grid)), [])
        self.assertIsNone(state["brain"]["prey"])
        state["brain"].update(batches=HUNT_BATCHES, prey=second["id"])
        self.assertEqual(HUNT.plan(situation(grid, state), context(grid)), [])

    def test_a_hunt_in_the_tick_chases_the_rabbit_down_and_takes_its_meat(self):
        grid = meadow()
        rabbit = animal(grid, cell=(12, 1, 0))
        rabbit["next_at"] = 0.0
        grid.herd.save(rabbit)
        state = pet()
        state["brain"].update(purpose="hunt", pending=None)
        ctx = context(grid)
        at = 0.0
        while at < 120.0 and not dead(grid.herd.get(rabbit["id"])):
            at += 0.5
            advance_actions(state, ctx, at)
            simulate(state, ctx, at)
            ctx.searches_left = 2
        self.assertTrue(dead(grid.herd.get(rabbit["id"])), state["recent_actions"][-3:])
        self.assertEqual(state["inventory"].get("raw_rabbit"), 1)
        self.assertIn("hunt", [event[1] for event in ctx.events])
        swings = [entry for entry in state["recent_actions"] if entry["kind"] == "attack"]
        self.assertEqual({entry["result"] for entry in swings}, {"done"})


if __name__ == "__main__":
    unittest.main()

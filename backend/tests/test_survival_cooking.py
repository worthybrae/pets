import sqlite3
import unittest

from backend.survival import cooking  # noqa: F401  (registers cook)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
COOK = {"kind": "cook", "item": "raw_fish"}


def meadow(edits=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (edits or {}).items():
        grid.put(*cell, block)
    return grid


def situation(inventory, grid=None, hunger=100.0):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": {**START_VITALS, "hunger": hunger}, "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or meadow(), DAY, 0.0, db)


def plan(s):
    return PURPOSES["cook"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                                  events=[], db=s.db))


def craft(recipe):
    return {"kind": "craft", "recipe": recipe}


def place(block):
    return {"kind": "place", "target": [1, 1, 0], "block": block}


PICK_UP = {"kind": "mine", "target": [1, 1, 0], "keep": True}


class CookTests(unittest.TestCase):
    def test_fish_cooks_at_a_fire_that_is_already_near(self):
        s = situation({"raw_fish": 2}, meadow({(3, 1, 0): "campfire"}))
        self.assertTrue(PURPOSES["cook"].valid(s))
        self.assertEqual(plan(s), [COOK, COOK])

    def test_a_carried_campfire_is_lit_for_cooking_and_picked_up_after(self):
        self.assertEqual(plan(situation({"raw_fish": 2, "campfire": 1})), [place("campfire"), COOK, COOK, PICK_UP])

    def test_with_no_fire_mimo_makes_a_campfire_from_logs(self):
        self.assertEqual(plan(situation({"raw_fish": 1, "oak_log": 3})),
                         [craft("planks"), craft("sticks"), craft("campfire"), place("campfire"), COOK, PICK_UP])

    def test_or_walks_to_a_fire_it_can_reach(self):
        s = situation({"raw_fish": 1}, meadow({(20, 1, 0): "furnace"}))
        self.assertEqual(plan(s), [{"kind": "walk", "target": [20, 1, 0], "reach": 2.0, "whole": True}])
        self.assertFalse(PURPOSES["cook"].valid(situation({"raw_fish": 1})))

    def test_wheat_bakes_into_bread_at_a_table(self):
        self.assertEqual(plan(situation({"wheat": 7, "planks": 4})),
                         [craft("crafting_table"), place("crafting_table"), craft("bread"), craft("bread"), PICK_UP])
        self.assertFalse(PURPOSES["cook"].valid(situation({"wheat": 2, "planks": 4})))

    def test_hunger_and_raw_food_raise_the_score(self):
        score = PURPOSES["cook"].score
        self.assertEqual(score(situation({"raw_fish": 2})), 60.0)
        self.assertEqual(score(situation({"raw_fish": 2, "wheat": 3}, hunger=40.0)), 80.0)


if __name__ == "__main__":
    unittest.main()

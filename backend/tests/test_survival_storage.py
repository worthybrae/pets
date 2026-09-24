import sqlite3
import unittest

from backend.survival import farming, storage  # noqa: F401  (register farm, build_storage and drop_items)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, finish_structure, know
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
LOOSE = {"dirt": 40, "moss": 3, "gravel": 5, "sand": 5, "clay": 2, "basalt": 1, "limestone": 1, "sandstone": 1,
         "copper_ore": 2, "brick": 1, "glass": 1, "cobblestone": 20, "oak_log": 3}  # 14 stacks


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


class Home:
    """A pet at the door of a finished 3x3 shelter (inside x 0..2, z 0..2, chest corner (2, 1, 2))."""

    def __init__(self, inventory, chest=None, position=(1, 1, 1)):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = meadow()
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        self.chest = design.one("chest")
        self.state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                      "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        if chest is not None:
            self.grid.put(*self.chest, "chest")
            self.state["chests"] = {"2,1,2": dict(chest)}
        ensure_actions(self.state)

    def situation(self):
        return Situation(self.state, self.grid, DAY, 0.0, self.db)

    def plan(self, name):
        s = self.situation()
        return PURPOSES[name].plan(s, ActionContext(grid=self.grid, clock_at=lambda at: DAY,
                                                    planner=lambda *args: [], events=[], db=self.db))


def store(item, amount):
    return {"kind": "store", "target": [2, 1, 2], "item": item, "amount": amount}


class StorageTests(unittest.TestCase):
    def test_nearly_full_arms_make_a_chest_and_fill_it_with_what_mimo_does_not_need(self):
        home = Home({**LOOSE, "planks": 8})
        self.assertEqual(home.chest, (2, 1, 2))
        self.assertTrue(PURPOSES["build_storage"].valid(home.situation()))
        steps = home.plan("build_storage")
        self.assertEqual(steps[:2], [{"kind": "craft", "recipe": "chest"},
                                     {"kind": "place", "target": [2, 1, 2], "block": "chest"}])
        self.assertEqual(steps[2:6], [store("dirt", 40), store("gravel", 5), store("sand", 5), store("cobblestone", 4)])
        self.assertEqual(len(steps), 2 + 8)

    def test_not_offered_with_room_to_spare_or_without_a_built_shelter(self):
        self.assertFalse(PURPOSES["build_storage"].valid(Home({"dirt": 40, "planks": 8}).situation()))
        home = Home({**LOOSE, "planks": 8})
        home.db.execute("DELETE FROM structures")
        self.assertFalse(PURPOSES["build_storage"].valid(home.situation()))

    def test_it_walks_home_first_and_takes_food_out_when_mimo_carries_little(self):
        home = Home({"cobblestone": 1}, chest={"bread": 4, "berries": 9}, position=(9, 1, 9))
        s = home.situation()
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertEqual(PURPOSES["build_storage"].score(s), 55.0)
        self.assertEqual(home.plan("build_storage"), [
            {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True},
            {"kind": "take", "target": [2, 1, 2], "item": "bread", "amount": 3}])

    def test_more_food_than_a_days_worth_goes_in_the_chest(self):
        home = Home({**LOOSE, "bread": 4, "berries": 10}, chest={})
        steps = home.plan("build_storage")
        self.assertIn(store("berries", 10), steps)
        self.assertNotIn("bread", [step.get("item") for step in steps])

    def test_a_chest_that_would_not_fit_is_not_planned(self):
        """Fix wave I1: making the chest from 20 planks at 16 stacks leaves 12 planks and a chest,
        17 stacks. The step would fail, so build_storage is not offered for it."""
        home = Home({**LOOSE, "planks": 20, "seeds": 1})  # 16 stacks
        self.assertFalse(PURPOSES["build_storage"].valid(home.situation()))
        self.assertEqual(home.plan("build_storage"), [])
        self.assertTrue(PURPOSES["build_storage"].valid(Home({**LOOSE, "planks": 8, "seeds": 1}).situation()))

    def test_the_fuller_mimo_is_the_more_it_wants_to_tidy(self):
        score = PURPOSES["build_storage"].score
        self.assertEqual(score(Home({**LOOSE, "planks": 8}).situation()), 60.0)  # 15 stacks
        home = Home({**LOOSE, "planks": 8, "seeds": 9})  # 16 stacks, and something had to stay behind
        home.state["full_at"] = 5.0
        self.assertEqual(score(home.situation()), 70.0)


class DropTests(unittest.TestCase):
    def test_known_poison_old_pickaxes_and_flowers_are_dropped(self):
        home = Home({"dirt": 40, "cobblestone": 20, "oak_log": 3, "planks": 5, "seeds": 3, "sticks": 2,
                     "red_mushroom": 3, "wooden_pickaxe": 1, "stone_pickaxe": 1, "flower_pink": 2})  # 11 stacks
        self.assertFalse(PURPOSES["drop_items"].valid(Home({"dirt": 1, "wooden_pickaxe": 1, "stone_pickaxe": 1}).situation()))
        know(home.db, "red_mushroom", "poisonous", 0.0)
        s = home.situation()
        self.assertTrue(PURPOSES["drop_items"].valid(s))
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "red_mushroom", "amount": 3},
                                                   {"kind": "drop", "item": "wooden_pickaxe", "amount": 1},
                                                   {"kind": "drop", "item": "flower_pink", "amount": 2}])
        self.assertEqual(PURPOSES["drop_items"].score(s), 38.0)

    def test_full_with_no_chest_the_least_useful_blocks_go_too(self):
        full = {**LOOSE, "seeds": 1, "wheat": 1}
        home = Home(full)
        self.assertEqual([step["item"] for step in home.plan("drop_items")], ["moss", "gravel", "sand", "clay"])
        with_chest = Home(full, chest={})
        self.assertFalse(PURPOSES["drop_items"].valid(with_chest.situation()))


class FarmHarvestTests(unittest.TestCase):
    def test_ripe_crops_wait_in_the_field_while_mimo_carries_a_days_food(self):
        grid = meadow()
        grid.put(3, 0, 0, "farmland")
        grid.put(3, 1, 0, "wheat_3")
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)

        def situation(inventory):
            state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                     "inventory": inventory, "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
            ensure_actions(state)
            return Situation(state, grid, DAY, 0.0, db)

        context = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)
        hungry = PURPOSES["farm"].plan(situation({}), context)
        self.assertIn({"kind": "harvest", "target": [3, 1, 0]}, hungry)
        self.assertFalse(PURPOSES["farm"].valid(situation({"bread": 3})))


if __name__ == "__main__":
    unittest.main()

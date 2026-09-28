import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import COOKING, RECIPES, craft, smelt
from backend.survival import cooking, storage  # noqa: F401  (register cook, build_storage and drop_items)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.carrying import valuable
from backend.survival.grid import Grid
from backend.survival.learning import learn_from_step
from backend.survival.memory import create_memory_tables, known
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.steps import FOOD, FOOD_RISK, finish_step
from backend.survival.toolmaking import open_swords, tool_orders, tool_plan
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_storage import LOOSE, Home

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
MEATS = ("beef", "mutton", "chicken", "rabbit")


def meadow(edits=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (edits or {}).items():
        grid.put(*cell, block)
    return grid


def situation(inventory, grid=None):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state, grid or meadow(), DAY, 0.0, db)


def craft_step(recipe):
    return {"kind": "craft", "recipe": recipe}


class MeatTests(unittest.TestCase):
    def test_raw_meat_fills_a_little_and_cooks_at_a_fire_into_far_more(self):
        for meat in MEATS:
            self.assertIn(f"raw_{meat}", COOKING)
            self.assertEqual(smelt({f"raw_{meat}": 1}, f"raw_{meat}", {"campfire"}), {f"cooked_{meat}": 1})
            self.assertLessEqual(FOOD[f"raw_{meat}"], 8.0)
            self.assertTrue(25.0 <= FOOD[f"cooked_{meat}"] <= 35.0)
            self.assertTrue(valuable(f"raw_{meat}") and valuable(f"cooked_{meat}"))

    def test_the_cook_purpose_cooks_every_raw_meat_mimo_carries(self):
        s = situation({"raw_beef": 2, "raw_chicken": 1, "raw_fish": 1}, meadow({(3, 1, 0): "campfire"}))
        self.assertTrue(PURPOSES["cook"].valid(s))
        plan = PURPOSES["cook"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                                       events=[], db=s.db))
        self.assertEqual(plan, [{"kind": "cook", "item": item} for item in ("raw_beef", "raw_beef", "raw_chicken",
                                                                             "raw_fish")])
        self.assertEqual(PURPOSES["cook"].facts(s), "carrying 4 raw fish and meat and 0 wheat")

    def test_raw_chicken_is_a_gamble_that_mimo_does_not_learn_to_shun(self):
        chance, _ = FOOD_RISK["raw_chicken"]
        for roll, kind in ((chance - 0.01, "sick"), (chance + 0.01, "ate")):
            state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                     "inventory": {"raw_chicken": 1}, "vitals": {**START_VITALS, "hunger": 50.0}}
            with patch("backend.survival.nature.roll", lambda *args: roll):
                event = finish_step({"kind": "eat", "item": "raw_chicken"}, state, meadow(), 10.0)
            self.assertEqual(event[0], kind)
            self.assertEqual(state["vitals"]["health"], 96.0 if kind == "sick" else 100.0)
            self.assertEqual(state["vitals"]["hunger"], 56.0)
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        learn_from_step(state, {"kind": "eat", "item": "raw_chicken"},
                        ActionContext(grid=meadow(), clock_at=lambda at: DAY, planner=lambda *args: [], events=[],
                                      db=db), 10.0)
        self.assertEqual(known(db, "poisonous"), [])


class SwordTests(unittest.TestCase):
    def test_swords_are_made_at_a_crafting_table(self):
        self.assertEqual(craft({"planks": 2, "sticks": 1}, "wooden_sword", {"crafting_table"}), {"wooden_sword": 1})
        self.assertEqual(craft({"cobblestone": 2, "sticks": 1}, "stone_sword", {"crafting_table"}), {"stone_sword": 1})
        self.assertEqual(craft({"iron_ingot": 2, "sticks": 1}, "iron_sword", {"crafting_table"}), {"iron_sword": 1})
        for sword in ("wooden_sword", "stone_sword", "iron_sword"):
            self.assertEqual(RECIPES[sword]["station"], "crafting_table")
            self.assertTrue(valuable(sword))

    def test_a_sword_only_up_to_the_tier_of_the_best_pickaxe(self):
        self.assertEqual(open_swords({}), [])
        self.assertEqual(open_swords({"wooden_pickaxe": 1}), ["wooden_sword"])
        self.assertEqual(open_swords({"stone_pickaxe": 1}), ["stone_sword", "wooden_sword"])
        self.assertEqual(open_swords({"stone_pickaxe": 1, "wooden_sword": 1}), ["stone_sword"])
        self.assertEqual(open_swords({"iron_pickaxe": 1, "iron_sword": 1}), [])
        self.assertEqual(tool_orders({"wooden_pickaxe": 1}), [("stone_pickaxe", "stone_sword"),
                                                                ("stone_pickaxe", "wooden_sword"),
                                                                ("stone_pickaxe",), ("wooden_sword",)])

    def test_a_new_pickaxe_comes_with_the_sword_it_opens_up_when_the_materials_stretch(self):
        table = meadow({(2, 1, 0): "crafting_table"})
        both = situation({"wooden_pickaxe": 1, "wooden_sword": 1, "cobblestone": 5, "sticks": 3}, table)
        self.assertEqual(tool_plan(both), [craft_step("stone_pickaxe"), craft_step("stone_sword")])
        self.assertEqual(PURPOSES["craft_tools"].facts(both), "can make a stone pickaxe and a stone sword now")
        short = situation({"wooden_pickaxe": 1, "wooden_sword": 1, "cobblestone": 3, "sticks": 2}, table)
        self.assertEqual(tool_plan(short), [craft_step("stone_pickaxe")])
        sword = situation({"stone_pickaxe": 1, "wooden_sword": 1, "cobblestone": 2, "sticks": 1}, table)
        self.assertEqual(tool_plan(sword), [craft_step("stone_sword")])


class LeftoversTests(unittest.TestCase):
    def test_hides_wool_and_feathers_are_put_away_and_a_meal_of_meat_is_kept(self):
        # W2: with its cloak made (a pet that wants one keeps its wool: backend.survival.winter_gear)
        home = Home({"leather": 7, "wool": 3, "feather": 6, "rabbit_hide": 9, "raw_beef": 1, "wool_cloak": 1}, chest={})
        self.assertEqual(storage.to_store(home.situation(), home.chest),  # L2 keeps 5 leather, 4 feathers, 8 hides
                         [("wool", 3), ("feather", 2), ("leather", 2), ("rabbit_hide", 1)])

    def test_a_sword_a_better_one_replaced_is_dropped(self):
        junk = storage.junk(Home({**LOOSE, "wooden_sword": 1, "stone_sword": 1}).situation())
        self.assertIn(("wooden_sword", 1), junk)
        self.assertNotIn(("stone_sword", 1), junk)


if __name__ == "__main__":
    unittest.main()

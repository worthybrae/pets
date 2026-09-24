import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import (
    LOGS, PLANKS, PLANKS_OF, RECIPES, STAND_INS, craft, fuel_of, have, paid, planks_recipe, smelt,
)
from backend.survival import nature
from backend.survival.blueprints import pick_block, supplies
from backend.survival.building import planks_first, usable_supplies, without_logs
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.renewal import create_growth_table, leaf_supported, orphaned_leaves, renew, scheduled
from backend.survival.senses import standing_logs
from backend.survival.storage import KEEP
from backend.survival.actions import ActionContext
from backend.survival.work import wood
from backend.tests.test_survival_storage import Home
from backend.tests.test_survival_toolmaking import craft as craft_step
from backend.tests.test_survival_toolmaking import mine_back, situation

BIRCH_TREE = (5, 0, 0)  # trunk x, trunk z, ground height: birch logs at y 1 to 4


def birch_wood():
    """A birch trunk at x 5, z 0 (logs at y 1 to 4) with a ring of birch leaves at y 4 and 5."""
    def rule(x, y, z):
        if (x, z) == (5, 0) and 1 <= y <= 4:
            return "birch_log"
        if y in (4, 5) and abs(x - 5) + abs(z) == 1:
            return "birch_leaves"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"
    return Grid(rule)


class RecipeTests(unittest.TestCase):
    def test_each_wood_makes_its_own_planks_and_cobblestone_makes_stone_bricks(self):
        self.assertEqual(craft({"birch_log": 1}, "birch_planks", set()), {"birch_planks": 4})
        self.assertEqual(craft({"spruce_log": 2}, "spruce_planks", set()), {"spruce_log": 1, "spruce_planks": 4})
        self.assertEqual(craft({"cobblestone": 5}, "stone_bricks", set()), {"cobblestone": 1, "stone_bricks": 4})
        self.assertEqual(PLANKS_OF, {"oak_log": "planks", "birch_log": "birch_planks", "spruce_log": "spruce_planks"})
        self.assertTrue(all(planks in RECIPES for planks in PLANKS))

    def test_any_wood_stands_in_where_a_recipe_asks_for_oak(self):
        self.assertEqual(STAND_INS, {"oak_log": LOGS[1:], "planks": PLANKS[1:]})
        self.assertEqual(have({"planks": 1, "birch_planks": 2, "spruce_planks": 3}, "planks"), 6)
        self.assertEqual(paid({"planks": 1, "birch_planks": 5}, {"planks": 3, "sticks": 2}),
                         {"planks": 1, "birch_planks": 2, "sticks": 2})
        self.assertEqual(craft({"spruce_planks": 3, "sticks": 2}, "wooden_pickaxe", {"crafting_table"}),
                         {"wooden_pickaxe": 1})
        self.assertEqual(craft({"birch_log": 2, "spruce_log": 1, "sticks": 3}, "campfire", set()),
                         {"spruce_log": 1, "campfire": 1})
        with self.assertRaisesRegex(ValueError, "Missing materials: planks"):
            craft({"birch_planks": 1}, "chest", set())

    def test_a_log_turns_into_its_own_planks_oak_first_and_planks_burn_as_fuel(self):
        self.assertEqual(planks_recipe({"spruce_log": 1, "birch_log": 1}), "birch_planks")
        self.assertEqual(planks_recipe({"oak_log": 1, "birch_log": 1}), "planks")
        self.assertEqual(planks_recipe({}), "planks")
        self.assertEqual((fuel_of({"coal": 1, "planks": 1}), fuel_of({"spruce_planks": 2}), fuel_of({})),
                         ("coal", "spruce_planks", "planks"))
        self.assertEqual(smelt({"iron_ore": 1, "birch_planks": 1}, "iron_ore", {"furnace"}), {"iron_ingot": 1})


class ToolTests(unittest.TestCase):
    def test_three_birch_logs_make_a_wooden_pickaxe_like_oak_does(self):
        s = situation({"birch_log": 3})
        self.assertEqual(PURPOSES["craft_tools"].plan(s, None), [
            craft_step("birch_planks"), craft_step("crafting_table"),
            {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
            craft_step("birch_planks"), craft_step("sticks"), craft_step("birch_planks"), craft_step("wooden_pickaxe"),
            craft_step("wooden_sword"), mine_back(1, 1, 0)])

    def test_spruce_planks_fuel_the_furnace_for_iron(self):
        s = situation({"stone_pickaxe": 1, "cobblestone": 8, "iron_ore": 3, "spruce_log": 1, "sticks": 2,
                       "crafting_table": 1})
        plan = PURPOSES["craft_tools"].plan(s, None)
        self.assertIn(craft_step("spruce_planks"), plan)
        self.assertEqual(sum(1 for step in plan if step["kind"] == "smelt"), 3)
        self.assertIn(craft_step("iron_pickaxe"), plan)


class GatheringTests(unittest.TestCase):
    def test_all_three_woods_count_as_wood_carried(self):
        self.assertEqual(wood({"spruce_log": 2, "birch_planks": 4, "sticks": 8, "oak_log": 1}), 5.0)
        for log in LOGS:
            self.assertEqual(KEEP[log], 8)
        for planks in PLANKS:
            self.assertEqual(KEEP[planks], 16)
        self.assertEqual(KEEP["stone_bricks"], 16)

    def test_a_birch_tree_is_a_tree_to_chop(self):
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [BIRCH_TREE]):
            self.assertEqual(standing_logs(birch_wood(), "1", (0, 1, 0)), [(5, y, 0) for y in range(1, 5)])

    def test_birch_leaves_decay_once_their_log_goes_and_drop_saplings(self):
        grid = birch_wood()
        self.assertTrue(leaf_supported(grid, (6, 5, 0)))
        self.assertEqual(sorted(orphaned_leaves(grid, (5, 4, 0))), [])
        db = sqlite3.connect(":memory:")
        create_growth_table(db)
        create_memory_tables(db)
        ctx = ActionContext(grid=grid, clock_at=lambda at: {"time_scale": 1.0}, planner=lambda *args: [], events=[],
                            db=db)
        state = {"name": "Pip", "world_seed": "7", "position": {"x": 5.0, "y": 1.0, "z": 3.0}, "inventory": {}}
        for y in range(1, 5):
            grid.put(5, y, 0, "air")
        renew(state, ctx, 0.0)
        self.assertEqual(len(scheduled(db)), 8)
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            renew(state, ctx, 400.0)
        self.assertEqual(grid.material(6, 5, 0), "air")
        self.assertEqual(state["inventory"]["sapling"], 8)
        self.assertNotIn("apple", state["inventory"])
        self.assertIn("spruce_leaves", nature.LEAVES)


class BuildingTests(unittest.TestCase):
    def test_spare_logs_of_any_wood_count_as_their_own_planks_oak_kept_first(self):
        self.assertEqual(supplies({"oak_log": 1, "birch_log": 4}), {"birch_planks": 12})
        self.assertEqual(supplies({"oak_log": 3, "spruce_log": 1}), {"planks": 4, "spruce_planks": 4})
        self.assertEqual(without_logs({"birch_log": 2, "planks": 3}), {"planks": 3})
        self.assertEqual(usable_supplies({"birch_log": 3}), {"birch_planks": 4})

    def test_a_wall_that_wants_planks_takes_other_planks_before_another_block(self):
        self.assertEqual(pick_block("planks", {"cobblestone": 9, "birch_planks": 2}), "birch_planks")
        self.assertEqual(pick_block("planks", {"cobblestone": 9}), "cobblestone")
        self.assertEqual(pick_block("stone_bricks", {"stone_bricks": 1}), "stone_bricks")
        self.assertEqual(planks_first({"birch_log": 2, "birch_planks": 1}, ["birch_planks"] * 6 + ["planks"]),
                         [craft_step("birch_planks"), craft_step("birch_planks")])

    def test_spare_planks_never_let_cobblestone_drop_below_the_stone_goal(self):
        """With more other building blocks than a finished shelter needs, the shelter's need was
        negative and let drop_items throw cobblestone below gather_stone's goal (12), so the two
        alternated; the goal is a floor."""
        filler = {f"item_{n}": 1 for n in range(13)}
        home = Home({**filler, "birch_planks": 5, "cobblestone": 40})  # 16 stacks, no chest to use
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 28}])


if __name__ == "__main__":
    unittest.main()

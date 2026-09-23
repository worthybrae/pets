import unittest

from backend.survival.actions import ensure_actions
from backend.survival.grid import Grid
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.toolmaking import next_tool, tool_plan
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def flat(cells=None):
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def situation(inventory, grid=None):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    return Situation(state, grid or flat(), DAY, 0.0)


def craft(recipe):
    return {"kind": "craft", "recipe": recipe}


class ToolmakingTests(unittest.TestCase):
    def test_three_logs_make_a_table_and_a_wooden_pickaxe_and_the_table_comes_back(self):
        s = situation({"oak_log": 3})
        self.assertEqual(next_tool(s.inventory), "wooden_pickaxe")
        self.assertTrue(PURPOSES["craft_tools"].valid(s))
        self.assertEqual(PURPOSES["craft_tools"].plan(s, None), [
            craft("planks"), craft("crafting_table"),
            {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"),
            {"kind": "mine", "target": [1, 1, 0]}])
        self.assertEqual(s.inventory, {"oak_log": 3})

    def test_a_table_already_placed_nearby_is_used_and_left(self):
        grid = flat()
        grid.put(2, 1, 0, "crafting_table")
        s = situation({"wooden_pickaxe": 1, "cobblestone": 3, "sticks": 2}, grid)
        self.assertEqual(tool_plan(s), [craft("stone_pickaxe")])

    def test_iron_needs_a_furnace_and_three_smelted_ingots(self):
        s = situation({"stone_pickaxe": 1, "cobblestone": 8, "iron_ore": 3, "coal": 3, "sticks": 2,
                       "crafting_table": 1})
        self.assertEqual(tool_plan(s), [
            {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
            craft("furnace"), {"kind": "place", "target": [-1, 1, 0], "block": "furnace"},
            {"kind": "smelt", "item": "iron_ore"}, {"kind": "smelt", "item": "iron_ore"},
            {"kind": "smelt", "item": "iron_ore"}, craft("iron_pickaxe"),
            {"kind": "mine", "target": [-1, 1, 0]}, {"kind": "mine", "target": [1, 1, 0]}])

    def test_not_enough_materials_or_nothing_left_to_make_is_not_offered(self):
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"oak_log": 2})))
        self.assertIsNone(next_tool({"iron_pickaxe": 1}))
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"iron_pickaxe": 1, "oak_log": 9})))

    def test_no_room_for_a_table_means_no_plan(self):
        walls = {cell: "stone" for cell in ((1, 1, 0), (-1, 1, 0), (0, 1, 1), (0, 1, -1), (0, 2, 0))}
        self.assertIsNone(tool_plan(situation({"oak_log": 3}, flat(walls))))


if __name__ == "__main__":
    unittest.main()

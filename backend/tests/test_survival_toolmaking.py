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


def situation(inventory, grid=None, position=(0.0, 1.0, 0.0)):
    """Mimo at `position` (seed "1": the natural surface there is at y 0, so y 1 stands on it)."""
    state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", position)), "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    return Situation(state, grid or flat(), DAY, 0.0)


def dug(*open_cells):
    """Solid dirt with only `open_cells` open: a hole Mimo dug below the surface."""
    return Grid(lambda x, y, z: "air" if (x, y, z) in open_cells else "dirt")


def mine_back(x, y, z):
    return {"kind": "mine", "target": [x, y, z], "keep": True}


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
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"), craft("wooden_sword"),
            mine_back(1, 1, 0)])
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
            {"kind": "smelt", "item": "iron_ore"}, craft("iron_pickaxe"), mine_back(-1, 1, 0), mine_back(1, 1, 0)])

    def test_below_the_surface_a_station_goes_in_a_niche_it_digs_never_in_the_way_out(self):
        # Mimo at the foot of a stair: headroom (0, -1, 0), the way up at (-1, -1, 0) over the
        # floor (-1, -2, 0). The sides across the dig heading come first.
        stairs = dug((0, -2, 0), (0, -1, 0), (-1, -1, 0), (-1, 0, 0))
        s = situation({"oak_log": 3}, stairs, (0.0, -2.0, 0.0))
        s.brain["dig_heading"] = [1, 0]
        self.assertEqual(tool_plan(s), [
            craft("planks"), craft("crafting_table"), {"kind": "mine", "target": [0, -2, 1]},
            {"kind": "place", "target": [0, -2, 1], "block": "crafting_table"},
            craft("planks"), craft("sticks"), craft("planks"), craft("wooden_pickaxe"), craft("wooden_sword"),
            mine_back(0, -2, 1)])

    def test_below_the_surface_open_cells_and_the_headroom_are_never_used(self):
        cave = dug((0, -2, 0), (0, -1, 0), (1, -2, 0), (-1, -2, 0), (0, -2, 1), (0, -2, -1))
        self.assertIsNone(tool_plan(situation({"oak_log": 3}, cave, (0.0, -2.0, 0.0))))
        rock = Grid(lambda x, y, z: "air" if (x, y, z) in ((0, -2, 0), (0, -1, 0)) else "stone")
        self.assertIsNone(tool_plan(situation({"oak_log": 3}, rock, (0.0, -2.0, 0.0))))  # stone needs a pickaxe

    def test_not_enough_materials_or_nothing_left_to_make_is_not_offered(self):
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"oak_log": 2})))
        self.assertIsNone(next_tool({"diamond_pickaxe": 1}))  # L3: gold and diamond come after iron
        self.assertFalse(PURPOSES["craft_tools"].valid(situation({"diamond_pickaxe": 1, "diamond_sword": 1, "oak_log": 9})))

    def test_no_plan_when_its_crafts_would_not_fit(self):
        """Fix wave I1: at 16 stacks the planks from the first log have nowhere to go."""
        filler = {f"item_{n}": 1 for n in range(15)}
        self.assertIsNone(tool_plan(situation({**filler, "oak_log": 5})))
        self.assertIsNotNone(tool_plan(situation({"oak_log": 5})))

    def test_no_room_for_a_table_means_no_plan(self):
        walls = {cell: "stone" for cell in ((1, 1, 0), (-1, 1, 0), (0, 1, 1), (0, 1, -1), (0, 2, 0))}
        self.assertIsNone(tool_plan(situation({"oak_log": 3}, flat(walls))))


if __name__ == "__main__":
    unittest.main()

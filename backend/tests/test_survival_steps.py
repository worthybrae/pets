import unittest

from backend.survival.grid import Grid
from backend.survival.steps import FOOD, StepFailed, finish_step, mine_seconds, start_step
from backend.survival.vitals import START_VITALS


def small_world(cells=None):
    """Stone at y <= 0 and air above, with `cells` overriding single cells. Mimo stands at (0, 1, 0)."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z), "stone" if y <= 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {}, "vitals": dict(START_VITALS)}
    state.update(changes)
    return state


class MiningTimeTests(unittest.TestCase):
    def test_hardness_divided_by_tool_speed(self):
        cases = [("dirt", {}, 0.6), ("dirt", {"iron_pickaxe": 1}, 0.6), ("leaves", {}, 0.3), ("tall_grass", {}, 0.1),
                 ("oak_log", {}, 2.0), ("oak_log", {"wooden_axe": 1}, 1.0), ("cobblestone", {}, 4.0),
                 ("stone", {"wooden_pickaxe": 1}, 2.0), ("stone", {"wooden_pickaxe": 1, "stone_pickaxe": 1}, 1.0),
                 ("iron_ore", {"iron_pickaxe": 1}, 5.0 / 6), ("coal_ore", {"wooden_pickaxe": 0}, 5.0)]
        for material, inventory, seconds in cases:
            self.assertAlmostEqual(mine_seconds(material, inventory), seconds, msg=(material, inventory))
        self.assertIsNone(mine_seconds("bedrock", {"iron_pickaxe": 1}))


class StepTests(unittest.TestCase):
    def test_mining_takes_its_time_and_yields_the_drop(self):
        grid, state = small_world({(1, 1, 0): "oak_log"}), pet()
        step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 100.0)
        self.assertEqual((step["ends_at"], step["block"], step["target"]), (102.0, "oak_log", {"x": 1, "y": 1, "z": 0}))
        self.assertIsNone(finish_step(step, state, grid, 102.0))
        self.assertEqual(grid.material(1, 1, 0), "air")
        self.assertEqual(state["inventory"], {"oak_log": 1})

    def test_mining_needs_the_right_tool_and_reach(self):
        grid, state = small_world({(0, 1, 4): "dirt", (0, 1, 5): "dirt"}), pet()
        with self.assertRaisesRegex(StepFailed, "stronger pickaxe"):
            start_step({"kind": "mine", "target": [0, 0, 0]}, state, grid, 0.0)
        self.assertEqual(start_step({"kind": "mine", "target": [0, 1, 4]}, state, grid, 0.0)["ends_at"], 0.6)
        with self.assertRaisesRegex(StepFailed, "out of reach"):
            start_step({"kind": "mine", "target": [0, 1, 5]}, state, grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "cannot be mined"):
            start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)

    def test_a_block_that_vanished_while_mining_fails(self):
        grid, state = small_world({(1, 1, 0): "dirt"}), pet()
        step = start_step({"kind": "mine", "target": [1, 1, 0]}, state, grid, 0.0)
        grid.put(1, 1, 0, "air")
        with self.assertRaisesRegex(StepFailed, "is gone"):
            finish_step(step, state, grid, 0.6)
        self.assertEqual(state["inventory"], {})

    def test_placing_takes_a_moment_and_uses_the_item(self):
        grid, state = small_world({(2, 1, 0): "tall_grass"}), pet(inventory={"planks": 2})
        step = start_step({"kind": "place", "target": [1, 1, 0], "block": "planks"}, state, grid, 5.0)
        self.assertEqual(step["ends_at"], 5.3)
        finish_step(step, state, grid, 5.3)
        self.assertEqual(grid.material(1, 1, 0), "planks")
        self.assertEqual(state["inventory"], {"planks": 1})
        start_step({"kind": "place", "target": [2, 1, 0], "block": "planks"}, state, grid, 6.0)  # plants give way
        for target, reason in (([1, 1, 0], "taken"), ([0, 1, 0], "stands"), ([9, 1, 0], "out of reach")):
            with self.assertRaisesRegex(StepFailed, reason):
                start_step({"kind": "place", "target": target, "block": "planks"}, state, grid, 6.0)
        with self.assertRaisesRegex(StepFailed, "no cobblestone"):
            start_step({"kind": "place", "target": [0, 1, 1], "block": "cobblestone"}, state, grid, 6.0)

    def test_eating_restores_hunger(self):
        grid, state = small_world(), pet(inventory={"berries": 2})
        state["vitals"]["hunger"] = 50.0
        step = start_step({"kind": "eat", "item": "berries"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], 1.6)
        self.assertEqual(finish_step(step, state, grid, 1.6), ("ate", "Pip ate berries."))
        self.assertEqual(state["vitals"]["hunger"], 50.0 + FOOD["berries"])
        self.assertEqual(state["inventory"], {"berries": 1})
        with self.assertRaisesRegex(StepFailed, "not food"):
            start_step({"kind": "eat", "item": "planks"}, state, grid, 2.0)

    def test_crafting_and_smelting_take_one_and_five_seconds_near_their_stations(self):
        grid = small_world()
        state = pet(inventory={"oak_log": 1, "cobblestone": 8, "iron_ore": 1, "coal": 1})
        step = start_step({"kind": "craft", "recipe": "planks"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], 1.0)
        self.assertEqual(finish_step(step, state, grid, 1.0), ("craft", "Pip crafted planks."))
        self.assertEqual(state["inventory"]["planks"], 4)
        with self.assertRaisesRegex(ValueError, "crafting_table"):
            start_step({"kind": "craft", "recipe": "furnace"}, state, grid, 1.0)
        grid.put(3, 1, 0, "crafting_table")
        grid.put(0, 1, 3, "furnace")
        self.assertEqual(start_step({"kind": "craft", "recipe": "furnace"}, state, grid, 1.0)["ends_at"], 2.0)
        step = start_step({"kind": "smelt", "item": "iron_ore"}, state, grid, 2.0)
        self.assertEqual(step["ends_at"], 7.0)
        self.assertEqual(finish_step(step, state, grid, 7.0), ("smelt", "Pip smelted iron ore."))
        self.assertEqual(state["inventory"]["iron_ingot"], 1)

    def test_walks_carry_a_timed_path(self):
        grid, state = small_world(), pet()
        step = start_step({"kind": "walk", "target": [3, 1, 0]}, state, grid, 10.0)
        self.assertEqual(step["ends_at"], 10.9)
        self.assertEqual([(entry["x"], entry["at"]) for entry in step["path"]],
                         [(0, 10.0), (1, 10.3), (2, 10.6), (3, 10.9)])
        self.assertTrue(step["reached"])
        finish_step(step, state, grid, 10.9)
        self.assertEqual(state["position"], {"x": 3.0, "y": 1.0, "z": 0.0})
        walls = {(dx, dy, dz): "stone" for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)) for dy in (1, 2)}
        with self.assertRaisesRegex(StepFailed, "no way there"):
            start_step({"kind": "walk", "target": [3, 1, 0]}, pet(), small_world(walls), 0.0)

    def test_sleep_has_no_fixed_end_waits_do_and_unknown_steps_fail(self):
        grid, state = small_world(), pet()
        self.assertIsNone(start_step({"kind": "sleep"}, state, grid, 0.0)["ends_at"])
        self.assertEqual(start_step({"kind": "wait", "seconds": 5}, state, grid, 1.0)["ends_at"], 6.0)
        with self.assertRaisesRegex(StepFailed, "unknown step"):
            start_step({"kind": "dance"}, state, grid, 0.0)


if __name__ == "__main__":
    unittest.main()

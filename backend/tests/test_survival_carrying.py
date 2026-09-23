import unittest

from backend.services.crafting import RECIPES, craft
from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.carrying import CARRY_STACKS, after_step, room_for, settle, stacks
from backend.survival.grid import Grid
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
# 16 kinds of item, one stack each: Mimo's arms are full.
FULL = {f"item_{n}": 1 for n in range(CARRY_STACKS)}


def pet(inventory):
    state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": dict(inventory),
             "vitals": dict(START_VITALS), "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    ensure_actions(state)
    return state


class StackTests(unittest.TestCase):
    def test_stacks_hold_up_to_32_of_one_item(self):
        self.assertEqual(stacks({}), 0)
        self.assertEqual(stacks({"dirt": 32, "planks": 1}), 2)
        self.assertEqual(stacks({"dirt": 33, "stone_pickaxe": 1, "moss": 0}), 3)

    def test_room_fills_the_last_stack_then_free_stacks(self):
        self.assertEqual(room_for({"dirt": 30}, "dirt", 1), 2)
        self.assertEqual(room_for({"dirt": 30}, "moss", 1), 0)
        self.assertEqual(room_for({"dirt": 30}, "moss", 2), 32)
        self.assertEqual(room_for(FULL, "item_0", CARRY_STACKS), 31)

    def test_what_a_step_brought_in_that_does_not_fit_stays_behind(self):
        inventory = {**FULL, "cobblestone": 1}
        self.assertEqual(settle(inventory, FULL), {"cobblestone": 1})
        self.assertNotIn("cobblestone", inventory)
        more = {**FULL, "item_0": 33}
        self.assertEqual(settle(more, FULL), {"item_0": 1})
        self.assertEqual(more["item_0"], 32)

    def test_what_mimo_already_carried_is_never_left(self):
        crowded = {**FULL, "dirt": 5}
        self.assertEqual(settle(dict(crowded), crowded), {})

    def test_full_hands_are_noted_once_and_cleared_when_there_is_room(self):
        state = pet({**FULL, "berries": 3})
        after_step(state, FULL, 10.0)
        self.assertEqual(state["full_at"], 10.0)
        state["inventory"]["berries"] = 3
        after_step(state, FULL, 12.0)
        self.assertEqual(state["full_at"], 10.0)
        state["inventory"] = {"berries": 3}
        after_step(state, {}, 14.0)
        self.assertIsNone(state["full_at"])


class FullHandsInTheTickTests(unittest.TestCase):
    def test_a_mined_block_that_does_not_fit_is_left_and_mimo_says_so(self):
        grid = Grid(lambda x, y, z: "dirt" if y <= 1 and (x, y, z) == (1, 1, 0) else "stone" if y <= 0 else "air")
        state = pet(FULL)
        state["queue"] = [{"kind": "mine", "target": [1, 1, 0]}]
        advance_actions(state, ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                             events=[]), 1.0)
        self.assertEqual(grid.material(1, 1, 0), "air")
        self.assertEqual(state["inventory"], FULL)
        self.assertEqual(state["full_at"], 0.6)
        self.assertIn("full", state["last_thought"])


class RecipeTests(unittest.TestCase):
    def test_torches_chests_beds_and_axes_can_be_made(self):
        self.assertEqual(craft({"coal": 1, "sticks": 1}, "torch", set()), {"torch": 4})
        self.assertEqual(craft({"planks": 8}, "chest", set()), {"chest": 1})
        self.assertEqual(craft({"planks": 6}, "bed", set()), {"bed": 1})
        self.assertEqual(craft({"cobblestone": 3, "sticks": 2}, "stone_axe", {"crafting_table"}), {"stone_axe": 1})
        for axe in ("wooden_axe", "stone_axe", "iron_axe"):
            self.assertEqual(RECIPES[axe]["station"], "crafting_table")


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.services.crafting import RECIPES, craft
from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.carrying import CARRY_STACKS, after_step, least_valuable, room_for, settle, stacks
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


class WhatGivesWayTests(unittest.TestCase):
    """Fix wave I2(a): something valuable that does not fit pushes out the least valuable block
    Mimo carries instead of being left behind itself."""

    carried = {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 3)}, "dirt": 40, "cobblestone": 20}  # 16 stacks

    def test_a_new_fish_or_berry_is_kept_and_a_dirt_stack_is_left(self):
        for food in ("raw_fish", "berries"):
            inventory = {**self.carried, food: 3}
            self.assertEqual(settle(inventory, self.carried), {"dirt": 8}, food)
            self.assertEqual(inventory, {**self.carried, "dirt": 32, food: 3})

    def test_seeds_saplings_ore_ingots_coal_and_tools_count_as_valuable(self):
        for item in ("seeds", "sapling", "iron_ore", "iron_ingot", "coal", "stone_pickaxe", "wooden_axe"):
            inventory = {**self.carried, item: 1}
            self.assertEqual(settle(inventory, self.carried), {"dirt": 8}, item)
            self.assertEqual(inventory[item], 1)

    def test_poisonous_food_does_not_push_out_a_block(self):
        """Fix wave M5(i): a red mushroom (steps.FOOD_HEALTH negative) is food Mimo will drop the
        moment it learns better, so it should not cost a good dirt or cobblestone stack to keep."""
        inventory = {**self.carried, "red_mushroom": 3}
        self.assertEqual(settle(inventory, self.carried), {"red_mushroom": 3})
        self.assertNotIn("red_mushroom", inventory)
        self.assertEqual(inventory, self.carried)

    def test_cobblestone_goes_only_when_no_dirt_is_left(self):
        carried = {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}, "cobblestone": 20}
        inventory = {**carried, "apple": 1}
        self.assertEqual(settle(inventory, carried), {"cobblestone": 20})
        self.assertEqual(inventory, {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}, "apple": 1})

    def test_a_low_value_newcomer_and_a_valuable_one_with_nothing_to_give_way_are_left(self):
        inventory = {**self.carried, "gravel": 3}
        self.assertEqual(settle(inventory, self.carried), {"gravel": 3})
        inventory = {**FULL, "berries": 3}
        self.assertEqual(settle(inventory, FULL), {"berries": 3})

    def test_in_the_tick_a_picked_berry_stays_and_mimo_says_its_arms_are_full(self):
        grid = Grid(lambda x, y, z: "berry_bush_ripe" if (x, y, z) == (1, 1, 0) else "grass" if y == 0 else "air")
        state = pet(self.carried)
        work(state, grid, [{"kind": "pick", "target": [1, 1, 0]}], until=2.0)
        self.assertEqual(state["inventory"], {**self.carried, "dirt": 32, "berries": 3})
        self.assertIn("full", state["last_thought"])


class FoodIsNeverLeftTests(unittest.TestCase):
    """L4a final fix wave, C1: goals filled all 16 stacks with things Mimo keeps (gear, ores,
    leather, feathers, hides), none of them a LOW_VALUE block, so every berry it picked was left
    behind and the pet starved. Food now pushes out a spare gear material, hide or extra ore, or is
    eaten there and then while Mimo is hungry."""

    # 16 stacks of things Mimo keeps: tools, stations, armor, wood, coal, ore, feathers, a hide.
    kept = {"iron_pickaxe": 1, "iron_sword": 1, "crafting_table": 1, "furnace": 1, "iron_cap": 1, "iron_tunic": 1,
            "oak_log": 8, "sticks": 4, "coal": 8, "iron_ore": 4, "gold_ore": 2, "seeds": 5, "sapling": 3,
            "wheat": 2, "feather": 3, "rabbit_hide": 2}

    def test_the_kept_stacks_fill_the_arms_and_hold_no_low_value_block(self):
        self.assertEqual(stacks(self.kept), CARRY_STACKS)
        self.assertEqual(least_valuable(self.kept, "iron_ore"), None)  # ore still pushes out only blocks

    def test_food_pushes_out_a_spare_gear_material_first_then_a_hide_then_an_extra_ore(self):
        inventory = {**self.kept, "berries": 3}
        self.assertEqual(settle(inventory, self.kept), {"feather": 3})
        self.assertEqual(inventory, {**{k: v for k, v in self.kept.items() if k != "feather"}, "berries": 3})
        without = {k: v for k, v in self.kept.items() if k != "feather"} | {"leather": 1}
        inventory = {**without, "raw_fish": 1}
        self.assertEqual(settle(inventory, without), {"rabbit_hide": 2})
        ores = {k: v for k, v in without.items() if k not in ("rabbit_hide", "leather")} | {"string": 1, "flint": 2}
        inventory = {**ores, "raw_beef": 2}
        self.assertEqual(settle(inventory, ores), {"string": 1})
        only_ore = {k: v for k, v in self.kept.items() if k not in ("feather", "rabbit_hide")} | {"cobblestone": 1,
                                                                                                    "planks": 4}
        inventory = {**only_ore, "apple": 1}
        self.assertEqual(settle(inventory, only_ore), {"cobblestone": 1})  # a LOW_VALUE block still goes first
        no_block = {k: v for k, v in only_ore.items() if k != "cobblestone"} | {"torch": 2}
        inventory = {**no_block, "apple": 1}
        self.assertEqual(settle(inventory, no_block), {"gold_ore": 2})

    def test_poisonous_food_or_a_non_food_newcomer_pushes_out_no_gear_material(self):
        for item in ("red_mushroom", "iron_ingot", "diamond"):
            inventory = {**self.kept, item: 1}
            self.assertEqual(settle(inventory, self.kept), {item: 1}, item)
            self.assertEqual(inventory, self.kept, item)

    def test_with_nothing_to_give_way_a_hungry_pet_eats_it_there_and_a_fed_one_leaves_it(self):
        hungry = pet(FULL)
        hungry["vitals"]["hunger"] = 40.0
        hungry["inventory"]["berries"] = 5
        events = []
        after_step(hungry, FULL, 10.0, events)
        self.assertEqual(hungry["inventory"], FULL)
        self.assertEqual(hungry["vitals"]["hunger"], 80.0)  # a meal's worth: up to FULL, like a meal
        self.assertEqual(events, [(10.0, "ate", "Pip ate 5 berries it had no room to carry.")])
        self.assertIsNone(hungry.get("full_at"))  # nothing was left behind
        fed = pet(FULL)
        fed["inventory"]["berries"] = 5
        after_step(fed, FULL, 10.0, [])
        self.assertEqual((fed["inventory"], fed["vitals"]["hunger"], fed["full_at"]), (FULL, 100.0, 10.0))

    def test_a_hungry_pet_eats_no_more_than_fills_it_and_no_food_that_makes_it_sick(self):
        state = pet(FULL)
        state["vitals"]["hunger"] = 60.0
        state["inventory"].update(cooked_beef=3, red_mushroom=2, raw_chicken=1)
        events = []
        after_step(state, FULL, 5.0, events)
        self.assertEqual(state["vitals"]["hunger"], 95.0)  # one cooked beef reaches FULL (90)
        self.assertEqual([text for _, _, text in events], ["Pip ate 1 cooked beef it had no room to carry."])
        self.assertEqual(state["inventory"], FULL)


class SettleCapTests(unittest.TestCase):
    """Fix wave M5(j): push-out only relieves what a step's own growth needs, not an older
    overflow already there before the step, so one berry never costs two stacks."""

    def test_an_older_overflow_is_left_alone_so_one_berry_costs_one_stack(self):
        before = {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}, "dirt": 32, "cobblestone": 20}  # 17 stacks
        inventory = {**before, "berries": 1}
        self.assertEqual(settle(inventory, before), {"dirt": 32})
        self.assertEqual(inventory, {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}, "cobblestone": 20,
                                     "berries": 1})

    def test_cobblestone_is_kept_before_dirt_even_once_dirt_runs_out(self):
        """Two valuable newcomers at once can need more than one stack pushed out in the same
        settle call: dirt goes first, and only once it is gone entirely does cobblestone start."""
        before = {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 2)}, "dirt": 32, "cobblestone": 20}  # 16 stacks
        inventory = {**before, "sapling": 1, "seeds": 1}
        self.assertEqual(settle(inventory, before), {"dirt": 32, "cobblestone": 20})
        self.assertEqual(inventory, {**{f"item_{n}": 1 for n in range(CARRY_STACKS - 2)}, "sapling": 1, "seeds": 1})


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


# 15 kinds of item, one stack each: one stack short of full.
FIFTEEN = {f"item_{n}": 1 for n in range(CARRY_STACKS - 1)}


def work(state, grid, queue, until=10.0):
    state["queue"] = list(queue)
    advance_actions(state, ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[]),
                    until)


def meadow(stations=()):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in stations:
        grid.put(*cell, block)
    return grid


class FullHandsMakeNothingTests(unittest.TestCase):
    """Fix wave I1: crafting, smelting or cooking with full arms used to use up the inputs and then
    leave the output behind. Now the step does not start: it fails with code "blocked"."""

    def assert_blocked(self, state, kept):
        self.assertEqual(state["inventory"], kept)
        self.assertEqual(state["last_failure"]["code"], "blocked")
        self.assertEqual(state["recent_actions"][-1]["result"], "failed")

    def test_planks_from_logs_do_not_fit_and_the_logs_stay(self):
        state = pet({**FIFTEEN, "oak_log": 5})
        work(state, meadow(), [{"kind": "craft", "recipe": "planks"}])
        self.assert_blocked(state, {**FIFTEEN, "oak_log": 5})
        self.assertIn("planks", state["last_failure"]["reason"])

    def test_a_chest_from_planks_does_not_fit_and_the_planks_stay(self):
        state = pet({**FIFTEEN, "planks": 20})
        work(state, meadow(), [{"kind": "craft", "recipe": "chest"}])
        self.assert_blocked(state, {**FIFTEEN, "planks": 20})

    def test_cooked_fish_does_not_fit_and_the_raw_fish_stays(self):
        state = pet({**FIFTEEN, "raw_fish": 3})
        work(state, meadow([((2, 1, 0), "campfire")]), [{"kind": "cook", "item": "raw_fish"}])
        self.assert_blocked(state, {**FIFTEEN, "raw_fish": 3})

    def test_an_ingot_does_not_fit_and_the_ore_and_coal_stay(self):
        fourteen = {f"item_{n}": 1 for n in range(CARRY_STACKS - 2)}
        state = pet({**fourteen, "iron_ore": 2, "coal": 2})
        work(state, meadow([((2, 1, 0), "furnace")]), [{"kind": "smelt", "item": "iron_ore"}])
        self.assert_blocked(state, {**fourteen, "iron_ore": 2, "coal": 2})

    def test_it_goes_ahead_when_the_inputs_free_the_stack_the_output_needs(self):
        state = pet({**FIFTEEN, "oak_log": 1})
        work(state, meadow(), [{"kind": "craft", "recipe": "planks"}])
        self.assertEqual(state["inventory"], {**FIFTEEN, "planks": 4})
        self.assertIsNone(state["last_failure"])

    def test_plans_are_checked_the_same_way(self):
        from backend.survival.carrying import crafts_fit
        self.assertFalse(crafts_fit({**FIFTEEN, "planks": 20}, [{"kind": "craft", "recipe": "chest"}]))
        self.assertTrue(crafts_fit({**FIFTEEN, "planks": 8}, [{"kind": "craft", "recipe": "chest"}]))
        # A table placed and then mined back needs its stack again at the end.
        thirteen = {f"item_{n}": 1 for n in range(CARRY_STACKS - 3)}
        torches = [{"kind": "craft", "recipe": "crafting_table"},
                   {"kind": "place", "target": [1, 1, 0], "block": "crafting_table"},
                   {"kind": "craft", "recipe": "torch"}]
        carried = {**thirteen, "planks": 4, "coal": 2, "sticks": 2}
        self.assertTrue(crafts_fit(carried, torches))
        self.assertFalse(crafts_fit(carried, [*torches, {"kind": "mine", "target": [1, 1, 0], "keep": True}]))


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

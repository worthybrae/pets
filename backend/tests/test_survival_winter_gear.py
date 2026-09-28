"""W2: the wool cloak, the hearth and smoked meat: their recipes, what each does, and the purposes that make them."""

import sqlite3
import unittest
from types import SimpleNamespace

from backend.services.crafting import FIRES, craft, smelt
from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.carrying import CARRY_STACKS, room_for, stacks
from backend.survival.creatures.harm import ARMOR, SLOTS, armor_cut
from backend.survival.goals import GOALS, adopt_goal
from backend.survival.housework import chest_key
from backend.survival.light import BLOCK_LIGHT
from backend.survival.memory import create_memory_tables, know
from backend.survival.purposes import PURPOSES
from backend.survival.rain import douse
from backend.survival.spoilage import PERISHABLE
from backend.survival.steps import FOOD, StepFailed, finish_step, start_step
from backend.survival.storage import chest_spot, kept, to_take
from backend.survival.vitals import WARM_BLOCKS, near_warm_block
from backend.survival.wild import cloaked
from backend.survival.cooking import cook_plan
from backend.survival.winter_gear import SMOKABLE, SMOKE_SECONDS, hearth_spot, smoke_wanted, spare_meat
from backend.survival.winter_prep import GOAL, hearth_home
from backend.tests.test_survival_cooking import meadow
from backend.tests.test_survival_winter_goal import on_day
from backend.tests.test_survival_life_goals import built


def outside(world):
    """Mimo out on the meadow, where a crafting table can stand (none goes inside its shelter)."""
    world.state["position"] = {"x": 12.0, "y": 1.0, "z": 12.0}
    return world


class RecipeTests(unittest.TestCase):
    def test_five_wool_make_a_cloak_and_stone_and_a_campfire_a_hearth_at_a_table(self):
        self.assertEqual(craft({"wool": 5}, "wool_cloak", {"crafting_table"}), {"wool_cloak": 1})
        self.assertEqual(craft({"cobblestone": 9, "campfire": 1}, "hearth", {"crafting_table"}),
                         {"cobblestone": 1, "hearth": 1})
        with self.assertRaises(ValueError):
            craft({"wool": 4}, "wool_cloak", {"crafting_table"})

    def test_the_cloak_is_its_own_slot_and_no_armor(self):
        self.assertEqual(SLOTS["wool_cloak"], "cloak")
        self.assertNotIn("wool_cloak", ARMOR)
        self.assertEqual(armor_cut({"wool_cloak": 1}), 0.0)

    def test_a_worn_cloak_takes_no_stack(self):
        arms = {f"item{n}": 1 for n in range(CARRY_STACKS - 1)}
        self.assertEqual(stacks({**arms, "wool_cloak": 1}), CARRY_STACKS - 1)
        self.assertEqual(room_for({**arms, "wool_cloak": 1}, "cobblestone", CARRY_STACKS), 32)

    def test_a_cloak_warms_a_gentle_pet_and_a_wild_one_once_it_knows_the_cloak(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        self.assertTrue(cloaked({"inventory": {"wool_cloak": 1}}, db))
        self.assertFalse(cloaked({"inventory": {}}, db))
        wild = {"inventory": {"wool_cloak": 1}, "difficulty": "wild"}
        self.assertFalse(cloaked(wild, db))
        know(db, "wild:cloak", "lesson", 0.0)
        self.assertTrue(cloaked(wild, db))

    def test_a_hearth_warms_lights_cooks_and_never_goes_out_in_the_rain(self):
        self.assertIn("hearth", WARM_BLOCKS)
        self.assertTrue(near_warm_block([(3, 1, 0, "hearth")], 0, 1, 0))
        self.assertEqual(BLOCK_LIGHT["hearth"], 13)
        self.assertIn("hearth", FIRES)
        self.assertEqual(smelt({"raw_beef": 1}, "raw_beef", {"hearth"}), {"cooked_beef": 1})
        grid = meadow({(2, 1, 0): "hearth"})
        state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "sky": {"weather": "rain"}}
        douse(state, SimpleNamespace(grid=grid, events=[], db=None), 1.0)
        self.assertEqual(grid.material(2, 1, 0), "hearth")


class SmokeTests(unittest.TestCase):
    def test_a_stick_and_raw_meat_smoke_into_meat_that_never_spoils(self):
        grid = meadow({(2, 1, 0): "campfire"})
        state = {"name": "Pip", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {"raw_beef": 2, "sticks": 1}}
        step = start_step({"kind": "smoke", "item": "raw_beef"}, state, grid, 0.0)
        self.assertEqual(step["ends_at"], SMOKE_SECONDS)
        event = finish_step(step, state, grid, step["ends_at"])
        self.assertEqual(state["inventory"], {"raw_beef": 1, "smoked_meat": 1})
        self.assertEqual(event, ("smoke", "Pip smoked raw beef."))
        self.assertEqual((FOOD["smoked_meat"], "smoked_meat" in PERISHABLE), (20.0, False))
        with self.assertRaises(StepFailed):  # no stick left
            start_step({"kind": "smoke", "item": "raw_beef"}, state, grid, 0.0)
        with self.assertRaises(StepFailed):  # no fire
            start_step({"kind": "smoke", "item": "raw_beef"}, {**state, "inventory": {"raw_beef": 1, "sticks": 1}},
                       meadow(), 0.0)

    def test_smoke_meat_smokes_all_autumn_whatever_the_goal_while_winter_wants_more(self):
        world = outside(built({"raw_mutton": 3, "sticks": 6, "oak_log": 2}))
        self.assertFalse(PURPOSES["smoke_meat"].valid(on_day(world, 15)))  # summer
        self.assertFalse(PURPOSES["smoke_meat"].valid(on_day(world, 31)))  # winter has come
        adopt_goal(world.state, "iron_tools", "utility", "", 0.0)  # the ruling on the W2 dry run: any goal will do
        s = on_day(world, 22)
        self.assertTrue(PURPOSES["smoke_meat"].valid(s))
        steps = PURPOSES["smoke_meat"].plan(s, None)
        self.assertEqual([step["kind"] for step in steps].count("smoke"), 3)
        self.assertEqual(steps[-1]["kind"], "mine")  # the campfire it put down comes back
        world.state["inventory"]["smoked_meat"] = 8
        self.assertFalse(PURPOSES["smoke_meat"].valid(on_day(world, 22)))  # enough for the winter

    def test_a_wild_pet_smokes_its_meat_while_its_winter_food_falls_short_and_leaves_it_uncooked(self):
        world = outside(built({"raw_mutton": 3, "sticks": 6, "oak_log": 2, "smoked_meat": 8}))
        world.state["difficulty"] = "wild"
        for lesson in ("winter", "smoking", "cooking", "fire"):
            know(world.db, f"wild:{lesson}", "lesson", 0.0)
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        s = on_day(world, 22)
        self.assertEqual(smoke_wanted(s), 18)  # the chests hold no winter food: 360 hunger points, 20 a smoked meat
        self.assertEqual([step["kind"] for step in PURPOSES["smoke_meat"].plan(s, None)].count("smoke"), 3)
        self.assertIsNone(cook_plan(s))  # the mutton is kept for smoking
        world.state["vitals"]["hunger"] = 40.0
        self.assertIn({"kind": "cook", "item": "raw_mutton"}, cook_plan(on_day(world, 22)))  # hungry: it cooks
        world.state["vitals"]["hunger"] = 80.0
        world.state["inventory"].update(sticks=0, planks=4)  # no stick: it makes them from its planks
        steps = PURPOSES["smoke_meat"].plan(on_day(world, 22), None)
        self.assertIn({"kind": "craft", "recipe": "sticks"}, steps)
        self.assertEqual([step["kind"] for step in steps].count("smoke"), 3)
        world.state["inventory"].update(oak_log=0, planks=0, sticks=5)  # no fire to put down: it walks to one it has
        x, y, z = (round(world.state["position"][axis]) for axis in "xyz")
        world.grid.put(x + 20, y, z, "campfire")
        self.assertEqual(PURPOSES["smoke_meat"].plan(on_day(world, 22), None)[0]["kind"], "walk")
        self.assertEqual(spare_meat(on_day(world, 22)), SMOKABLE)
        world.state["inventory"].update(sticks=0)  # no stick and no wood for one: meat it cannot smoke is not spared
        self.assertEqual(spare_meat(on_day(world, 22)), ())


class CloakTests(unittest.TestCase):
    def test_make_cloak_makes_one_with_five_wool_and_keeps_the_wool_meanwhile(self):
        world = outside(built({"wool": 5, "planks": 4}))
        s = on_day(world, 5)
        self.assertTrue(PURPOSES["make_cloak"].valid(s))
        steps = PURPOSES["make_cloak"].plan(s, None)
        self.assertIn({"kind": "craft", "recipe": "wool_cloak"}, steps)
        self.assertEqual(kept(s, "wool"), 5)
        world.state["inventory"]["wool_cloak"] = 1
        s = on_day(world, 5)
        self.assertFalse(PURPOSES["make_cloak"].valid(s))
        self.assertEqual(kept(s, "wool"), 0)

    def test_the_wool_comes_back_out_of_the_chest_for_it(self):
        world = built({"wool": 1})
        cell = chest_spot(on_day(world, 5))
        world.grid.put(*cell, "chest")
        world.state["chests"] = {chest_key(cell): {"wool": 6}}
        self.assertIn((cell, "wool", 4), to_take(on_day(world, 5)))


class HearthTests(unittest.TestCase):
    def test_build_hearth_puts_one_in_a_front_corner_of_home_while_the_winter_goal_wants_it(self):
        world = outside(built({"cobblestone": 8, "campfire": 1, "planks": 4}))
        s = on_day(world, 22)
        self.assertFalse(PURPOSES["build_hearth"].valid(s))
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        s = on_day(world, 22)
        spot = hearth_spot(s)
        self.assertIsNotNone(spot)
        self.assertTrue(PURPOSES["build_hearth"].valid(s))
        steps = PURPOSES["build_hearth"].plan(s, None)
        self.assertIn({"kind": "craft", "recipe": "hearth"}, steps)
        self.assertEqual(steps[-1], {"kind": "place", "target": list(spot), "block": "hearth"})
        world.grid.put(*spot, "hearth")
        s = on_day(world, 22)
        self.assertTrue(hearth_home(s))
        self.assertFalse(PURPOSES["build_hearth"].valid(s))
        self.assertEqual(GOALS[GOAL].milestones[2].share(s), 1.0)


if __name__ == "__main__":
    unittest.main()

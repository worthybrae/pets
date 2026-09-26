import unittest
from unittest.mock import patch

from backend.services.crafting import craft, smelt
from backend.survival import brain  # noqa: F401  (registers every purpose)
from backend.survival.making import (
    COLOURS, NEEDS, craft_plan, favourite_colour, needs, place_steps, raw_needs, sources,
)
from backend.survival.purposes import PURPOSES
from backend.survival.storage import junk, kept
from backend.survival.work import stone_goal, wanted_ores
from backend.tests.test_survival_building import NIGHT, World

FLAT = lambda x, z, seed: 0  # noqa: E731
CLAY = {(4, 0), (5, 0), (9, 3)}


def shore(x, z, seed):
    return "clay" if (x, z) in CLAY else "grass"


def want(test, items):
    """A project that wants `items` made and put in place while the test runs (making.NEEDS)."""
    wants = lambda s: dict(items)  # noqa: E731
    NEEDS.append(wants)
    test.addCleanup(NEEDS.remove, wants)


class RecipeTests(unittest.TestCase):
    CASES = {
        "paper": ({"sugar_cane": 3}, {"paper": 3}),
        "book": ({"paper": 3, "leather": 1}, {"book": 1}),
        "dye_pink": ({"flower_pink": 1}, {"dye_pink": 2}),
        "wool_pink": ({"wool": 1, "dye_pink": 1}, {"wool_pink": 1}),
        "rug_pink": ({"wool_pink": 2}, {"rug_pink": 3}),
        "bookshelf": ({"birch_planks": 6, "book": 1}, {"bookshelf": 1}),  # any wood's planks
        "kiln": ({"brick": 3, "cobblestone": 5}, {"kiln": 1}),
        "stairs": ({"planks": 6}, {"stairs": 4}),
        "slab": ({"planks": 3}, {"slab": 6}),
        "glass_pane": ({"glass": 6}, {"glass_pane": 16}),
        "trapdoor": ({"planks": 6}, {"trapdoor": 2}),
        "iron_bars": ({"iron_ingot": 6}, {"iron_bars": 16}),
        "flower_pot": ({"brick": 3}, {"flower_pot": 1}),
        "sign": ({"planks": 6, "sticks": 1}, {"sign": 3}),
        "barrel": ({"planks": 6, "slab": 2}, {"barrel": 1}),
        "composter": ({"slab": 7}, {"composter": 1}),
        "candle": ({"tallow": 1, "string": 1}, {"candle": 1}),
    }

    def test_the_new_recipes_make_what_they_say(self):
        for recipe, (inventory, made) in self.CASES.items():
            self.assertEqual(craft(inventory, recipe, {"crafting_table"}), made, recipe)
        with self.assertRaises(ValueError):
            craft({"sugar_cane": 3}, "paper", set())  # paper is made at a crafting table

    def test_a_kiln_fires_clay_and_sand_without_fuel_and_a_furnace_still_burns_some(self):
        self.assertEqual(smelt({"clay": 2}, "clay", {"kiln"}), {"clay": 1, "brick": 1})
        self.assertEqual(smelt({"sand": 1}, "sand", {"kiln"}), {"glass": 1})
        self.assertEqual(smelt({"clay": 1, "coal": 1}, "clay", {"furnace"}), {"brick": 1})
        with self.assertRaises(ValueError):
            smelt({"clay": 1}, "clay", {"furnace"})  # no fuel
        with self.assertRaises(ValueError):
            smelt({"iron_ore": 1, "coal": 1}, "iron_ore", {"kiln"})  # a kiln fires clay and sand only


class NeedsTests(unittest.TestCase):
    def test_raw_needs_work_out_clay_for_a_kiln_and_sand_for_windows(self):
        world = World({"cobblestone": 5, "oak_log": 4})
        self.assertEqual((needs(world.situation()), raw_needs(world.situation())), ({}, {}))
        want(self, {"kiln": 1})
        self.assertEqual(raw_needs(world.situation()), {"clay": 3})
        world.state["inventory"]["brick"] = 2
        self.assertEqual(raw_needs(world.situation()), {"clay": 1})
        want(self, {"glass_pane": 2})
        self.assertEqual(raw_needs(world.situation()), {"clay": 1, "sand": 6})
        self.assertEqual(needs(world.situation()), {"kiln": 1, "glass_pane": 2})

    def test_what_no_gathering_brings_leaves_a_thing_waiting(self):
        world = World({"planks": 6})
        want(self, {"bookshelf": 1})
        self.assertEqual(raw_needs(world.situation()), {"sugar_cane": 3})  # the leather waits for a hunt

    def test_the_chest_keeps_off_what_a_project_needs_and_its_flowers_are_not_junk(self):
        world = World({"clay": 3, "flower_pink": 2, **{f"item_{n}": 1 for n in range(9)}})
        s = world.situation()
        self.assertEqual(kept(s, "clay"), 0)
        self.assertIn(("flower_pink", 2), junk(s))
        want(self, {"kiln": 1, "rug_pink": 1})
        s = world.situation()
        self.assertEqual(kept(s, "clay"), 32)
        self.assertNotIn("flower_pink", [item for item, _ in junk(s)])

    def test_gather_stone_digs_for_the_cobblestone_making_wants_a_stack_at_most(self):
        world = World({"wooden_pickaxe": 1, "clay": 3, "oak_log": 2})
        self.assertEqual(stone_goal(world.situation()), 12)
        want(self, {"kiln": 1})
        self.assertEqual(raw_needs(world.situation())["cobblestone"], 5)
        self.assertEqual(stone_goal(world.situation()), 12 + 5)
        want(self, {"furnace": 6})
        self.assertEqual(stone_goal(world.situation()), 12 + 32)

    def test_mine_ore_goes_after_copper_while_making_wants_it(self):
        world = World({"stone_pickaxe": 1, "coal": 8, "iron_ore": 3})
        self.assertNotIn("copper_ore", wanted_ores(world.situation()))
        want(self, {"copper_ingot": 2})
        self.assertIn("copper_ore", wanted_ores(world.situation()))

    def test_the_favourite_colour_is_a_trait_fixed_by_the_seed_and_the_name(self):
        colour = favourite_colour({"name": "Pip", "world_seed": "1"})
        self.assertIn(colour, COLOURS)
        self.assertEqual(favourite_colour({"name": "Pip", "world_seed": "1"}), colour)
        self.assertGreater(len({favourite_colour({"name": name, "world_seed": "1"})
                                for name in ("Pip", "Pebble", "Moss", "Juniper", "Sol", "Wren")}), 1)


class MakingThingsTests(unittest.TestCase):
    def test_a_table_and_a_furnace_go_down_beside_mimo_and_come_back_after(self):
        world = World({"clay": 3, "cobblestone": 13, "oak_log": 4})
        steps = craft_plan(world.situation(), {"kiln": 1})
        places = [step for step in steps if step["kind"] == "place"]
        self.assertEqual([step["block"] for step in places], ["crafting_table", "furnace"])
        self.assertEqual([step["item"] for step in steps if step["kind"] == "smelt"], ["clay"] * 3)
        self.assertEqual([step["recipe"] for step in steps if step["kind"] == "craft"][-1], "kiln")
        self.assertEqual(steps[-2:], [{"kind": "mine", "target": places[1]["target"], "keep": True},
                                      {"kind": "mine", "target": places[0]["target"], "keep": True}])
        self.assertIsNone(craft_plan(world.situation(), {"kiln": 2}))  # not enough clay for two
        self.assertEqual(craft_plan(World({"kiln": 1}).situation(), {"kiln": 1}), [])  # carried already

    def test_stations_placed_within_reach_are_used_where_they_stand(self):
        world = World({"clay": 3, "cobblestone": 5, "planks": 3})
        world.grid.put(3, 1, 1, "crafting_table")
        world.grid.put(1, 1, 3, "kiln")
        steps = craft_plan(world.situation(), {"kiln": 1})
        self.assertEqual([step["kind"] for step in steps], ["smelt", "smelt", "smelt", "craft"])

    def test_place_steps_walk_to_the_nearest_stand_that_reaches(self):
        world = World(position=(1, 1, 1))
        place = {"kind": "place", "target": [8, 1, 0], "block": "lamp"}
        steps = place_steps(world.situation(), [(0, 1, 0), (6, 1, 0), (7, 1, 3)], [((8, 1, 0), [place])])
        self.assertEqual(steps, [{"kind": "walk", "target": [6, 1, 0], "reach": 0.0, "whole": True}, place])
        here = {"kind": "place", "target": [1, 1, 1], "block": "rug_pink"}
        self.assertEqual(place_steps(world.situation(), [(1, 1, 2)], [((1, 1, 1), [here])])[0]["target"], [1, 1, 2])


@patch("backend.survival.making.terrain_height", FLAT)
@patch("backend.survival.making.surface_material", shore)
class GatherTests(unittest.TestCase):
    def setUp(self):
        self.world = World({"cobblestone": 5, "oak_log": 4})
        for x, z in CLAY:
            self.world.grid.put(x, 0, z, "clay")
        self.world.grid.put(5, 1, 0, "water")  # this clay lies under water

    def test_it_digs_the_nearest_clay_a_project_wants_and_never_under_water(self):
        gather = PURPOSES["gather_materials"]
        self.assertFalse(gather.valid(self.world.situation()))  # nothing wanted
        want(self, {"kiln": 1})
        s = self.world.situation()
        self.assertTrue(gather.valid(s))
        self.assertEqual(sources(s), [((4, 0, 0), "clay"), ((9, 0, 3), "clay")])
        self.assertIn("wants 3 clay", gather.facts(s))
        self.assertEqual(gather.plan(s, self.world.context()), [
            {"kind": "mine", "target": [4, 0, 0]},
            {"kind": "walk", "target": [9, 0, 3], "reach": 2.0, "whole": True},
            {"kind": "mine", "target": [9, 0, 3]}])
        self.assertFalse(gather.valid(self.world.situation(NIGHT)))

    def test_sugar_cane_comes_down_from_the_top_of_its_stalk(self):
        for y in (1, 2, 3):
            self.world.grid.put(3, y, 0, "sugar_cane")
        want(self, {"bookshelf": 1})
        with patch("backend.survival.making.natural_plants", lambda seed, x, z, radius, kinds: [(3, 1, 0)]):
            s = self.world.situation()
            self.assertEqual([cell for cell, _ in sources(s)], [(3, 3, 0), (3, 2, 0), (3, 1, 0)])
            self.assertEqual([step["target"] for step in PURPOSES["gather_materials"].plan(s, self.world.context())],
                             [[3, 3, 0], [3, 2, 0], [3, 1, 0]])


if __name__ == "__main__":
    unittest.main()

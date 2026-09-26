import unittest
from unittest.mock import patch

from backend.services.crafting import craft, smelt
from backend.survival import brain  # noqa: F401  (registers every purpose)
from backend.survival.making import (
    COLOURS, FAR, FAR_SIGHT, NEEDS, SOURCE_SIGHT, craft_plan, favourite_colour, gathered_wanted,
    kept_for_making, making_room, needs, place_steps, raw_needs, sources,
)
from backend.survival.building import spared, sparing
from backend.survival.carrying import GIVES_WAY_TO_FOOD, LOW_VALUE, settle, stacks
from backend.survival.goals import GOALS, adopt_goal, advancing, workable
from backend.survival.memory import know, remember
from backend.survival.purposes import PURPOSES
from backend.survival.storage import junk, kept, loose_blocks, to_store, to_take
from backend.survival.work import ore_targets, stone_goal, wanted_ores
from backend.tests.test_survival_building import NIGHT, World
from backend.tests.test_survival_storage import Home

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
        "candle": ({"tallow": 1, "sticks": 1}, {"candle": 1}),  # the final fix wave: a stick, not string
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
        know(world.db, "workshop", "goal", 0.0)  # its workshop reached: no kiln keeps clay for later
        s = world.situation()
        self.assertEqual(kept(s, "clay"), 0)
        self.assertIn(("flower_pink", 2), junk(s))
        want(self, {"kiln": 1, "rug_pink": 1})
        s = world.situation()
        self.assertEqual(kept(s, "clay"), 3)  # the final fix wave (I1): what the kiln takes, not a whole stack
        self.assertEqual([item for item, _ in junk(s) if item.startswith("flower")], ["flower_pink"])
        self.assertIn(("flower_pink", 1), junk(s))  # one flower makes the rug's two dyes: the other is spare

    def test_what_is_kept_is_what_the_needs_take_not_a_stack_of_the_whole_chain_nor_wood_and_stone(self):
        """The Making final fix wave, I1: with the cozy home the goal, making kept a stack more of 14 kinds,
        which filled Mimo's arms. Now it keeps the counts the needs take, through their recipes, and leaves
        wood and stone to L4a's own keep."""
        world = World({"clay": 12, "sand": 16, "cobblestone": 20, "planks": 20, "iron_ingot": 2, "wool": 5})
        want(self, {"kiln": 1, "glass_pane": 2, "iron_bars": 2})
        s = world.situation()
        self.assertEqual({item: kept_for_making(s, item) for item in ("clay", "sand", "iron_ingot", "wool")},
                         {"clay": 3.0, "sand": 6.0, "iron_ingot": 2.0, "wool": 0.0})
        self.assertEqual((kept_for_making(s, "cobblestone"), kept_for_making(s, "planks")), (0.0, 0.0))
        self.assertEqual(kept(s, "clay"), 3)
        self.assertEqual(kept(s, "cobblestone"), 16)  # L4a's own keep, as without a project

    def test_iron_bars_send_mine_ore_after_iron(self):
        """C1 (b): iron ore was not in MINED, so raw_needs stopped at the workshop's bars and mine_ore never
        went after their iron once Mimo had an iron pickaxe."""
        world = World({"iron_pickaxe": 1, "coal": 8})
        self.assertNotIn("iron_ore", wanted_ores(world.situation()))
        want(self, {"iron_bars": 2})
        s = world.situation()
        self.assertEqual(raw_needs(s), {"iron_ore": 6})
        self.assertIn("iron_ore", wanted_ores(s))
        remember(world.db, "ore", (20, -3, 4), 0.0, "iron_ore")
        self.assertEqual([place["note"] for place in ore_targets(world.situation())], ["iron_ore"])

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

    def test_nothing_is_gathered_without_room_to_carry_it(self):
        """The Making final fix wave: a pet with its 16 stacks taken dug every clay within 160 blocks of home on
        the gate's route check, and each was left behind at once (carrying.settle). With no room, gathering
        waits (build_storage makes room first)."""
        want(self, {"kiln": 1})
        self.world.state["inventory"].update({f"item_{n}": 1 for n in range(14)})  # 16 stacks, with the two there
        s = self.world.situation()
        self.assertEqual((raw_needs(s), gathered_wanted(s)), ({"clay": 3}, {}))
        self.assertFalse(PURPOSES["gather_materials"].valid(s))
        del self.world.state["inventory"]["item_0"]
        self.assertTrue(PURPOSES["gather_materials"].valid(self.world.situation()))

    def test_a_picked_plant_is_no_source(self):
        """The Making final fix wave, I2: a picked stalk's root reads "air", and the loop still counted it,
        so gather_materials was offered with nothing to gather and kept the goal "workable"."""
        want(self, {"bookshelf": 1})
        roots = [(3, 1, 0), (6, 1, 2)]
        with patch("backend.survival.making.natural_plants", lambda seed, x, z, radius, kinds: list(roots)):
            self.world.grid.put(3, 1, 0, "sugar_cane")  # one stalk still stands; the other root was picked
            s = self.world.situation()
            self.assertEqual(sources(s), [((3, 1, 0), "sugar_cane")])
            self.world.grid.put(3, 1, 0, "air")  # now both are picked
            s = self.world.situation()
            self.assertEqual(sources(s), [])
            self.assertFalse(PURPOSES["gather_materials"].valid(s))


FAR_CLAY = {(60, 1), (61, 1), (62, 1), (60, 2)}


def far_shore(x, z, seed):
    return "clay" if (x, z) in FAR_CLAY else "grass"


def far_ground(x, y, z):
    """A meadow whose only clay lies on a shore 60 blocks east of home."""
    if y == 0:
        return "clay" if (x, z) in FAR_CLAY else "grass"
    return "dirt" if y < 0 else "air"


@patch("backend.survival.making.terrain_height", FLAT)
@patch("backend.survival.making.surface_material", far_shore)
@patch("backend.survival.making.swamp_pool", lambda x, z, seed: False)
@patch("backend.survival.making.SEA_LEVEL", 0)
class FarTests(unittest.TestCase):
    """The Making final fix wave, C1: gather_materials looked for clay only within SOURCE_SIGHT of where
    Mimo stood, so a home out of sight of a shore never got its kiln."""

    def test_clay_beyond_sight_is_looked_for_once_a_day_and_walked_to(self):
        from backend.tests.test_survival_workshop import BLOCKS_FOR_IT, Yard

        yard = Yard(BLOCKS_FOR_IT, position=(2, 1, 5), natural=far_ground)
        yard.goal("workshop")
        s = yard.situation()
        self.assertEqual(raw_needs(s)["clay"], 3)
        found = sources(s)
        self.assertEqual({(x, z) for (x, _, z), _ in found}, FAR_CLAY)  # every column is looked at
        self.assertTrue(all(SOURCE_SIGHT < s.distance(cell) <= FAR_SIGHT for cell, _ in found))
        self.assertEqual(yard.state["brain"][FAR]["found"]["clay"]["day"], 1)  # remembered, with the day it was
        nearest = found[0][0]
        self.assertIn(f"0 to gather within {SOURCE_SIGHT} blocks; the nearest clay lies {round(s.distance(nearest))} "
                      "blocks away", PURPOSES["gather_materials"].facts(s))
        steps = PURPOSES["gather_materials"].plan(s, yard.context())
        self.assertEqual(steps, [{"kind": "walk", "target": list(nearest), "reach": 2.0, "whole": True},
                                 {"kind": "mine", "target": list(nearest)}])  # one far one, then look again there

    def test_a_home_with_clay_sixty_blocks_away_gets_its_workshops_kiln(self):
        from backend.survival.workshop import current_workshop, fixtures_left
        from backend.survival.structures import blueprint_of
        from backend.tests.test_survival_workshop import BLOCKS_FOR_IT, Yard, shares

        yard = Yard({**BLOCKS_FOR_IT, "iron_ingot": 6, "sticks": 4, "coal": 6}, position=(2, 1, 5), natural=far_ground)
        yard.goal("workshop")
        yard.build()
        blueprint = blueprint_of(current_workshop(yard.situation()))
        self.assertEqual([planned.block for planned in fixtures_left(yard.situation(), blueprint)], ["kiln"])
        gather = PURPOSES["gather_materials"]
        for _ in range(3):
            s = yard.situation()
            if not gather.valid(s):
                break
            yard.carry_out(gather.plan(s, yard.context()), "gather_materials")
        self.assertEqual(yard.state["inventory"].get("clay"), 3)
        self.assertGreater(yard.situation().distance((1, 1, 1)), 50)  # it went out to the shore
        yard.state["position"] = dict(zip("xyz", map(float, (2, 1, 5))))  # and home again
        yard.build()
        self.assertEqual(fixtures_left(yard.situation(), blueprint), [])
        kiln = next(planned.cell for planned in blueprint.cells if planned.block == "kiln")
        self.assertEqual(yard.grid.material(*kiln), "kiln")
        self.assertEqual(shares(yard.situation(), "workshop"), [1.0, 1.0, 1.0, 1.0])


class ChestTests(unittest.TestCase):
    """The Making final fix wave, I1: what a project needs is neither thrown away nor left in the chest."""

    FULL = {"clay": 12, "sand": 16, **{f"item_{n}": 1 for n in range(14)}}  # 16 stacks

    def test_full_arms_drop_only_the_clay_and_sand_no_project_keeps(self):
        world = World(dict(self.FULL))
        know(world.db, "workshop", "goal", 0.0)  # its workshop reached: no kiln keeps clay for later
        self.assertEqual(loose_blocks(world.situation()), [("sand", 16), ("clay", 12)])
        want(self, {"kiln": 1, "glass_pane": 2})
        s = world.situation()
        self.assertEqual(loose_blocks(s), [("sand", 10), ("clay", 9)])
        self.assertIn(("clay", 9), junk(s))

    def test_a_find_at_full_arms_never_pushes_out_clay_or_copper(self):
        """On the gate's route check every clay a pet dug was pushed out by the next meat or ore it picked up
        (carrying.settle: clay was a LOW_VALUE block), and the bench's copper by the next fish (it gave way to
        food). The find stays behind instead, or a real LOW_VALUE block gives way."""
        full = {"clay": 3, "copper_ore": 3, **{f"item_{n}": 1 for n in range(14)}}  # 16 stacks
        inventory = {**full, "iron_ore": 1}
        self.assertEqual(settle(inventory, full), {"iron_ore": 1})
        inventory = {**full, "raw_fish": 1}
        self.assertEqual(settle(inventory, full), {"raw_fish": 1})
        self.assertEqual((inventory["clay"], inventory["copper_ore"]), (3, 3))
        with_dirt = {**{key: value for key, value in full.items() if key != "item_0"}, "dirt": 5}
        inventory = {**with_dirt, "iron_ore": 1}
        self.assertEqual(settle(inventory, with_dirt), {"dirt": 5})
        self.assertNotIn("clay", LOW_VALUE)
        self.assertFalse({"copper_ore", "copper_ingot"} & set(GIVES_WAY_TO_FOOD))

    def test_the_clay_for_the_kiln_is_kept_and_no_wall_takes_it_until_the_kiln_is_in(self):
        """The Making final fix wave: on the gate's first run every clay within 96 blocks of home was dug, then
        raised into the workshop's walls or dropped as a loose block while another goal was Mimo's, and no
        kiln was ever made. Until the workshop goal is reached with its kiln in, 3 clay (or bricks) are kept."""
        world = World({"clay": 5, "cobblestone": 2, **{f"item_{n}": 1 for n in range(14)}})  # 16 stacks
        s = world.situation()
        self.assertEqual((kept(s, "clay"), loose_blocks(s)), (3, [("clay", 2)]))
        self.assertEqual(spared(s), {"clay": 3})
        self.assertEqual(sparing(s, s.inventory)["clay"], 2)  # walls may take the other 2
        world.state["inventory"].update(clay=0, brick=3)
        self.assertEqual(spared(world.situation()), {"brick": 3})  # fired already: the bricks are kept instead
        know(world.db, "workshop", "goal", 0.0)
        self.assertEqual(spared(world.situation()), {})

    def test_the_levers_cobblestone_comes_back_out_of_the_chest(self):
        """On the gate's route check three pets had the spark, the wire and the lamp's copper, but full arms had
        put all their cobblestone in the chest, and nothing took it back for the lever: wood and stone are
        taken out too (never made, and kept only with full arms, where L4a's own keep is none)."""
        home = Home({"sticks": 2, "coal": 2, "copper_ingot": 1}, chest={"cobblestone": 80})
        know(home.db, "workshop", "goal", 0.0)
        know(home.db, "first_circuits", "goal", 0.0)  # (Making wave 2: no tinker bench wants copper)
        want(self, {"lever": 1, "lamp": 1})
        s = home.situation()
        self.assertEqual(raw_needs(s), {})
        self.assertEqual([(item, amount) for _, item, amount in to_take(s)], [("cobblestone", 1)])
        self.assertEqual(kept_for_making(s, "cobblestone"), 0.0)  # L4a's keep of 16 holds it
        home.state["inventory"].update({"cobblestone": 1, **{f"item_{n}": 1 for n in range(12)}})  # 16 stacks
        self.assertEqual(kept_for_making(home.situation(), "cobblestone"), 1.0)  # full arms: not put back

    def test_what_making_made_and_no_project_needs_goes_in_the_chest(self):
        """The Making final fix wave: a glass pane recipe makes 16, iron bars 16, stairs 4; what was left over
        stayed in Mimo's arms for good (a fifth of them at day 100), so what it dug for the kiln was pushed
        out."""
        home = Home({"glass_pane": 14, "iron_bars": 14, "stairs": 3, "tallow": 9, "sign": 2, "cobblestone": 60,
                     **{f"item_{n}": 1 for n in range(8)}}, chest={})
        know(home.db, "workshop", "goal", 0.0)
        stored = {item for item, _ in to_store(home.situation(), (2, 1, 2))}
        self.assertLessEqual({"glass_pane", "iron_bars", "stairs", "tallow", "sign"}, stored)
        want(self, {"glass_pane": 2})
        self.assertIn(("glass_pane", 12), to_store(home.situation(), (2, 1, 2)))  # two kept for the windows

    def test_build_storage_takes_back_out_what_a_project_needs_and_does_not_put_it_back(self):
        home = Home({"planks": 12, "cobblestone": 8, "sticks": 2}, chest={"clay": 5, "copper_ore": 3, "wool": 2})
        know(home.db, "workshop", "goal", 0.0)  # (no kiln waits for it later)
        know(home.db, "first_circuits", "goal", 0.0)  # (Making wave 2: nor a tinker bench)
        s = home.situation()
        self.assertEqual(to_take(s), [])  # no project wants anything (and the chest holds no food)
        want(self, {"kiln": 1, "copper_wire": 1})
        s = home.situation()
        self.assertEqual(raw_needs(s), {})  # what the chest holds counts: no shore, no mine for it
        self.assertEqual(sorted((item, amount) for _, item, amount in to_take(s)), [("clay", 3), ("copper_ore", 1)])
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        takes = [step for step in home.plan("build_storage") if step["kind"] == "take"]
        self.assertEqual(sorted((step["item"], step["amount"]) for step in takes), [("clay", 3), ("copper_ore", 1)])
        home.state["inventory"].update(clay=3, copper_ore=1)  # taken out
        home.state["chests"]["2,1,2"].update(clay=2, copper_ore=2)
        s = home.situation()
        self.assertEqual([entry for entry in to_take(s) if entry[1] in ("clay", "copper_ore")], [])
        self.assertEqual([entry for entry in to_store(s, (2, 1, 2)) if entry[0] in ("clay", "copper_ore")], [])


class RoomTests(unittest.TestCase):
    """Making wave 2: on the gate's route runs Willow and Clover carried 16 stacks of what L4a keeps on hand
    (seeds, saplings, iron, logs, coal) and four kinds of food, so their copper was "not wanted" (no room)
    and the first circuits idled; Pip had the spark and the copper, but the lamp's torch chain had no room."""

    # 16 stacks: gear (4), a day's food (2), and what L4a keeps for its own goals (10).
    ARMS = {"iron_pickaxe": 1, "iron_sword": 1, "iron_cap": 1, "iron_tunic": 1, "cooked_beef": 1, "berries": 3,
            "seeds": 8, "sapling": 4, "wheat": 6, "iron_ore": 16, "feather": 4, "flint": 4, "gold_ore": 3,
            "coal": 8, "oak_log": 8, "sticks": 8}

    def home(self):
        home = Home(dict(self.ARMS), chest={"copper_ore": 3, "cobblestone": 20})
        know(home.db, "workshop", "goal", 0.0)
        return home

    def test_with_first_circuits_the_goal_full_arms_put_away_what_other_goals_keep(self):
        home = self.home()
        s = home.situation()
        self.assertEqual(stacks(s.inventory), 16)
        self.assertFalse(making_room(s))  # no making goal: L4a keeps all of it
        self.assertEqual(to_store(s, (2, 1, 2)), [])
        adopt_goal(home.state, "first_circuits", "rules", "", 0.0)
        s = home.situation()
        self.assertTrue(making_room(s))
        self.assertEqual(needs(s), {"lever": 1, "copper_wire": 1, "lamp": 1})  # the tinker bench (C2)
        stored = dict(to_store(s, (2, 1, 2)))
        self.assertEqual(stored, {"seeds": 8, "sapling": 4, "wheat": 6, "iron_ore": 16, "feather": 4, "flint": 4,
                                  "gold_ore": 3})
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        # Fuel, wood, food and gear stay: the bench's torch burns coal on a stick, and the copper is smelted.
        for item in ("coal", "oak_log", "sticks"):
            self.assertGreaterEqual(kept(s, item), 8, item)
        steps = home.plan("build_storage")
        self.assertEqual({step["item"]: step["amount"] for step in steps if step["kind"] == "store"}, stored)
        for item, amount in stored.items():
            home.state["inventory"][item] -= amount
        home.state["inventory"] = {item: count for item, count in home.state["inventory"].items() if count}
        s = home.situation()
        self.assertEqual(stacks(s.inventory), 9)
        self.assertFalse(making_room(s))  # room enough: L4a's keep holds again, nothing more goes in
        self.assertEqual(sorted((item, amount) for _, item, amount in to_take(s)),
                         [("cobblestone", 1), ("copper_ore", 2)])  # the bench's copper and the lever's stone
        home.state["inventory"].update(copper_ore=2, cobblestone=1)
        home.grid.put(0, 1, 0, "crafting_table")  # the workshop's own stations
        home.grid.put(0, 1, 2, "furnace")
        self.assertIsNotNone(craft_plan(home.situation(), {"lever": 1, "copper_wire": 1, "lamp": 1}))
        home.state["inventory"] = dict(self.ARMS, copper_ore=2, cobblestone=1)  # and without the room made:
        self.assertIsNone(craft_plan(home.situation(), {"lever": 1, "copper_wire": 1, "lamp": 1}))

    def test_taking_the_goals_copper_out_of_the_chest_works_toward_it(self):
        """Hazel's chest held 5 copper ore while "First circuits" was its goal 14 times: build_storage would have
        taken the bench's copper out, but it counted toward no goal, so the goal was set aside ("nothing to do for
        it now") within half a game day each time."""
        home = Home({"coal": 4, "sticks": 4, "oak_log": 4, "iron_pickaxe": 1},
                    chest={"copper_ore": 5, "cobblestone": 9})
        know(home.db, "workshop", "goal", 0.0)
        adopt_goal(home.state, "first_circuits", "rules", "", 0.0)
        s = home.situation()
        goal = GOALS["first_circuits"]
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertIn("build_storage", advancing(s, goal))
        self.assertTrue(workable(s, goal))
        home.state["inventory"].update(copper_ore=2, cobblestone=1)  # taken out: nothing more to take
        home.state["chests"]["2,1,2"].update(copper_ore=3, cobblestone=8)
        s = home.situation()
        self.assertNotIn("build_storage", advancing(s, goal))
        adopt_goal(home.state, "armor_up", "rules", "", 1.0)
        home.state["inventory"].update(copper_ore=0, cobblestone=0)
        self.assertNotIn("build_storage", advancing(home.situation(), GOALS["armor_up"]))  # not a making goal

    def test_full_arms_and_full_chests_never_drop_the_cobblestone_a_machine_takes(self):
        """On the gate's route runs Pip's computer lacked 54 cobblestone for its repeaters: with both chests full,
        drop_items left all but gather_stone's own 12 behind."""
        full_chest = {f"thing_{n}": 32 for n in range(24)}
        home = Home({"cobblestone": 40, **{f"item_{n}": 1 for n in range(15)}}, chest=full_chest)  # 16 stacks
        know(home.db, "workshop", "goal", 0.0)
        know(home.db, "first_circuits", "goal", 0.0)  # (Making wave 2: no tinker bench wants copper)
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 28}])
        want(self, {"repeater": 10})  # 30 cobblestone
        self.assertEqual(home.plan("drop_items"), [{"kind": "drop", "item": "cobblestone", "amount": 10}])

    def test_what_the_goal_needs_stays_and_other_goals_keep_theirs(self):
        home = self.home()
        adopt_goal(home.state, "workshop", "rules", "", 0.0)
        want(self, {"iron_bars": 1})  # the workshop's windows: iron stays
        s = home.situation()
        self.assertTrue(making_room(s))
        self.assertNotIn("iron_ore", dict(to_store(s, (2, 1, 2))))
        self.assertIn("seeds", dict(to_store(s, (2, 1, 2))))
        adopt_goal(home.state, "armor_up", "rules", "", 1.0)  # not a making goal: L4a keeps its own
        self.assertFalse(making_room(home.situation()))
        self.assertEqual(to_store(home.situation(), (2, 1, 2)), [])


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from backend.services.crafting import RECIPES
from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.creatures import hunting
from backend.survival.creatures.harm import armor_wanted
from backend.survival.goals import GOALS, adopt_goal, advances, complete, counted, is_open, progress_of, share_of
from backend.survival.life_goals import DAY_SECONDS, hides_wanted, land_seen
from backend.survival.memory import mark_explored, places, remember, structures
from backend.survival.trips import REASONS
from backend.survival.purposes import PURPOSES
from backend.survival.structures import blueprint_of
from backend.survival.work import wanted_ores
from backend.tests.test_survival_building import World


def shares(s, name):
    return [round(share_of(s, milestone), 2) for _, milestone in counted(GOALS[name])]


def built(inventory=None):
    """A pet that built its first shelter on a meadow and put a bed in it."""
    world = World({"cobblestone": 60, "planks": 20, "oak_log": 4, "sticks": 4})
    for _ in range(12):
        steps = world.plan()
        if not steps:
            break
        world.carry_out(steps)
    world.state["inventory"] = dict(inventory or {})
    return world


class FirstShelterTests(unittest.TestCase):
    def test_blocks_then_the_walls_and_roof_then_a_bed(self):
        world = World({"cobblestone": 10})
        self.assertEqual(shares(world.situation(), "first_shelter"), [0.53, 0.0, 0.0])  # 10 of the 19 to start with
        s = built().situation()
        self.assertEqual(shares(s, "first_shelter"), [1.0, 1.0, 1.0])
        self.assertTrue(complete(s, GOALS["first_shelter"]))

    def test_every_other_goal_waits_for_it(self):
        s = World().situation()
        self.assertEqual([name for name, goal in GOALS.items() if is_open(s, goal)], ["first_shelter"])
        s = built().situation()
        self.assertNotIn("first_shelter", [name for name, goal in GOALS.items() if is_open(s, goal)])
        self.assertTrue(is_open(s, GOALS["iron_tools"]))
        self.assertFalse(is_open(s, GOALS["armor_up"]))  # after iron tools


class ToolsAndArmorTests(unittest.TestCase):
    def test_iron_tools_climb_the_pickaxe_ladder_to_iron(self):
        world = built({"oak_log": 3})
        self.assertEqual(shares(world.situation(), "iron_tools"), [0.5, 0.0, 0.0, 0.0, 0.0])
        world.state["inventory"] = {"stone_pickaxe": 1, "iron_ore": 2}
        self.assertEqual(shares(world.situation(), "iron_tools"), [1.0, 1.0, 1.0, 0.67, 0.0])
        world.state["inventory"] = {"stone_pickaxe": 1}
        remember(world.db, "ore", (4, -6, 4), 0.0, "iron_ore")
        self.assertEqual(shares(world.situation(), "iron_tools")[2], 1.0)  # seen is found
        world.state["inventory"] = {"iron_pickaxe": 1}
        s = world.situation()
        self.assertTrue(complete(s, GOALS["iron_tools"]))
        self.assertTrue(is_open(s, GOALS["armor_up"]))

    def test_armor_counts_leather_and_the_pieces_and_iron_armor_once_its_recipes_exist(self):
        world = built({"iron_pickaxe": 1, "leather": 2, "rabbit_hide": 4})
        armor = GOALS["armor_up"]
        iron = "iron_cap" in RECIPES and "iron_tunic" in RECIPES
        self.assertEqual(len(counted(armor)), 4 if iron else 3)
        self.assertEqual(shares(world.situation(), "armor_up")[:3], [0.6, 0.0, 0.0])
        world.state["inventory"] = {"iron_pickaxe": 1, "leather_cap": 1, "leather_tunic": 1}
        self.assertEqual(shares(world.situation(), "armor_up")[:3], [1.0, 1.0, 1.0])
        self.assertEqual(complete(world.situation(), armor), not iron)

    def test_while_armor_is_the_goal_mimo_hunts_for_hides_a_few_times_a_day(self):
        self.assertIn(hides_wanted, hunting.HUNT_FOR)
        world = built({"iron_pickaxe": 1})
        self.assertFalse(hides_wanted(world.situation()))
        adopt_goal(world.state, "armor_up", "utility", "", 0.0)
        self.assertTrue(hides_wanted(world.situation()))
        world.state["hunted_at"] = -DAY_SECONDS / 6 + 1.0  # killed something less than a sixth of a game day ago
        self.assertFalse(hides_wanted(world.situation()))
        world.state.update(hunted_at=None, inventory={"iron_pickaxe": 1, "leather": 5})
        self.assertFalse(hides_wanted(world.situation()))

    def test_with_armor_the_goal_iron_armor_is_worth_making_before_any_blow(self):
        world = built({"iron_pickaxe": 1, "coal": 8})
        self.assertFalse(armor_wanted(world.state))
        self.assertNotIn("iron_ore", wanted_ores(world.situation()))
        adopt_goal(world.state, "armor_up", "utility", "", 0.0)
        self.assertTrue(armor_wanted(world.state))
        self.assertIn("iron_ore", wanted_ores(world.situation()))  # the 13 ingots iron armor takes

    def test_with_diamond_tools_the_goal_mine_ore_goes_for_a_single_known_diamond(self):
        world = built({"iron_pickaxe": 1, "coal": 8})
        remember(world.db, "ore", (4, -6, 4), 0.0, "diamond_ore")
        self.assertNotIn("diamond_ore", wanted_ores(world.situation()))  # one of the 3 a pickaxe takes
        adopt_goal(world.state, "better_tools", "utility", "", 0.0)
        self.assertIn("diamond_ore", wanted_ores(world.situation()))

    def test_diamond_tools_wait_for_the_diamond_pickaxe_recipe(self):
        self.assertEqual(bool(counted(GOALS["better_tools"])), "diamond_pickaxe" in RECIPES)


class HomeGoalTests(unittest.TestCase):
    def test_a_safe_yard_counts_the_corner_torches_and_the_door(self):
        world = built()
        self.assertEqual(shares(world.situation(), "safe_yard")[:2], [0.0, 1.0])
        torches = [planned.cell for planned in blueprint_of(structures(world.db)[0]).parts("torch")]
        for cell in torches[:2]:
            world.grid.put(*cell, "torch")
        self.assertEqual(shares(world.situation(), "safe_yard")[0], round(2 / len(torches), 2))
        self.assertEqual(len(counted(GOALS["safe_yard"])), 2 + ("build_fence" in PURPOSES and "fence" in RECIPES))

    def test_a_herd_waits_for_the_pen_purposes(self):
        self.assertEqual(bool(counted(GOALS["herd"])), "build_pen" in PURPOSES and "fence" in RECIPES)

    def test_mapping_the_land_counts_the_dry_patches_walked_near_home(self):
        world = built()
        s = world.situation()
        self.assertEqual(land_seen(s), 0.0)
        mark_explored(world.db, [(rx, rz) for rx in range(-8, 9) for rz in range(-8, 9) if rx < 0], 0.0)
        s = world.situation()
        self.assertAlmostEqual(land_seen(s), 0.47, places=1)
        self.assertAlmostEqual(progress_of(s, GOALS["map_land"]), land_seen(s) / 0.6, places=3)


SINKHOLE = {(40 + dx, dz): (-2, 3) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}  # a shaft of air from y -2 to 3


def one_sinkhole(rx, rz, seed):
    return ("sinkhole", SINKHOLE) if (rx, rz) == (0, 0) else ("", {})


class TripTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.life_goals.region_openings", one_sinkhole),
                            ("backend.survival.life_goals.terrain_height", lambda x, z, seed: 0),
                            ("backend.survival.exploring.terrain_height", lambda x, z, seed: 0)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_with_no_iron_known_mimo_looks_for_it_at_cave_mouths_and_sinkholes(self):
        world = built({"stone_pickaxe": 1})
        s = world.situation()
        iron = REASONS["iron"]
        self.assertEqual(iron.wanted(s), "my pickaxe needs it")
        self.assertEqual((iron.value(s, 36, 4), iron.value(s, -60, 0)), ((1.0, "a sinkhole"), (0.0, "")))
        self.assertEqual(iron.spots(s), [(40, 0, "a sinkhole")])
        self.assertTrue(advances(s, "explore", GOALS["iron_tools"]))
        self.assertFalse(advances(s, "explore", GOALS["map_land"]))
        remember(world.db, "cave", (40, 1, 0), 0.0, "sinkhole")  # looked into already
        s = world.situation()
        self.assertEqual((iron.value(s, 36, 4), iron.spots(s)), ((0.0, ""), []))
        remember(world.db, "ore", (30, -3, 0), 0.0, "iron_ore")
        self.assertIsNone(iron.wanted(world.situation()))  # iron known within reach: mine_ore goes for it

    def test_looking_into_a_sinkhole_remembers_it_and_the_ore_mimo_can_reach(self):
        world = built({"stone_pickaxe": 1})
        world.grid.put(42, 0, 0, "iron_ore")  # in the wall, 1 below the rim
        world.grid.put(41, -3, 0, "coal_ore")  # the floor, far down the shaft: out of reach from the rim
        world.state["position"] = {"x": 44.0, "y": 1.0, "z": 0.0}
        find = REASONS["iron"].look(world.situation(), world.context())
        self.assertEqual((find.words, find.done), ("a sinkhole with iron ore in its walls", True))
        self.assertEqual([(place["kind"], place["x"], place["note"]) for place in places(world.db, ("cave", "ore"))],
                         [("cave", 40, "sinkhole"), ("ore", 42, "iron_ore")])
        self.assertIsNone(REASONS["iron"].look(world.situation(), world.context()))  # nothing new to look into

    def test_armor_looks_for_leather_where_cows_graze(self):
        world = built({"iron_pickaxe": 1})
        hides = REASONS["hides"]
        self.assertIsNone(hides.wanted(world.situation()))
        adopt_goal(world.state, "armor_up", "utility", "", 0.0)
        s = world.situation()
        self.assertEqual(hides.wanted(s), "my armor needs leather and no animal is near")
        self.assertEqual(hides.value(s, 40, 0), (1.0, "grazing land for cows"))  # the meadow

    def test_a_herd_looks_for_a_creature_seed_in_the_tall_grass_breaking_it_at_each_stop(self):
        world = built()
        seed = REASONS["seed"]
        adopt_goal(world.state, "herd", "utility", "", 0.0)
        self.assertEqual(seed.wanted(world.situation()), "a pen of animals grows from creature seeds")
        grass = [(2, 1, 1), (3, 1, 1)]
        with patch("backend.survival.life_goals.grass_near", lambda grid, seed, here, radius: grass), \
                patch("backend.survival.life_goals.natural_plants", lambda seed, x, z, radius, kinds: [(x, 1, z)] * 6):
            s = world.situation()
            self.assertEqual(seed.work(s), [{"kind": "mine", "target": [2, 1, 1]}, {"kind": "mine", "target": [3, 1, 1]}])
            self.assertEqual(seed.value(s, 40, 0), (0.5, "tall grass"))
        world.state["inventory"] = {"creature_seed": 1}
        s = world.situation()
        self.assertIsNone(seed.wanted(s))
        self.assertEqual(seed.look(s, world.context()).words, "a creature seed")

    def test_mapping_the_land_heads_for_the_ground_it_has_seen_least(self):
        world = built()
        self.assertIsNone(REASONS["map"].wanted(world.situation()))
        adopt_goal(world.state, "map_land", "utility", "", 0.0)
        s = world.situation()
        self.assertEqual(REASONS["map"].wanted(s), "I want to know the land around home")
        [(x, z, words)] = REASONS["map"].spots(s)
        self.assertEqual(words, "land it has not seen")


if __name__ == "__main__":
    unittest.main()

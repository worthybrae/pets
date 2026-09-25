import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.blueprints import find_site
from backend.survival.goals import GOALS, adopt_goal, complete, is_open
from backend.survival.homes import better_design, blocks_wanted, moved_up, rising
from backend.survival.memory import places, structures
from backend.survival.purposes import PURPOSES
from backend.survival.trips import REASONS
from backend.tests.test_survival_life_goals import built, shares


def sites_east(grid, center, size, sides, roof):
    """Only the land 20 or more blocks east of home has room for a bigger home."""
    return find_site(grid, center, size, sides, roof) if center[0] >= 20 else None


class BetterHomeTests(unittest.TestCase):
    def test_once_mimo_has_a_home_a_bigger_stone_one_is_a_goal(self):
        world = built()
        s = world.situation()
        self.assertTrue(is_open(s, GOALS["better_home"]))
        design = better_design(s)
        self.assertEqual((design.style["size"], design.style["wall"], design.name),
                         ([4, 3], "cobblestone", "Pip's Snug Stone House"))  # the next tier up: it carries nothing

    def test_improve_home_is_offered_only_for_the_goal_and_with_half_the_blocks(self):
        world = built({"cobblestone": 64, "planks": 16})
        improve = PURPOSES["improve_home"]
        self.assertFalse(improve.valid(world.situation()))
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        s = world.situation()
        self.assertTrue(improve.valid(s))
        self.assertEqual((better_design(s).style["size"], blocks_wanted(s)), ([5, 4], 31))  # the biggest it covers
        world.state["inventory"] = {"cobblestone": 20}  # a 4x3 house takes 46: half is 23
        self.assertFalse(improve.valid(world.situation()))

    def test_it_starts_the_bigger_home_build_shelter_finishes_it_and_mimo_moves_in(self):
        world = built({"cobblestone": 64, "planks": 16})
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        world.carry_out(PURPOSES["improve_home"].plan(world.situation(), world.context()))
        s = world.situation()
        self.assertEqual(rising(s)["status"], "building")
        self.assertFalse(PURPOSES["improve_home"].valid(s))  # one at a time
        self.assertEqual(shares(s, "better_home")[0], 1.0)
        for _ in range(15):
            steps = PURPOSES["build_shelter"].plan(world.situation(), world.context())
            if not steps:
                break
            world.carry_out(steps)
        s = world.situation()
        self.assertEqual([row["status"] for row in structures(world.db)], ["done", "done"])
        home = places(world.db, ("home",))[0]
        self.assertEqual((home["x"], home["y"], home["z"]), tuple(structures(world.db)[1][axis] for axis in "xyz"))
        self.assertTrue(moved_up(s))
        self.assertTrue(complete(s, GOALS["better_home"]))


    def test_with_no_site_near_home_mimo_scouts_for_flat_ground_and_remembers_the_site(self):
        world = built()
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        site = REASONS["site"]
        with patch("backend.survival.homes.find_site", sites_east), \
                patch("backend.survival.homes.terrain_height", lambda x, z, seed: 3):
            s = world.situation()
            self.assertIsNone(better_design(s))
            self.assertTrue(is_open(s, GOALS["better_home"]))  # home can still grow: find a site first
            self.assertEqual(shares(s, "better_home")[0], 0.0)
            self.assertEqual(site.wanted(s), "no site near home fits a bigger home")
            self.assertEqual(site.value(s, 30, 0), (1.0, "flat ground"))
            self.assertIsNone(site.look(s, world.context()))  # no room here
            world.state["position"] = {"x": 24.0, "y": 1.0, "z": 1.0}
            find = site.look(world.situation(), world.context())
            self.assertEqual((find.words, find.done), ("flat ground for a bigger home", True))
            self.assertEqual([(place["x"], place["z"]) for place in places(world.db, ("site",))], [(24, 1)])
            world.state["position"] = {"x": 1.0, "y": 1.0, "z": 1.0}
            s = world.situation()
            self.assertIsNotNone(better_design(s))  # at the site it found
            self.assertIsNone(site.wanted(s))
            self.assertEqual(shares(s, "better_home")[0], 1.0)


if __name__ == "__main__":
    unittest.main()

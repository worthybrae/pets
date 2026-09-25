import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.blueprints import find_site
from backend.survival.goals import GOALS, adopt_goal, complete, is_open
from backend.survival.homes import better_design, blocks_wanted, moved_up, rising
from backend.survival.larder import chest_food
from backend.survival.lighting import home_blueprint
from backend.survival.memory import places, structures
from backend.survival.pens import home_done
from backend.survival.purposes import PURPOSES
from backend.survival.storage import chest_spot, storage_valid
from backend.survival.structures import blueprint_of
from backend.survival.trips import REASONS
from backend.tests.test_survival_life_goals import built, shares

DUSK = {"phase": "day", "seconds_into_day": 2000.0, "time_scale": 1.0, "day_number": 1}


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


class HomeResolutionTests(unittest.TestCase):
    """Fix round 1: while the bigger home is under way, storage.chest_spot, lighting.home_blueprint
    and pens.home_done used to resolve "home" through building.current_shelter, the newest shelter
    within reach -- the still-rising second one. They now resolve the home Mimo actually lives in,
    so build_storage, light_up and build_pen (and the larder's progress) keep working the whole
    build, and follow home once the bigger shelter finishes and takes over."""

    def two_shelters(self):
        """Shelter 1 finished (home, with a chest holding food) and shelter 2 rising beside it."""
        world = built({"cobblestone": 64, "planks": 16})
        first = structures(world.db)[0]
        first_chest = blueprint_of(first).one("chest")
        world.grid.put(*first_chest, "chest")
        world.state["chests"] = {f"{first_chest[0]},{first_chest[1]},{first_chest[2]}": {"cooked_fish": 3}}
        adopt_goal(world.state, "better_home", "utility", "", 0.0)
        world.carry_out(PURPOSES["improve_home"].plan(world.situation(), world.context()))
        return world, first, first_chest

    def test_storage_lighting_and_the_pen_still_see_shelter_1_while_shelter_2_rises(self):
        world, first, first_chest = self.two_shelters()
        s = world.situation()
        self.assertEqual(rising(s)["status"], "building")  # shelter 2 is under way, not home yet

        # build_storage still finds and uses shelter 1's chest, not the rising shelter 2 (no chest yet)
        self.assertEqual(chest_spot(s), first_chest)
        world.state["inventory"] = {}  # empty-handed: hungry enough to want the stored food back
        s = world.situation()
        self.assertTrue(storage_valid(s))
        steps = PURPOSES["build_storage"].plan(s, world.context())
        self.assertTrue(any(step["kind"] == "take" and step["target"] == list(first_chest) for step in steps))

        # light_up still targets shelter 1's corners at dusk
        anchor = (first["x"], first["y"], first["z"])
        world.state["position"] = dict(zip("xyz", map(float, anchor)))
        s = world.situation(DUSK)
        blueprint = home_blueprint(s)
        self.assertIsNotNone(blueprint)
        self.assertEqual(blueprint.anchor, anchor)

        # build_pen sees the home as done
        self.assertTrue(home_done(s))

        # the larder's progress counts shelter 1's chest
        self.assertGreater(chest_food(s), 0.0)

    def test_they_follow_home_once_shelter_2_finishes_and_takes_over(self):
        world, first, first_chest = self.two_shelters()
        for _ in range(15):
            steps = PURPOSES["build_shelter"].plan(world.situation(), world.context())
            if not steps:
                break
            world.carry_out(steps)
        s = world.situation()
        self.assertTrue(moved_up(s))  # shelter 2 is home now
        second = structures(world.db)[1]
        anchor = (second["x"], second["y"], second["z"])
        self.assertNotEqual(anchor, (first["x"], first["y"], first["z"]))
        self.assertEqual(chest_spot(s), blueprint_of(second).one("chest"))
        world.state["position"] = dict(zip("xyz", map(float, anchor)))
        s = world.situation(DUSK)
        blueprint = home_blueprint(s)
        self.assertIsNotNone(blueprint)
        self.assertEqual(blueprint.anchor, anchor)
        self.assertTrue(home_done(s))


if __name__ == "__main__":
    unittest.main()

"""L4a final fix wave, I1: the one home lookup (backend.survival.home) and what reads it."""

import unittest

from backend.survival import brain  # noqa: F401  (registers every purpose, goal and reason)
from backend.survival import home
from backend.survival.building import shelter_valid, site_center
from backend.survival.exploring import candidates
from backend.survival.memory import remember, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.trips import REASONS, targets
from backend.tests.test_survival_building import World
from backend.tests.test_survival_life_goals import built
from backend.tests.test_survival_trips import flat_ground


def move(world, x, z):
    world.state["position"] = {"x": float(x), "y": 1.0, "z": float(z)}


class HomeLookupTests(unittest.TestCase):
    def test_home_is_found_however_far_mimo_walked(self):
        world = World()
        s = world.situation()
        self.assertEqual((home.home_place(s), home.home_cell(s), home.built_home(s), home.home_structure(s)),
                         (None, None, False, None))
        self.assertIsNone(home.from_home(s, 5, 5))
        remember(world.db, "home", (1, 1, 1), 0.0)  # a sheltered spot it found: home, not built
        move(world, 300, 0)  # past what Situation.places reads around Mimo
        s = world.situation()
        self.assertEqual((home.home_cell(s), home.built_home(s)), ((1, 1, 1), False))
        self.assertEqual(home.from_home(s, 4, 5), 5.0)

    def test_the_shelter_mimo_built_is_home_and_its_structures_are_by_home(self):
        world = built()
        move(world, 300, 0)
        s = world.situation()
        self.assertTrue(home.built_home(s))
        shelter = home.home_structure(s)
        self.assertEqual((shelter["kind"], (shelter["x"], shelter["y"], shelter["z"])), ("shelter", home.home_cell(s)))
        self.assertEqual([found["id"] for found in home.by_home(s, "shelter")], [shelter["id"]])
        self.assertEqual(home.by_home(s, "pen"), [])


class SitesFollowHomeTests(unittest.TestCase):
    def test_sites_are_by_the_home_mimo_built_wherever_it_stands(self):
        world = built()
        anchor = home.home_cell(world.situation())
        move(world, 100, 0)
        self.assertEqual(site_center(world.situation())[::2], anchor[::2])

    def test_with_a_home_of_its_own_mimo_starts_no_second_shelter_far_out(self):
        world = built({"cobblestone": 64})
        move(world, 200, 0)  # a day trip out, carrying enough for a whole hut
        self.assertFalse(shelter_valid(world.situation()))
        self.assertEqual(PURPOSES["build_shelter"].plan(world.situation(), world.context()), [])

    def test_before_it_builds_a_far_found_home_does_not_pull_the_first_shelter_there(self):
        world = World({"cobblestone": 64})
        remember(world.db, "home", (200, 1, 0), 0.0)
        self.assertEqual(site_center(world.situation())[::2], (1, 1))
        set_home(world.db, (200, 1, 0), 0.0)  # (a shelter it built out there)
        self.assertEqual(site_center(world.situation())[::2], (200, 0))


class LeashFollowsHomeTests(unittest.TestCase):
    def test_trips_keep_their_reach_from_home_past_what_mimo_sees_around_it(self):
        flat_ground(self)
        world = built()
        move(world, 300, 0)
        s = world.situation()
        x = s.here[0]
        # heading back toward home is fine, and nothing farther from home than Mimo is now
        cells = [target.cell for target in targets(s, REASONS["wander"])]
        self.assertTrue(cells)
        self.assertTrue(all(cell[0] < x for cell in cells), cells)
        found = candidates(s, (32, 48))
        self.assertTrue(found)
        self.assertTrue(all(candidate.cell[0] < x for candidate in found))


if __name__ == "__main__":
    unittest.main()

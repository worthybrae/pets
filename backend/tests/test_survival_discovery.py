import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal and reason)
from backend.survival.curiosity import curiosity_state
from backend.survival.discovery import FAR_PATCHES, far_walked, pull
from backend.survival.goals import GOALS, adopt_goal, complete, is_open, progress_of
from backend.survival.memory import know, mark_explored, remember
from backend.survival.trips import REASONS
from backend.tests.test_survival_building import World
from backend.tests.test_survival_life_goals import built, one_sinkhole

TAIGA_EAST = lambda x, z, seed: "taiga" if x > 30 else "meadow"  # noqa: E731
DISCOVERY = ("new_land", "new_creature", "cave", "water", "far_hills")


def open_goals(s):
    return [name for name in DISCOVERY if is_open(s, GOALS[name])]


class DiscoveryGoalTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.discovery.biome_at", TAIGA_EAST),
                            ("backend.survival.curiosity.biome_at", TAIGA_EAST),
                            ("backend.survival.life_goals.region_openings", one_sinkhole),
                            ("backend.survival.life_goals.terrain_height", lambda x, z, seed: 3),
                            ("backend.survival.discovery.terrain_height", lambda x, z, seed: 1 if z > 40 else 3)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_they_open_once_mimo_has_a_home_and_repeat_once_reached(self):
        self.assertEqual(open_goals(World().situation()), [])  # no home yet
        world = built()
        know(world.db, "meadow", "biome", 0.0)
        self.assertEqual(open_goals(world.situation()), list(DISCOVERY))
        for name in DISCOVERY:
            know(world.db, name, "goal", 1.0)  # reached once
        self.assertEqual(open_goals(world.situation()), list(DISCOVERY))
        know(world.db, "taiga", "biome", 2.0)  # every land near seen now
        self.assertNotIn("new_land", open_goals(world.situation()))

    def test_their_pull_rises_with_curiosity_and_a_restless_pet_turns_to_them(self):
        world = built()
        for value, score in ((0.0, 30.0), (50.0, 65.0), (80.0, 186.0)):
            curiosity_state(world.state, 0.0)["value"] = value
            self.assertAlmostEqual(pull(world.situation(), "far_hills"), score)  # (with a target: I4)

    def test_they_count_only_what_is_found_after_they_were_set(self):
        world = built()
        know(world.db, "meadow", "biome", 0.0)
        know(world.db, "forest", "biome", 5.0)  # before the goal
        adopt_goal(world.state, "new_land", "utility", "", 10.0)
        self.assertEqual(progress_of(world.situation(), GOALS["new_land"]), 0.0)
        know(world.db, "taiga", "biome", 20.0)
        self.assertTrue(complete(world.situation(), GOALS["new_land"]))
        adopt_goal(world.state, "cave", "utility", "", 30.0)
        remember(world.db, "cave", (40, 4, 0), 25.0, "sinkhole")
        self.assertEqual(progress_of(world.situation(), GOALS["cave"]), 0.0)
        remember(world.db, "water", (0, 2, 60), 31.0)
        adopt_goal(world.state, "water", "utility", "", 30.0)
        self.assertEqual(progress_of(world.situation(), GOALS["water"]), 1.0)

    def test_far_hills_count_new_patches_far_from_home(self):
        world = built()
        adopt_goal(world.state, "far_hills", "utility", "", 10.0)
        mark_explored(world.db, [(rx, 0) for rx in range(8, 20)], 20.0)  # 64 blocks east and on
        mark_explored(world.db, [(1, 1), (2, 2)], 20.0)  # near home: not far
        self.assertEqual(far_walked(world.situation()), 12)
        self.assertEqual(progress_of(world.situation(), GOALS["far_hills"]), 0.5)  # I4: 12 was the whole goal once
        mark_explored(world.db, [(rx, 0) for rx in range(20, 8 + FAR_PATCHES)], 20.0)
        self.assertEqual(far_walked(world.situation()), FAR_PATCHES)
        self.assertTrue(complete(world.situation(), GOALS["far_hills"]))

    def test_each_trip_goes_only_for_its_goal_where_its_find_is_likely(self):
        world = built()
        know(world.db, "meadow", "biome", 0.0)
        s = world.situation()
        self.assertEqual([REASONS[name].wanted(s) for name in DISCOVERY], [None] * 5)
        adopt_goal(world.state, "new_land", "utility", "", 10.0)
        s = world.situation()
        self.assertEqual(REASONS["new_land"].wanted(s), "I want to see land I have never seen")
        self.assertEqual((REASONS["new_land"].value(s, 40, 0), REASONS["new_land"].value(s, 0, 0)),
                         ((1.0, "the taiga, which it has never seen"), (0.0, "")))
        self.assertEqual(REASONS["cave"].value(s, 36, 4), (1.0, "a sinkhole"))
        self.assertEqual(REASONS["water"].value(s, 0, 50), (1.0, "a lake"))
        self.assertEqual(REASONS["far_hills"].value(s, 0, 0), (0.0, ""))  # home ground is not far
        world.state["brain"]["trip"] = {"reason": "new_land", "since": 15.0}
        self.assertIsNone(REASONS["new_land"].look(world.situation(), world.context()))
        know(world.db, "taiga", "biome", 16.0)
        self.assertEqual(REASONS["new_land"].look(world.situation(), world.context()).words, "the taiga")


if __name__ == "__main__":
    unittest.main()

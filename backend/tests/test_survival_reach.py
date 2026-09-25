"""L4a final fix wave, I4: day trips keep finding new land after day 3.

Wander and the discovery goals reached a fixed 90 blocks from home, land a pet had used up by day 3
or 4; far_hills was always valid and a restless pet's +100 pull applied with nothing to do, so it
picked a stuck discovery goal, idled about a day, set it aside and did it again. Now the reach grows
ring by ring as the land is walked, trips head toward land farther out a walk at a time, the
discovery goals are open only while their trip has a target, and each Reason has its own cooldown.
"""

import math
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose, goal and reason)
from backend.survival.curiosity import (
    FAR_OUT, RING, RING_WALKED, WANDER_REACH, curiosity_state, trip_reach, wander_spots,
)
from backend.survival.discovery import GOAL_NAMES, has_target, pull
from backend.survival.goals import GOALS, is_open, offers
from backend.survival.home import FARTHEST_TRIP, home_cell
from backend.survival.memory import PATCH, know, mark_explored, patch_of
from backend.survival.purposes import PURPOSES, home_of
from backend.survival.reflexes import head_home_due
from backend.survival.situation import DUSK
from backend.survival.trips import (
    REASONS, TRIP_PENALTY_SECONDS, WANDER_PENALTY_SECONDS, Reason, cool_down, reach_of, targets,
)
from backend.tests.test_survival_life_goals import built
from backend.tests.test_survival_trips import flat_ground


def patches_within(center, near, far):
    """Every patch whose middle lies more than `near` and at most `far` blocks from `center`."""
    cx, _, cz = center
    low, high = patch_of(math.floor(cx - far), math.floor(cz - far)), patch_of(math.ceil(cx + far), math.ceil(cz + far))
    return [(rx, rz) for rx in range(low[0], high[0] + 1) for rz in range(low[1], high[1] + 1)
            if near < math.hypot(rx * PATCH + PATCH / 2 - cx, rz * PATCH + PATCH / 2 - cz) <= far]


def walk(world, center, near, far, share=1.0):
    """Mark `share` of the patches in the ring as walked (long ago, so none of it is fresh)."""
    ring = patches_within(center, near, far)
    mark_explored(world.db, ring[:math.ceil(share * len(ring))], -1e6)


class ReachTests(unittest.TestCase):
    def setUp(self):
        flat_ground(self)  # (dry: the legacy land within 192 blocks of the origin)
        self.world = built()
        self.home = home_cell(self.world.situation())

    def test_the_reach_grows_a_ring_at_a_time_as_the_land_is_walked(self):
        self.assertEqual(trip_reach(self.world.situation()), WANDER_REACH)
        walk(self.world, self.home, WANDER_REACH - RING, WANDER_REACH, RING_WALKED - 0.1)
        self.assertEqual(trip_reach(self.world.situation()), WANDER_REACH)  # not most of it yet
        walk(self.world, self.home, WANDER_REACH - RING, WANDER_REACH, RING_WALKED + 0.05)
        self.assertEqual(trip_reach(self.world.situation()), WANDER_REACH + RING)
        walk(self.world, self.home, WANDER_REACH, WANDER_REACH + RING)
        self.assertEqual(trip_reach(self.world.situation()), WANDER_REACH + 2 * RING)
        walk(self.world, self.home, 0, FARTHEST_TRIP + PATCH)
        self.assertEqual(trip_reach(self.world.situation()), FARTHEST_TRIP)  # day trips go no farther
        for name in ("wander", *GOAL_NAMES):
            self.assertEqual(reach_of(self.world.situation(), REASONS[name]), FARTHEST_TRIP, name)
        self.assertEqual(reach_of(self.world.situation(), REASONS["iron"]), 60.0)  # the others keep their leash

    def test_once_the_land_near_is_walked_a_wander_heads_out_to_land_it_never_walked(self):
        curiosity_state(self.world.state, 0.0)
        walk(self.world, self.home, 0, WANDER_REACH + RING)  # everything within 120 walked
        s = self.world.situation()
        self.assertEqual(trip_reach(s), WANDER_REACH + 2 * RING)
        spots = wander_spots(s)
        self.assertTrue(spots)
        for x, z, words in spots:  # one walk out toward the ring past 120 blocks
            self.assertLessEqual(math.hypot(x - s.here[0], z - s.here[2]), FAR_OUT + 1)
            self.assertEqual(words, "the way to land it never walked")
        self.assertTrue(targets(s, REASONS["wander"]))

    def test_the_discovery_goals_are_open_only_while_their_trip_has_a_target(self):
        know(self.world.db, "meadow", "biome", 0.0)
        s = self.world.situation()
        self.assertTrue(is_open(s, GOALS["far_hills"]))
        self.assertTrue(has_target(s, "far_hills"))
        walk(self.world, self.home, 0, FARTHEST_TRIP + PATCH)  # every patch it could reach is walked
        s = self.world.situation()
        self.assertFalse(has_target(s, "far_hills"))
        self.assertFalse(is_open(s, GOALS["far_hills"]))  # nothing to find: not a goal to pick

    def test_a_restless_pet_is_pulled_only_toward_a_goal_it_can_work_on_now(self):
        curiosity_state(self.world.state, 0.0)["value"] = 90.0
        s = self.world.situation()
        self.assertAlmostEqual(pull(s, "far_hills"), 30.0 + 0.7 * 90.0 + 100.0)
        walk(self.world, self.home, 0, FARTHEST_TRIP + PATCH)
        s = self.world.situation()
        self.assertAlmostEqual(pull(s, "far_hills"), 30.0 + 0.7 * 90.0)
        self.assertNotIn("far_hills", [goal.name for goal, _, _ in offers(s)])


class GoingHomeFromFarOutTests(unittest.TestCase):
    """A day trip can end up to FARTHEST_TRIP blocks from home now, so going home at dusk looks that
    far for the home Mimo built; running from a creature does not run that far home."""

    def test_go_home_and_head_home_reach_a_built_home_from_a_day_trip_out(self):
        world = built()
        anchor = home_cell(world.situation())
        world.state["position"] = {"x": anchor[0] + 200.0, "y": 1.0, "z": float(anchor[2])}
        dusk = {"phase": "day", "seconds_into_day": DUSK - 100.0, "time_scale": 1.0, "day_number": 1}
        s = world.situation(dusk)
        self.assertTrue(PURPOSES["go_home"].valid(s))
        self.assertEqual(PURPOSES["go_home"].plan(s, world.context())[0]["target"], list(anchor))
        self.assertTrue(head_home_due(s))
        self.assertIsNone(home_of(s))  # but not a refuge to flee to (creatures.defense) or swim for from out there


class CooldownTests(unittest.TestCase):
    def test_each_reason_has_a_cooldown_of_its_own(self):
        self.assertEqual(REASONS["wander"].cooldown, WANDER_PENALTY_SECONDS)
        self.assertEqual(REASONS["iron"].cooldown, TRIP_PENALTY_SECONDS)
        own = Reason("slow", "look", lambda s: "", lambda s, x, z: (0.0, ""), lambda s: 1.0, cooldown=900.0)
        mind = {}
        with patch.dict(REASONS, {"slow": own}):
            for name, seconds in (("slow", 900.0), ("wander", WANDER_PENALTY_SECONDS), ("iron", TRIP_PENALTY_SECONDS),
                                  ("gone", TRIP_PENALTY_SECONDS)):
                cool_down(mind, name, 10.0, 2.0)
                self.assertEqual(mind["trip_penalties"][name], 10.0 + seconds / 2.0, name)


if __name__ == "__main__":
    unittest.main()

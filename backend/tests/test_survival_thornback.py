import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers the thornback, its spawner and the ringed hooks)
from backend.survival.creatures.archery import finish_shoot
from backend.survival.creatures.combat import finish_attack
from backend.survival.creatures.defense import fight_target, flee_due, plan_fight
from backend.survival.creatures.hostiles import sunlit
from backend.survival.creatures.kinds import KINDS, huntable
from backend.survival.creatures.thornback import MOST_NEAR, SPAWN_EVERY, spawn_thornbacks
from backend.survival.journal import LESSONS
from backend.survival.lessons import claims
from backend.tests.test_survival_darkness import DAY, land, scene
from backend.tests.test_survival_defense import meadow, pet as defended, situation
from backend.tests.test_survival_ringed import far_out

THORNBACK = KINDS["thornback"]


class KindTests(unittest.TestCase):
    def test_a_slow_armoured_hostile_that_walks_by_day(self):
        self.assertTrue(THORNBACK.hostile and THORNBACK.daylight)
        self.assertEqual((THORNBACK.health, THORNBACK.speed, THORNBACK.damage, THORNBACK.shell), (24.0, 1.2, 4.0, 0.6))
        self.assertFalse(huntable(THORNBACK))

    def test_the_sun_neither_burns_nor_fades_it(self):
        grid = land()
        creature = grid.herd.add("thornback", (5, 1, 0), 24.0, 0.0, 0.0, {"home": [5, 1, 0]})
        gloomling = grid.herd.add("gloomling", (6, 1, 0), 20.0, 0.0, 0.0, {"home": [6, 1, 0]})
        by_day = scene(grid, far_out(), clock=DAY)
        with patch("backend.survival.light.terrain_height", lambda x, z, seed: 0):
            self.assertFalse(sunlit(creature, THORNBACK, by_day))
            self.assertTrue(sunlit(gloomling, KINDS["gloomling"], by_day))


class ShellTests(unittest.TestCase):
    def test_a_sword_blow_loses_most_of_its_bite_but_an_arrow_gets_through(self):
        grid = meadow()
        target = grid.herd.add("thornback", (1, 1, 0), 24.0, 0.0, 0.0, {"home": [1, 1, 0]})
        state = defended(inventory={"stone_sword": 1, "bow": 1, "arrow": 2})
        finish_attack({"kind": "attack", "creature": target["id"], "weapon": "stone_sword"}, state, grid, 1.0, [])
        self.assertEqual(grid.herd.get(target["id"])["health"], 22.0)  # 5, less 60 %
        finish_shoot({"kind": "shoot", "creature": target["id"], "hit": True}, state, grid, 2.0, [])
        self.assertEqual(grid.herd.get(target["id"])["health"], 17.0)  # an arrow's full 5


class MeetingTests(unittest.TestCase):
    def test_with_only_a_sword_mimo_runs_from_a_thornback_close_by(self):
        grid = meadow()
        grid.herd.add("thornback", (4, 1, 0), 24.0, 0.0, 0.0, {"home": [4, 1, 0], "chasing": True})
        sworded = situation(grid, defended(inventory={"iron_sword": 1}))
        self.assertIsNone(fight_target(sworded))
        self.assertTrue(flee_due(sworded))

    def test_with_a_bow_mimo_shoots_it_even_in_sword_reach(self):
        grid = meadow()
        grid.herd.add("thornback", (2, 1, 0), 24.0, 0.0, 0.0, {"home": [2, 1, 0], "chasing": True})
        s = situation(grid, defended(inventory={"iron_sword": 1, "bow": 1, "arrow": 8}))
        self.assertFalse(flee_due(s))
        self.assertEqual(fight_target(s)["kind"], "thornback")
        self.assertEqual([step["kind"] for step in plan_fight(s, None)], ["shoot"])


class SpawnTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.creatures.darkness.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)

    def chances(self, state, grid, calls=30):
        found = []
        for call in range(calls):
            found += spawn_thornbacks(scene(grid, state, at=100.0 + call * SPAWN_EVERY, clock=DAY))
        return found

    def test_none_come_out_nearer_home_than_the_far_wilds(self):
        self.assertEqual(self.chances(far_out(100.0), land()), [])

    def test_in_the_far_wilds_they_come_out_by_day_on_open_ground_and_tougher(self):
        grid = land()
        found = self.chances(far_out(150.0), grid)
        self.assertEqual(len(found), MOST_NEAR)  # no more than two near Mimo
        for creature in found:
            self.assertEqual(creature["kind"], "thornback")
            self.assertTrue(20 <= abs(complex(creature["x"] - 150.0, creature["z"])) <= 41)
            self.assertEqual((creature["y"], creature["health"], creature["state"]["ring"]), (1.0, 40.8, 2))


class LessonTests(unittest.TestCase):
    def test_the_owner_can_teach_what_a_thornback_is_like(self):
        # Pre-flight (carry 6): Mind's habits lesson says what a thornback is, so true words teach it.
        self.assertIn("arrows hurt them", LESSONS["thornback:habits"].fact)
        for line in ("thornbacks fear arrows", "arrows hurt thornbacks", "thornbacks walk by day",
                     "swords bounce off thornbacks"):
            self.assertIn("thornback:habits", claims(line).taught, line)
        self.assertIn("thornback:drops", claims("thornbacks drop flint").taught)
        self.assertTrue(claims("thornbacks drop diamonds").doubtful)


if __name__ == "__main__":
    unittest.main()

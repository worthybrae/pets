import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.tick import advance_world, surroundings_at, tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0


class SurvivalTickTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def change(self, **vitals):
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"].update(vitals)
            write_state(db, state)

    def kinds(self):
        return [event["kind"] for event in self.world.events(50)]

    def test_a_tick_drains_hunger_and_saves_the_time(self):
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertAlmostEqual(state["vitals"]["hunger"], 100 - 0.84)
        self.assertEqual(state["last_tick_at"], BORN + 60)
        self.assertEqual(self.world.state()["status"], "idle")

    def test_time_scale_speeds_up_every_rate(self):
        state = tick_life(self.registry, BORN + 60, scale=60)
        self.assertAlmostEqual(state["vitals"]["hunger"], 100 - 0.014 * 3600)
        self.assertIn("sleep", self.kinds())

    def test_the_pet_sleeps_at_night_and_wakes_rested_after_dawn(self):
        self.assertEqual(tick_life(self.registry, BORN + 2450, scale=1)["status"], "sleeping")
        self.assertEqual(tick_life(self.registry, BORN + 3700, scale=1)["status"], "idle")
        self.assertEqual(self.kinds()[:2], ["wake", "sleep"])

    def test_an_exhausted_pet_sleeps_by_day_until_rested(self):
        self.change(energy=5.0)
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertEqual(state["status"], "sleeping")
        self.assertAlmostEqual(state["vitals"]["energy"], 17.0)
        self.assertEqual(tick_life(self.registry, BORN + 600, scale=1)["status"], "idle")

    def test_a_long_gap_is_caught_up_and_an_unfed_pet_starves(self):
        state = tick_life(self.registry, BORN + 20_000, scale=1)
        self.assertEqual((state["status"], state["cause"]), ("dead", "starvation"))
        self.assertTrue(BORN + 10_100 <= state["died_at"] <= BORN + 10_300, state["died_at"] - BORN)
        self.assertEqual(state["last_tick_at"], state["died_at"])
        life = self.registry.get(self.life["id"])
        self.assertEqual((life["died_at"], life["cause"]), (state["died_at"], "starvation"))
        self.assertIsNone(self.registry.active_life())
        self.assertIsNone(tick_life(self.registry, BORN + 30_000, scale=1))
        self.assertIn(f"{self.life['name']} died of starvation on day 3.", self.world.events()[0]["text"])
        self.assertIn("hungry", self.kinds())
        self.assertIn("starving", self.kinds())

    def test_a_dead_world_is_never_advanced_again(self):
        dead = tick_life(self.registry, BORN + 20_000, scale=1)
        again = advance_world(self.world, BORN + 40_000, 1)
        self.assertEqual(again, dead)

    def test_cold_can_kill_and_archives_the_life(self):
        self.change(health=1.0, warmth=0.0)
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertEqual(state["cause"], "cold")
        self.assertEqual(self.registry.get(self.life["id"])["cause"], "cold")

    def test_a_pet_with_its_head_in_water_drowns(self):
        position = self.world.state()["position"]
        self.world.put_block(round(position["x"]), round(position["y"]), round(position["z"]), "water")
        self.change(air=0.0, health=1.0)
        self.assertEqual(tick_life(self.registry, BORN + 60, scale=1)["cause"], "drowning")

    def test_hunger_crossing_thirty_is_logged_with_a_thought(self):
        self.change(hunger=30.5)
        state = tick_life(self.registry, BORN + 60, scale=1)
        self.assertEqual(state["last_thought"], "My tummy is rumbling. I need food.")
        self.assertEqual(self.kinds()[0], "hungry")

    def test_surroundings_see_shelter_fire_and_water(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["position"]["y"] = 100.0
            write_state(db, state)
        position = self.world.state()["position"]
        x, z = round(position["x"]), round(position["z"])
        with self.world.connect() as db:
            open_air = surroundings_at(db, self.world.seed, position)
        self.assertFalse(open_air.sheltered or open_air.near_fire or open_air.head_in_water)
        for cell in ((x, 102, z), (x + 2, 100, z), (x - 2, 100, z), (x, 100, z + 2)):
            self.world.put_block(*cell, "planks")
        self.world.put_block(x + 3, 100, z - 3, "furnace")
        with self.world.connect() as db:
            hut = surroundings_at(db, self.world.seed, position)
        self.assertTrue(hut.sheltered)
        self.assertTrue(hut.near_fire)


if __name__ == "__main__":
    unittest.main()

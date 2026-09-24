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

    def test_a_stopping_worker_stops_between_committed_catch_up_steps(self):
        """Fix wave minor 1: `should_stop` is asked after each committed step of a long catch-up,
        so a worker told to stop does not first run the rest of the gap."""
        asked, between = [], []

        def should_stop():
            asked.append(True)
            return len(asked) >= 2

        state = tick_life(self.registry, BORN + 600, scale=1, between=between.append, should_stop=should_stop)
        self.assertEqual(state["last_tick_at"], BORN + 120)
        self.assertEqual(self.world.state()["last_tick_at"], BORN + 120)  # both steps were committed
        self.assertEqual(between, [BORN + 60])  # no rules choice once stopping
        self.assertIsNotNone(self.registry.active_life())
        self.assertEqual(tick_life(self.registry, BORN + 600, scale=1)["last_tick_at"], BORN + 600)

    def test_a_catch_up_that_crashed_between_steps_resumes_without_applying_anything_twice(self):
        """Fix wave fold-in: every catch-up step is its own transaction, so a crash between steps
        keeps the steps already committed, and the next tick picks up from there. The result is
        the same as one uninterrupted catch-up: no step's vitals or events are applied twice."""
        root = Path(self.directory.name)
        other = LifeRegistry(root / "other", root / "no-legacy.sqlite3")
        hatch(other, random.Random(8), timestamp=BORN)
        whole = tick_life(other, BORN + 120, scale=60)

        calls = []

        def crash(at):
            calls.append(at)
            if len(calls) == 50:
                raise RuntimeError("the worker died here")

        with self.assertRaises(RuntimeError):
            tick_life(self.registry, BORN + 120, scale=60, between=crash)
        self.assertEqual(self.world.state()["last_tick_at"], BORN + 50)  # 50 steps of 1 real second
        resumed = tick_life(self.registry, BORN + 120, scale=60)
        for key in ("vitals", "last_tick_at", "status", "position", "inventory"):
            self.assertEqual(resumed[key], whole[key], key)
        timeline = [(event["at"], event["kind"], event["text"]) for event in self.world.events(500)]
        other_world = SurvivalWorld(other.world_path(other.active_life()))
        self.assertEqual(timeline, [(event["at"], event["kind"], event["text"]) for event in other_world.events(500)])
        self.assertIn("sleep", [kind for _, kind, _ in timeline])

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

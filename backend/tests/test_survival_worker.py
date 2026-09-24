import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival.choosing import Chooser, InlineExecutor, decide
from backend.survival.hatch import hatch
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, WorldMissing
from backend.workers.mimo_worker import WORKER_MIND, run_once, should_log_data_error, tick_seconds


class SurvivalWorkerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")

    def tearDown(self):
        self.directory.cleanup()

    def test_without_a_pet_the_worker_waits_and_logs_once(self):
        with self.assertLogs("mimo_worker", level="INFO") as logs:
            line = run_once(self.registry, None)
            self.assertEqual(run_once(self.registry, line), line)
        self.assertEqual(logs.output, ["INFO:mimo_worker:No pet is alive. Waiting for the egg to hatch."])

    def test_the_worker_ticks_the_active_life(self):
        life = hatch(self.registry, random.Random(8), timestamp=1000.0)
        with patch.dict(os.environ, {"MIMO_TIME_SCALE": "1"}):
            line = run_once(self.registry, None, timestamp=1060.0)
            self.assertEqual(line, f"{life['name']} is idle: Everything is new. I wonder what is out there.")
            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):  # L2: it starves
                died = run_once(self.registry, line, timestamp=1000.0 + 20_000)
        self.assertEqual(died, f"{life['name']} died of starvation.")
        self.assertIsNone(self.registry.active_life())

    def test_after_a_long_outage_mimo_kept_choosing_and_eating_on_the_rules(self):
        life = hatch(self.registry, random.Random(8), timestamp=1000.0)
        asked = []
        chooser = Chooser(env={"TYPESAFE_API_KEY": "k"}, http=lambda *args: asked.append(args) or {},
                          executor=InlineExecutor(), rng=random.Random(8), scale=60.0)
        # Fix round 1: `asked` only sees calls made through chooser's own http lambda. The
        # between-steps rules chooser (run_once's `rules`, built with env={}) is never given that
        # lambda, so a regression like passing it chooser.env instead of {} would route it to Jev
        # and call the module's real, network-hitting post_json by default -- invisible to `asked`.
        # Spy on decide() itself (looked up fresh on every call, unlike a bound default argument)
        # and require every call not using chooser's own http to have kept an empty, rules-only env.
        stray_envs = []

        def spy(ask, env, http, rng):
            if http is not chooser.http and env:
                stray_envs.append(env)
            return decide(ask, env, http, rng)

        with patch("backend.survival.choosing.decide", side_effect=spy):
            with patch.dict(os.environ, {"MIMO_TIME_SCALE": "60", "MIMO_ACTION_SCALE": "60"}):
                line = run_once(self.registry, None, timestamp=1000.0 + 2 * 60, mind=WORKER_MIND, chooser=chooser)
        self.assertIn(life["name"], line)
        events = SurvivalWorld(self.registry.world_path(life)).events(5000)
        kinds = [event["kind"] for event in events]
        self.assertGreater(kinds.count("purpose"), 5)
        self.assertIn("ate", kinds)
        self.assertLessEqual(len(asked), 1)  # at most the last ask goes to Jev; the catch-up ran on rules
        self.assertEqual(stray_envs, [])  # the rules chooser never picked up the main chooser's env

    def test_a_stop_signal_ends_a_long_catch_up_after_the_step_it_is_on(self):
        """Fix wave minor 1: run_once passes the stop flag down, so SIGTERM during a long catch-up
        stops after the step in progress (committed) instead of running the rest of the gap."""
        life = hatch(self.registry, random.Random(8), timestamp=1000.0)
        chooser = Chooser(env={}, http=lambda *args, **kwargs: {}, executor=InlineExecutor(),
                          rng=random.Random(1), scale=1.0)
        with patch.dict(os.environ, {"MIMO_TIME_SCALE": "1"}):
            with patch.object(chooser, "poll") as poll:
                run_once(self.registry, None, timestamp=1000.0 + 600, chooser=chooser, should_stop=lambda: True)
        self.assertEqual(SurvivalWorld(self.registry.world_path(life)).state()["last_tick_at"], 1060.0)
        poll.assert_not_called()  # nothing is chosen for a moment the world has not reached

    def test_tick_seconds_defaults_to_one(self):
        with patch.dict(os.environ, {"MIMO_TICK_SECONDS": "0.5"}):
            self.assertEqual(tick_seconds(), 0.5)
        for bad in ("0", "soon"):
            with patch.dict(os.environ, {"MIMO_TICK_SECONDS": bad}):
                self.assertEqual(tick_seconds(), 1.0)
        with patch.dict(os.environ, {}):
            os.environ.pop("MIMO_TICK_SECONDS", None)
            self.assertEqual(tick_seconds(), 1.0)

    def test_tick_seconds_rejects_non_finite_values(self):
        for bad in ("inf", "-inf", "nan", "Infinity"):
            with patch.dict(os.environ, {"MIMO_TICK_SECONDS": bad}):
                self.assertEqual(tick_seconds(), 1.0)

    def test_a_crashing_chooser_is_logged_once_and_the_status_line_still_builds(self):
        forget_logged()
        life = hatch(self.registry, random.Random(8), timestamp=1000.0)
        chooser = Chooser(env={}, http=lambda *args, **kwargs: {}, executor=InlineExecutor(),
                          rng=random.Random(1), scale=1.0)
        with patch("backend.survival.choosing.prepare", side_effect=RuntimeError("boom")):
            with self.assertLogs("mimo_worker", level="ERROR") as logs:
                with patch.dict(os.environ, {"MIMO_TIME_SCALE": "1"}):
                    line = run_once(self.registry, None, timestamp=1060.0, chooser=chooser)
                    line = run_once(self.registry, line, timestamp=1061.0, chooser=chooser)
        self.assertEqual(len(logs.records), 1)
        self.assertIn(life["name"], line)

    def test_a_data_error_is_logged_once_per_distinct_message(self):
        first = WorldMissing("world 2 is missing")
        log_it, last = should_log_data_error(first, None)
        self.assertTrue(log_it)
        log_it, last = should_log_data_error(WorldMissing("world 2 is missing"), last)
        self.assertFalse(log_it)
        log_it, last = should_log_data_error(WorldMissing("world 3 is missing"), last)
        self.assertTrue(log_it)


if __name__ == "__main__":
    unittest.main()

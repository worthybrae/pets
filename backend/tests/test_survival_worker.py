import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.world import WorldMissing
from backend.workers.mimo_worker import run_once, should_log_data_error, tick_seconds


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
            died = run_once(self.registry, line, timestamp=1000.0 + 20_000)
        self.assertEqual(died, f"{life['name']} died of starvation.")
        self.assertIsNone(self.registry.active_life())

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

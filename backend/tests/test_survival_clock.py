import os
import unittest
from unittest.mock import patch

from backend.survival.clock import DAY_SECONDS, action_scale, clock_at, is_night, phase_at, time_scale


class ClockTests(unittest.TestCase):
    def test_a_life_starts_at_dawn_on_day_one(self):
        clock = clock_at(1000.0, 1000.0)
        self.assertEqual(clock["day_number"], 1)
        self.assertEqual(clock["phase"], "dawn")
        self.assertEqual(clock["time_of_day"], 0.0)
        self.assertEqual(clock["day_seconds"], 3600.0)

    def test_phase_boundaries_follow_the_spec(self):
        expected = [(0, "dawn"), (179.9, "dawn"), (180, "day"), (2219.9, "day"), (2220, "dusk"),
                    (2399.9, "dusk"), (2400, "night"), (3419.9, "night"), (3420, "pre_dawn"),
                    (3599.9, "pre_dawn"), (3600, "dawn")]
        for seconds, phase in expected:
            self.assertEqual(phase_at(seconds), phase, seconds)

    def test_night_lasts_twenty_minutes_including_pre_dawn(self):
        dark = sum(1 for second in range(int(DAY_SECONDS)) if is_night(phase_at(second)))
        self.assertEqual(dark, 1200)
        self.assertFalse(is_night("dusk"))

    def test_day_number_and_time_of_day_advance_with_real_time(self):
        self.assertEqual(clock_at(0, 3600)["day_number"], 2)
        later = clock_at(0, 2 * 3600 + 2700)
        self.assertEqual(later["day_number"], 3)
        self.assertEqual(later["phase"], "night")
        self.assertAlmostEqual(later["time_of_day"], 0.75)

    def test_time_scale_multiplies_game_time(self):
        self.assertEqual(clock_at(0, 40, scale=60)["phase"], "night")
        fast = clock_at(0, 61, scale=60)
        self.assertEqual(fast["day_number"], 2)
        self.assertAlmostEqual(fast["seconds_into_day"], 60)
        self.assertEqual(fast["time_scale"], 60)

    def test_times_before_birth_count_as_the_first_dawn(self):
        early = clock_at(500, 100)
        self.assertEqual(early["day_number"], 1)
        self.assertEqual(early["seconds_into_day"], 0)

    def test_time_scale_reads_the_environment(self):
        with patch.dict(os.environ, {"MIMO_TIME_SCALE": "60"}):
            self.assertEqual(time_scale(), 60.0)
        for bad in ("0", "-3", "fast", "inf", "nan"):
            with patch.dict(os.environ, {"MIMO_TIME_SCALE": bad}):
                self.assertEqual(time_scale(), 1.0, bad)
        with patch.dict(os.environ, {}):
            os.environ.pop("MIMO_TIME_SCALE", None)
            self.assertEqual(time_scale(), 1.0)


class ActionScaleTests(unittest.TestCase):
    def test_reads_mimo_action_scale_and_defaults_to_one(self):
        with patch.dict(os.environ, {"MIMO_ACTION_SCALE": "60"}):
            self.assertEqual(action_scale(), 60.0)
        for bad in ("0", "-2", "fast", "inf", "nan"):
            with patch.dict(os.environ, {"MIMO_ACTION_SCALE": bad}):
                self.assertEqual(action_scale(), 1.0, bad)
        with patch.dict(os.environ, {}):
            os.environ.pop("MIMO_ACTION_SCALE", None)
            self.assertEqual(action_scale(), 1.0)


if __name__ == "__main__":
    unittest.main()

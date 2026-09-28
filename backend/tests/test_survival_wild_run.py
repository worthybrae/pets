"""W1's headless lives (the gate's harness, backend/scripts/wild_gate.py, for a few short lives).

By default seed 8 for 3 game days, untaught and taught: the untaught pet posts at least 3 questions, the taught
one knows all 11 W1 lessons by the end of day 1, and both live. With MIMO_SLOW_TESTS=1, seeds 3 and 11 for 20
game days: the untaught pet's sick minutes are at least twice the taught pet's, both are alive on day 5, and the
taught one on day 20. No model is ever called and nothing is logged as an error. The W1 criteria that compare
the conditions (6', 7', 10') are checked on made-up summaries.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.scripts.wild_gate import CONDITIONS, SEEDS, check_w1, live
from backend.tests.no_model import no_model


def summary(condition, seed, **changes):
    """A made-up life's summary, as `live` writes it: a quiet 150-day life unless changed."""
    found = {"seed": seed, "condition": condition, "died_day": None, "health_mean": 99.0, "near_death_days": [],
             "sick_minutes": 0, "sick_by_day": [0] * 150, "lost_by_day": [0.0] * 150,
             "machines": {"lamp_lever": 50.0}, "lessons": {}, "wonders_met": {}, "questions": [], "open_most": 0,
             "ever": {"sick": False, "wound": False, "lots": False, "question": False}, "model_calls": 0, "errors": []}
    found.update(changes)
    return found


def untaught(seed, **changes):
    """An untaught life that is sick 40 game minutes and loses 110 health in its first month, 150 minutes in all,
    and meets 5 wonders and asks 3 questions in its first 3 days."""
    found = summary("untaught", seed, sick_minutes=150, sick_by_day=[40] * 30 + [150] * 120,
                    lost_by_day=[110.0] * 30 + [300.0] * 120, near_death_days=[12],
                    wonders_met={name: 1.5 for name in ("a", "b", "c", "d", "e")},
                    questions=[[1.5, "a"], [2.0, "b"], [3.5, "c"]], open_most=3)
    found.update(changes)
    return found


class WildRunTests(unittest.TestCase):
    def life(self, seed, days, condition):
        found = live(seed, days, condition, http=no_model(self))
        self.assertEqual(found["errors"], [])
        return found

    def test_an_untaught_pet_asks_and_a_taught_one_knows_every_lesson_on_day_one(self):
        untaught = self.life(8, 3, "untaught")
        taught = self.life(8, 3, "taught")
        self.assertIsNone(untaught["died_day"])
        self.assertIsNone(taught["died_day"])
        self.assertGreaterEqual(len(untaught["questions"]), 3)
        self.assertLessEqual(untaught["open_most"], 3)
        self.assertEqual(len(taught["lessons"]), 11)
        self.assertTrue(all(entry["day"] < 2 for entry in taught["lessons"].values()), taught["lessons"])

    @unittest.skipUnless(os.environ.get("MIMO_SLOW_TESTS"), "a slow run: set MIMO_SLOW_TESTS=1")
    def test_twenty_days_untaught_is_sicker_and_taught_lives(self):
        for seed in (3, 11):
            untaught = self.life(seed, 20, "untaught")
            taught = self.life(seed, 20, "taught")
            self.assertGreaterEqual(untaught["sick_minutes"], 2 * taught["sick_minutes"], seed)
            for found in (untaught, taught):
                self.assertTrue(found["died_day"] is None or found["died_day"] > 5, (seed, found["condition"]))
            self.assertIsNone(taught["died_day"], seed)


class CheckTests(unittest.TestCase):
    def rows(self, **untaught_changes):
        """The W1 check on six lives of each condition; `untaught_changes` changes the untaught life of seed 3."""
        with tempfile.TemporaryDirectory() as root:
            for condition in CONDITIONS:
                for seed in SEEDS:
                    if condition == "untaught":
                        life = untaught(seed, **(untaught_changes if seed == 3 else {}))
                    else:
                        life = summary(condition, seed, sick_minutes=10, sick_by_day=[5] * 30 + [10] * 120,
                                       lost_by_day=[20.0] * 150)
                    (Path(root) / f"{condition}_{seed}.json").write_text(json.dumps(life))
            return {name.split(" ")[0]: passed for name, passed, _ in check_w1(Path(root))}

    def test_a_newborns_first_month_a_life_without_the_owner_and_four_wonders(self):
        rows = self.rows()
        self.assertEqual((rows["6'"], rows["7'"], rows["10'"]), (True, True, True))
        # 6': 100 health a life lost to hazards in the first month, at least (550 over six lives is too few)
        self.assertFalse(self.rows(lost_by_day=[0.0] * 150)["6'"])
        # 7': deaths and near-death days together 6 at least (six near-death days above; one fewer here)
        self.assertFalse(self.rows(near_death_days=[])["7'"])
        self.assertTrue(self.rows(near_death_days=[], died_day=80.5)["7'"])
        # 10': 4 wonders met by the end of the third game day, on every seed
        self.assertTrue(self.rows(wonders_met={name: 3.9 for name in "abcd"})["10'"])
        self.assertFalse(self.rows(wonders_met={name: 3.9 for name in "abc"})["10'"])


if __name__ == "__main__":
    unittest.main()

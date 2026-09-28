"""W1's headless lives (the gate's harness, backend/scripts/wild_gate.py, for a few short lives).

By default seed 8 for 3 game days, untaught and taught: the untaught pet posts at least 3 questions, the taught
one knows all 11 W1 lessons by the end of day 1, and both live. With MIMO_SLOW_TESTS=1, seeds 3 and 11 for 20
game days: the untaught pet's sick minutes are at least twice the taught pet's, both are alive on day 5, and the
taught one on day 20. No model is ever called and nothing is logged as an error. The W1 criteria that compare
the conditions (6', 7', 10') and the robustness check W1R (8R) are checked on made-up summaries.
"""

import json
import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.scripts.wild_gate import (
    BORN, CONDITIONS, R_DAYS, R_SEEDS, SEEDS, check_w1, check_w1r, live, new_record, sample, summarize,
)
from backend.survival.hatch import hatch
from backend.survival.knocks import OWNER_ONLY
from backend.survival.registry import LifeRegistry
from backend.survival.wild import SURVIVAL
from backend.survival.world import SurvivalWorld
from backend.tests.no_model import no_model

W1_ALONE = [lesson.name for lesson in SURVIVAL[:11] if lesson.name not in OWNER_ONLY]  # controller note: 9 names


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
    meets 5 wonders and asks 3 questions in its first 3 days, and works 8 lessons out alone by day 40."""
    found = summary("untaught", seed, sick_minutes=150, sick_by_day=[40] * 30 + [150] * 120,
                    lost_by_day=[110.0] * 30 + [300.0] * 120, near_death_days=[12],
                    wonders_met={name: 1.5 for name in ("a", "b", "c", "d", "e")},
                    questions=[[1.5, "a"], [2.0, "b"], [3.5, "c"]], open_most=3,
                    lessons={name: {"day": 40.0, "source": "figured"} for name in W1_ALONE[:8]})
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
        w1 = [lesson.name for lesson in SURVIVAL[:11]]
        self.assertTrue(all(taught["lessons"][name]["day"] < 2 for name in w1), taught["lessons"])
        self.assertEqual(len(taught["lessons"]), len(SURVIVAL))  # W2's seven on day 2
        self.assertTrue(all(entry["day"] < 3 for entry in taught["lessons"].values()), taught["lessons"])

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

    def test_nine_counts_seven_of_the_nine_lessons_a_pet_can_learn_alone(self):
        def alone(count):
            return {name: {"day": 40.0, "source": "figured"} for name in W1_ALONE[:count]}
        self.assertTrue(self.rows(lessons=alone(7))["9"])
        self.assertFalse(self.rows(lessons=alone(6))["9"])
        # learned after day 60, or from the owner, does not count
        late = {**alone(6), W1_ALONE[6]: {"day": 61.0, "source": "figured"}}
        self.assertFalse(self.rows(lessons=late)["9"])

    def test_controller_note_w2_lessons_do_not_dilute_the_nine(self):
        """Controller note (the W2 interim report): since W2 Task 9, W2's seven lessons can be figured alone too, but
        criterion 9 still counts only the 9 W1 lessons that can be learned alone (W1_ALONE)."""
        w2 = [lesson.name for lesson in SURVIVAL[11:]]

        def figured(names):
            return {name: {"day": 40.0, "source": "figured"} for name in names}
        self.assertFalse(self.rows(lessons=figured(W1_ALONE[:6]) | figured(w2[:3]))["9"])  # 6 W1 + 3 W2: still fails
        self.assertTrue(self.rows(lessons=figured(W1_ALONE[:7]))["9"])  # 7 W1 alone: passes

    def test_ten_prime_reads_the_questions_as_they_were_posted_not_the_inbox_at_the_end(self):
        # Fix B: by day 150 the inbox has pruned the early questions (a life read (8 wonders, 0 asked) that had asked
        # 3 in its first days), so the gate keeps a record as the life runs.
        wonders = {name: {"met_at": BORN + 60 * (0.5 + index * 0.5)} for index, name in enumerate("abcd")}  # days 1.5 to 3
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN,
                                                            difficulty="wild")))
            with world.connect() as db:
                for index, name in enumerate("abc"):
                    db.execute("INSERT INTO mimo_inbox(at, kind, text, data) VALUES (?, 'ask', ?, ?)",
                               (BORN + 60 * (0.5 + index), f"About {name}?", json.dumps({"ask": "wonder", "wonder": name,
                                                                                          "closed": "taught"})))
            state = world.state()
            state.setdefault("wild", {})["wonders"] = wonders
            found = new_record()
            sample(found, state, 3 * 60, world)  # the end of the third game day
            with world.connect() as db:
                db.execute("DELETE FROM mimo_inbox")  # pruned by the end of the life
            life = summarize(world, found, 3, 150, "untaught", 0.0)  # the stored state never had the wonders
        self.assertEqual((len(life["wonders_met"]), len(life["questions"])), (4, 3))
        rows = self.rows(wonders_met=life["wonders_met"], questions=life["questions"], open_most=life["open_most"])
        self.assertTrue(rows["10'"])
        self.assertFalse(self.rows(wonders_met={}, questions=[])["10'"])  # what the inbox at the end would say

    def test_robustness_no_newborn_dies_before_day_five_and_at_most_four_of_twelve_by_day_thirty(self):
        def passed(died, days=R_DAYS, seeds=R_SEEDS):
            """Check W1R on untaught lives of `seeds`, each run `days`; `died` maps a seed to its death day."""
            with tempfile.TemporaryDirectory() as root:
                for seed in seeds:
                    life = untaught(seed, days=days, died_day=died.get(seed))
                    (Path(root) / f"untaught_{seed}.json").write_text(json.dumps(life))
                return [passed for _, passed, _ in check_w1r(Path(root))]

        self.assertEqual(passed({1: 5.5, 2: 12.0, 4: 29.9, 6: 30.8}), [True, True])
        self.assertEqual(passed({1: 4.9}), [False, True])  # a newborn dead before day 5
        self.assertEqual(passed({1: 5.5, 2: 12.0, 4: 29.9, 6: 30.8, 7: 18.0}), [True, False])  # 5 of 12 dead
        self.assertEqual(passed({}, seeds=R_SEEDS[:-1]), [False, False])  # a seed missing
        self.assertEqual(passed({}, days=20), [False, False])  # lives run short


if __name__ == "__main__":
    unittest.main()

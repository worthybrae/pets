import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every creature, recipe and goal registered, for the tags)
from backend.survival import minding  # noqa: F401  (the mirror, the moments and consolidation registered)
from backend.survival.clock import DAY_SECONDS
from backend.survival.consolidation import NIGHTLY, gist_text
from backend.survival.hatch import hatch
from backend.survival.mind import TEXT_LIMIT
from backend.survival.once import forget_logged
from backend.survival.owner_facts import remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.world import SurvivalWorld, log_event

BORN = 1_000_000.0
EVENING = 2500.0  # game seconds into a day: night, when Mimo goes to sleep
NOON = 1200.0


def at(day, seconds):
    return BORN + (day - 1) * DAY_SECONDS + seconds


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]

    def tearDown(self):
        self.directory.cleanup()

    def log(self, *events):
        with self.world.transaction() as db:
            for when, kind, text in events:
                log_event(db, when, kind, text)
        for _ in range(5):
            run_chores(self.world, events[-1][0] + 1, 1.0)

    def rows(self, where="1=1"):
        with self.world.connect() as db:
            return [dict(row) for row in db.execute(
                f"SELECT game_day, kind, text, importance, source, count FROM mind_memories WHERE {where} ORDER BY id")]

    def a_busy_day(self, day, sleep_at=EVENING):
        name = self.name
        self.log((at(day, 100), "found", f"{name} met its first skitter."),
                 *((at(day, 200 + n), "ate", f"{name} ate apple.") for n in range(5)),
                 *((at(day, 300 + n), "fish", f"{name} caught a fish.") for n in range(4)),
                 *((at(day, 400 + n), "craft", f"{name} crafted planks.") for n in range(6)),
                 (at(day, 500), "hurt", f"{name} was hit by a skitter."),
                 (at(day, 501), "hurt", f"{name} was hit by a skitter."),
                 (at(day, 600), "learned", f"{name} learned that gravel sometimes hides flint."),
                 (at(day, 601), "learned", f"{name} learned that sand lies in the desert."),
                 (at(day, 700), "goal", f"{name} reached a goal: iron tools."),
                 (at(day, sleep_at), "sleep", f"{name} fell asleep."))

    def test_an_evening_sleep_writes_one_gist_and_merges_the_days_repeats(self):
        self.a_busy_day(1)
        [gist] = self.rows("kind='gist'")
        self.assertEqual(gist, {"game_day": 1, "kind": "gist", "source": "gist", "importance": 8, "count": 22,
                                "text": "Day 1: hatched into a brand-new world, reached a goal: iron tools, met my "
                                        "first skitter, learned two things, ate five meals and crafted six things."})
        episodes = {row["source"]: (row["text"], row["count"]) for row in self.rows("kind='episode'")}
        self.assertEqual(episodes["ate"], ("I ate 5 meals.", 5))
        self.assertEqual(episodes["fish"], ("I caught 4 fish.", 4))
        self.assertEqual(len(self.rows("source='hurt'")), 2)  # under MERGE_AT: kept one by one
        self.assertEqual(len(self.rows("source='found'")), 1)  # a moment that mattered is kept whole

    def test_the_day_is_consolidated_in_log_order_so_the_mirrors_lag_leaves_nothing_out(self):
        # The mirrors read the log a few seconds late: the sleep is consolidated when the mirror reaches it,
        # after every event logged before it, never before they are read.
        name = self.name
        with self.world.transaction() as db:
            for n in range(3):
                log_event(db, at(1, 2300 + n), "ate", f"{name} ate apple.")
            log_event(db, at(1, 2400), "found", f"{name} met its first cow.")
            log_event(db, at(1, EVENING), "sleep", f"{name} fell asleep.")
            log_event(db, at(1, EVENING + 50), "found", f"{name} met its first sheep.")
        run_chores(self.world, at(1, EVENING + 60), 1.0)
        [gist] = self.rows("kind='gist'")
        self.assertEqual(gist["text"], "Day 1: hatched into a brand-new world, met my first cow and ate three meals.")

    def test_a_gist_never_holds_what_the_owner_told_or_did(self):
        with self.world.transaction() as db:
            remember_fact(db, "likes", "purple kites", at(1, 100))
        self.log((at(1, 200), "care", f"You gave {self.name} a snack."),
                 (at(1, 300), "found", f"{self.name} met its first cow."),
                 (at(1, EVENING), "sleep", f"{self.name} fell asleep."))
        [gist] = self.rows("kind='gist'")
        self.assertEqual(gist["text"], "Day 1: hatched into a brand-new world and met my first cow.")

    def test_a_nap_by_day_is_not_the_night_and_a_night_is_consolidated_once(self):
        self.log((at(1, NOON), "sleep", f"{self.name} fell asleep."))
        self.assertEqual(self.rows("kind='gist'"), [])
        self.log((at(1, EVENING), "sleep", f"{self.name} fell asleep."),
                 (at(1, 3000), "wake", f"{self.name} woke up."),
                 (at(1, 3100), "sleep", f"{self.name} fell asleep."))
        self.assertEqual([row["text"] for row in self.rows("kind='gist'")], ["Day 1: hatched into a brand-new world."])

    def test_a_day_that_ends_without_an_evening_sleep_is_consolidated_as_the_next_begins(self):
        self.log((at(1, 100), "found", f"{self.name} met its first cow."), (at(2, 10), "wake", f"{self.name} woke up."))
        self.assertEqual([(row["game_day"], row["text"]) for row in self.rows("kind='gist'")],
                         [(1, "Day 1: hatched into a brand-new world and met my first cow.")])

    def test_small_things_fade_and_what_mattered_stays(self):
        name = self.name
        self.log((at(1, 100), "ate", f"{name} ate apple."), (at(1, 110), "hunt", f"{name} hunted a cow."),
                 (at(1, 120), "found", f"{name} met its first cow."), (at(1, EVENING), "sleep", f"{name} fell asleep."))
        self.log((at(2, EVENING), "sleep", f"{name} fell asleep."))
        self.assertEqual([row["source"] for row in self.rows("game_day=1 AND kind='episode'")],
                         ["birth", "hunt", "found"])
        for day in range(3, 6):
            self.log((at(day, EVENING), "sleep", f"{name} fell asleep."))
        self.assertEqual([row["source"] for row in self.rows("game_day=1")], ["birth", "found", "gist"])
        self.assertEqual(len(self.rows("kind='gist'")), 5)

    def test_the_nightly_hooks_run_after_each_day_and_one_that_crashes_is_rolled_back_alone(self):
        seen = []

        def broken(db, state, day, when, scale):
            db.execute("INSERT INTO mind_memories(at, game_day, kind, text, importance) "
                       "VALUES (0, 1, 'episode', 'x', 1)")
            raise RuntimeError("boom")
        with patch.dict(NIGHTLY, {"broken": broken, "seen": lambda db, state, day, when, scale: seen.append(day)}):
            with self.assertLogs("backend.survival.consolidation", level="ERROR"):
                self.log((at(1, EVENING), "sleep", f"{self.name} fell asleep."))
        self.assertEqual(seen, [1])
        self.assertEqual(self.rows("text='x'"), [])

    def test_a_gist_is_one_line_within_its_limit(self):
        self.assertEqual(gist_text(4, [], {}), "Day 4: a quiet day.")
        self.assertEqual(gist_text(4, [], {"craft": 1}), "Day 4: crafted one thing.")
        self.a_busy_day(1)
        for row in self.rows("kind='gist'"):
            self.assertLessEqual(len(row["text"]), TEXT_LIMIT)


if __name__ == "__main__":
    unittest.main()

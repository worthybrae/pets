"""The memory over a whole life, headless and model-free (Mind M1).

The fast test lives 30 game days through the real event log: each day logs far more than a pet
lives (180 finds that each matter, 60 meals, 40 fish, 20 hunts, blows at night, lessons, a snack,
a goal every third day), the Talker's chores mirror it and Mimo sleeps each evening. It proves one
gist a day, merging and fading, the 5,000 cap holding every day, every moment that mattered kept,
the oldest small ones forgotten first, and recall staying bounded on the full stream. The slow test
(MIMO_SLOW_TESTS=1) runs a real pet for five game days with the tick, the rules chooser and the
Talker's chores, and finds a gist for every evening.
"""

import os
import random
import tempfile
import time
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every creature, recipe and goal registered, for the tags)
from backend.survival import minding  # noqa: F401  (the mirror, the moments and consolidation registered)
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.clock import DAY_SECONDS
from backend.survival.hatch import hatch
from backend.survival.mind import CAP, POOL, candidates, count_memories, cue_of, recall
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
DAYS = 30
FINDS = 180  # finds a day, each of importance 6: only the cap forgets them
THINGS = ("iron ore", "coal ore", "a cave", "a lake", "gold ore", "a birch grove", "clay", "a sinkhole")


def at(day, seconds):
    return BORN + (day - 1) * DAY_SECONDS + seconds


def a_day(name, day):
    """A very busy game day's events, in order, ending with sleep in the evening."""
    events = [(at(day, 100 + n * 5), "found", f"{name} spotted {THINGS[n % len(THINGS)]}, find {day}-{n}.")
              for n in range(FINDS)]
    events += [(at(day, 1100 + n), "ate", f"{name} ate apple.") for n in range(60)]
    events += [(at(day, 1200 + n), "fish", f"{name} caught a fish.") for n in range(40)]
    events += [(at(day, 1300 + n), "hunt", f"{name} hunted a cow.") for n in range(20)]
    events += [(at(day, 1400 + n), "learned", f"{name} learned that lesson {day}-{n} is true.") for n in range(5)]
    events += [(at(day, 1500), "care", f"You gave {name} a snack.")]
    if day % 3 == 0:
        events += [(at(day, 1600), "goal", f"{name} reached a goal: goal number {day}.")]
    events += [(at(day, 2410 + n), "hurt", f"{name} was hit by a skitter.") for n in range(6)]
    return events + [(at(day, 2500), "sleep", f"{name} fell asleep.")]


class ThirtyDaysTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def mirror_all(self, now):
        with self.world.connect() as db:
            newest = db.execute("SELECT MAX(id) FROM mimo_events").fetchone()[0]
        for _ in range(100):  # a busy day is a few batches
            if self.world.state().get("mirrored", {}).get("memory") == newest:
                return
            run_chores(self.world, now, 1.0)
        self.fail("the mirror never caught up")

    def nearly_die(self, day):
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"]["health"] = 8.0
            state.update(hurt_at=at(day, 1000), hurt_by="gloomling")
            write_state(db, state)
        run_chores(self.world, at(day, 1001), 1.0)
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"]["health"] = 100.0
            write_state(db, state)

    def meal_days(self):
        with self.world.connect() as db:
            return db.execute("SELECT game_day, text FROM mind_memories WHERE source='ate' ORDER BY id").fetchall()

    def test_thirty_busy_days_keep_every_gist_and_what_mattered_within_the_cap(self):
        written = 0
        for day in range(1, DAYS + 1):
            events = a_day(self.life["name"], day)
            with self.world.transaction() as db:
                for when, kind, text in events:
                    log_event(db, when, kind, text)
            if day == 7:
                self.nearly_die(day)
            self.mirror_all(at(day, 2600))
            written += sum(1 for _, kind, _ in events if kind not in ("sleep",))
            with self.world.connect() as db:
                self.assertLessEqual(count_memories(db), CAP, f"day {day}")
            if day == 2:  # each night merged the day's 60 meals into one memory
                self.assertEqual([tuple(meal) for meal in self.meal_days()],
                                 [(1, "I ate 60 meals."), (2, "I ate 60 meals.")])
            if day == 5:  # and small things fade: day 1's meals are gone, its gist says what they were
                self.assertEqual([meal[0] for meal in self.meal_days()], [2, 3, 4, 5])
        with self.world.connect() as db:
            count = count_memories(db)
            gists = db.execute("SELECT game_day, text FROM mind_memories WHERE kind='gist' ORDER BY id").fetchall()
            mattered = dict(db.execute("SELECT source, COUNT(*) FROM mind_memories WHERE importance >= 7 "
                                       "AND kind IN ('episode', 'told', 'lesson') GROUP BY source").fetchall())
            finds = [row[0] for row in db.execute("SELECT DISTINCT game_day FROM mind_memories WHERE source='found' "
                                                  "ORDER BY game_day")]
            cue = cue_of("the skitter that hit me at night")
            pool = len(candidates(db, cue))
            started = time.perf_counter()
            for _ in range(50):
                found = recall(db, cue, at(DAYS, 2600), 1.0, 5)
            seconds = time.perf_counter() - started
        self.assertGreater(written, CAP)  # far more was lived than the stream can hold...
        self.assertLessEqual(count, CAP)  # ...so it holds its cap
        self.assertGreater(count, CAP - 500)
        self.assertEqual([day for day, _ in gists], list(range(1, DAYS + 1)))  # one gist a day, every day kept
        self.assertTrue(all(text.startswith(f"Day {day}: ") for day, text in gists))
        self.assertEqual(mattered, {"birth": 1, "goal": DAYS // 3, "near_death": 1})
        self.assertGreater(finds[0], 1)  # the oldest finds went first...
        self.assertEqual(finds[-5:], list(range(DAYS - 4, DAYS + 1)))  # ...the newest days' are all there
        self.assertLessEqual(pool, POOL)
        self.assertIn("skitter", found[0].memory.about)
        self.assertLess(seconds, 5.0)  # 50 recalls on a full stream (a few milliseconds each)


@unittest.skipUnless(os.environ.get("MIMO_SLOW_TESTS"), "set MIMO_SLOW_TESTS=1 to run the real five-day life")
class RealLifeTests(unittest.TestCase):
    def test_a_real_pet_remembers_its_days_and_sums_up_every_evening(self):
        scale = 60.0
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=scale)
            for second in range(1, 5 * 60 + 1):
                state = tick_life(registry, BORN + second, scale=scale, mind=BRAIN, action_scale=scale)
                self.assertIsNone(state["died_at"], state["cause"])
                chooser.poll(registry, BORN + second)
                run_chores(world, BORN + second, scale)
            with world.connect() as db:
                gists = [row[0] for row in db.execute(
                    "SELECT game_day FROM mind_memories WHERE kind='gist' ORDER BY id")]
                kinds = dict(db.execute("SELECT kind, COUNT(*) FROM mind_memories GROUP BY kind").fetchall())
        self.assertEqual(gists, [1, 2, 3, 4, 5])  # every evening, day 5 the last
        self.assertGreater(kinds["episode"], 10)
        self.assertGreater(kinds.get("lesson", 0), 0)


if __name__ == "__main__":
    unittest.main()

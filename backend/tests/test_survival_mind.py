import hashlib
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every creature, recipe and goal registered, for the tags)
from backend.survival import mind
from backend.survival.clock import DAY_SECONDS
from backend.survival.hatch import hatch
from backend.survival.mind import (
    POOL, STRENGTH_TOP, TEXT_LIMIT, add_memory, candidates, count_memories, cue_of, memories_view, recall, rehearse,
    story_memories, tags_in,
)
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import alive_snapshot
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0
DAY = DAY_SECONDS  # one game day in real seconds at scale 1


class MemoryStreamTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def add(self, day, text, kind="episode", importance=3, about=(), strength=1.0):
        with self.world.transaction() as db:
            return add_memory(db, BORN + (day - 1) * DAY, day, kind, text, about, importance, 0, "test",
                              strength=strength)

    def recalled(self, cue, now, limit=5, kinds=None):
        with self.world.connect() as db:
            return [item.memory.text for item in recall(db, cue, now, 1.0, limit, kinds)]

    def test_a_memory_keeps_its_tags_and_at_most_160_characters(self):
        self.assertEqual(tags_in("I met my first skitter near the cave."), ["skitter", "cave"])
        self.assertEqual(tags_in("I learned that iron ore needs a stone pickaxe."),
                         ["iron_ore", "iron", "ore", "stone_pickaxe", "stone", "pickaxe"])
        self.add(1, "word " * 60, about=("owner",))
        with self.world.connect() as db:
            row = db.execute("SELECT text, about FROM mind_memories").fetchone()
            tags = [tag for (tag,) in db.execute("SELECT tag FROM mind_tags ORDER BY tag")]
        self.assertLessEqual(len(row["text"]), TEXT_LIMIT)
        self.assertTrue(row["text"].endswith("..."))
        self.assertEqual((row["about"], tags), ("owner", ["owner"]))
        with self.assertRaises(ValueError):
            self.add(1, "a dream", kind="dream")

    def test_recall_weighs_recency_importance_and_relevance(self):
        self.add(1, "I hatched into a brand-new world.", importance=8)
        self.add(9, "I ate an apple.", importance=1)
        self.add(9, "I met my first skitter.", importance=6)
        self.add(10, "I ate some berries.", importance=1)
        now = BORN + 9.5 * DAY
        # No cue: what is recent and what mattered.
        self.assertEqual(self.recalled("", now, 2), ["I met my first skitter.", "I ate some berries."])
        # A cue brings back what it is about, even an old, plain memory.
        self.add(2, "A skitter bit me in the dark cave.", importance=3)
        self.assertEqual(self.recalled("remember the skitter in the cave?", now, 1),
                         ["A skitter bit me in the dark cave."])
        self.assertEqual(self.recalled("tell me a story", BORN + 30 * DAY, 1), ["I hatched into a brand-new world."])

    def test_the_cue_is_widened_by_synonyms(self):
        self.add(1, "I hunted a cow.", importance=2)
        self.add(1, "I made an iron cap.", importance=2)
        self.add(1, "I picked berries.", importance=2)
        now = BORN + 1.5 * DAY
        self.assertEqual(self.recalled("do cattle scare you?", now, 1), ["I hunted a cow."])
        self.assertEqual(self.recalled("tell me about your armor", now, 1), ["I made an iron cap."])
        self.assertEqual(cue_of("cows").terms, (("cow", frozenset({"cow", "cattle", "beef", "leather"}), True),))

    def test_rehearsal_strengthens_a_memory_so_it_fades_slower(self):
        weak = self.add(1, "I found a pretty flower.", importance=3)
        strong = self.add(1, "I found a shiny pebble.", importance=3)
        with self.world.transaction() as db:
            for _ in range(3):
                rehearse(db, [strong], BORN + DAY)
        now = BORN + 6 * DAY
        with self.world.connect() as db:
            found = {item.memory.id: item for item in recall(db, "", now, 1.0, 5)}
            self.assertEqual(found[strong].memory.strength, 4.0)
            self.assertEqual(found[strong].memory.last_recalled, BORN + DAY)
        self.assertGreater(found[strong].recency, found[weak].recency * 4)
        with self.world.transaction() as db:
            for _ in range(20):
                rehearse(db, [strong], BORN + DAY)
        with self.world.connect() as db:
            self.assertEqual(db.execute("SELECT strength FROM mind_memories WHERE id=?", (strong,)).fetchone()[0],
                             STRENGTH_TOP)

    def test_recall_scores_a_bounded_pool_found_through_the_indexes(self):
        with self.world.transaction() as db:
            for number in range(1200):
                add_memory(db, BORN + number, 1 + number // 100, "episode",
                           f"I saw a {('cow', 'sheep', 'skitter')[number % 3]} number {number}.", (), 1 + number % 9)
            cue = cue_of("the cow and the skitter")
            self.assertLessEqual(len(candidates(db, cue)), POOL)
            self.assertLessEqual(len(candidates(db, cue, ("episode", "thought"))), POOL)
            plans = [" ".join(row[3] for row in db.execute("EXPLAIN QUERY PLAN " + query, args))
                     for query, args in (
                         ("SELECT DISTINCT memory FROM mind_tags WHERE tag IN (?, ?) ORDER BY memory DESC LIMIT 200",
                          ("cow", "skitter")),
                         ("SELECT id FROM mind_memories WHERE kind=? ORDER BY id DESC LIMIT 75", ("thought",)),
                         ("SELECT id FROM mind_memories WHERE kind=? ORDER BY importance DESC, id DESC LIMIT 25",
                          ("thought",)),
                         ("SELECT id FROM mind_memories ORDER BY importance DESC, id DESC LIMIT 50", ()))]
        for plan in plans:
            self.assertRegex(plan, "PRIMARY KEY|INDEX", plan)
        self.assertEqual(len(self.recalled("cow", BORN + 13 * DAY, 10)), 10)

    def test_past_the_cap_the_weakest_are_forgotten_and_gists_and_thoughts_stay(self):
        with patch.object(mind, "CAP", 40), patch.object(mind, "ROOM", 10):
            for day in range(1, 11):
                self.add(day, f"Day {day}: a day.", kind="gist", importance=4)
                self.add(day, f"A thought on day {day}.", kind="thought", importance=7)
                self.add(day, f"Something big on day {day}.", importance=9)
                for number in range(4):
                    self.add(day, f"A meal on day {day}, number {number}.", importance=1)
            with self.world.connect() as db:
                self.assertLessEqual(count_memories(db), 40)
                kinds = dict(db.execute("SELECT kind, COUNT(*) FROM mind_memories GROUP BY kind").fetchall())
                big = db.execute("SELECT COUNT(*) FROM mind_memories WHERE importance=9").fetchone()[0]
                meals = [row[0] for row in db.execute("SELECT game_day FROM mind_memories WHERE importance=1")]
                orphans = db.execute("SELECT COUNT(*) FROM mind_tags WHERE memory NOT IN "
                                     "(SELECT id FROM mind_memories)").fetchone()[0]
        self.assertEqual((kinds["gist"], kinds["thought"], big), (10, 10, 10))
        self.assertTrue(meals and min(meals) >= 8, meals)  # the old small things went first
        self.assertEqual(orphans, 0)

    def test_the_kinds_kept_for_good_come_from_kept_and_the_oldest_gists_go_before_any_thought(self):
        # Final fix wave (M1): forget_weakest reads KEPT rather than naming the kinds itself.
        for day in (1, 2, 3):
            self.add(day, f"Day {day}: a day.", kind="gist", importance=9)
            self.add(day, f"A thought on day {day}.", kind="thought", importance=9)
            self.add(day, f"You taught me thing {day}.", kind="told", importance=1)
        with patch.object(mind, "KEPT", ("gist", "thought", "told")), self.world.transaction() as db:
            self.assertEqual(mind.forget_weakest(db, 3, 2), 2)  # nothing else to forget: the two oldest gists
            left = [tuple(row) for row in db.execute("SELECT kind, game_day FROM mind_memories ORDER BY id")]
        self.assertEqual(left, [("thought", 1), ("told", 1), ("thought", 2), ("told", 2),
                                ("gist", 3), ("thought", 3), ("told", 3)])

    def test_api_mimo_shows_the_memories_and_reading_never_writes(self):
        self.add(1, "I met my first cow.", importance=6)
        self.add(1, "Day 1: met my first cow.", kind="gist", importance=6)
        self.add(1, "I love fishing by the lake.", kind="thought", importance=7)
        self.add(2, "I ate an apple.", importance=1)
        before = hashlib.sha256(Path(self.world.path).read_bytes()).hexdigest()
        reader = SurvivalWorld(self.world.path, read_only=True)
        view = alive_snapshot(self.life, reader, BORN + 2 * DAY, 1.0)["memories"]
        self.assertEqual(hashlib.sha256(Path(self.world.path).read_bytes()).hexdigest(), before)
        self.assertEqual(view["count"], 4)
        self.assertEqual([item["text"] for item in view["recent"]], ["I ate an apple.", "I met my first cow."])
        self.assertEqual([item["text"] for item in view["moments"]], ["I met my first cow."])
        self.assertEqual([item["text"] for item in view["thoughts"]], ["I love fishing by the lake."])
        self.assertEqual(view["days"][0], {"id": 2, "at": BORN, "day": 1, "kind": "gist",
                                           "text": "Day 1: met my first cow.", "importance": 6, "feeling": 0})

    def test_a_days_story_never_holds_the_owners_words(self):
        self.add(3, "I met my first cow.", importance=6)
        self.add(3, "You told me you like purple kites.", kind="told", importance=6, about=("owner",))
        self.add(3, "You gave me a snack.", importance=5, about=("owner",))
        self.add(3, "Day 3: met my first cow.", kind="gist", importance=6)
        self.add(3, "I ate an apple.", importance=1)
        self.add(2, "I reached a goal: iron tools.", importance=7)
        with self.world.connect() as db:
            story = [memory.text for memory in story_memories(db, 3, limit=3)]
        self.assertEqual(story, ["Day 3: met my first cow.", "I met my first cow.", "I ate an apple."])

    def test_a_world_from_before_mind_remembers_nothing(self):
        raw = sqlite3.connect(self.world.path)
        raw.execute("DROP TABLE mind_memories")
        raw.execute("DROP TABLE mind_tags")
        raw.commit()
        raw.close()
        archive = SurvivalWorld(self.world.path, read_only=True)
        with archive.connect() as db:
            self.assertEqual(memories_view(db), {"count": 0, "recent": [], "moments": [], "thoughts": [], "days": []})
            self.assertEqual(recall(db, "cow", BORN, 1.0), [])
            self.assertEqual(story_memories(db, 1), [])


if __name__ == "__main__":
    unittest.main()

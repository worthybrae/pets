"""Bond's headless run: a real pet lives a game day and a bit with the worker's Chooser and Talker
(the rules only: no model is ever called, and Bond's final fix wave's T1 counts that: NoModel) while its
owner visits, talks and leaves."""

import os
import random
import re
import tempfile
import unittest
from pathlib import Path

from backend.survival.bond import START, bond_level
from backend.survival.bond_view import note_visit
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items, unread
from backend.survival.owner_facts import owner_facts
from backend.survival.registry import LifeRegistry
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld
from backend.tests.no_model import NoModel

BORN = 1_000_000.0
SCALE = 60.0  # a game day is a real minute, one tick a real second, as in the manual check
SLOW = os.environ.get("MIMO_SLOW_TESTS") == "1"


class OwnerAwayTests(unittest.TestCase):
    def test_a_day_with_the_owner_then_a_story_waits_for_them(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))
            http = NoModel()
            chooser = Chooser(env={}, http=http, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
            talker = Talker(env={}, http=http, executor_factory=InlineExecutor, scale=SCALE)
            for second in range(1, 81):
                now = BORN + second
                state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
                self.assertIsNone(state["died_at"], state["cause"])
                chooser.poll(registry, now)
                if second == 5:
                    note_visit(world, now)  # the owner opens the viewer
                if second == 10:
                    owner_says(world, "Hi! My name is Sam.", now, SCALE)
                if second == 12:
                    owner_says(world, "What are you doing?", now, SCALE)
                talker.poll(registry, now)
                self.assertEqual(state["last_tick_at"], now)  # the Talker never holds the tick back
            with world.connect() as db:
                chat = [tuple(row) for row in db.execute("SELECT who, text FROM mimo_chat ORDER BY id")]
                stories = [item for item in inbox_items(db, 1000) if item["kind"] == "story"]
                facts, waiting = owner_facts(db), unread(db)
                items = inbox_items(db, 1000)
            bond = bond_level(world.state(), BORN + 80)
        self.assertEqual([who for who, _ in chat], ["owner", "mimo", "owner", "mimo"])
        self.assertEqual(chat[1][1], "Nice to meet you, Sam! I'll remember that.")
        self.assertTrue(chat[3][1].startswith("I'm "), chat[3][1])
        self.assertIn(("name", "Sam"), facts)
        [story] = stories  # the first dawn after the visit, about game day 1, and only that one
        self.assertEqual(story["data"], {"day": 1, "writer": "rules", "present": True})  # N3: the owner was there
        self.assertTrue(3 <= len(re.split(r"(?<=[.!?])(?<!\.\.\.)\s+", story["text"])) <= 6, story["text"])
        self.assertEqual(waiting, len(items))  # nothing read yet: every item counts
        self.assertGreater(bond, START)  # the chat grew the bond
        self.assertEqual(http.calls, [])  # T1: no model was asked, not even one that failed unseen

    @unittest.skipUnless(SLOW, "a few game days: set MIMO_SLOW_TESTS=1")
    def test_left_alone_for_days_mimo_reports_its_home_and_waits_with_one_story(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))
            http = NoModel()
            chooser = Chooser(env={}, http=http, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
            talker = Talker(env={}, http=http, executor_factory=InlineExecutor, scale=SCALE)
            for second in range(1, 4 * 60 + 1):
                now = BORN + second
                state = tick_life(registry, now, scale=SCALE, mind=BRAIN, action_scale=SCALE)
                self.assertIsNone(state["died_at"], state["cause"])
                chooser.poll(registry, now)
                if second == 5:
                    note_visit(world, now)  # the owner looks in once, then leaves for days
                talker.poll(registry, now)
            with world.connect() as db:
                items = list(reversed(inbox_items(db, 1000)))
            name = world.state()["name"]
        texts = [item["text"] for item in items if item["kind"] == "report"]
        self.assertTrue(any(text.startswith("I finished building") and text.endswith("moved in.") for text in texts), texts)
        # Bond's final fix wave (I1): the home's report never names the pet ("I finished building my Round Cottage").
        self.assertFalse([text for text in texts if name in text], texts)
        self.assertEqual([item["data"]["day"] for item in items if item["kind"] == "story"], [1])  # one visit, one story
        [story] = [item for item in items if item["kind"] == "story"]
        self.assertEqual((story["data"].get("last"), story["read"]), (4, False))  # pre-flight 2: it tells the whole absence
        self.assertTrue(story["text"].startswith("Days 1 to 4 were"), story["text"])
        self.assertEqual(http.calls, [])  # T1


if __name__ == "__main__":
    unittest.main()

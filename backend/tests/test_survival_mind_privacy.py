import json
import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose, goal and creature registered)
from backend.survival import minding  # noqa: F401  (every Mind hook registered)
from backend.survival.choosing import prepare
from backend.survival.hatch import hatch
from backend.survival.mind import story_memories
from backend.survival.once import forget_logged
from backend.survival.owner_facts import remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.talk import owner_says
from backend.survival.talker import Talker, run_chores
from backend.survival.triggers import mark_trigger
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state
from backend.tests.test_survival_talker import FakeJev

BORN = 1_000_000.0
LUNA = {"MIMO_MODEL_API_KEY": "k"}
TAUGHT = ("Cows give leather!", "Iron armor needs iron ingots.")


class LunaNeverHearsTheOwnerTests(unittest.TestCase):
    """B1 re-review: a told memory holds what the owner said; only the owner's name may reach Luna."""

    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def test_no_told_memory_reaches_a_luna_payload_or_a_days_story(self):
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN + 2)
            remember_fact(db, "likes", "purple kites", BORN + 3)
            remember_fact(db, "about", "I work nights at the bakery", BORN + 4)
        for at, words in zip((BORN + 10, BORN + 20), TAUGHT):
            owner_says(self.world, words, at, 1.0)
            talker = Talker(env={}, http=FakeJev(), scale=1.0)
            talker.poll(self.registry, at + 1)
            talker.close()
        name = self.life["name"]
        with self.world.transaction() as db:
            log_event(db, BORN + 30, "found", f"{name} met its first cow.")
            log_event(db, BORN + 2300, "sleep", f"{name} fell asleep.")  # the day's gist
        run_chores(self.world, BORN + 2301, 1.0)
        with self.world.connect() as db:
            told = [tuple(row) for row in db.execute(
                "SELECT text, source FROM mind_memories WHERE kind='told' ORDER BY id")]
            story = [memory.text for memory in story_memories(db, 1, limit=50)]
        self.assertEqual(len(told), 5)  # three facts about the owner, two lessons taught
        with self.world.transaction() as db:
            state = read_state(db)
            mark_trigger(state, "hello", BORN + 2310)
            write_state(db, state)
        ask = prepare(SurvivalWorld(self.world.path, read_only=True), BORN + 2311, 1.0, LUNA)
        self.assertEqual(ask.route, "luna")
        self.assertTrue(story)
        sent = json.dumps([ask.payload, story])
        # What the owner said of themselves ("you like purple kites"), their own words and any told memory, whole
        # or retold ("You taught Pip that ..."). A lesson's fact is the world's, not the owner's: the journal shows it.
        facts = [text.split(" me ", 1)[-1] for text, source in told if source == "owner_fact"]
        for words in (*(text for text, _ in told), *facts, *TAUGHT, "you taught", "you told me", "purple kites",
                      "bakery"):
            self.assertNotIn(words.rstrip(".!").lower(), sent.lower())


if __name__ == "__main__":
    unittest.main()

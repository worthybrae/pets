"""W1: a wild pet's moments in its memory, its news and danger in the inbox, and "You were right"."""

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.survival import bonding, minding  # noqa: F401  (every writer registered)
from backend.survival.ailments import tend_night
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.memory import BUILT, create_memory_tables, set_home
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.teaching import confirms, teach_lesson
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0


class NewsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]
        run_chores(self.world, BORN, 1.0)  # the mirrors start at the newest event

    def tearDown(self):
        self.directory.cleanup()

    def log(self, *events, at=BORN + 10):
        with self.world.transaction() as db:
            for number, (kind, text) in enumerate(events):
                log_event(db, at + number, kind, text)
        run_chores(self.world, at + 60, 1.0)

    def test_the_new_moments_are_remembered_with_their_weight(self):
        name = self.name
        self.log(("figured", f"{name} worked out that cooking makes meat safe."), ("wound", f"A skitter cut {name}."),
                 ("chill", f"{name} caught a chill in the night."), ("asked", f"{name} asked you how to sleep better."))
        with self.world.connect() as db:
            rows = {row[0]: tuple(row[1:]) for row in db.execute(
                "SELECT source, kind, importance, feeling, text FROM mind_memories WHERE source IN "
                "('figured', 'wound', 'chill', 'asked')")}
            private = db.execute("SELECT COUNT(*) FROM mind_tags WHERE tag='owner'").fetchone()[0]
        self.assertEqual(rows["figured"], ("lesson", 7, 2, "I worked out that cooking makes meat safe."))
        self.assertEqual(rows["wound"], ("episode", 4, -2, "A skitter cut me."))
        self.assertEqual(rows["chill"][:3], ("episode", 5, -2))
        self.assertEqual(rows["asked"][:3], ("episode", 3, 0))
        self.assertGreaterEqual(private, 1)  # the question is about the owner: never in a story

    def test_the_inbox_tells_what_mimo_worked_out_and_its_ailments_once_a_game_day(self):
        name = self.name
        self.log(("figured", f"{name} worked out that cooking makes meat safe."),
                 ("festering", f"{name}'s wound is festering."), ("festering", f"{name}'s wound is festering."),
                 ("chill", f"{name} caught a chill in the night."))
        with self.world.connect() as db:
            items = [(item["kind"], item["text"]) for item in reversed(inbox_items(db))]
        self.assertEqual(items, [("report", "I worked it out myself: cooking makes meat safe."),
                                 ("danger", "My wound is festering."), ("danger", "I caught a chill in the night.")])

    def test_a_taught_survival_lesson_seen_true_says_you_were_right(self):
        with self.world.transaction() as db:
            state = read_state(db)
            teach_lesson(db, state, thing("berries"), BORN + 1, 1)
            teach_lesson(db, state, thing("bed"), BORN + 1, 1)
            write_state(db, state)
        self.log(("ate", f"{self.name} ate berries."), ("rested", f"{self.name} slept soundly in its bed."))
        with self.world.connect() as db:
            said = [row[0] for row in db.execute("SELECT text FROM mimo_chat WHERE who='mimo'")]
        self.assertEqual(said, ["You were right: bright red berries are safe to eat. I saw it myself!",
                                "You were right: six planks make a bed, and sleep in a bed rests you best. I saw it myself!"])
        self.assertTrue(confirms(thing("cooking"), "cook"))
        self.assertFalse(confirms(thing("cooking"), "found"))
        self.assertFalse(confirms("gravel", "ate"))  # the other lessons keep their seeing kinds


class DawnEventTests(unittest.TestCase):
    def test_a_night_in_a_bed_and_a_quiet_night_at_home_are_logged_at_dawn(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        set_home(db, (0, 1, 0), 0.0, BUILT)
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 0.0}, "difficulty": "wild",
                 "vitals": {"warmth": 80.0}}
        context = SimpleNamespace(db=db, events=[])
        for _ in range(10):
            tend_night(state, context, 60.0, ("night", "night"), "sleeping_in_bed", True, 1.0)
        tend_night(state, context, 1.0, ("pre_dawn", "dawn"), "idle", True, 2.0)
        self.assertEqual([kind for _, kind, _ in context.events], ["rested", "safe_night"])


if __name__ == "__main__":
    unittest.main()

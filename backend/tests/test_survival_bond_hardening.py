"""Bond's final fix wave, group 4: hardening.

m4 (the egg screen's poll reads only the stories it sends), m10 (a stuck viewer's visits and reads never
take the write lock), m12 (nothing is marked read for a pet that died), m9 (a name far too long is refused
before it is cleaned) and T1 (the counting no-model stub has teeth).
"""

import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import diary
from backend.survival.bond_view import note_visit
from backend.survival.choosing import InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.inbox import mark_ids, mark_one, mark_read, name_place, post_item
from backend.survival.registry import LifeRegistry
from backend.survival.talker import Talker
from backend.survival.talk import owner_says
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state
from backend.tests.no_model import NoModel

BORN = 1_000_000.0


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def test_the_egg_screens_diary_reads_only_what_it_sends(self):
        """m4: life_diary(limit) asks the database for the newest `limit`, not every story."""
        with self.world.transaction() as db:
            for day in range(1, 26):
                post_item(db, BORN + day, "story", f"Day {day} was a good one.", {"day": day, "writer": "rules"})
        asked = []
        real = diary.diary_entries

        def spy(db, limit=None):
            asked.append(limit)
            return real(db, limit)
        with patch("backend.survival.diary.diary_entries", spy):
            entries = diary.life_diary(self.world, 10)
        self.assertEqual(asked, [10])
        self.assertEqual([entry["day"] for entry in entries], list(range(16, 26)))  # the newest, oldest first
        self.assertEqual(len(diary.life_diary(self.world)), 25)

    def test_a_visit_within_a_minute_of_the_last_writes_nothing(self):
        """m10: the viewer's visits and a stuck client's loop cost one write a minute at most."""
        note_visit(self.world, BORN + 10)
        seen = self.world.state()["bond"]["seen_at"]
        with patch.object(SurvivalWorld, "transaction", side_effect=AssertionError("no write")):
            self.assertEqual(note_visit(self.world, BORN + 40), {"level": 20, "feeling": "shy"})
            self.assertEqual(mark_read(self.world, 999, BORN + 41), 0)  # nothing unread: no write either
            self.assertEqual(mark_ids(self.world, [1, 2], BORN + 41), 0)
        self.assertEqual(self.world.state()["bond"]["seen_at"], seen)
        note_visit(self.world, BORN + 75)
        self.assertEqual(self.world.state()["bond"]["seen_at"], BORN + 75)

    def test_nothing_is_marked_read_for_a_pet_that_died(self):
        """m12: the inbox's writers check died_at as the others do."""
        with self.world.transaction() as db:
            item = post_item(db, BORN + 5, "report", "I reached a goal: iron tools.")
            state = read_state(db)
            state["died_at"] = BORN + 6
            write_state(db, state)
        for mark in (lambda: mark_read(self.world, item, BORN + 7), lambda: mark_one(self.world, item, BORN + 7),
                     lambda: mark_ids(self.world, [item], BORN + 7)):
            with self.assertRaises(LifeOver):
                mark()

    def test_a_name_far_too_long_is_refused_before_it_is_cleaned(self):
        """m9: a huge body is never split in full."""
        with patch("backend.survival.inbox.PLACE_NAME") as pattern, self.assertRaises(ValueError):
            name_place(self.world, 1, "Echo " * 10_000, BORN + 5)
        pattern.match.assert_not_called()

    def test_the_no_model_stub_counts_a_call_the_rules_covered_for(self):
        """T1: a Jev key set by mistake is caught, though the chat still answers by the rules."""
        http = NoModel()
        owner_says(self.world, "Hi!", BORN + 5, 1.0)
        Talker(env={"TYPESAFE_API_KEY": "k"}, http=http, executor_factory=InlineExecutor, scale=1.0).poll(
            self.registry, BORN + 6)
        self.assertEqual(len(http.calls), 1)


if __name__ == "__main__":
    unittest.main()

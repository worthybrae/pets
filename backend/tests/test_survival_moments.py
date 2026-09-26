import random
import tempfile
import unittest
from pathlib import Path

from backend.survival import moments  # noqa: F401  (the moments register with the inbox's mirror)
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items, mark_read, unread
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0


class MomentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(registry.world_path(self.life))
        self.name = self.life["name"]
        run_chores(self.world, BORN + 1, 1.0)  # the inbox starts

    def tearDown(self):
        self.directory.cleanup()

    def log(self, *events):
        with self.world.transaction() as db:
            for at, kind, text in events:
                log_event(db, at, kind, text)

    def items(self):
        with self.world.connect() as db:
            return [(item["kind"], item["text"]) for item in reversed(inbox_items(db, 1000))]

    def test_first_sightings_and_a_hatching_seed_reach_the_inbox_and_a_growing_sapling_does_not(self):
        self.log((BORN + 2, "found", f"{self.name} met its first skitter."),
                 (BORN + 3, "discovered", f"{self.name} found water."),
                 (BORN + 4, "grow", "A sapling grew into a tree."),
                 (BORN + 5, "grow", "A creature seed grew into a sheep."),
                 (BORN + 6, "purpose", f'{self.name} decided to rest. "Ahh."'))
        run_chores(self.world, BORN + 10, 1.0)
        self.assertEqual(self.items(), [("found", "I met my first skitter."), ("found", "I found water."),
                                         ("hatched", "My creature seed grew into a sheep!")])

    def test_danger_is_told_at_most_once_a_game_hour(self):
        self.log((BORN + 2, "threat", f"{self.name} saw a gloomling coming."),
                 (BORN + 3, "hurt", f"{self.name} was hit by a gloomling."),
                 (BORN + 4, "hurt", f"{self.name} was hit by a gloomling."))
        run_chores(self.world, BORN + 10, 60.0)
        self.assertEqual(self.items(), [("danger", "I saw a gloomling coming.")])
        self.log((BORN + 2 + 61, "trapped", f"{self.name} is stuck in a pit and starts digging out."))
        run_chores(self.world, BORN + 70, 60.0)  # a game hour later at 60x
        self.assertEqual(self.items()[-1], ("danger", "I got stuck in a pit. I'm digging my way out."))

    def test_near_death_is_told_once_a_game_hour_and_the_inbox_counts_it_until_read(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"]["health"] = 12.0
            write_state(db, state)
        run_chores(self.world, BORN + 10, 1.0)
        run_chores(self.world, BORN + 20, 1.0)
        self.assertEqual(self.items(), [("ask", "I got badly hurt. Could you bandage me?"),  # B2's ask
                                        ("danger", "I'm badly hurt. I need to rest and heal.")])
        with self.world.connect() as db:
            self.assertEqual(unread(db), 2)
            newest = inbox_items(db, 1)[0]["id"]
        self.assertEqual(mark_read(self.world, newest, BORN + 30), 0)
        run_chores(self.world, BORN + 10 + 3600, 1.0)
        self.assertEqual([kind for kind, _ in self.items()].count("danger"), 2)

    def test_the_computer_mimo_built_is_reported_in_its_own_words(self):
        """Pre-flight 2 (carry 9): Making's notable "computer" event reaches the inbox through events.mirror."""
        self.log((BORN + 2, "computer", f"{self.name} built a machine that remembers how long it has been alive!"))
        run_chores(self.world, BORN + 10, 1.0)
        self.assertEqual(self.items(), [("report", "I built a machine that remembers how long I have been alive!")])

    def test_a_cave_mouth_is_told_in_mimos_voice(self):
        """Pre-flight 2: the cave's walls, not Mimo's (Mind's episodes.voice)."""
        self.log((BORN + 2, "discovered", f"{self.name} found a cave mouth with coal ore in its walls."))
        run_chores(self.world, BORN + 10, 1.0)
        self.assertEqual(self.items(), [("found", "I found a cave mouth with coal ore in its walls.")])


if __name__ == "__main__":
    unittest.main()

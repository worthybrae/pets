"""W2: the weather's and the seasons' moments in Mimo's memory, its news and danger in the inbox, which of them are
routine, and the sky in /api/mimo (a GET never writes)."""

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival import bonding, minding  # noqa: F401  (every writer registered)
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.world import ROUTINE_EVENTS, SurvivalWorld, log_event

BORN = 1_000_000.0


class NewsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
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

    def test_the_skys_moments_are_remembered_with_their_weight(self):
        name = self.name
        self.log(("struck", f"Lightning struck {name}!"), ("fire", f"Lightning set a tree on fire near {name}."),
                 ("season", "Winter has come."), ("spring", "Spring! Things are growing again."),
                 ("colder", "The nights are getting colder."))
        with self.world.connect() as db:
            rows = {row[0]: tuple(row[1:]) for row in db.execute(
                "SELECT source, importance, feeling, text FROM mind_memories WHERE source IN "
                "('struck', 'fire', 'season', 'spring', 'colder')")}
        self.assertEqual(rows["struck"], (8, -2, "Lightning struck me!"))
        self.assertEqual(rows["fire"], (5, 0, "Lightning set a tree on fire near me."))
        self.assertEqual(rows["season"][:2], (4, 1))
        self.assertEqual(rows["spring"][:2], (6, 1))
        self.assertEqual(rows["colder"][:2], (4, 0))

    def test_the_inbox_tells_of_a_strike_or_a_fire_once_a_game_day_and_of_winter_and_spring(self):
        name = self.name
        self.log(("struck", f"Lightning struck {name}!"), ("fire", f"Lightning set a tree on fire near {name}."),
                 ("fire", f"Lightning set a tree on fire near {name}."), ("season", "Summer has come."),
                 ("season", "Winter has come."), ("spring", "Spring! Things are growing again."))
        with self.world.connect() as db:
            items = [(item["kind"], item["text"]) for item in reversed(inbox_items(db))]
        self.assertEqual(items, [("danger", "Lightning struck me!"), ("danger", "Lightning set a tree on fire near me."),
                                 ("report", "Winter has come."), ("report", "Spring! Things are growing again.")])

    def test_which_of_them_are_routine(self):
        self.assertLessEqual({"season", "storm", "fire_out", "smoke"}, ROUTINE_EVENTS)
        self.assertFalse({"spring", "colder", "struck", "fire"} & ROUTINE_EVENTS)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_sky_in_api_mimo_and_a_get_never_writes(self):
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        before = world.state()
        sky = get_mimo()["sky"]
        self.assertEqual(set(sky), {"season", "day", "to_next", "weather", "until", "snow", "frozen", "strikes", "fires"})
        self.assertEqual((sky["season"], sky["day"], sky["to_next"]), ("spring", 1, 10))
        self.assertEqual(world.state(), before)


if __name__ == "__main__":
    unittest.main()

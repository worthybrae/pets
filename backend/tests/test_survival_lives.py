import hashlib
import math
import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.live_mimo import MimoStore
from backend.survival.eggs import TRAITS
from backend.survival.hatch import hatch
from backend.survival.registry import LifeConflict, LifeRegistry, data_dir, read_legacy_life
from backend.survival.world import SurvivalWorld


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), Path(path).stat().st_mtime_ns


class LifeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.legacy_path = root / "mimo.sqlite3"
        legacy = MimoStore(self.legacy_path)
        legacy.put_block(80, 20, 0, "stone")
        self.legacy_seed = legacy.world_seed
        self.legacy_before = fingerprint(self.legacy_path)
        self.data = root / "data"
        self.registry = LifeRegistry(self.data, self.legacy_path, timestamp=5000.0)

    def tearDown(self):
        self.directory.cleanup()

    def test_the_legacy_world_becomes_retired_life_one_without_being_touched(self):
        lives = self.registry.list_lives()
        self.assertEqual(len(lives), 1)
        legacy = lives[0]
        self.assertEqual((legacy["id"], legacy["kind"], legacy["name"]), (1, "legacy", "Mimo"))
        self.assertEqual((legacy["died_at"], legacy["cause"]), (5000.0, "retired"))
        self.assertEqual(legacy["seed"], self.legacy_seed)
        self.assertEqual((legacy["spawn_x"], legacy["spawn_z"]), (73, 0))
        self.assertFalse(legacy["alive"])
        self.assertEqual(self.registry.world_path(legacy), self.legacy_path.resolve())
        LifeRegistry(self.data, self.legacy_path, timestamp=9000.0)
        self.assertEqual(len(self.registry.list_lives()), 1)
        MimoStore(self.legacy_path, read_only=True).snapshot()
        self.assertEqual(fingerprint(self.legacy_path), self.legacy_before)
        self.assertIsNone(self.registry.active_life())

    def test_without_a_legacy_file_there_is_no_legacy_life(self):
        empty = LifeRegistry(Path(self.directory.name) / "other", Path(self.directory.name) / "missing.sqlite3")
        self.assertEqual(empty.list_lives(), [])
        self.assertIsNone(empty.last_life())

    def test_a_broken_legacy_file_is_not_treated_as_missing(self):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        broken = root / "broken.sqlite3"
        broken.write_bytes(b"not a database")
        with self.assertRaises(sqlite3.DatabaseError):
            read_legacy_life(broken)
        with self.assertRaises(sqlite3.Error):
            LifeRegistry(root / "data", broken)
        directory.cleanup()

    def test_data_dir_resolves_a_relative_path_to_absolute(self):
        with patch.dict(os.environ, {"MIMO_DATA_DIR": "some_relative_survival_data_dir"}):
            self.assertTrue(data_dir().is_absolute())

    def test_the_registry_schema_is_initialized_once_per_path_per_process(self):
        # A fresh directory this process has never opened, so the module-level cache starts empty for it.
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        with patch.object(LifeRegistry, "initialize", autospec=True, side_effect=LifeRegistry.initialize) as spy:
            LifeRegistry(root / "data", root / "no-legacy.sqlite3", timestamp=1.0)
            LifeRegistry(root / "data", root / "no-legacy.sqlite3", timestamp=2.0)
            LifeRegistry(root / "data", root / "no-legacy.sqlite3", timestamp=3.0)
        self.assertEqual(spy.call_count, 1)
        directory.cleanup()

    def test_the_pending_egg_is_rolled_once_and_kept(self):
        first = self.registry.pending_egg(random.Random(1))
        self.assertEqual(self.registry.pending_egg(random.Random(2)), first)
        self.assertEqual(len(first["attributes"]), 5)

    def test_hatching_creates_a_survival_life_with_its_own_world(self):
        egg = self.registry.pending_egg(random.Random(1))
        life = hatch(self.registry, random.Random(4), timestamp=6000.0)
        self.assertEqual((life["id"], life["kind"], life["born_at"]), (2, "survival", 6000.0))
        self.assertTrue(life["alive"])
        self.assertEqual(life["egg"], egg)
        self.assertEqual(set(life["traits"]), set(TRAITS))
        self.assertEqual(life["db_path"], str(Path("lives") / "2.sqlite3"))
        self.assertTrue(3000 <= math.hypot(life["spawn_x"], life["spawn_z"]) <= 6000)
        state = SurvivalWorld(self.registry.world_path(life)).state()
        self.assertEqual(state["name"], life["name"])
        self.assertEqual(state["world_seed"], life["seed"])
        self.assertEqual((state["position"]["x"], state["position"]["z"]), (life["spawn_x"], life["spawn_z"]))
        self.assertEqual(self.registry.active_life()["id"], 2)
        with self.registry.connect() as db:
            self.assertIsNone(db.execute("SELECT egg FROM pending_egg").fetchone())
        self.assertEqual(fingerprint(self.legacy_path), self.legacy_before)

    def test_an_egg_cannot_hatch_while_a_pet_is_alive(self):
        hatch(self.registry, random.Random(4), timestamp=6000.0)
        with self.assertRaises(LifeConflict):
            hatch(self.registry, random.Random(5), timestamp=6100.0)

    def test_death_is_recorded_once_and_frees_the_next_egg(self):
        first = hatch(self.registry, random.Random(4), timestamp=6000.0)
        self.registry.mark_dead(first["id"], 7000.0, "starvation")
        self.registry.mark_dead(first["id"], 8000.0, "cold")
        dead = self.registry.get(first["id"])
        self.assertEqual((dead["died_at"], dead["cause"], dead["alive"]), (7000.0, "starvation", False))
        self.assertIsNone(self.registry.active_life())
        self.assertEqual(self.registry.last_life()["id"], first["id"])
        second = hatch(self.registry, random.Random(5), timestamp=9000.0)
        self.assertEqual(second["id"], 3)
        self.assertNotEqual(second["name"], first["name"])
        self.assertNotEqual(second["seed"], first["seed"])
        self.assertEqual([life["id"] for life in self.registry.list_lives()], [3, 2, 1])


if __name__ == "__main__":
    unittest.main()

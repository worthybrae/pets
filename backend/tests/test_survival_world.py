import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.live_mimo import MimoStore
from backend.services.worldgen import block_at, terrain_height
from backend.survival import world as world_module
from backend.survival.world import (
    LifeOver, SurvivalWorld, WorldBehind, WorldMissing, new_survival_state, read_state, write_state,
)

SEED = "123456789123456789"
SPAWN = {"x": 3682, "y": 5, "z": 4143}


def file_fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), Path(path).stat().st_mtime_ns


class SurvivalWorldTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "lives" / "2.sqlite3"
        self.world = SurvivalWorld.create(self.path, new_survival_state(
            name="Pip", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={"curiosity": 50}))

    def tearDown(self):
        self.directory.cleanup()

    def set_state(self, **changes):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(changes)
            write_state(db, state)

    def test_a_new_world_starts_with_full_vitals_and_a_birth_event(self):
        state = SurvivalWorld(self.path).state()
        self.assertEqual(state["name"], "Pip")
        self.assertEqual(state["position"], {"x": 3682.0, "y": 5.0, "z": 4143.0})
        self.assertEqual(state["vitals"]["health"], 100.0)
        self.assertEqual(state["status"], "idle")
        self.assertIsNone(state["died_at"])
        self.assertEqual(self.world.seed, SEED)
        self.assertEqual([event["kind"] for event in self.world.events()], ["birth"])
        self.assertEqual(self.world.blocks_seq(), 0)

    def test_creating_over_a_leftover_file_replaces_it_with_a_fresh_world(self):
        self.world.put_block(3682, 6, 4143, "lantern")
        again = SurvivalWorld.create(self.path, new_survival_state(
            name="Wren", seed=SEED, spawn=SPAWN, born_at=2000.0, traits={}))
        self.assertEqual(again.state()["name"], "Wren")
        self.assertEqual(len(again.events()), 1)
        self.assertIn("Wren", again.events()[0]["text"])
        self.assertEqual(again.blocks_since(0)["changes"], [])

    def test_blocks_reach_thirty_thousand_and_are_numbered(self):
        self.world.put_block(29_999, 10, -29_999, "stone")
        self.world.put_block(3682, 6, 4143, "lantern")
        with self.assertRaises(ValueError):
            self.world.put_block(30_001, 10, 0, "stone")
        with self.assertRaises(ValueError):
            self.world.put_block(0, 10, 0, "not_a_block")
        page = self.world.blocks_since(0, limit=1)
        self.assertEqual(page["changes"], [{"x": 29_999, "y": 10, "z": -29_999, "material": "stone"}])
        self.assertTrue(page["more"])
        self.assertEqual(self.world.blocks_since(page["seq"])["changes"][0]["material"], "lantern")
        self.assertEqual(self.world.blocks_seq(), 2)

    def test_legacy_worlds_keep_their_old_limit(self):
        store = MimoStore(Path(self.directory.name) / "mimo.sqlite3")
        with self.assertRaises(ValueError):
            store.put_block(4097, 10, 0, "stone")

    def test_material_at_mixes_worldgen_and_edits(self):
        x, z = SPAWN["x"], SPAWN["z"]
        ground = terrain_height(x, z, SEED)
        self.assertEqual(self.world.material_at(x, ground, z), block_at(x, ground, z, SEED))
        self.world.put_block(x, ground, z, "air")
        self.assertEqual(self.world.material_at(x, ground, z), "air")

    def test_hello_lifts_mood_and_is_logged(self):
        self.set_state(vitals={**self.world.state()["vitals"], "mood": 97.0}, last_tick_at=1495.0)
        result = self.world.greet(1500.0)
        self.assertEqual(result["mood"], 100.0)
        state = self.world.state()
        self.assertEqual(state["last_hello_at"], 1500.0)
        self.assertEqual(self.world.events()[0]["kind"], "hello")

    def test_owner_can_help_craft_and_place_machines(self):
        self.set_state(inventory={"oak_log": 2}, last_tick_at=1495.0)
        self.world.owner_action("craft", "planks", 1500.0)
        self.world.owner_action("craft", "crafting_table", 1501.0)
        result = self.world.owner_action("place_machine", "crafting_table", 1502.0)
        self.assertNotIn("crafting_table", result["inventory"])
        changes = self.world.blocks_since(0)["changes"]
        self.assertEqual([change["material"] for change in changes], ["crafting_table"])
        self.assertLessEqual(abs(changes[0]["x"] - SPAWN["x"]) + abs(changes[0]["z"] - SPAWN["z"]), 3)
        self.assertEqual(self.world.events()[0]["kind"], "owner")
        with self.assertRaises(ValueError):
            self.world.owner_action("craft", "furnace", 1503.0)
        with self.assertRaises(ValueError):
            self.world.owner_action("juggle", "planks", 1504.0)

    def test_a_dead_pet_cannot_be_greeted_or_helped(self):
        self.set_state(died_at=1800.0, cause="starvation", status="dead")
        with self.assertRaises(LifeOver):
            self.world.greet(1900.0)
        with self.assertRaises(LifeOver):
            self.world.owner_action("craft", "planks", 1900.0)

    def test_owner_writes_are_refused_while_the_world_is_behind(self):
        self.set_state(last_tick_at=1000.0)
        with self.assertRaises(WorldBehind):
            self.world.greet(1011.0)
        with self.assertRaises(WorldBehind):
            self.world.owner_action("craft", "planks", 1011.0)
        # Within the 10s allowance, both go through.
        self.world.greet(1005.0)
        self.set_state(inventory={"oak_log": 1})
        self.world.owner_action("craft", "planks", 1008.0)

    def test_a_missing_world_file_is_reported(self):
        with self.assertRaises(WorldMissing):
            SurvivalWorld(Path(self.directory.name) / "lives" / "99.sqlite3")

    def test_a_world_opened_writable_twice_runs_schema_setup_once(self):
        # Simulate a world file this process has never opened before (schema setup still
        # pending), the way a freshly-started worker or API process would first see it.
        path = Path(self.directory.name) / "lives" / "9.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        state = new_survival_state(name="Q", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={})
        with sqlite3.connect(path) as raw:
            raw.execute("CREATE TABLE survival_state (id INTEGER PRIMARY KEY CHECK (id=1), data TEXT NOT NULL)")
            raw.execute("INSERT INTO survival_state(id, data) VALUES (1, ?)", (json.dumps(state),))
        with patch.object(world_module, "create_world_tables", wraps=world_module.create_world_tables) as spy:
            SurvivalWorld(path)
            SurvivalWorld(path)
        self.assertEqual(spy.call_count, 1)

    def test_read_only_worlds_cannot_be_written(self):
        archive = SurvivalWorld(self.path, read_only=True)
        self.assertEqual(archive.state()["name"], "Pip")
        with self.assertRaises(sqlite3.OperationalError):
            archive.put_block(3682, 6, 4143, "stone")

    def test_read_only_legacy_store_leaves_the_file_untouched(self):
        legacy_path = Path(self.directory.name) / "legacy.sqlite3"
        MimoStore(legacy_path).put_block(80, 20, 0, "stone")
        before = file_fingerprint(legacy_path)
        archive = MimoStore(legacy_path, read_only=True)
        self.assertEqual(archive.snapshot()["plans"][0]["kind"], "station")
        self.assertEqual(archive.blocks_since(0)["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
        self.assertEqual(file_fingerprint(legacy_path), before)


if __name__ == "__main__":
    unittest.main()

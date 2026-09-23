import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.live_mimo import MimoStore


def _write_old_schema_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    # A database that already went through a run (like the API/worker's) is in WAL
    # mode already; set it here so the test races the migration, not the one-time
    # journal mode switch.
    connection.execute("PRAGMA journal_mode=WAL")
    with connection:
        connection.execute("CREATE TABLE mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
                           "material TEXT NOT NULL, PRIMARY KEY(x,y,z))")
        connection.execute("INSERT INTO mimo_blocks VALUES (1,2,3,'stone'), (4,5,6,'air'), (7,8,9,'dirt')")
    connection.close()


class BlockSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "mimo.sqlite3"
        self.store = MimoStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_every_block_write_gets_a_new_sequence_number(self):
        self.store.put_block(80, 20, 0, "stone")
        first = self.store.blocks_since(0)
        self.assertEqual(first["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
        self.store.put_block(80, 20, 0, "air")
        second = self.store.blocks_since(first["seq"])
        self.assertEqual(second["changes"], [{"x": 80, "y": 20, "z": 0, "material": "air"}])
        self.assertGreater(second["seq"], first["seq"])
        self.assertFalse(second["more"])

    def test_block_edits_are_ordered_by_position(self):
        self.store.put_block(5, 20, 0, "stone")
        self.store.put_block(1, 20, 0, "stone")
        self.store.put_block(3, 20, 0, "stone")
        self.assertEqual([edit["x"] for edit in self.store.block_edits()], [1, 3, 5])

    def test_falling_sand_reports_both_cells(self):
        self.store.put_block(73, 2, 0, "sand")
        seq = self.store.blocks_since(0)["seq"]
        self.assertEqual(self.store.step_loose_blocks(), 1)
        changes = self.store.blocks_since(seq)["changes"]
        self.assertIn({"x": 73, "y": 2, "z": 0, "material": "air"}, changes)
        self.assertIn({"x": 73, "y": 1, "z": 0, "material": "sand"}, changes)

    def test_worker_and_owner_writes_are_numbered(self):
        state = self.store.claim_due(time.time() + 10 ** 6)
        self.store.finish(state, None, (81, 3, 0, "planks"))
        seq = self.store.blocks_since(0)["seq"]
        self.assertEqual(self.store.blocks_since(0)["changes"], [{"x": 81, "y": 3, "z": 0, "material": "planks"}])
        self.store.owner_action("craft", "planks")
        self.store.owner_action("craft", "crafting_table")
        self.store.owner_action("place_machine", "crafting_table")
        materials = [change["material"] for change in self.store.blocks_since(seq)["changes"]]
        self.assertEqual(materials, ["crafting_table"])

    def test_since_pages_through_changes_in_order(self):
        for x in range(90, 97):
            self.store.put_block(x, 20, 0, "stone")
        page = self.store.blocks_since(0, limit=3)
        self.assertEqual(len(page["changes"]), 3)
        self.assertTrue(page["more"])
        seen = list(page["changes"])
        while page["more"]:
            page = self.store.blocks_since(page["seq"], limit=3)
            seen += page["changes"]
        self.assertEqual([change["x"] for change in seen], list(range(90, 97)))

    def test_old_database_without_seq_is_migrated(self):
        path = Path(self.directory.name) / "old.sqlite3"
        connection = sqlite3.connect(path)
        with connection:
            connection.execute("CREATE TABLE mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
                               "material TEXT NOT NULL, PRIMARY KEY(x,y,z))")
            connection.execute("INSERT INTO mimo_blocks VALUES (1,2,3,'stone'), (4,5,6,'air')")
        connection.close()
        store = MimoStore(path)
        page = store.blocks_since(0)
        self.assertEqual(len(page["changes"]), 2)
        self.assertEqual(page["seq"], 2)
        store.put_block(7, 8, 9, "dirt")
        self.assertEqual(store.blocks_since(2)["changes"], [{"x": 7, "y": 8, "z": 9, "material": "dirt"}])

    def test_snapshot_reports_blocks_seq_instead_of_every_edit(self):
        self.store.put_block(80, 20, 0, "stone")
        snapshot = self.store.snapshot()
        self.assertNotIn("block_edits", snapshot)
        self.assertNotIn("catalog", snapshot)
        self.assertIn("recipes", snapshot)
        self.assertEqual(snapshot["blocks_seq"], self.store.blocks_since(0)["seq"])

    def test_repeated_initialize_on_old_schema_keeps_seq_stable(self):
        path = Path(self.directory.name) / "old_repeat.sqlite3"
        _write_old_schema_database(path)
        first = MimoStore(path)
        before_edits = first.block_edits()
        before_seq = first.snapshot()["blocks_seq"]
        second = MimoStore(path)
        after_edits = second.block_edits()
        after_seq = second.snapshot()["blocks_seq"]
        self.assertEqual(before_edits, after_edits)
        self.assertEqual(before_seq, after_seq)

    def test_concurrent_initialize_on_old_schema_does_not_race(self):
        for attempt in range(5):
            path = Path(self.directory.name) / f"race_{attempt}.sqlite3"
            _write_old_schema_database(path)
            errors = []
            barrier = threading.Barrier(4)

            def worker():
                try:
                    barrier.wait(timeout=5)
                    MimoStore(path)
                except Exception as error:  # noqa: BLE001 - captured for the assertion below
                    errors.append(error)

            threads = [threading.Thread(target=worker) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [], f"attempt {attempt}: {errors}")
            with sqlite3.connect(path) as check:
                check.row_factory = sqlite3.Row
                seqs = [row["seq"] for row in check.execute("SELECT seq FROM mimo_blocks ORDER BY seq")]
            self.assertEqual(len(seqs), 3, f"attempt {attempt}: {seqs}")
            self.assertEqual(len(seqs), len(set(seqs)), f"attempt {attempt}: duplicate seqs {seqs}")
            self.assertTrue(all(seq >= 1 for seq in seqs), f"attempt {attempt}: {seqs}")

    def test_blocks_endpoint_reads_the_configured_store(self):
        self.store.put_block(80, 20, 0, "stone")
        with patch.dict("os.environ", {"MIMO_DB_PATH": str(self.path)}):
            from backend.api.mimo import get_mimo_blocks
            result = get_mimo_blocks(since=0, limit=5000)
        self.assertEqual(result["changes"], [{"x": 80, "y": 20, "z": 0, "material": "stone"}])


if __name__ == "__main__":
    unittest.main()

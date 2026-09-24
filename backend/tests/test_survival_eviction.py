import sqlite3
import unittest

from backend.survival.blueprints import Blueprint, Planned
from backend.survival.creatures.eviction import evict
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid


def walled_off():
    """Solid rock everywhere: `outside` finds nowhere standable to put an evicted creature."""
    return Grid(lambda x, y, z: "stone")


def shelter_blueprint():
    """Just enough of a shelter's blueprint for `evict`: a door and the cell in front of it."""
    return Blueprint("shelter", "Test Hut", (0, 1, 0), (Planned((0, 1, -1), "door", "door"),), front=(0, 1, -2))


class EvictionTests(unittest.TestCase):
    def herd(self):
        db = sqlite3.connect(":memory:")
        create_creature_tables(db)
        return Herd(db)

    def test_a_tame_animal_with_no_room_outside_is_left_alive_where_it_stands(self):
        """L3 Task 11 carry-over (fix round 1, item 5): resolution 24 has a tame animal stay where
        it grew, so eviction must never delete it, even with nowhere to put it outside."""
        grid = walled_off()
        herd = self.herd()
        grid.herd = herd
        grid.claims.add((0, 1, 0))
        tame = herd.add("rabbit", (0, 1, 0), 3.0, 0.0, 0.0, {"home": [0, 1, 0], "pose": "idle", "tame": True})
        wild = herd.add("rabbit", (0, 1, 0), 3.0, 0.0, 0.0, {"home": [0, 1, 0], "pose": "idle"})

        moved = evict(grid, shelter_blueprint())

        self.assertEqual(moved, [])
        self.assertIsNotNone(herd.get(tame["id"]))  # left alive, right where it was
        self.assertEqual((herd.get(tame["id"])["x"], herd.get(tame["id"])["y"], herd.get(tame["id"])["z"]),
                         (0.0, 1.0, 0.0))
        self.assertIsNone(herd.get(wild["id"]))  # a wild animal keeps today's behaviour: removed

    def test_a_tame_animal_is_moved_outside_when_there_is_room(self):
        def rule(x, y, z):
            if y <= 0:
                return "stone"
            return "air"
        grid = Grid(rule)
        herd = self.herd()
        grid.herd = herd
        grid.claims.add((0, 1, 0))
        tame = herd.add("rabbit", (0, 1, 0), 3.0, 0.0, 0.0, {"home": [0, 1, 0], "pose": "idle", "tame": True})

        moved = evict(grid, shelter_blueprint())

        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["id"], tame["id"])
        saved = herd.get(tame["id"])
        self.assertTrue(saved["state"]["tame"])
        self.assertEqual(saved["state"]["home"], list(map(int, (saved["x"], saved["y"], saved["z"]))))
        self.assertNotEqual((saved["x"], saved["y"], saved["z"]), (0.0, 1.0, 0.0))


if __name__ == "__main__":
    unittest.main()

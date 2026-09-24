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
    """Just enough of a shelter's blueprint for `evict`: the room cell Mimo lives in, a door and the
    cell in front of it."""
    return Blueprint("shelter", "Test Hut", (0, 1, 0),
                     (Planned((0, 1, 0), "room", "air"), Planned((0, 1, -1), "door", "door")), front=(0, 1, -2))


def open_ground():
    return Grid(lambda x, y, z: "stone" if y <= 0 else "air")


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
        grid = open_ground()
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


    def test_an_animal_in_a_nearby_pen_stays_put_when_a_shelter_goes_up(self):
        """L3 final fix wave: eviction took every creature on any claimed cell within 8 blocks of
        the new shelter, so a tame sheep in a pen 5 blocks away was pulled out beside the door. Only
        the shelter's own cells are cleared now."""
        grid = open_ground()
        herd = self.herd()
        grid.herd = herd
        grid.claims.update({(0, 1, 0), (5, 1, 0)})  # the shelter's room, and a cell of a pen near it
        inside = herd.add("rabbit", (0, 1, 0), 3.0, 0.0, 0.0, {"home": [0, 1, 0], "pose": "idle"})
        penned = herd.add("sheep", (5, 1, 0), 8.0, 0.0, 0.0, {"home": [5, 1, 0], "pose": "idle", "tame": True})

        moved = evict(grid, shelter_blueprint())

        self.assertEqual([creature["id"] for creature in moved], [inside["id"]])
        saved = herd.get(penned["id"])
        self.assertEqual((saved["x"], saved["y"], saved["z"], saved["state"]["home"]), (5.0, 1.0, 0.0, [5, 1, 0]))


if __name__ == "__main__":
    unittest.main()

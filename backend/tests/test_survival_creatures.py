import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.creatures.kinds import KINDS, Kind, huntable, kind_of, land_kinds, register_kind, water_kinds
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid, world_grid
from backend.survival.world import SurvivalWorld, new_survival_state


def herd():
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    return Herd(db)


class KindTests(unittest.TestCase):
    def test_the_four_animals_and_fish_are_registered_with_the_spec_values(self):
        self.assertEqual({name: KINDS[name].health for name in ("rabbit", "chicken", "sheep", "cow", "fish")},
                         {"rabbit": 3.0, "chicken": 4.0, "sheep": 8.0, "cow": 10.0, "fish": 2.0})
        self.assertLess(KINDS["rabbit"].speed, KINDS["cow"].speed)  # seconds per block: the rabbit is fast
        self.assertEqual(KINDS["rabbit"].drops, {"raw_rabbit": (1, 1), "rabbit_hide": 0.5})
        self.assertEqual(KINDS["chicken"].drops, {"raw_chicken": (1, 1), "feather": (0, 2)})
        self.assertEqual(KINDS["sheep"].drops, {"raw_mutton": (1, 2), "wool": (1, 2)})
        self.assertEqual(KINDS["cow"].drops, {"raw_beef": (1, 3), "leather": (0, 2)})
        self.assertTrue(KINDS["fish"].water)
        self.assertEqual(KINDS["fish"].drops, {})
        for kind in KINDS.values():
            self.assertFalse(kind.hostile)
            self.assertTrue(kind.flee_when_hurt)
            self.assertLessEqual(kind.herd[0], kind.herd[1])

    def test_kinds_by_biome_and_what_mimo_hunts(self):
        self.assertEqual([kind.name for kind in land_kinds("meadow")], ["rabbit", "chicken", "sheep", "cow"])
        self.assertEqual([kind.name for kind in land_kinds("desert")], ["rabbit"])
        self.assertEqual([kind.name for kind in water_kinds()], ["fish"])
        self.assertTrue(huntable(KINDS["cow"]))
        self.assertFalse(huntable(KINDS["fish"]))
        self.assertFalse(huntable(None))
        self.assertIsNone(kind_of("dragon"))
        self.assertIsNone(kind_of(None))

    def test_a_hostile_kind_registers_like_any_other_and_is_not_hunted_or_spawned_as_a_herd(self):
        gloom = register_kind(Kind("test_gloom", health=20.0, speed=1.0, size=1.6, hostile=True, damage=3.0,
                                   reach=1.5, biomes=("meadow",)))
        try:
            self.assertIs(kind_of("test_gloom"), gloom)
            self.assertFalse(huntable(gloom))
            self.assertNotIn(gloom, land_kinds("meadow"))
        finally:
            del KINDS["test_gloom"]


class HerdTests(unittest.TestCase):
    def test_creatures_are_added_read_near_saved_and_removed(self):
        creatures = herd()
        cow = creatures.add("cow", (3, 1, 4), 10.0, 5.0, 6.0, {"home": [3, 1, 4], "pose": "idle", "turn": 0})
        far = creatures.add("rabbit", (90, 1, 0), 3.0, 5.0, 6.0, {})
        self.assertEqual((cow["kind"], cell_of(cow), cow["health"], cow["heading"], cow["spawned_at"], cow["next_at"]),
                         ("cow", (3, 1, 4), 10.0, 0.0, 5.0, 6.0))
        self.assertEqual([found["id"] for found in creatures.near(0, 0, 48)], [cow["id"]])
        cow.update(x=4.0, heading=1.5, health=6.0, next_at=9.0)
        cow["state"]["pose"] = "walking"
        creatures.save(cow)
        again = creatures.get(cow["id"])
        self.assertEqual((again["x"], again["heading"], again["health"], again["next_at"], again["state"]["pose"]),
                         (4.0, 1.5, 6.0, 9.0, "walking"))
        self.assertFalse(dead(again))
        creatures.remove(far["id"])
        self.assertIsNone(creatures.get(far["id"]))

    def test_chunks_count_their_living_animals_and_empty_when_the_last_one_dies(self):
        creatures = herd()
        creatures.note_chunk((1, 2), 2, 2, 10.0)
        creatures.note_chunk((5, 5), 1, 0, 10.0)  # its herd could not stand anywhere
        creatures.note_chunk((1, 2), 0, 0, 99.0)  # noted once: a second note changes nothing
        creatures.lost([1, 2], 20.0)
        self.assertEqual(creatures.chunks((1, 2), (1, 2))[(1, 2)]["animals"], 1)
        self.assertIsNone(creatures.chunks((1, 2), (1, 2))[(1, 2)]["empty_since"])
        creatures.lost([1, 2], 30.0)
        creatures.lost([1, 2], 40.0)
        self.assertEqual(creatures.chunks((0, 0), (9, 9)), {
            (1, 2): {"cx": 1, "cz": 2, "herds": 2, "animals": 0, "spawned_at": 10.0, "empty_since": 30.0},
            (5, 5): {"cx": 5, "cz": 5, "herds": 1, "animals": 0, "spawned_at": 10.0, "empty_since": 10.0}})
        creatures.regained((1, 2), 3, 50.0)
        self.assertEqual(creatures.chunks((1, 2), (1, 2))[(1, 2)]["animals"], 3)
        self.assertIsNone(creatures.chunks((1, 2), (1, 2))[(1, 2)]["empty_since"])
        creatures.lost(None, 60.0)  # a creature with no home chunk changes nothing

    def test_a_database_without_the_tables_reads_as_no_creatures(self):
        empty = Herd(sqlite3.connect(":memory:"))
        self.assertEqual((empty.near(0, 0, 48), empty.get(1), empty.chunks((0, 0), (1, 1))), ([], None, {}))


class WorldTests(unittest.TestCase):
    def test_every_world_has_the_creature_tables_and_its_grid_reaches_them(self):
        with tempfile.TemporaryDirectory() as root:
            state = new_survival_state(name="Pip", seed="1", spawn={"x": 0, "y": 1, "z": 0}, born_at=0.0, traits={})
            world = SurvivalWorld.create(Path(root) / "world.sqlite3", state)
            with world.transaction() as db:
                grid = world_grid(db, "1")
                grid.herd.add("sheep", (2, 1, 2), 8.0, 0.0, 1.0, {})
                create_creature_tables(db)  # again: changes nothing
            with world.connect() as db:
                self.assertEqual([found["kind"] for found in world_grid(db, "1").herd.near(0, 0, 10)], ["sheep"])
        self.assertIsNone(Grid(lambda x, y, z: "air").herd)


if __name__ == "__main__":
    unittest.main()

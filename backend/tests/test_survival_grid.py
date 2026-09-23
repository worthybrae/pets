import tempfile
import unittest
from pathlib import Path

from backend.services.block_table import material_in
from backend.services.worldgen import terrain_height
from backend.survival.grid import Grid, world_grid
from backend.survival.world import SurvivalWorld, new_survival_state

SEED = "123456789123456789"
SPAWN = {"x": 3682, "y": 5, "z": 4143}


def small_world(cells):
    """Stone at y <= 0 and air above, with `cells` overriding single cells."""
    return Grid(lambda x, y, z: cells.get((x, y, z), "stone" if y <= 0 else "air"))


class GridTests(unittest.TestCase):
    def test_edits_win_and_a_plant_over_an_edited_cell_is_air(self):
        grid = small_world({(0, 1, 0): "tall_grass"})
        self.assertEqual(grid.material(0, 1, 0), "tall_grass")
        grid.put(0, 0, 0, "air")
        self.assertEqual(grid.material(0, 0, 0), "air")
        self.assertEqual(grid.material(0, 1, 0), "air")

    def test_body_rules(self):
        grid = small_world({(1, 0, 0): "water", (2, 1, 0): "water", (3, 1, 0): "tall_grass", (4, 1, 0): "lava",
                            (5, 0, 0): "air"})
        self.assertTrue(grid.standable((0, 1, 0)))
        self.assertFalse(grid.swimming((0, 1, 0)))
        self.assertTrue(grid.standable((1, 1, 0)))
        self.assertTrue(grid.swimming((1, 1, 0)))
        self.assertTrue(grid.water((2, 1, 0)))
        self.assertFalse(grid.passable((2, 1, 0)))
        self.assertTrue(grid.standable((3, 1, 0)))
        self.assertFalse(grid.passable((4, 1, 0)))
        self.assertFalse(grid.supported((5, 1, 0)))
        self.assertTrue(grid.solid((0, 0, 0)))
        self.assertFalse(grid.standable((0, 0, 0)))

    def test_natural_blocks_are_generated_once_per_cell(self):
        calls = []

        def natural(x, y, z):
            calls.append((x, y, z))
            return "air"

        grid = Grid(natural)
        for _ in range(3):
            grid.material(4, 5, 6)
        self.assertEqual(calls, [(4, 5, 6)])

    def test_placed_near_finds_workstations_within_reach(self):
        grid = small_world({})
        grid.put(3, 1, 4, "crafting_table")
        grid.put(20, 1, 0, "furnace")
        self.assertEqual(grid.placed_near(0, 0, 6, ("crafting_table", "furnace")), {"crafting_table"})


class WorldGridTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.world = SurvivalWorld.create(Path(self.directory.name) / "2.sqlite3", new_survival_state(
            name="Pip", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={}))

    def tearDown(self):
        self.directory.cleanup()

    def test_matches_the_world_database_cell_for_cell(self):
        x0, z0 = SPAWN["x"], SPAWN["z"]
        ground = terrain_height(x0, z0, SEED)
        self.world.put_block(x0, ground, z0, "air")
        self.world.put_block(x0 + 1, ground + 1, z0, "planks")
        self.world.put_block(x0 + 17, ground, z0 - 1, "stone")  # in the next chunk
        with self.world.connect() as db:
            grid = world_grid(db, SEED)
            for x in range(x0 - 2, x0 + 19):
                for z in (z0 - 1, z0, z0 + 1):
                    for y in range(ground - 2, ground + 7):
                        self.assertEqual(grid.material(x, y, z), material_in(db, x, y, z, SEED), (x, y, z))

    def test_put_writes_a_numbered_block_change(self):
        x, z = SPAWN["x"], SPAWN["z"]
        with self.world.transaction() as db:
            world_grid(db, SEED).put(x, 40, z, "planks")
        self.assertEqual(self.world.blocks_seq(), 1)
        self.assertEqual(self.world.material_at(x, 40, z), "planks")


if __name__ == "__main__":
    unittest.main()

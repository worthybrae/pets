import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.services.worldgen import block_at, plant_at, terrain_height
from backend.survival.grid import Grid
from backend.survival.senses import food_near, grass_near, near_failure, plants_in_chunk, shores_near, standing_logs
from backend.survival.situation import Situation

SEED = "123456789123456789"


def real():
    """The generated world of SEED."""
    return Grid(lambda x, y, z: block_at(x, y, z, SEED))


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


def first_plant(kind):
    """The first cell (scanning a strip of generated land) where worldgen grows `kind`."""
    for x in range(300, 900):
        for z in range(-40, 40):
            if plant_at(x, z, SEED) == kind:
                return x, terrain_height(x, z, SEED) + 1, z
    raise AssertionError(f"no {kind} found")


class PlantSenseTests(unittest.TestCase):
    def test_a_chunk_lists_its_wild_plants_once(self):
        bush = first_plant("berry_bush_ripe")
        plants = dict(plants_in_chunk(bush[0] // 16, bush[2] // 16, SEED))
        self.assertEqual(plants[bush], "berry_bush_ripe")
        self.assertTrue(all(kind == plant_at(cell[0], cell[2], SEED) for cell, kind in plants.items()))
        self.assertIs(plants_in_chunk(bush[0] // 16, bush[2] // 16, SEED),
                      plants_in_chunk(bush[0] // 16, bush[2] // 16, SEED))

    def test_ripe_food_is_listed_nearest_first_until_picked_and_again_when_it_grew_back(self):
        bush = first_plant("berry_bush_ripe")
        grid, here = real(), (bush[0] + 3, bush[1], bush[2])
        found = food_near(grid, SEED, here, 8)
        self.assertIn(bush, found)
        self.assertEqual(found, sorted(found, key=lambda cell: (math.dist(cell, here), cell)))
        grid.put(*bush, "berry_bush")
        self.assertNotIn(bush, food_near(grid, SEED, here, 8))
        grid.put(*bush, "berry_bush_ripe")
        self.assertIn(bush, food_near(grid, SEED, here, 8))

    def test_food_known_to_be_poisonous_is_left_out(self):
        grid = meadow()
        grid.put(2, 1, 0, "red_mushroom")
        grid.put(3, 1, 0, "brown_mushroom")
        self.assertEqual(food_near(grid, SEED, (0, 1, 0), 8), [(2, 1, 0), (3, 1, 0)])
        self.assertEqual(food_near(grid, SEED, (0, 1, 0), 8, avoid=("red_mushroom",)), [(3, 1, 0)])

    def test_tall_grass_counts_while_it_stands(self):
        grass = first_plant("tall_grass")
        grid = real()
        self.assertIn(grass, grass_near(grid, SEED, grass, 4))
        grid.put(*grass, "air")
        self.assertNotIn(grass, grass_near(grid, SEED, grass, 4))


@patch("backend.survival.senses.terrain_height", lambda x, z, seed: 0 if x >= 3 else 2)
class ShoreTests(unittest.TestCase):
    def test_a_shore_cell_comes_with_water_within_reach(self):
        lake = Grid(lambda x, y, z: ("water" if 1 <= y <= 2 else "stone" if y <= 0 else "air") if x >= 3
                    else ("stone" if y <= 2 else "air"))
        shores = shores_near(lake, SEED, (0, 3, 0), 6)
        self.assertEqual(shores[0], ((2, 3, 0), (3, 2, 0)))
        self.assertTrue(all(stand[0] == 2 and water[0] == 3 and water[1] == 2 for stand, water in shores))
        lake.put(3, 2, 0, "dirt")
        self.assertNotIn(((2, 3, 0), (3, 2, 0)), shores_near(lake, SEED, (0, 3, 0), 6))


class GrownTreeTests(unittest.TestCase):
    @patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [])
    def test_trees_grown_from_saplings_count_as_trees(self):
        grid = meadow()
        for y in (1, 2, 3, 4):
            grid.put(6, y, 0, "oak_log")
        grown = {(6, 0)}  # a sapling Mimo planted there
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0), grown=grown), [(6, 1, 0), (6, 2, 0), (6, 3, 0), (6, 4, 0)])
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0), skip={(6, 0)}, grown=grown), [])

    @patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [])
    def test_placed_logs_that_did_not_grow_from_a_sapling_are_not_a_tree(self):
        grid = meadow()
        for y in (1, 2):
            grid.put(6, y, 0, "oak_log")  # a log wall, say
        self.assertEqual(standing_logs(grid, SEED, (0, 1, 0)), [])


class FailureTests(unittest.TestCase):
    def test_cells_near_a_failed_step_are_left_alone_for_a_while(self):
        state = {"recent_actions": [{"kind": "walk", "result": "failed", "target": {"x": 10, "y": 1, "z": 0}},
                                    {"kind": "walk", "result": "done", "target": {"x": 30, "y": 1, "z": 0}}]}
        self.assertTrue(near_failure(state, (13, 5, 0)))
        self.assertFalse(near_failure(state, (15, 1, 0)))
        self.assertFalse(near_failure(state, (30, 1, 0)))
        self.assertFalse(near_failure({}, (10, 1, 0)))


class SensedTests(unittest.TestCase):
    def test_a_situation_looks_once_per_key(self):
        looks = []
        s = Situation({}, meadow(), {}, 0.0, sqlite3.connect(":memory:"))
        for _ in range(3):
            self.assertEqual(s.sensed("food", lambda: looks.append(1) or ["bush"]), ["bush"])
        self.assertEqual(len(looks), 1)


if __name__ == "__main__":
    unittest.main()

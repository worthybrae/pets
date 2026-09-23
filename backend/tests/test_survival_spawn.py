import math
import random
import unittest

from backend.services.blocks import is_replaceable
from backend.services.worldgen import SEA_LEVEL, biome_at, block_at, surface_material, terrain_height, trees_in_chunk
from backend.survival.spawn import MAX_DISTANCE, MIN_DISTANCE, find_spawn, ring_points, spawn_fits

SEEDS = ("1", "123456789123456789", "987654321987654321")


def trees_within(x, z, seed, reach):
    found = []
    for cx in range((x - reach) // 16 - 1, (x + reach) // 16 + 2):
        for cz in range((z - reach) // 16 - 1, (z + reach) // 16 + 2):
            found += [tree for tree in trees_in_chunk(cx, cz, seed) if math.hypot(tree[0] - x, tree[1] - z) <= reach]
    return found


class SpawnTests(unittest.TestCase):
    def test_spawn_follows_every_rule(self):
        for index, seed in enumerate(SEEDS):
            spawn = find_spawn(seed, random.Random(index))
            x, y, z = spawn["x"], spawn["y"], spawn["z"]
            self.assertTrue(MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE, spawn)
            self.assertIn(biome_at(x, z, seed), ("meadow", "forest"))
            self.assertIn(surface_material(x, z, seed), ("grass", "moss"))
            self.assertEqual(y, terrain_height(x, z, seed) + 1)
            self.assertGreaterEqual(y - 1, SEA_LEVEL)
            for cell_y in (y, y + 1):
                here = block_at(x, cell_y, z, seed)
                self.assertTrue(is_replaceable(here) and here != "water", (spawn, here))
            self.assertTrue(trees_within(x, z, seed, 24), f"no tree near {spawn}")

    def test_the_same_seed_and_random_state_give_the_same_spawn(self):
        self.assertEqual(find_spawn("42", random.Random(9)), find_spawn("42", random.Random(9)))

    def test_spawn_fits_rejects_the_home_region_deserts_and_water(self):
        seed = SEEDS[1]
        self.assertFalse(spawn_fits(100, 0, seed))
        desert = water = None
        for x in range(3100, 5900, 23):
            for z in range(-2000, 2000, 29):
                if not MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE:
                    continue
                if desert is None and biome_at(x, z, seed) == "desert":
                    desert = (x, z)
                if water is None and terrain_height(x, z, seed) < SEA_LEVEL:
                    water = (x, z)
            if desert and water:
                break
        self.assertIsNotNone(desert)
        self.assertIsNotNone(water)
        self.assertFalse(spawn_fits(*desert, seed))
        self.assertFalse(spawn_fits(*water, seed))

    def test_ring_points_walk_the_square_perimeter(self):
        self.assertEqual(list(ring_points(0, 0, 0, 4)), [(0, 0)])
        ring = list(ring_points(10, 20, 1, 1))
        self.assertEqual(len(ring), 8)
        self.assertEqual(set(ring), {(10 + dx, 20 + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1)} - {(10, 20)})
        wide = list(ring_points(0, 0, 2, 4))
        self.assertEqual(len(wide), 16)
        self.assertEqual(len(set(wide)), 16)
        self.assertTrue(all(max(abs(x), abs(z)) == 8 for x, z in wide))


if __name__ == "__main__":
    unittest.main()

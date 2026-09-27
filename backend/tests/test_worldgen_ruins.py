import math
import unittest

from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, RUIN_HALF, RUIN_REGION, RUIN_SLOPE, SEA_LEVEL, block_at, plant_stack,
    region_ruin, rock_column, ruin_column, surface_opened, terrain_height, tree_base,
)

SEED = "123456789123456789"
WALLS = ("stone_bricks", "mossy_cobblestone")


def ruins(count=6, rxs=range(3, 60)):
    found = []
    for rx in rxs:
        for rz in range(-30, 30):
            ruin = region_ruin(rx, rz, SEED)
            if ruin is not None:
                found.append(ruin)
                if len(found) == count:
                    return found
    return found


def square(ruin):
    x, z, _ = ruin
    return [(x + dx, z + dz) for dx in range(-RUIN_HALF, RUIN_HALF + 1) for dz in range(-RUIN_HALF, RUIN_HALF + 1)]


class RuinTests(unittest.TestCase):
    def test_some_regions_hold_a_ruin_and_the_same_seed_always_places_it_the_same(self):
        found = [region_ruin(rx, rz, SEED) for rx in range(30, 50) for rz in range(-10, 10)]
        share = sum(ruin is not None for ruin in found) / len(found)
        self.assertTrue(0.15 < share < 0.4, share)
        region_ruin.cache_clear()
        self.assertEqual(found, [region_ruin(rx, rz, SEED) for rx in range(30, 50) for rz in range(-10, 10)])
        self.assertNotEqual(found, [region_ruin(rx, rz, "42") for rx in range(30, 50) for rz in range(-10, 10)])

    def test_none_stands_near_the_legacy_clearing(self):
        # Task 5 review, Important (test only): the old version of this test passed even with the
        # guard removed -- on SEED, the regions nearest the origin never happened to roll a ruin, so
        # "ruin is None or far enough" was true for the wrong reason. This checks every region whose
        # centre lies within the guarded band (region_ruin's own bound: LEGACY_RADIUS + RUIN_REGION)
        # is unconditionally None, over several seeds including the legacy world's own, so removing
        # the guard (which places a ruin ~198 blocks out on the legacy seed) fails it.
        reach = int((LEGACY_RADIUS + RUIN_REGION) // RUIN_REGION) + 1
        seeds = (SEED, "1", "42", "7", "24680", "99999", LEGACY_WORLD_SEED)
        checked = 0
        for seed in seeds:
            for rx in range(-reach, reach + 1):
                for rz in range(-reach, reach + 1):
                    x0, z0 = rx * RUIN_REGION, rz * RUIN_REGION
                    if math.hypot(x0 + RUIN_REGION / 2, z0 + RUIN_REGION / 2) > LEGACY_RADIUS + RUIN_REGION:
                        continue
                    checked += 1
                    self.assertIsNone(region_ruin(rx, rz, seed), (seed, rx, rz))
        self.assertGreater(checked, 20)  # the band around the origin was actually exercised

    def test_it_stands_on_dry_even_ground_with_no_tree_rock_or_cave_mouth(self):
        for ruin in ruins(8) + ruins(4, range(-60, -3)):
            for x, z in square(ruin):
                height = terrain_height(x, z, SEED)
                self.assertGreater(height, SEA_LEVEL)
                self.assertLessEqual(abs(height - ruin[2]), RUIN_SLOPE)
                self.assertFalse(surface_opened(x, z, SEED))
                self.assertIsNone(tree_base(x, z, SEED))
                self.assertIsNone(rock_column(x, z, SEED))

    def test_an_old_chest_in_the_middle_and_broken_walls_of_stone_bricks_and_moss_round_it(self):
        for ruin in ruins(6):
            x, z, ground = ruin
            self.assertEqual(block_at(x, ground + 1, z, SEED), "chest")
            self.assertEqual(block_at(x, ground + 2, z, SEED), "air")
            walls = [(wx, wz) for wx, wz in square(ruin) if max(abs(wx - x), abs(wz - z)) == RUIN_HALF]
            standing = [cell for cell in walls if ruin_column(*cell, SEED)]
            self.assertLess(len(standing), len(walls))  # a doorway, and gaps where the wall fell
            for wx, wz in standing:
                _, top = ruin_column(wx, wz, SEED)
                ground_here = terrain_height(wx, wz, SEED)
                self.assertTrue(ground_here + 1 <= top <= ground_here + 3)
                self.assertEqual({block_at(wx, y, wz, SEED) in WALLS for y in range(ground_here + 1, top + 1)}, {True})
                self.assertEqual(block_at(wx, top + 1, wz, SEED), "air")
                self.assertIsNone(plant_stack(wx, wz, SEED))
            for corner in ((x - RUIN_HALF, z - RUIN_HALF), (x + RUIN_HALF, z + RUIN_HALF)):
                self.assertEqual(ruin_column(*corner, SEED)[1], terrain_height(*corner, SEED) + 3)
            inside = [(wx, wz) for wx, wz in square(ruin) if 0 < max(abs(wx - x), abs(wz - z)) < RUIN_HALF]
            self.assertTrue(all(ruin_column(wx, wz, SEED) is None for wx, wz in inside))


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.services.worldgen import (
    LEGACY_WORLD_SEED, base_material, biome_at, cave_at, hash32, terrain_height,
)


class WorldgenTests(unittest.TestCase):
    def test_same_seed_recreates_chunks_and_uses_full_64_bits(self):
        sample = [(x, z) for x in range(200, 260, 7) for z in range(-250, -190, 9)]
        first = [terrain_height(x, z, "123456789123456789") for x, z in sample]
        self.assertEqual(first, [terrain_height(x, z, "123456789123456789") for x, z in sample])
        self.assertNotEqual(first, [terrain_height(x, z, "123456789123456790") for x, z in sample])
        self.assertNotEqual(hash32(2, 3, 4, "1"), hash32(2, 3, 4, str(1 + (1 << 32))))

    def test_existing_clearing_and_underground_are_preserved(self):
        self.assertEqual(terrain_height(0, 0, LEGACY_WORLD_SEED), 0)
        self.assertEqual(terrain_height(48, 0, LEGACY_WORLD_SEED), 0)
        self.assertEqual(base_material(0, -1, 0, LEGACY_WORLD_SEED), "dirt")
        self.assertEqual(base_material(0, -5, 0, LEGACY_WORLD_SEED), "bedrock")
        self.assertEqual(terrain_height(40, 20, "1"), terrain_height(40, 20, "2"))

    def test_generated_region_has_height_biomes_caves_and_ores(self):
        seed = "123456789123456789"
        points = [(x, z) for x in range(180, 520, 12) for z in range(-500, 500, 24)]
        heights = [terrain_height(x, z, seed) for x, z in points]
        biomes = {biome_at(x, z, seed) for x, z in points}
        self.assertGreater(max(heights), min(heights) + 8)
        self.assertGreaterEqual(len(biomes), 3)
        self.assertTrue(any(cave_at(x, -3, z, seed) for x, z in points))
        materials = {base_material(x, -3, z, seed) for x, z in points}
        self.assertIn("stone", materials)
        self.assertIn("air", materials)
        self.assertTrue({"iron_ore", "coal_ore", "copper_ore"} & materials)


if __name__ == "__main__":
    unittest.main()

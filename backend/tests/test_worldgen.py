import json
import unittest

from backend.services.worldgen import (
    LEGACY_WORLD_SEED, base_material, biome_at, block_at, cave_at, hash32, legacy_hash, plant_at,
    surface_material, terrain_height, trees_in_chunk,
)
from backend.scripts.worldgen_fixture import FIXTURE_PATH, build_fixture


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


class NaturalBlockTests(unittest.TestCase):
    def test_home_clearing_matches_what_the_viewer_always_drew(self):
        seed = LEGACY_WORLD_SEED
        expected = {
            (5, 0, -4): "dirt_path",      # cottage floor
            (4, 1, -4): "plaster",        # cottage wall
            (5, 1, -3): "air",            # doorway
            (5, 2, -6): "glass",          # window
            (3, 4, -7): "roof_tile",
            (-6, 3, -4): "oak_log",       # big tree trunk
            (-6, 5, -4): "oak_log",       # trunk wins over canopy
            (-7, 5, -4): "leaves",
            (-6, 7, -4): "leaves",
            (-8, 1, 0): "flower_orange",
            (-5, 0, 4): "water",          # pond
            (-3, 0, 2): "dirt_path",      # stepping stone
            (3, 0, -2): "dirt_path",      # walkway
            (0, -1, 0): "dirt",
        }
        for (x, y, z), material in expected.items():
            self.assertEqual(block_at(x, y, z, seed), material, (x, y, z))

    def test_javascript_hash_is_reproduced(self):
        # Values from the viewer: Math.abs((x * 73856093) ^ (z * 19349663)).
        self.assertEqual(legacy_hash(0, 0), 0)
        self.assertEqual(legacy_hash(1, 0), 73856093)
        self.assertEqual(legacy_hash(100, 100), 882750904)  # 100 * 73856093 overflows int32
        self.assertEqual(legacy_hash(-7, 3), 497381208)

    def test_generated_trees_have_trunk_and_canopy_inside_their_chunk(self):
        seed = "123456789123456789"
        trees = [tree for cx in range(20, 40) for cz in range(-10, 10) for tree in trees_in_chunk(cx, cz, seed)]
        self.assertGreater(len(trees), 5)
        for tx, tz, _ in trees:
            self.assertTrue(3 <= tx % 16 <= 12 and 3 <= tz % 16 <= 12)
        x, z, base = trees[0]
        self.assertEqual([block_at(x, base + dy, z, seed) for dy in range(1, 7)],
                         ["oak_log"] * 4 + ["leaves", "leaves"])
        if terrain_height(x + 1, z, seed) < base + 5:
            self.assertEqual(block_at(x + 1, base + 5, z, seed), "leaves")

    def test_plants_grow_on_open_grass_only(self):
        seed = "123456789123456789"
        found = {}
        for x in range(300, 460):
            for z in range(-80, 80):
                plant = plant_at(x, z, seed)
                if plant:
                    found.setdefault(plant, (x, z))
                    self.assertIn(surface_material(x, z, seed), ("grass", "moss"))
        self.assertIn("tall_grass", found)
        x, z = found["tall_grass"]
        self.assertEqual(block_at(x, terrain_height(x, z, seed) + 1, z, seed), "tall_grass")
        self.assertIsNone(plant_at(0, 0, seed))
        self.assertIs(base_material, block_at)


class FixtureTests(unittest.TestCase):
    def test_shared_fixture_matches_python_worldgen(self):
        saved = json.loads(FIXTURE_PATH.read_text())
        self.assertTrue(build_fixture() == saved,
                        "Worldgen output changed. Run: python3 -m backend.scripts.worldgen_fixture")

    def test_fixture_covers_every_natural_feature(self):
        materials = set(json.loads(FIXTURE_PATH.read_text())["materials"])
        for name in ("oak_log", "leaves", "tall_grass", "plaster", "roof_tile", "dirt_path",
                     "water", "sand", "stone", "bedrock", "grass"):
            self.assertIn(name, materials)

    def test_fixture_covers_generated_trees_at_negative_x(self):
        fixture = json.loads(FIXTURE_PATH.read_text())
        oak_log = fixture["materials"].index("oak_log")
        self.assertTrue(any(x < -16 for _, x, _, _, material in fixture["cells"] if material == oak_log),
                        "fixture has no oak_log cells with x < -16")


if __name__ == "__main__":
    unittest.main()

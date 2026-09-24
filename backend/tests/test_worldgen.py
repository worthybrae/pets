import json
import math
import unittest

from backend.services.blocks import is_solid
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, TREE_LEAVES, TREE_LOGS, base_material, biome_at, block_at, cave_at, cave_plant,
    hash32, legacy_hash, plant_at, plant_stack, surface_material, terrain_height, tree_kind, trees_in_chunk, wild_food,
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
        kind = tree_kind(x, z, seed)
        self.assertEqual([block_at(x, base + dy, z, seed) for dy in range(1, 7)],
                         [TREE_LOGS[kind]] * 4 + [TREE_LEAVES[kind]] * 2)
        if terrain_height(x + 1, z, seed) < base + 5:
            self.assertEqual(block_at(x + 1, base + 5, z, seed), TREE_LEAVES[kind])

    def test_plants_grow_on_the_ground_their_biome_offers(self):
        seed = "123456789123456789"
        found = {}
        for x in range(300, 460):
            for z in range(-80, 80):
                plant = plant_at(x, z, seed)
                if plant:
                    found.setdefault(plant, (x, z))
                    ground = surface_material(x, z, seed)
                    self.assertIn(ground, ("grass", "moss", "mud", "sand", "gravel"))
                    if ground in ("sand", "gravel"):  # desert plants, or sugar cane on a shore
                        self.assertIn(plant_stack(x, z, seed)[0], ("cactus", "dead_bush", "sugar_cane"))
        self.assertIn("tall_grass", found)
        x, z = found["tall_grass"]
        self.assertEqual(block_at(x, terrain_height(x, z, seed) + 1, z, seed), "tall_grass")
        self.assertIsNone(plant_at(0, 0, seed))
        self.assertIs(base_material, block_at)


class WildFoodTests(unittest.TestCase):
    def test_bushes_grow_in_meadows_and_forest_edges_and_mushrooms_on_the_forest_floor(self):
        seed = "123456789123456789"
        found = {}
        for x in range(300, 900):
            for z in range(-40, 40):
                food = wild_food(x, z, seed)
                if food is None:
                    continue
                expected = ("meadow", "forest") if food == "berry_bush_ripe" else ("forest",)
                self.assertIn(biome_at(x, z, seed), expected, (x, z, food))
                if plant_at(x, z, seed) == food:
                    found.setdefault(food, (x, z))
        self.assertEqual(set(found), {"berry_bush_ripe", "brown_mushroom", "red_mushroom"})
        for food, (x, z) in found.items():
            self.assertEqual(block_at(x, terrain_height(x, z, seed) + 1, z, seed), food)

    def test_the_legacy_clearing_grows_no_wild_food(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 3):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 3):
                if math.hypot(x, z) <= LEGACY_RADIUS:
                    self.assertIsNone(wild_food(x, z, LEGACY_WORLD_SEED), (x, z))

    def test_mushrooms_grow_on_cave_floors(self):
        seed = "123456789123456789"
        found = [(x, y, z) for x in range(250, 700, 3) for z in range(-100, 100, 3)
                 for y in range(-4, terrain_height(x, z, seed) - 2) if cave_plant(x, y, z, seed)]
        self.assertGreater(len(found), 5)
        for x, y, z in found[:5]:
            self.assertIn(block_at(x, y, z, seed), ("brown_mushroom", "red_mushroom"))
            self.assertTrue(is_solid(block_at(x, y - 1, z, seed)), (x, y, z))


class FixtureTests(unittest.TestCase):
    def test_shared_fixture_matches_python_worldgen(self):
        saved = json.loads(FIXTURE_PATH.read_text())
        self.assertTrue(build_fixture() == saved,
                        "Worldgen output changed. Run: python3 -m backend.scripts.worldgen_fixture")

    def test_fixture_covers_every_natural_feature(self):
        materials = set(json.loads(FIXTURE_PATH.read_text())["materials"])
        for name in ("oak_log", "leaves", "tall_grass", "plaster", "roof_tile", "dirt_path",
                     "water", "sand", "stone", "bedrock", "grass", "berry_bush_ripe", "brown_mushroom", "red_mushroom",
                     "birch_log", "birch_leaves", "spruce_log", "spruce_leaves", "snow", "snow_block", "ice", "mud",
                     "cactus", "sugar_cane", "dead_bush", "fern", "pumpkin", "melon", "gravel", "lava", "gold_ore",
                     "diamond_ore", "granite", "andesite", "diorite", "ashstone"):
            self.assertIn(name, materials)

    def test_fixture_covers_generated_trees_at_negative_x(self):
        fixture = json.loads(FIXTURE_PATH.read_text())
        oak_log = fixture["materials"].index("oak_log")
        self.assertTrue(any(x < -16 for _, x, _, _, material in fixture["cells"] if material == oak_log),
                        "fixture has no oak_log cells with x < -16")

    def test_fixture_covers_far_survival_coordinates(self):
        fixture = json.loads(FIXTURE_PATH.read_text())
        oak_log = fixture["materials"].index("oak_log")
        far = [cell for cell in fixture["cells"] if max(abs(cell[1]), abs(cell[3])) >= 2500]
        self.assertGreater(len(far), 1000)
        self.assertTrue(any(cell[4] == oak_log for cell in far), "fixture has no far oak_log cells")
        self.assertTrue(any(max(abs(cell[1]), abs(cell[3])) >= 25000 for cell in far))


if __name__ == "__main__":
    unittest.main()

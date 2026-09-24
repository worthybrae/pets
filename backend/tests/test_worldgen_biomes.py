import math
import unittest

from backend.services.blocks import is_solid
from backend.services.worldgen import (
    LEGACY_RADIUS, LEGACY_WORLD_SEED, SEA_LEVEL, TREE_LEAVES, TREE_LOGS, biome_at, block_at, plant_stack,
    shore, surface_material, swamp_pool, tall_plant, terrain_height, tree_kind, trees_in_chunk,
)
from backend.survival.creatures.kinds import land_kinds

SEED = "123456789123456789"
WIDE = [(x, z) for x in range(250, 3250, 23) for z in range(-1500, 1500, 29)]


def columns(test, count=1, xs=range(250, 1250), zs=range(-60, 60, 2)):
    """The first `count` generated columns where `test(x, z)` holds."""
    found = []
    for x in xs:
        for z in zs:
            if test(x, z):
                found.append((x, z))
                if len(found) == count:
                    return found
    return found


def trees_of(kind, count=5):
    found = []
    for cx in range(16, 120):
        for cz in range(-40, 40):
            found += [tree for tree in trees_in_chunk(cx, cz, SEED) if tree_kind(tree[0], tree[1], SEED) == kind]
            if len(found) >= count:
                return found[:count]
    return found


class BiomeTests(unittest.TestCase):
    def test_every_biome_turns_up_in_the_generated_land(self):
        seen = {biome_at(x, z, SEED) for x, z in WIDE}
        self.assertEqual(seen, {"meadow", "forest", "birch_forest", "taiga", "swamp", "desert", "alpine"})

    def test_the_legacy_clearing_stays_a_meadow_with_only_oaks_and_its_old_plants(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 7):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 7):
                if math.hypot(x, z) <= LEGACY_RADIUS:
                    self.assertEqual(biome_at(x, z, LEGACY_WORLD_SEED), "meadow")
                    self.assertIsNone(tall_plant(x, z, LEGACY_WORLD_SEED))
                    stack = plant_stack(x, z, LEGACY_WORLD_SEED)
                    self.assertIn(stack, (None, ("tall_grass", 1), ("flower_orange", 1), ("flower_yellow", 1)))
        for cx in range(-8, 8):
            for cz in range(-8, 8):
                for tx, tz, _ in trees_in_chunk(cx, cz, LEGACY_WORLD_SEED):
                    self.assertEqual(tree_kind(tx, tz, LEGACY_WORLD_SEED), "oak")


class TreeTests(unittest.TestCase):
    def test_each_wood_has_its_own_logs_and_leaves_and_shape(self):
        for kind, top in (("oak", 6), ("birch", 7), ("spruce", 7)):
            for x, z, base in trees_of(kind, 3):
                with self.subTest(kind=kind, tree=(x, z)):
                    self.assertEqual([block_at(x, base + dy, z, SEED) for dy in range(1, 5)], [TREE_LOGS[kind]] * 4)
                    self.assertEqual(block_at(x, base + top, z, SEED), TREE_LEAVES[kind])
                    self.assertEqual(block_at(x, base + top + 1, z, SEED), "air")

    def test_the_taiga_grows_spruce_the_birch_forest_birch_and_a_forest_mostly_oak(self):
        kinds = {}
        for cx in range(16, 200, 3):
            for cz in range(-60, 60, 3):
                for tx, tz, _ in trees_in_chunk(cx, cz, SEED):
                    kinds.setdefault(biome_at(tx, tz, SEED), []).append(tree_kind(tx, tz, SEED))
        self.assertEqual(set(kinds["taiga"]), {"spruce"})
        self.assertGreater(kinds["birch_forest"].count("birch"), len(kinds["birch_forest"]) / 2)
        self.assertGreater(kinds["forest"].count("oak"), len(kinds["forest"]) / 2)
        self.assertEqual(set(kinds["meadow"]), {"oak"})


class GroundTests(unittest.TestCase):
    def test_taiga_ground_has_snow_patches_ferns_and_frozen_lakes(self):
        taiga = [(x, z) for x, z in WIDE if biome_at(x, z, SEED) == "taiga" and terrain_height(x, z, SEED) >= SEA_LEVEL]
        self.assertEqual({surface_material(x, z, SEED) for x, z in taiga}, {"grass", "snow", "gravel"})
        (x, z), = columns(lambda x, z: biome_at(x, z, SEED) == "taiga" and terrain_height(x, z, SEED) < SEA_LEVEL,
                          xs=range(250, 3250, 3), zs=range(-900, 900, 3))
        self.assertEqual(block_at(x, SEA_LEVEL, z, SEED), "ice")
        if terrain_height(x, z, SEED) < SEA_LEVEL - 1:
            self.assertEqual(block_at(x, SEA_LEVEL - 1, z, SEED), "water")
        (x, z), = columns(lambda x, z: plant_stack(x, z, SEED) == ("fern", 1))
        self.assertEqual(biome_at(x, z, SEED), "taiga")
        self.assertEqual(block_at(x, terrain_height(x, z, SEED) + 1, z, SEED), "fern")

    def test_a_swamp_has_mud_and_shallow_pools_level_with_the_lakes(self):
        (x, z), = columns(lambda x, z: swamp_pool(x, z, SEED))
        self.assertEqual((biome_at(x, z, SEED), terrain_height(x, z, SEED)), ("swamp", SEA_LEVEL))
        self.assertEqual([block_at(x, SEA_LEVEL + dy, z, SEED) for dy in (-1, 0, 1)], ["mud", "water", "air"])
        swamp = [(x, z) for x, z in WIDE if biome_at(x, z, SEED) == "swamp"]
        self.assertIn("mud", {surface_material(x, z, SEED) for x, z in swamp})
        self.assertTrue(all(terrain_height(x, z, SEED) <= SEA_LEVEL + 1 for x, z in swamp))

    def test_alpine_peaks_are_bare_snow(self):
        (x, z), = columns(lambda x, z: terrain_height(x, z, SEED) >= 15, xs=range(250, 3250, 3), zs=range(-900, 900, 3))
        self.assertEqual(block_at(x, terrain_height(x, z, SEED), z, SEED), "snow_block")


class GravelTests(unittest.TestCase):
    def test_gravel_lines_lake_beds_and_shores_and_lies_in_taiga_and_mountain_patches(self):
        beds = [surface_material(x, z, SEED) for x, z in WIDE if terrain_height(x, z, SEED) < SEA_LEVEL
                and biome_at(x, z, SEED) != "desert"]
        self.assertEqual(set(beds), {"gravel", "sand"})
        self.assertGreater(beds.count("gravel"), len(beds) / 3)
        (x, z), = columns(lambda x, z: shore(x, z, SEED) and surface_material(x, z, SEED) == "gravel")
        self.assertEqual(block_at(x, SEA_LEVEL, z, SEED), "gravel")
        self.assertEqual(block_at(x, SEA_LEVEL + 1, z, SEED), "air")
        for biome in ("taiga", "alpine"):
            ground = {surface_material(x, z, SEED) for x, z in WIDE if biome_at(x, z, SEED) == biome}
            self.assertIn("gravel", ground, biome)

    def test_the_legacy_clearing_has_no_gravel(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 5):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS + 1, 5):
                if math.hypot(x, z) <= LEGACY_RADIUS:
                    self.assertNotEqual(surface_material(x, z, LEGACY_WORLD_SEED), "gravel", (x, z))


class PlantTests(unittest.TestCase):
    def test_cacti_stand_one_to_three_high_on_desert_sand(self):
        found = columns(lambda x, z: (plant_stack(x, z, SEED) or ("",))[0] == "cactus", count=6)
        self.assertEqual(len(found), 6)
        for x, z in found:
            height, tall = terrain_height(x, z, SEED), plant_stack(x, z, SEED)[1]
            self.assertTrue(1 <= tall <= 3)
            self.assertEqual(block_at(x, height, z, SEED), "sand")
            self.assertEqual([block_at(x, height + dy, z, SEED) for dy in range(1, tall + 2)], ["cactus"] * tall + ["air"])

    def test_sugar_cane_grows_on_a_shore_beside_a_lake(self):
        (x, z), = columns(lambda x, z: (plant_stack(x, z, SEED) or ("",))[0] == "sugar_cane")
        self.assertEqual(terrain_height(x, z, SEED), SEA_LEVEL)
        self.assertTrue(any(block_at(x + dx, SEA_LEVEL, z + dz, SEED) == "water"
                            for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))))
        self.assertEqual(block_at(x, SEA_LEVEL + 1, z, SEED), "sugar_cane")

    def test_dead_bushes_pumpkins_and_melons(self):
        for name, ground in (("dead_bush", ("sand",)), ("pumpkin", ("grass", "moss")), ("melon", ("grass", "moss"))):
            (x, z), = columns(lambda x, z: (plant_stack(x, z, SEED) or ("",))[0] == name)
            height = terrain_height(x, z, SEED)
            self.assertIn(block_at(x, height, z, SEED), ground, name)
            self.assertEqual(block_at(x, height + 1, z, SEED), name)
        self.assertTrue(is_solid("pumpkin"))


class AnimalTests(unittest.TestCase):
    def test_the_new_biomes_have_their_own_animals(self):
        self.assertEqual([kind.name for kind in land_kinds("taiga")], ["rabbit", "sheep"])
        self.assertEqual([kind.name for kind in land_kinds("birch_forest")], ["rabbit", "chicken", "sheep", "cow"])
        self.assertEqual([kind.name for kind in land_kinds("swamp")], ["rabbit", "chicken", "cow"])


if __name__ == "__main__":
    unittest.main()

import math
import unittest

from backend.services.blocks import is_replaceable, is_solid
from backend.services.worldgen import (
    block_at, biome_at, cave_plant, plant_stack, region_openings, rock_column, rocks_in_chunk, surface_material,
    surface_opened, terrain_height,
)
from backend.survival.spawn import (
    MAX_DISTANCE, MIN_DISTANCE, SPAWN_BIOMES, SPAWN_SURFACES, spawn_fits, tree_near,
)

SEED = "123456789123456789"


def entrances(kind, count=3):
    found = []
    for rx in range(4, 40):
        for rz in range(-20, 20):
            found_kind, spans = region_openings(rx, rz, SEED)
            if found_kind == kind:
                found.append(spans)
                if len(found) == count:
                    return found
    return found


def rocks(kind, count=6):
    found = []
    for cx in range(16, 160):
        for cz in range(-40, 40):
            found += [rock for rock in rocks_in_chunk(cx, cz, SEED) if rock[2] == kind]
            if len(found) >= count:
                return found[:count]
    return found


class EntranceTests(unittest.TestCase):
    def test_a_sinkhole_opens_a_deep_round_shaft_to_the_sky(self):
        found = entrances("sinkhole")
        self.assertTrue(found)
        for spans in found:
            self.assertEqual(len(spans), 21)
            for (x, z), (low, high) in spans.items():
                height = terrain_height(x, z, SEED)
                self.assertEqual(high, height)
                self.assertTrue(surface_opened(x, z, SEED))
                self.assertTrue(low == -3 or height - low >= 8, (x, z, low, height))
                self.assertEqual([block_at(x, y, z, SEED) for y in (low, height)], ["air", "air"])
                self.assertIsNone(plant_stack(x, z, SEED))
                self.assertFalse(spawn_fits(x, z, SEED))

    def test_a_hillside_mouth_is_two_wide_and_sinks_into_the_ground_under_a_roof(self):
        roofed = 0
        for spans in entrances("mouth", 6):
            self.assertGreaterEqual(len(spans), 4)
            items = list(spans.items())
            two_wide = any((low1, high1) == (low2, high2) and abs(x1 - x2) + abs(z1 - z2) == 1
                            for i, ((x1, z1), (low1, high1)) in enumerate(items)
                            for (x2, z2), (low2, high2) in items[i + 1:])
            self.assertTrue(two_wide, "no adjacent pair of columns shares a floor and a roof")
            for (x, z), (low, high) in spans.items():
                self.assertTrue(0 <= high - low <= 2)
                self.assertTrue(all(block_at(x, y, z, SEED) == "air" for y in range(low, high + 1)))
                if high < terrain_height(x, z, SEED) and is_solid(block_at(x, high + 1, z, SEED)):
                    roofed += 1
            floors = sorted({low for low, _ in spans.values()})
            self.assertEqual(floors, list(range(floors[0], floors[-1] + 1)))  # it steps down a block at a time
        self.assertGreater(roofed, 0)

    def test_no_entrance_near_the_legacy_clearing(self):
        for rx in range(-3, 3):
            for rz in range(-3, 3):
                self.assertEqual(region_openings(rx, rz, SEED), ("", {}))


class RockTests(unittest.TestCase):
    def test_boulders_rest_on_their_own_ground_one_or_two_high(self):
        for x, z, _, size, block in rocks("boulder"):
            ground = terrain_height(x, z, SEED)
            self.assertEqual(rock_column(x, z, SEED), (block, ground + size))
            for dx in range(-2, 3):
                for dz in range(-2, 3):
                    rock = rock_column(x + dx, z + dz, SEED)
                    if rock is None:
                        continue
                    bottom = terrain_height(x + dx, z + dz, SEED) + 1
                    self.assertEqual(block_at(x + dx, bottom, z + dz, SEED), block)  # on the ground, never floating
                    self.assertIsNone(plant_stack(x + dx, z + dz, SEED))

    def test_outcrops_crown_hills_in_jagged_pillars(self):
        for x, z, _, size, block in rocks("outcrop"):
            self.assertGreaterEqual(terrain_height(x, z, SEED), 8)
            tops = {rock_column(x + dx, z + dz, SEED)[1] - terrain_height(x + dx, z + dz, SEED)
                    for dx in range(-size, size + 1) for dz in range(-size, size + 1)
                    if rock_column(x + dx, z + dz, SEED)}
            self.assertTrue(tops <= {1, 2, 3} and len(tops) > 1)

    def test_rocks_are_of_the_local_stone(self):
        seen = set()
        for x, z, kind, _, block in rocks("boulder", 120) + rocks("outcrop", 40):
            biome = biome_at(x, z, SEED)
            if biome in ("forest", "taiga", "swamp", "birch_forest") and kind == "boulder":
                self.assertEqual(block, "mossy_cobblestone")
                seen.add("mossy_cobblestone")
            if biome == "desert":
                self.assertEqual(block, "sandstone")
                seen.add("desert sandstone")
            if biome == "meadow" and kind == "boulder":
                self.assertEqual(block, "andesite")
                seen.add("meadow andesite")
            if biome == "alpine" and kind == "boulder":
                self.assertEqual(block, "stone")
                seen.add("alpine stone")
        self.assertEqual(seen, {"mossy_cobblestone", "desert sandstone", "meadow andesite", "alpine stone"})


class SpawnGuardTests(unittest.TestCase):
    def test_a_cave_entrance_inside_the_spawn_band_blocks_spawning(self):
        """spawn_fits refuses a column whose ground cell an entrance took, even one that would
        otherwise pass distance, height, biome, surface, headroom and tree checks: proof the guard
        itself (not some other check) is why. The first sinkholes region_openings finds sit well
        inside MIN_DISTANCE, where spawn_fits already returns False before reaching the guard, so
        this searches the spawn band (3,000-6,000) on purpose."""
        found = None
        for rx in range(47, 94):
            for rz in range(-93, 94):
                kind, spans = region_openings(rx, rz, SEED)
                if not kind:
                    continue
                for x, z in spans:
                    if not surface_opened(x, z, SEED) or not MIN_DISTANCE <= math.hypot(x, z) <= MAX_DISTANCE:
                        continue
                    if biome_at(x, z, SEED) not in SPAWN_BIOMES or surface_material(x, z, SEED) not in SPAWN_SURFACES:
                        continue
                    height = terrain_height(x, z, SEED)
                    blocked = any(block_at(x, y, z, SEED) == "water" or not is_replaceable(block_at(x, y, z, SEED))
                                  for y in (height + 1, height + 2))
                    if blocked or not tree_near(x, z, SEED):
                        continue
                    found = (x, z)
                    break
                if found:
                    break
            if found:
                break
        self.assertIsNotNone(found, "no opened column in the spawn band met every other spawn_fits check")
        x, z = found
        self.assertFalse(spawn_fits(x, z, SEED))


class CavePlantTests(unittest.TestCase):
    def test_no_mushroom_floats_over_air_an_entrance_carved(self):
        # A sinkhole shaft at (1129, -1245), span (-3, 7): the cell right below y -1 is itself
        # carved to air by the entrance, so cave_at(x, y - 1, z) reading False (no natural cave
        # noise there) must not be mistaken for a solid floor.
        x, y, z = 1129, -1, -1245
        self.assertIsNone(cave_plant(x, y, z, SEED))
        self.assertEqual(block_at(x, y, z, SEED), "air")


if __name__ == "__main__":
    unittest.main()

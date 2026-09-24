import unittest

from backend.services.blocks import is_solid
from backend.services.worldgen import (
    block_at, biome_at, plant_stack, region_openings, rock_column, rocks_in_chunk, surface_opened, terrain_height,
)
from backend.survival.spawn import spawn_fits

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
        for spans in entrances("sinkhole"):
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
        for x, z, kind, _, block in rocks("boulder", 40) + rocks("outcrop", 20):
            biome = biome_at(x, z, SEED)
            if biome in ("forest", "taiga", "swamp", "birch_forest") and kind == "boulder":
                self.assertEqual(block, "mossy_cobblestone")
            if biome == "desert":
                self.assertEqual(block, "sandstone")


if __name__ == "__main__":
    unittest.main()

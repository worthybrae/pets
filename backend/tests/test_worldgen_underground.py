import math
import unittest

from backend.services.crafting import can_harvest
from backend.services.worldgen import (
    CAVE_MUSHROOM_RARITY, LEGACY_RADIUS, LEGACY_WORLD_SEED, block_at, cave_at, cave_plant, hash32, terrain_block,
    terrain_height,
)

SEED = "123456789123456789"


def underground(xs=range(2000, 2300, 3), zs=range(-150, 150, 3)):
    """(x, y, z, block) of every generated cell from y -4 up to 3 below the surface."""
    for x in xs:
        for z in zs:
            for y in range(-4, terrain_height(x, z, SEED) - 2):
                yield x, y, z, terrain_block(x, y, z, SEED)


class CaveTests(unittest.TestCase):
    def test_caves_take_a_fifth_of_the_underground_and_stand_taller(self):
        cells = list(underground())
        open_cells = [cell for cell in cells if cell[3] in ("air", "water", "lava")]
        self.assertGreater(len(open_cells) / len(cells), 0.18)  # about 0.16 before L3 (0.162 in this sample)
        # L3 final fix wave: "stand taller" counted open cells per column, 5 or more of which the
        # caves before L3 had already. It now takes each column's longest unbroken run of open cells
        # and counts the columns where that run is 10 or more high: 29 in this sample before L3, 93
        # with all of L3, and 67 with caves not stretched upward (CAVE_STRETCH 1), which must fail.
        runs = {}
        for x, _, z, block in cells:  # a column's cells come together, from y -4 up
            run, longest = runs.get((x, z), (0, 0))
            run = run + 1 if block in ("air", "water", "lava") else 0
            runs[(x, z)] = (run, max(longest, run))
        tall = sum(longest >= 10 for _, longest in runs.values())
        self.assertGreater(tall, 2.5 * 29)

    def test_lakes_lie_low_in_caves_and_lava_on_their_lowest_floor(self):
        cells = list(underground())
        water = [(x, y, z) for x, y, z, block in cells if block == "water"]
        lava = [(x, y, z) for x, y, z, block in cells if block == "lava"]
        self.assertTrue(water and lava)
        self.assertTrue(all(y <= -2 and cave_at(x, y, z, SEED) for x, y, z in water))
        self.assertTrue(all(y == -4 and cave_at(x, y, z, SEED) for x, y, z in lava))
        # L3 final fix wave: no mushroom on water or lava. Checked on the cells where one would grow
        # but for that rule: on a cave floor (solid rock under it) and picked by the mushroom's roll.
        rolled = [(x, y, z) for x, y, z in water + lava if not cave_at(x, y - 1, z, SEED)
                  and hash32(x, y, z, SEED, 17) % CAVE_MUSHROOM_RARITY == 0]
        self.assertGreater(len(rolled), 20)
        for x, y, z in rolled:
            self.assertIsNone(cave_plant(x, y, z, SEED), (x, y, z))

    def test_the_legacy_clearing_keeps_its_old_underground(self):
        for x in range(-LEGACY_RADIUS, LEGACY_RADIUS, 17):
            for z in range(-LEGACY_RADIUS, LEGACY_RADIUS, 13):
                for y in (-4, -3) if math.hypot(x, z) <= LEGACY_RADIUS else ():
                    self.assertIn(block_at(x, y, z, LEGACY_WORLD_SEED), ("stone", "iron_ore", "coal_ore"), (x, y, z))


class GravelTests(unittest.TestCase):
    def test_gravel_lies_in_patches_on_cave_floors(self):
        cells = list(underground())
        gravel = [(x, y, z) for x, y, z, block in cells if block == "gravel"]
        self.assertGreater(len(gravel), 20)
        for x, y, z in gravel:
            self.assertTrue(cave_at(x, y + 1, z, SEED), (x, y, z))
            self.assertEqual(terrain_block(x, y + 1, z, SEED), "air")


class RockTests(unittest.TestCase):
    def test_gold_lies_at_zero_and_below_and_diamonds_deeper_both_for_an_iron_pickaxe(self):
        cells = list(underground(xs=range(2000, 2600, 2)))
        gold = [y for _, y, _, block in cells if block == "gold_ore"]
        diamond = [y for _, y, _, block in cells if block == "diamond_ore"]
        self.assertTrue(gold and diamond)
        self.assertLessEqual(max(gold), 0)
        self.assertLessEqual(max(diamond), -3)
        self.assertGreater(len(gold), len(diamond))
        for ore in ("gold_ore", "diamond_ore"):
            self.assertFalse(can_harvest(ore, {"stone_pickaxe": 1}))
            self.assertTrue(can_harvest(ore, {"iron_pickaxe": 1}))

    def test_seams_of_granite_andesite_diorite_and_deep_ashstone(self):
        cells = {(x, y, z): block for x, y, z, block in underground()}
        kinds = set(cells.values())
        self.assertTrue({"granite", "andesite", "diorite", "ashstone", "stone"} <= kinds)
        self.assertTrue(all(y <= -2 for (_, y, _), block in cells.items() if block == "ashstone"))
        granite = [cell for cell, block in cells.items() if block == "granite"]
        beside = sum(1 for x, y, z in granite if cells.get((x, y + 1, z)) == "granite" or cells.get((x + 3, y, z)) == "granite")
        self.assertGreater(beside / len(granite), 0.5)  # blobs, not specks
        self.assertGreater(list(cells.values()).count("stone"), len(cells) / 2)


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, hardness, is_plant, is_replaceable, is_solid, mining_tool
from backend.services.crafting import BLOCKS

# L3's blocks, in registry order right after L2's door (Making's follow them).
BIGGER_WORLD = ("granite", "andesite", "diorite", "ashstone", "gold_ore", "diamond_ore",
                "birch_log", "birch_leaves", "birch_planks", "spruce_log", "spruce_leaves", "spruce_planks",
                "snow_block", "ice", "mud", "cactus", "sugar_cane", "pumpkin", "melon", "fern", "dead_bush",
                "mossy_cobblestone", "stone_bricks", "ladder", "fence", "creature_sprout")
STONES = ("granite", "andesite", "diorite", "ashstone", "mossy_cobblestone")
PLANTS = ("cactus", "sugar_cane", "fern", "dead_bush", "creature_sprout")


class BiggerWorldBlockTests(unittest.TestCase):
    def test_the_bigger_worlds_blocks_follow_the_door_so_older_ids_never_change(self):
        names = [block["name"] for block in BLOCK_LIST]
        start = BLOCK_IDS["granite"]
        self.assertEqual(names[start:start + len(BIGGER_WORLD)], list(BIGGER_WORLD))
        self.assertEqual(BLOCK_IDS["granite"], BLOCK_IDS["door"] + 1)  # right after L2's door
        self.assertLess(len(BLOCK_LIST), 255)

    def test_every_new_face_has_a_tile(self):
        for name in BIGGER_WORLD:
            textures = BLOCK_LIST[BLOCK_IDS[name]]["textures"]
            for tile in [textures] if isinstance(textures, str) else textures.values():
                self.assertIn(tile, TILES, name)

    def test_stone_variants_break_into_cobblestone_with_a_pickaxe(self):
        for name in STONES:
            self.assertEqual(BLOCKS[name]["drop"], "cobblestone", name)
            self.assertEqual(BLOCKS[name]["requires"], "wooden_pickaxe", name)
            self.assertEqual((hardness(name), mining_tool(name)), (4.0, "pickaxe"), name)
        self.assertEqual(BLOCKS["stone_bricks"]["drop"], "stone_bricks")

    def test_gold_and_diamond_need_an_iron_pickaxe_and_diamond_ore_gives_a_diamond(self):
        self.assertEqual((BLOCKS["gold_ore"]["drop"], BLOCKS["gold_ore"]["requires"]), ("gold_ore", "iron_pickaxe"))
        self.assertEqual((BLOCKS["diamond_ore"]["drop"], BLOCKS["diamond_ore"]["requires"]), ("diamond", "iron_pickaxe"))
        self.assertGreater(hardness("diamond_ore"), hardness("gold_ore"))

    def test_birch_and_spruce_wood_like_oak(self):
        for wood in ("birch", "spruce"):
            self.assertEqual(BLOCKS[f"{wood}_log"]["drop"], f"{wood}_log")
            self.assertEqual(BLOCKS[f"{wood}_planks"]["drop"], f"{wood}_planks")
            self.assertIsNone(BLOCKS[f"{wood}_leaves"]["drop"])
            self.assertEqual((mining_tool(f"{wood}_log"), mining_tool(f"{wood}_leaves")), ("axe", None))
            self.assertEqual(hardness(f"{wood}_leaves"), hardness("leaves"))

    def test_desert_swamp_and_taiga_plants_are_see_through_plants(self):
        for name in PLANTS:
            self.assertTrue(is_plant(name), name)
            self.assertFalse(is_solid(name), name)
        self.assertTrue(is_replaceable("fern") and is_replaceable("dead_bush"))
        self.assertFalse(is_replaceable("cactus") or is_replaceable("sugar_cane") or is_replaceable("creature_sprout"))
        self.assertEqual(BLOCKS["creature_sprout"]["drop"], "creature_seed")

    def test_ground_fruit_ice_and_the_fittings(self):
        for name in ("snow_block", "ice", "mud", "pumpkin", "melon", "fence"):
            self.assertTrue(is_solid(name), name)
        self.assertFalse(is_solid("ladder"))
        self.assertEqual(BLOCK_LIST[BLOCK_IDS["ice"]]["layer"], "translucent")
        self.assertEqual(BLOCKS["mud"]["drop"], "dirt")
        self.assertIsNone(BLOCKS["ice"]["drop"])
        self.assertTrue(BLOCKS["fence"]["tall"])
        for name in ("cactus", "ladder", "fence"):  # the viewer draws these as see-through cubes
            self.assertEqual(BLOCK_LIST[BLOCK_IDS[name]]["shape"], "cube", name)
            self.assertNotIn("shape", BLOCKS[name])


if __name__ == "__main__":
    unittest.main()

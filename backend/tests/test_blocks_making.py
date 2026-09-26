import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, hardness, is_replaceable, is_solid, mining_tool
from backend.services.crafting import BLOCKS
from backend.tests.test_blocks_bigger_world import BIGGER_WORLD

# Making's T1 blocks, in registry order right after L3's.
MAKING = ("bookshelf", "wool_orange", "wool_pink", "wool_yellow", "rug_orange", "rug_pink", "rug_yellow", "kiln",
          "stairs", "slab", "glass_pane", "trapdoor", "iron_bars", "flower_pot", "sign", "barrel", "composter",
          "candle")
AXE = ("bookshelf", "stairs", "slab", "trapdoor", "sign", "barrel", "composter")
THIN = ("rug_orange", "rug_pink", "rug_yellow", "trapdoor", "flower_pot", "sign", "candle")


def shape(name: str) -> str | None:
    return BLOCK_LIST[BLOCK_IDS[name]].get("shape")


class MakingBlockTests(unittest.TestCase):
    def test_the_new_blocks_follow_the_bigger_worlds_so_older_ids_never_change(self):
        names = [block["name"] for block in BLOCK_LIST]
        start = BLOCK_IDS["bookshelf"]
        self.assertEqual(start, BLOCK_IDS[BIGGER_WORLD[-1]] + 1)
        self.assertEqual(names[start:start + len(MAKING)], list(MAKING))
        self.assertLess(len(BLOCK_LIST), 255)

    def test_every_new_face_has_a_tile(self):
        for name in MAKING:
            textures = BLOCK_LIST[BLOCK_IDS[name]]["textures"]
            for tile in [textures] if isinstance(textures, str) else textures.values():
                self.assertIn(tile, TILES, name)

    def test_each_drops_itself_and_breaks_fastest_with_its_tool(self):
        for name in MAKING:
            self.assertEqual(BLOCKS[name]["drop"], name)
            self.assertIsNotNone(hardness(name), name)
            self.assertFalse(is_replaceable(name), name)
        for name in AXE:
            self.assertEqual(mining_tool(name), "axe", name)
        self.assertEqual((mining_tool("kiln"), mining_tool("iron_bars")), ("pickaxe", "pickaxe"))

    def test_rugs_trapdoors_pots_signs_and_candles_let_mimo_through(self):
        for name in THIN:
            self.assertFalse(is_solid(name), name)
        for name in ("bookshelf", "wool_pink", "kiln", "stairs", "slab", "glass_pane", "iron_bars", "barrel",
                     "composter"):
            self.assertTrue(is_solid(name), name)

    def test_the_viewer_draws_the_thin_ones_by_shape(self):
        for name in ("rug_orange", "rug_pink", "rug_yellow", "trapdoor"):
            self.assertEqual(shape(name), "flat", name)
        self.assertEqual(shape("slab"), "slab")
        for name in ("stairs", "glass_pane", "iron_bars", "composter"):
            self.assertEqual(shape(name), "cube", name)
        for name in MAKING:
            self.assertNotIn("shape", BLOCKS[name])  # how a block is drawn is not gameplay

    def test_the_kiln_and_the_candle_glow(self):
        self.assertTrue(BLOCKS["kiln"]["glow"] and BLOCKS["candle"]["glow"])
        self.assertNotIn("glow", BLOCKS["bookshelf"])


if __name__ == "__main__":
    unittest.main()

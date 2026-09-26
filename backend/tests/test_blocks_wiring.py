import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES, is_solid
from backend.services.crafting import BLOCKS
from backend.tests.test_blocks_making import MAKING

# Making's T2 blocks (wiring), in registry order right after its T1 blocks. A part that can be on has a
# block for each look; the lit one drops the plain part.
WIRING = ("copper_wire", "copper_wire_lit", "lever", "lever_on", "button", "button_on", "pressure_plate",
          "daylight_sensor", "repeater", "repeater_lit", "inverter", "inverter_lit", "joiner", "joiner_lit",
          "lamp", "lamp_lit", "bell")
LIT = {"copper_wire_lit": "copper_wire", "lever_on": "lever", "button_on": "button", "repeater_lit": "repeater",
       "inverter_lit": "inverter", "joiner_lit": "joiner", "lamp_lit": "lamp"}


class WiringBlockTests(unittest.TestCase):
    def test_the_wiring_blocks_follow_makings_first_ones(self):
        names = [block["name"] for block in BLOCK_LIST]
        start = BLOCK_IDS["copper_wire"]
        self.assertEqual(start, BLOCK_IDS[MAKING[-1]] + 1)
        self.assertEqual(names[start:start + len(WIRING)], list(WIRING))
        self.assertLess(len(BLOCK_LIST), 255)
        for name in WIRING:
            textures = BLOCK_LIST[BLOCK_IDS[name]]["textures"]
            for tile in [textures] if isinstance(textures, str) else textures.values():
                self.assertIn(tile, TILES, name)

    def test_a_lit_part_drops_the_plain_one_and_glows_while_the_plain_one_does_not(self):
        for lit, plain in LIT.items():
            self.assertEqual((BLOCKS[lit]["drop"], BLOCKS[plain]["drop"]), (plain, plain))
        for lit in ("copper_wire_lit", "repeater_lit", "inverter_lit", "joiner_lit", "lamp_lit"):
            self.assertTrue(BLOCKS[lit].get("glow"), lit)
            self.assertFalse(BLOCKS[LIT[lit]].get("glow"), lit)

    def test_wire_and_gates_lie_flat_and_mimo_walks_over_them(self):
        for name in ("copper_wire", "pressure_plate", "repeater", "inverter", "joiner", "joiner_lit"):
            self.assertEqual(BLOCK_LIST[BLOCK_IDS[name]]["shape"], "flat", name)
            self.assertFalse(is_solid(name), name)
        self.assertEqual(BLOCK_LIST[BLOCK_IDS["daylight_sensor"]]["shape"], "slab")
        self.assertTrue(is_solid("lamp") and is_solid("lamp_lit") and is_solid("daylight_sensor"))
        self.assertFalse(is_solid("lever") or is_solid("button") or is_solid("bell"))


if __name__ == "__main__":
    unittest.main()

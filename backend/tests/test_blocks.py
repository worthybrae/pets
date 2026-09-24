import unittest

from backend.services.blocks import (
    BLOCK_IDS, BLOCK_LIST, TILES, hardness, is_plant, is_replaceable, is_solid, mining_tool,
)
from backend.services.crafting import BLOCKS

# Gameplay properties as they were before the registry moved to shared/blocks.json.
LEGACY_BLOCKS = {
    "grass": {"color": [127, 173, 137], "drop": "dirt"},
    "snow": {"color": [236, 241, 243], "drop": "dirt"},
    "dirt": {"color": [126, 105, 89], "drop": "dirt"},
    "stone": {"color": [153, 151, 148], "drop": "cobblestone", "requires": "wooden_pickaxe"},
    "cobblestone": {"color": [130, 137, 137], "drop": "cobblestone"},
    "bedrock": {"color": [67, 72, 75], "drop": None},
    "sand": {"color": [222, 203, 158], "drop": "sand", "gravity": True},
    "gravel": {"color": [159, 166, 162], "drop": "gravel", "gravity": True},
    "clay": {"color": [166, 190, 192], "drop": "clay"},
    "brick": {"color": [184, 105, 86], "drop": "brick"},
    "basalt": {"color": [75, 83, 86], "drop": "basalt"},
    "oak_log": {"color": [139, 105, 82], "drop": "oak_log"},
    "planks": {"color": [202, 171, 125], "drop": "planks"},
    "leaves": {"color": [101, 164, 128], "drop": None},
    "coal_ore": {"color": [88, 94, 97], "drop": "coal", "requires": "wooden_pickaxe"},
    "iron_ore": {"color": [182, 138, 107], "drop": "iron_ore", "requires": "stone_pickaxe"},
    "copper_ore": {"color": [170, 116, 91], "drop": "copper_ore", "requires": "stone_pickaxe"},
    "glass": {"color": [160, 218, 218], "drop": "glass", "opacity": 0.38},
    "water": {"color": [103, 179, 203], "drop": None, "opacity": 0.58, "fluid": True},
    "lava": {"color": [244, 117, 57], "drop": None, "opacity": 0.85, "fluid": True, "glow": True},
    "wool": {"color": [238, 226, 204], "drop": "wool"},
    "moss": {"color": [85, 139, 100], "drop": "moss"},
    "lantern": {"color": [247, 213, 143], "drop": "lantern", "glow": True},
    "crafting_table": {"color": [169, 117, 72], "drop": "crafting_table"},
    "furnace": {"color": [88, 91, 89], "drop": "furnace", "glow": True},
}
# M4's blocks, in registry order after the older ones.
FOOD_AND_CAMP = ("berry_bush", "berry_bush_ripe", "brown_mushroom", "red_mushroom", "farmland",
                 "wheat_0", "wheat_1", "wheat_2", "wheat_3", "carrot_0", "carrot_1", "carrot_2", "carrot_3",
                 "sapling", "campfire", "torch", "bed", "chest")
CUBES = ("farmland", "bed", "chest")


class BlockRegistryTests(unittest.TestCase):
    def test_air_is_id_zero_and_ids_fit_below_the_missing_id(self):
        self.assertEqual(BLOCK_IDS["air"], 0)
        self.assertLess(len(BLOCK_LIST), 255)
        self.assertEqual(len(BLOCK_IDS), len(BLOCK_LIST), "block names must be unique")

    def test_existing_block_properties_are_unchanged(self):
        mining_keys = {"hardness", "tool"}
        for name, properties in LEGACY_BLOCKS.items():
            gameplay = {key: value for key, value in BLOCKS[name].items() if key not in mining_keys}
            self.assertEqual(gameplay, properties, name)
        self.assertNotIn("air", BLOCKS)

    def test_every_block_face_uses_a_defined_tile(self):
        for block in BLOCK_LIST:
            textures = block["textures"]
            tiles = [textures] if isinstance(textures, str) else [textures["top"], textures["side"], textures["bottom"]]
            for tile in tiles:
                self.assertIn(tile, TILES, f"{block['name']} uses unknown tile {tile}")

    def test_new_build_and_plant_materials_exist(self):
        for name in ("limestone", "polished_stone", "dark_slate", "plaster", "roof_tile", "dirt_path",
                     "hull_panel", "solar_panel", "brass", "sandstone", "verdigris",
                     "tall_grass", "flower_orange", "flower_pink", "flower_yellow"):
            self.assertIn(name, BLOCKS)

    def test_only_air_water_and_plants_are_replaceable(self):
        for name in ("air", "water", "tall_grass", "flower_pink"):
            self.assertTrue(is_replaceable(name), name)
        for name in ("stone", "leaves", "glass", "not_a_block"):
            self.assertFalse(is_replaceable(name), name)

    def test_is_plant_identifies_the_cutout_natural_decorations(self):
        for name in ("tall_grass", "flower_orange", "flower_pink", "flower_yellow"):
            self.assertTrue(is_plant(name), name)
        for name in ("air", "stone", "leaves", "glass", "water", "not_a_block"):
            self.assertFalse(is_plant(name), name)

    def test_is_solid_follows_the_registry(self):
        for name in ("stone", "leaves", "glass", "grass"):
            self.assertTrue(is_solid(name), name)
        for name in ("air", "water", "lava", "tall_grass", "not_a_block"):
            self.assertFalse(is_solid(name), name)

    def test_hardness_follows_the_spec_table(self):
        expected = {"dirt": 0.6, "grass": 0.6, "sand": 0.6, "gravel": 0.6, "leaves": 0.3, "tall_grass": 0.1,
                    "flower_pink": 0.1, "oak_log": 2.0, "planks": 2.0, "stone": 4.0, "cobblestone": 4.0,
                    "coal_ore": 5.0, "iron_ore": 5.0, "copper_ore": 5.0}
        for name, seconds in expected.items():
            self.assertEqual(hardness(name), seconds, name)
        for name in ("bedrock", "air", "water", "lava", "not_a_block"):
            self.assertIsNone(hardness(name), name)

    def test_every_block_declares_a_hardness(self):
        for block in BLOCK_LIST:
            self.assertIn("hardness", block, block["name"])
            self.assertTrue(block["hardness"] is None or block["hardness"] > 0, block["name"])

    def test_pickaxes_help_with_stone_and_axes_with_wood(self):
        for name in ("stone", "cobblestone", "coal_ore", "iron_ore", "furnace", "brick"):
            self.assertEqual(mining_tool(name), "pickaxe", name)
        for name in ("oak_log", "planks", "crafting_table"):
            self.assertEqual(mining_tool(name), "axe", name)
        for name in ("dirt", "leaves", "tall_grass", "bedrock", "not_a_block"):
            self.assertIsNone(mining_tool(name), name)

    def test_food_and_camp_blocks_come_after_the_older_blocks(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[BLOCK_IDS["flower_yellow"] + 1:BLOCK_IDS["chest"] + 1], list(FOOD_AND_CAMP))
        self.assertEqual(names[BLOCK_IDS["chest"] + 1], "door")  # L2; L3's blocks follow it

    def test_plants_crops_and_fires_are_see_through_and_kept_when_building(self):
        for name in FOOD_AND_CAMP:
            if name in CUBES:
                self.assertTrue(is_solid(name), name)
                continue
            self.assertTrue(is_plant(name), name)
            self.assertFalse(is_solid(name), name)
            self.assertFalse(is_replaceable(name), name)
        self.assertTrue(BLOCKS["campfire"]["glow"])
        self.assertTrue(BLOCKS["torch"]["glow"])
        self.assertEqual(hardness("wheat_2"), 0.1)
        self.assertEqual(mining_tool("campfire"), "axe")

    def test_plants_drop_what_grows_on_them(self):
        drops = {"wheat_0": "seeds", "wheat_3": "wheat", "carrot_1": "carrot", "sapling": "sapling",
                 "brown_mushroom": "brown_mushroom", "berry_bush_ripe": None, "farmland": "dirt", "campfire": "campfire"}
        for name, drop in drops.items():
            self.assertEqual(BLOCKS[name]["drop"], drop, name)



if __name__ == "__main__":
    unittest.main()

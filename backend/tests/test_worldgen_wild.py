"""W1: nightberry bushes and sunleaf in the world, only on bare natural columns (both ports: the fixture)."""

import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.services import worldgen
from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, is_replaceable, is_solid
from backend.services.worldgen import LEGACY_RADIUS, plant_at, plant_stack
from backend.survival import nature
from backend.survival.actions import ActionContext
from backend.survival.fieldwork import finish_pick, start_pick
from backend.survival.grid import Grid
from backend.survival.renewal import BERRY_REGROW, create_growth_table, renew, scheduled

SEED = "123456789123456789"
AREA = [(x, z) for x in range(3000, 3160) for z in range(-80, 80)]


def plants(area=AREA):
    plant_stack.cache_clear()
    return {(x, z): plant_at(x, z, SEED) for x, z in area}


class WorldgenTests(unittest.TestCase):
    def test_the_new_plants_grow_only_where_nothing_grew_before(self):
        now = plants()
        with patch.object(worldgen, "wild_herb", lambda *args: None):
            before = plants()
        plant_stack.cache_clear()
        changed = {column: now[column] for column in AREA if now[column] != before[column]}
        self.assertTrue(changed)
        self.assertEqual({before[column] for column in changed}, {None})
        self.assertEqual(set(changed.values()), {"nightberry_bush_ripe", "sunleaf"})

    def test_about_two_nightberry_bushes_for_three_berry_bushes_and_none_in_the_clearing(self):
        found = list(plants().values())
        berries, nightberries = found.count("berry_bush_ripe"), found.count("nightberry_bush_ripe")
        self.assertTrue(0.45 < nightberries / berries < 0.85, (berries, nightberries))
        self.assertGreater(found.count("sunleaf"), 0)
        clearing = plants([(x, z) for x in range(-LEGACY_RADIUS, LEGACY_RADIUS, 3) for z in range(-60, 60, 3)
                           if math.hypot(x, z) <= LEGACY_RADIUS])
        self.assertFalse({"nightberry_bush_ripe", "sunleaf"} & set(clearing.values()))

    def test_the_blocks_come_last_and_give_way_like_tall_grass(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-3:], ["nightberry_bush", "nightberry_bush_ripe", "sunleaf"])
        self.assertEqual(BLOCK_IDS["nightberry_bush"], BLOCK_IDS["warding_lantern"] + 1)
        for name in names[-3:]:
            self.assertTrue(is_replaceable(name), name)
            self.assertFalse(is_solid(name), name)


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


class GrowingTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_growth_table(self.db)
        self.grid = meadow()
        self.state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {}}

    def renew_at(self, at):
        renew(self.state, ActionContext(grid=self.grid, clock_at=lambda when: {"time_scale": 1.0}, planner=None,
                                        events=[], db=self.db), at)

    def test_a_ripe_nightberry_bush_gives_three_nightberries_and_ripens_again_in_two_game_days(self):
        self.grid.put(1, 1, 0, "nightberry_bush_ripe")
        self.grid.take_changes()
        step = start_pick({"kind": "pick", "target": [1, 1, 0]}, self.state, self.grid, 0.0, 1.0)
        finish_pick(step, self.state, self.grid, 1.0)
        self.assertEqual((self.state["inventory"], self.grid.material(1, 1, 0)), ({"nightberries": 3}, "nightberry_bush"))
        self.renew_at(1.0)
        self.assertEqual([(cell, block) for cell, block, _ in scheduled(self.db)], [((1, 1, 0), "nightberry_bush_ripe")])
        self.renew_at(1.0 + BERRY_REGROW)
        self.assertEqual(self.grid.material(1, 1, 0), "nightberry_bush_ripe")

    def test_a_picked_sunleaf_comes_back_in_its_chunk_like_a_mushroom(self):
        self.assertEqual(nature.PICKS["sunleaf"], ({"sunleaf": 1}, "air"))
        self.grid.put(3, 1, 3, "sunleaf")
        self.grid.take_changes()
        self.grid.put(3, 1, 3, "air")
        with patch("backend.survival.renewal.biome_at", lambda x, z, seed: "meadow"), \
                patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0):
            self.renew_at(10.0)
            [(cell, block, _)] = scheduled(self.db)
            self.assertEqual(block, "sunleaf")
            self.renew_at(10.0 + 3600.0)
        self.assertEqual(self.grid.material(*cell), "sunleaf")


if __name__ == "__main__":
    unittest.main()

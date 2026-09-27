import math
import sqlite3
import unittest

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, TILES
from backend.services.crafting import RECIPES, craft
from backend.survival import brain  # noqa: F401  (registers the warding lantern, amber armor and ward_home)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.carrying import valuable
from backend.survival.creatures.harm import armor_cut
from backend.survival.creatures.hostiles import chase
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.moves import where
from backend.survival.frontier_gear import WARD_REACH, frontier_orders, note_wards
from backend.survival.goals import meets_need
from backend.survival.journal import LESSONS
from backend.survival.grid import Grid
from backend.survival.lessons import claims
from backend.survival.light import Lights
from backend.survival.lighting import dark_corners
from backend.survival.memory import create_memory_tables, finish_structure, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.storage import KEEP
from backend.survival.structures import start
from backend.survival.toolmaking import tool_orders
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_darkness import land, pet, scene
from backend.tests.test_survival_lighting import CORNERS, DAY


def chased(wards):
    """Where a gloomling 9 blocks east of Mimo stands after chasing it for a minute, with warding lanterns
    Mimo hung at `wards`."""
    grid = land({cell: "warding_lantern" for cell in wards})
    state = pet()
    state.update(name="Pip", position={"x": 0.0, "y": 1.0, "z": 1.0}, wards=[list(cell) for cell in wards])
    creature = grid.herd.add("gloomling", (9, 1, 1), 20.0, 0.0, 0.0, {"home": [9, 1, 1], "turn": 0})
    for turn in range(20):
        creature = grid.herd.get(creature["id"])
        at = 100.0 + turn * 3.0
        chase(creature, KINDS["gloomling"], scene(grid, state, at=at))
        grid.herd.save(creature)
    return where(grid.herd.get(creature["id"]), 200.0)


class WardTests(unittest.TestCase):
    def test_a_lantern_and_four_gloom_dust_make_a_warding_lantern_that_shines_like_a_lantern(self):
        self.assertEqual(craft({"lantern": 1, "gloom_dust": 4}, "warding_lantern", set()), {"warding_lantern": 1})
        grid = land({(0, 1, 5): "warding_lantern"})
        self.assertEqual(Lights(grid, (0, 1, 0), 16.0).at((0, 1, 5)), 15)
        self.assertEqual(KEEP["gloom_dust"], 4)  # kept on hand for one
        self.assertTrue(valuable("warding_lantern"))

    def test_no_hostile_steps_within_six_blocks_of_one(self):
        self.assertLess(math.dist(chased([]), (0, 1, 1)), 2.0)  # without one it walks right up to Mimo
        stopped = chased([(0, 1, 0)])
        self.assertGreater(math.dist(stopped, (0, 1, 0)), WARD_REACH)

    def test_the_warding_lantern_is_the_last_block_after_makings_wiring(self):
        # Pre-flight (eda93d4): Making's blocks followed L3's after this plan was written, so L5's one
        # block goes after Making's last (the bell), and no older id moves.
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-1], "warding_lantern")
        self.assertEqual(BLOCK_IDS["warding_lantern"], BLOCK_IDS["bell"] + 1)
        self.assertIn(BLOCK_LIST[BLOCK_IDS["warding_lantern"]]["textures"], TILES)
        self.assertLess(len(BLOCK_LIST), 255)

    def test_mimo_keeps_the_cells_of_the_wards_it_hangs_and_takes_down(self):
        state = {}
        note_wards(state, {"kind": "place", "block": "warding_lantern", "target": {"x": 1, "y": 2, "z": 3}}, None, 1.0)
        note_wards(state, {"kind": "place", "block": "torch", "target": {"x": 4, "y": 2, "z": 3}}, None, 1.0)
        self.assertEqual(state["wards"], [[1, 2, 3]])
        note_wards(state, {"kind": "mine", "block": "warding_lantern", "target": {"x": 1, "y": 2, "z": 3}}, None, 2.0)
        self.assertEqual(state["wards"], [])


class AmberTests(unittest.TestCase):
    def test_amber_studded_armor_is_a_step_past_iron(self):
        self.assertEqual(RECIPES["amber_cap"]["ingredients"], {"iron_ingot": 2, "amber": 2})
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "iron_tunic": 1}), 0.45)
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "iron_tunic": 1, "amber_cap": 1, "amber_tunic": 1}), 0.60)

    def test_craft_tools_studs_a_slot_mimo_wears_iron_on_once_it_carries_the_amber(self):
        self.assertEqual(frontier_orders({"iron_tunic": 1, "amber": 3}), [("amber_tunic",)])
        self.assertEqual(frontier_orders({"iron_tunic": 1, "iron_cap": 1, "amber": 2}), [("amber_cap",)])
        self.assertEqual(frontier_orders({"amber": 5}), [])  # no iron to stud
        self.assertIn(("amber_tunic",), tool_orders({"iron_pickaxe": 1, "iron_tunic": 1, "amber": 3}))
        self.assertIn(("warding_lantern",), tool_orders({"iron_pickaxe": 1, "lantern": 1, "gloom_dust": 4}))

    def test_the_owner_can_teach_the_new_loot(self):
        # Pre-flight (carry 6): Mind's recipe lessons cover the amber pieces (they are armor), and the warding
        # lantern and gold nuggets get one of their own; each is written from the recipe, so it is true.
        self.assertEqual(LESSONS["recipe:amber_cap"].fact, "An amber cap takes two iron ingots and two amber, at a crafting table.")
        self.assertEqual(LESSONS["recipe:warding_lantern"].fact, "A warding lantern takes a lantern and four gloom dust.")
        self.assertEqual(LESSONS["recipe:gold_nuggets"].fact, "Four gold nuggets make a gold ingot.")
        for line, lesson in (("a warding lantern takes gloom dust and a lantern", "recipe:warding_lantern"),
                             ("gold nuggets make a gold ingot", "recipe:gold_nuggets"),
                             ("amber armor takes amber and iron ingots", "recipe:amber_tunic")):
            self.assertIn(lesson, claims(line).taught, line)


class WardHomeTests(unittest.TestCase):
    """A finished cottage at home on a meadow, as test_survival_lighting builds it."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        set_home(self.db, design.anchor, 1.0)

    def situation(self, inventory):
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 1.0},
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, DAY, 0.0, self.db)

    def test_ward_home_hangs_one_on_a_corner_in_place_of_its_torch(self):
        ward = PURPOSES["ward_home"]
        self.assertFalse(ward.valid(self.situation({"warding_lantern": 1})))  # no light on a corner yet
        self.grid.put(*CORNERS[0], "torch")
        s = self.situation({"warding_lantern": 1})
        self.assertTrue(ward.valid(s))
        self.assertTrue(meets_need(s, "ward_home", ward.score(s)))
        steps = ward.plan(s, ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                           events=[], db=self.db))
        self.assertEqual([step["kind"] for step in steps][-2:], ["mine", "place"])
        self.assertEqual((steps[-1]["target"], steps[-1]["block"]), (CORNERS[0], "warding_lantern"))
        self.grid.put(*CORNERS[0], "warding_lantern")
        self.assertNotIn(tuple(CORNERS[0]), [tuple(cell) for cell in dark_corners(self.situation({}))])


if __name__ == "__main__":
    unittest.main()

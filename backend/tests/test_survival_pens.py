import sqlite3
import unittest

from backend.survival import pens, storage
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.building import finish_if_built
from backend.survival.creatures.moves import steps as creature_steps
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.housework import chest_key
from backend.survival.memory import create_memory_tables, finish_structure, structures
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
WOOD = {"planks": 30, "sticks": 12}  # 16 fences: 6 crafts of 4 planks and 2 sticks


class PenTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        create_creature_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        self.grid.herd = Herd(self.db)
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        home = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in home.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, home, 0.0), 1.0)

    def situation(self, inventory, clock=DAY, position=(12, 1, 1)):
        state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, clock, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=self.db)

    def test_a_pen_is_a_ring_of_16_fences_round_3x3_of_grass_with_a_walkway_round_it(self):
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        fences = sorted(planned.cell for planned in design.parts("fence"))
        self.assertEqual(len(fences), 16)
        self.assertEqual({cell[1] for cell in fences}, {1})
        self.assertEqual(len(design.parts("pen")), 9)
        self.assertEqual(len(design.stands), 24)
        self.assertEqual(design.anchor, (12, 1, 1))
        self.assertTrue(all(not pens.inside(design, stand) for stand in design.stands))
        claimed = pens.design_pen(self.grid, (1, 1, 1), "Pip")  # the shelter's own ground is left alone
        self.assertFalse(any(self.grid.claimed(planned.cell) for planned in claimed.cells))

    def test_built_by_day_with_a_home_a_creature_seed_and_the_wood_for_its_fences(self):
        build = PURPOSES["build_pen"]
        self.assertTrue(build.valid(self.situation({"creature_seed": 1, **WOOD})))
        self.assertFalse(build.valid(self.situation({**WOOD})))
        self.assertFalse(build.valid(self.situation({"creature_seed": 1, "planks": 8, "sticks": 4})))
        self.assertFalse(build.valid(self.situation({"creature_seed": 1, **WOOD}, clock=NIGHT)))

    def test_fences_go_up_from_the_walkway_8_a_batch_and_the_last_one_finishes_the_pen(self):
        s = self.situation({"creature_seed": 1, **WOOD})
        steps = PURPOSES["build_pen"].plan(s, self.context())
        (pen,) = structures(self.db, ("pen",))
        design = pens.design_pen  # the pen now claims its ring and inside
        self.assertTrue(self.grid.claimed((12, 1, 1)) and self.grid.claimed((10, 1, -1)))
        self.assertEqual([step["recipe"] for step in steps if step["kind"] == "craft"].count("fence"), 3)
        placed = [step["target"] for step in steps if step["kind"] == "place"]
        self.assertEqual(len(placed), 8)
        walks = [step["target"] for step in steps if step["kind"] == "walk"]
        self.assertTrue(walks and all(not pens.inside(pens.blueprint_of(pen), tuple(cell)) for cell in walks))
        blueprint = pens.blueprint_of(pen)
        for planned in blueprint.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        ctx = self.context()
        finish_if_built(s.state, ctx, pen["id"], 5.0)
        self.assertEqual(structures(self.db, ("pen",))[0]["status"], "done")
        self.assertEqual(ctx.events[-1][1:], ("built", "Pip laid out Pip's pen."))
        self.assertIsNotNone(design)

    def test_a_finished_pen_is_stocked_with_seeds_from_the_walkway_and_holds_what_grows(self):
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        s = self.situation({"creature_seed": 5})
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        steps = PURPOSES["stock_pen"].plan(s, self.context())
        planted = [step["target"] for step in steps if step["kind"] == "plant"]
        self.assertEqual(len(planted), pens.PEN_ANIMALS)
        self.assertTrue(all(pens.inside(design, tuple(cell)) for cell in planted))
        self.assertTrue(all(not pens.inside(design, tuple(step["target"])) for step in steps if step["kind"] == "walk"))
        cow = self.grid.herd.add("cow", (11, 1, 0), 10.0, 0.0, 1e9, {"tame": True})
        self.assertTrue(all(pens.inside(design, cell) for cell in creature_steps(self.grid, (11, 1, 0), False)))
        self.assertEqual(creature_steps(self.grid, (9, 1, 1), False).count((10, 1, 1)), 0)  # no wild animal walks in
        for cell in ((12, 1, 1), (13, 1, 2)):
            self.grid.put(*cell, "creature_sprout")
        self.assertEqual(pens.pen_life(self.situation({"creature_seed": 5}), design), 3)
        self.assertFalse(PURPOSES["stock_pen"].valid(self.situation({"creature_seed": 5})))
        self.assertIsNotNone(cow)

    def test_fences_left_over_once_the_pen_is_done_are_no_use_to_carry(self):
        pen = start(self.db, self.grid, pens.design_pen(self.grid, (12, 1, 1), "Pip"), 0.0)
        self.assertNotIn(("fence", 2), storage.junk(self.situation({"fence": 2})))  # still building it
        finish_structure(self.db, pen, 1.0)
        self.assertIn(("fence", 2), storage.junk(self.situation({"fence": 2})))

    def test_seeds_kept_in_the_chest_are_taken_out_first(self):
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        s = self.situation({})
        chest = storage.chest_spot(s)
        self.grid.put(*chest, "chest")
        s.state["chests"] = {chest_key(chest): {"creature_seed": 2}}
        self.assertEqual(pens.seeds_at_hand(s), 2)
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        steps = PURPOSES["stock_pen"].plan(s, self.context())
        self.assertEqual(steps[1], {"kind": "take", "target": list(chest), "item": "creature_seed", "amount": 2})
        self.assertEqual(len([step for step in steps if step["kind"] == "plant"]), 2)


if __name__ == "__main__":
    unittest.main()

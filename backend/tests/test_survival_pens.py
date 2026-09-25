import math
import sqlite3
import unittest

from backend.survival import life_goals, pens, storage
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.building import finish_if_built
from backend.survival.creatures.moves import steps as creature_steps
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.housework import chest_key
from backend.survival.memory import create_memory_tables, finish_structure, set_home, structures
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
        set_home(self.db, home.anchor, 1.0)  # fix round 1: home_done and the seed chest now read the home place

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
        blueprint = pens.blueprint_of(pen)
        # fix round 1: home is now set (see setUp), so pen_design's site_center is home, not
        # Mimo's own position -- check the ring and inside the pen actually claimed, not a
        # position that assumed the pen sat where Mimo stood.
        self.assertTrue(self.grid.claimed(blueprint.anchor) and self.grid.claimed(blueprint.parts("fence")[0].cell))
        self.assertEqual([step["recipe"] for step in steps if step["kind"] == "craft"].count("fence"), 3)
        placed = [step["target"] for step in steps if step["kind"] == "place"]
        self.assertEqual(len(placed), 8)
        walks = [step["target"] for step in steps if step["kind"] == "walk"]
        self.assertTrue(walks and all(not pens.inside(blueprint, tuple(cell)) for cell in walks))
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

    def test_a_chest_a_step_just_failed_near_is_skipped_for_one_still_reachable(self):
        """Follow-up fix, item 3: plan_stock_pen looped chests_built unfiltered, so a chest whose
        stand a step just failed near (an old home's chest behind dug-out ground, or the like) kept
        being walked to and failing again, even with another built chest's seeds just as reachable.
        The same near_failure guard storage's reachable_chests already has."""
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        site = find_site(self.grid, (1, 1, 20), (3, 3), ("north",), "flat", reach=0)
        old = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Old Cottage")
        for planned in old.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, old, 0.0), 1.0)
        home_chest, old_chest = storage.chest_spot(self.situation({})), old.one("chest")
        self.grid.put(*home_chest, "chest")
        self.grid.put(*old_chest, "chest")
        s = self.situation({})
        s.state["chests"] = {chest_key(home_chest): {"creature_seed": 2}, chest_key(old_chest): {"creature_seed": 2}}
        s.state["recent_actions"] = [{"target": {"x": 1, "y": 1, "z": 1}, "result": "failed"}]  # home's own stand
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        steps = PURPOSES["stock_pen"].plan(s, self.context())
        takes = [step for step in steps if step["kind"] == "take"]
        self.assertTrue(takes)
        self.assertEqual([take["target"] for take in takes], [list(old_chest)])

    def test_not_valid_while_its_only_seeds_are_in_a_chest_a_step_just_failed_near(self):
        """Fix round 1, Important 1: stock_valid counted every built chest (seeds_at_hand ->
        chests_built), unfiltered, while plan_stock_pen (item 3) takes only from reachable_chests.
        With seeds only in a chest a step just failed near, stock_valid stayed True but the plan
        was [] -- a stall: plan_done with no penalty, so utility_pick picked stock_pen again every
        tick and Mimo stood idle until something else broke in. Validity must match the plan."""
        design = pens.design_pen(self.grid, (12, 1, 1), "Pip")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        home_chest = storage.chest_spot(self.situation({}))
        self.grid.put(*home_chest, "chest")
        s = self.situation({})
        s.state["chests"] = {chest_key(home_chest): {"creature_seed": 2}}
        s.state["recent_actions"] = [{"target": {"x": 1, "y": 1, "z": 1}, "result": "failed"}]  # home's own stand
        self.assertFalse(PURPOSES["stock_pen"].valid(s))
        self.assertEqual(PURPOSES["stock_pen"].plan(s, self.context()), [])
        s.state["recent_actions"] = []  # the failure ages out of the window: worth trying again
        s = self.situation({})
        s.state["chests"] = {chest_key(home_chest): {"creature_seed": 2}}
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        self.assertTrue(PURPOSES["stock_pen"].plan(s, self.context()))


class PenByHomeTests(unittest.TestCase):
    """L4a final fix wave, I1: pens resolve from home (home.py), never from where Mimo stands. The
    reviewer's probe: a seed carried 80 blocks out started a second pen there, and the herd goal
    counted only the oldest pen, so after the seed and wander trips most pens stood 76-86 blocks out
    and the herd never completed."""

    setUp = PenTests.setUp
    situation = PenTests.situation
    context = PenTests.context

    def finished(self, center):
        design = pens.design_pen(self.grid, center, "Pip")
        number = start(self.db, self.grid, design, 0.0)
        finish_structure(self.db, number, 1.0)
        for planned in design.parts("fence"):
            self.grid.put(*planned.cell, "fence")
        return number, design

    def test_a_seed_carried_80_blocks_out_builds_no_pen_there(self):
        far = self.situation({"creature_seed": 1, **WOOD}, position=(80, 1, 1))
        self.assertFalse(PURPOSES["build_pen"].valid(far))
        self.assertEqual(PURPOSES["build_pen"].plan(far, self.context()), [])
        self.assertEqual(structures(self.db, ("pen",)), [])
        near = self.situation({"creature_seed": 1, **WOOD})  # back by home, the pen goes up there
        self.assertTrue(PURPOSES["build_pen"].valid(near))
        self.assertTrue(PURPOSES["build_pen"].plan(near, self.context()))
        (pen,) = structures(self.db, ("pen",))
        self.assertLessEqual(math.hypot(pen["x"] - 1, pen["z"] - 1), pens.SITE_REACH + pens.PEN_SIZE)

    def test_the_pen_by_home_is_mimos_pen_wherever_it_stands_and_the_herd_counts_it(self):
        self.finished((80, 1, 1))  # an old save's pen, started out where Mimo stood
        number, design = self.finished((12, 1, 1))
        inside = design.parts("pen")[0].cell
        self.grid.herd.add("cow", inside, 10.0, 0.0, 1e9, {"tame": True})
        for position in ((80, 1, 4), (12, 1, 4)):
            s = self.situation({"creature_seed": 1}, position=position)
            self.assertEqual(pens.current_pen(s)["id"], number, position)
            self.assertEqual(life_goals.finished_pen(s)["id"], number, position)
            self.assertEqual(life_goals.animals_in_pen(s), 1, position)
        self.assertFalse(PURPOSES["stock_pen"].valid(self.situation({"creature_seed": 1}, position=(80, 1, 4))))
        self.assertTrue(PURPOSES["stock_pen"].valid(self.situation({"creature_seed": 1}, position=(12, 1, 4))))

    def test_creature_seeds_in_any_chest_mimo_built_are_at_hand(self):
        """The parked Task 6 minor: an old home's chest still holds its seeds once a bigger home
        takes over, so they are counted and taken out from there (as build_storage takes food)."""
        self.finished((12, 1, 1))
        site = find_site(self.grid, (1, 1, 20), (3, 3), ("north",), "flat", reach=0)
        old = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Old Cottage")
        for planned in old.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, old, 0.0), 1.0)
        chest = old.one("chest")
        self.grid.put(*chest, "chest")
        s = self.situation({})
        s.state["chests"] = {chest_key(chest): {"creature_seed": 2}}
        self.assertNotEqual(storage.chest_spot(s), chest)  # not home's own chest
        self.assertEqual(pens.seeds_at_hand(s), 2)
        self.assertTrue(PURPOSES["stock_pen"].valid(s))
        steps = PURPOSES["stock_pen"].plan(s, self.context())
        self.assertEqual(steps[:2], [{"kind": "walk", "target": list(old.anchor), "reach": 0.0, "whole": True},
                                     {"kind": "take", "target": list(chest), "item": "creature_seed", "amount": 2}])
        self.assertEqual(len([step for step in steps if step["kind"] == "plant"]), 2)


if __name__ == "__main__":
    unittest.main()

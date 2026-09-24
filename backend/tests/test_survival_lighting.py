import sqlite3
import unittest

from backend.survival import lighting  # noqa: F401  (registers light_up)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, finish_structure
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import start
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
EVENING = {**DAY, "seconds_into_day": 2000.0}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
CORNERS = [[-2, 1, -2], [4, 1, -2], [-2, 1, 4], [4, 1, 4]]


class LightTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        design = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in design.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        finish_structure(self.db, start(self.db, self.grid, design, 0.0), 1.0)

    def situation(self, inventory, clock=EVENING, position=(1, 1, 1)):
        state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                 "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, clock, 0.0, self.db)

    def plan(self, s):
        return PURPOSES["light_up"].plan(s, ActionContext(grid=self.grid, clock_at=lambda at: s.clock,
                                                           planner=lambda *args: [], events=[], db=self.db))

    def test_offered_in_the_evening_at_home_with_torches_or_coal_and_sticks(self):
        light = PURPOSES["light_up"]
        self.assertTrue(light.valid(self.situation({"torch": 1})))
        self.assertTrue(light.valid(self.situation({"coal": 1, "planks": 2})))
        self.assertFalse(light.valid(self.situation({})))
        self.assertFalse(light.valid(self.situation({"torch": 4}, clock=DAY)))
        self.assertFalse(light.valid(self.situation({"torch": 4}, clock=NIGHT)))
        self.assertFalse(light.valid(self.situation({"torch": 4}, position=(40, 1, 40))))
        self.assertEqual(light.score(self.situation({"torch": 4})), 72.0)

    def test_it_makes_torches_puts_one_on_each_dark_corner_and_goes_back_inside(self):
        steps = self.plan(self.situation({"coal": 2, "sticks": 1, "planks": 2}))
        self.assertEqual([step["recipe"] for step in steps if step["kind"] == "craft"], ["torch"])
        placed = [step["target"] for step in steps if step["kind"] == "place"]
        self.assertEqual(sorted(placed), sorted(CORNERS))
        self.assertTrue(all(step["whole"] for step in steps if step["kind"] == "walk"))
        self.assertEqual(steps[-1], {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True})

    def test_no_torches_are_made_when_they_would_not_fit(self):
        """Fix wave I1: 2 coal and 2 sticks at 16 stacks would make 4 torches with nowhere to go."""
        filler = {f"item_{n}": 1 for n in range(14)}
        s = self.situation({**filler, "coal": 2, "sticks": 2})
        self.assertFalse(PURPOSES["light_up"].valid(s))
        self.assertEqual(self.plan(s), [])
        self.assertTrue(PURPOSES["light_up"].valid(self.situation({**filler, "coal": 1, "sticks": 1})))

    def test_a_mushroom_on_a_corner_is_mined_before_the_torch_goes_there(self):
        """Fix wave I3: a torch cannot go where a mushroom stands."""
        self.grid.put(-2, 1, -2, "brown_mushroom")
        steps = self.plan(self.situation({"torch": 4}))
        at = steps.index({"kind": "place", "target": [-2, 1, -2], "block": "torch"})
        self.assertEqual(steps[at - 1], {"kind": "mine", "target": [-2, 1, -2]})

    def test_lit_corners_are_left_and_one_torch_lights_one_corner(self):
        self.grid.put(-2, 1, -2, "torch")
        steps = self.plan(self.situation({"torch": 1}))
        self.assertEqual(len([step for step in steps if step["kind"] == "place"]), 1)
        for cell in CORNERS[1:]:
            self.grid.put(*cell, "torch")
        self.assertFalse(PURPOSES["light_up"].valid(self.situation({"torch": 3})))


if __name__ == "__main__":
    unittest.main()

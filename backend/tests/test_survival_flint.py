import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import flint  # noqa: F401  (registers gather_flint)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, know
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.steps import finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
BEACH = {(x, 0, z) for x in range(6, 9) for z in range(-1, 2)}  # a gravel shore
LAKE = {(12, 0, 0)}  # gravel under water


def shore():
    def rule(x, y, z):
        if (x, y, z) in BEACH or (x, y, z) in LAKE:
            return "gravel"
        if (x, y, z) == (12, 1, 0):
            return "water"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"
    return Grid(rule)


def situation(inventory, clock=DAY, grid=None, learned=True):
    """L4b: by default Mimo has learned that gravel hides flint (backend.survival.journal)."""
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": inventory,
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    if learned:
        know(db, "gravel", "lesson", 0.0)
    return Situation(state, grid or shore(), clock, 0.0, db)


def natural_gravel(x, z, seed):
    return "gravel" if (x, 0, z) in BEACH or (x, 0, z) in LAKE else "grass"


@patch("backend.survival.flint.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.flint.surface_material", natural_gravel)
@patch("backend.survival.flint.SEA_LEVEL", 0)
class FlintTests(unittest.TestCase):
    def test_wanted_by_day_with_a_bow_or_its_string_and_little_flint(self):
        flint_purpose = PURPOSES["gather_flint"]
        self.assertTrue(flint_purpose.valid(situation({"bow": 1})))
        self.assertTrue(flint_purpose.valid(situation({"string": 3, "flint": 1})))
        self.assertFalse(flint_purpose.valid(situation({})))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1, "flint": 2})))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1, "arrow": 8})))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1}, NIGHT)))
        self.assertFalse(flint_purpose.valid(situation({"bow": 1}, learned=False)))  # L4b: gravel's lesson first
        self.assertEqual(flint_purpose.score(situation({"bow": 1})), 50.0)

    def test_it_walks_to_the_nearest_dry_gravel_and_digs_it(self):
        s = situation({"bow": 1})
        self.assertEqual(flint.gravel_near(s)[0], (6, 0, 0))
        self.assertNotIn((12, 0, 0), flint.gravel_near(s))  # under water
        plan = PURPOSES["gather_flint"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY,
                                                              planner=lambda *args: [], events=[], db=s.db))
        self.assertEqual(plan[0], {"kind": "walk", "target": [6, 0, 0], "reach": 2.0, "whole": True})
        self.assertEqual([step["target"] for step in plan if step["kind"] == "mine"][:3], [[6, 0, 0], [6, 0, -1], [6, 0, 1]])
        self.assertEqual(len([step for step in plan if step["kind"] == "mine"]), 8)

    def test_gravel_in_the_walls_of_its_passage_counts_too(self):
        grid = Grid(lambda x, y, z: "gravel" if (x, y, z) == (1, -3, 0) else "air" if (x, y, z) in ((0, -3, 0), (1, -2, 0)) else "stone")
        s = situation({"bow": 1}, grid=grid)
        s.state["position"] = {"x": 0.0, "y": -3.0, "z": 0.0}
        self.assertEqual(flint.gravel_near(s), [(1, -3, 0)])

    def test_one_mined_gravel_in_eight_gives_a_flint(self):
        grid = shore()
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 7.0, "y": 1.0, "z": 0.0}, "inventory": {}}
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            running = start_step({"kind": "mine", "target": [7, 0, 0]}, state, grid, 0.0)
            finish_step(running, state, grid, running["ends_at"])
        self.assertEqual(state["inventory"], {"gravel": 1, "flint": 1})


if __name__ == "__main__":
    unittest.main()

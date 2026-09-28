"""W2: the new blocks, rain putting out a campfire under the open sky, relighting it, and a fire under a roof."""

import sqlite3
import unittest
from types import SimpleNamespace

from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, hardness, is_solid
from backend.services.crafting import BLOCKS
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Planned
from backend.survival.memory import create_memory_tables, know
from backend.survival.purposes import PURPOSES
from backend.survival.rain import DOUSED, douse, relight_steps, roofed, roofed_first
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.structures import missing
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_cooking import meadow

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def pet(weather="rain", **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0, "sky": {"weather": weather}}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state, grid, wild=False):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    if wild:
        state["difficulty"] = "wild"
    return Situation(state, grid, DAY, 0.0, db)


class BlockTests(unittest.TestCase):
    def test_the_doused_campfire_the_fire_and_the_hearth_come_last(self):
        names = [block["name"] for block in BLOCK_LIST]
        self.assertEqual(names[-3:], ["campfire_out", "fire", "hearth"])
        self.assertEqual(BLOCK_IDS["campfire_out"], BLOCK_IDS["sunleaf"] + 1)
        self.assertEqual((is_solid("campfire_out"), BLOCKS["campfire_out"]["drop"], BLOCKS["campfire_out"].get("glow")),
                         (False, "campfire", None))
        self.assertEqual((is_solid("fire"), hardness("fire"), BLOCKS["fire"]["glow"]), (False, None, True))
        self.assertEqual((is_solid("hearth"), BLOCKS["hearth"]["drop"], BLOCKS["hearth"]["glow"]), (True, "hearth", True))


class DouseTests(unittest.TestCase):
    def douse(self, grid, state):
        events, heard = [], []
        DOUSED.append(lambda state, context, cell, at: heard.append(cell))
        self.addCleanup(DOUSED.pop)
        douse(state, SimpleNamespace(grid=grid, events=events), 5.0)
        return events, heard

    def test_rain_puts_out_a_campfire_under_the_open_sky(self):
        grid = meadow({(2, 1, 0): "campfire"})
        events, heard = self.douse(grid, pet())
        self.assertEqual(grid.material(2, 1, 0), "campfire_out")
        self.assertEqual(events, [(5.0, "fire_out", "The rain put out Pip's campfire.")])
        self.assertEqual(heard, [(2, 1, 0)])

    def test_a_storm_does_too_but_not_clear_weather_or_a_roof(self):
        storm = meadow({(2, 1, 0): "campfire"})
        self.douse(storm, pet("storm"))
        self.assertEqual(storm.material(2, 1, 0), "campfire_out")
        clear = meadow({(2, 1, 0): "campfire"})
        self.douse(clear, pet("clear"))
        self.assertEqual(clear.material(2, 1, 0), "campfire")
        roof = meadow({(2, 1, 0): "campfire", (2, 4, 0): "planks"})
        events, _ = self.douse(roof, pet())
        self.assertEqual((roof.material(2, 1, 0), events), ("campfire", []))
        far = meadow({(80, 1, 0): "campfire"})
        self.douse(far, pet())
        self.assertEqual(far.material(80, 1, 0), "campfire")


class RelightTests(unittest.TestCase):
    def test_a_stick_lights_a_doused_campfire_again(self):
        grid = meadow({(1, 1, 0): "campfire_out"})
        state = pet(inventory={"sticks": 2})
        step = start_step({"kind": "relight", "target": [1, 1, 0]}, state, grid, 0.0)
        finish_step(step, state, grid, step["ends_at"])
        self.assertEqual((grid.material(1, 1, 0), state["inventory"]), ("campfire", {"sticks": 1}))
        with self.assertRaises(StepFailed):
            start_step({"kind": "relight", "target": [1, 1, 0]}, pet(inventory={"sticks": 1}), grid, 0.0)
        with self.assertRaises(StepFailed):
            start_step({"kind": "relight", "target": [2, 1, 0]}, pet(), meadow({(2, 1, 0): "campfire_out"}), 0.0)

    def test_a_doused_campfire_still_furnishes_a_shelter(self):
        planned = Planned((2, 1, 0), "campfire", "campfire")
        self.assertFalse(missing(meadow({(2, 1, 0): "campfire_out"}), planned))
        self.assertTrue(missing(meadow(), planned))

    def test_cook_lights_a_doused_campfire_within_reach_before_it_puts_down_another(self):
        state = pet("clear", inventory={"raw_beef": 1, "sticks": 3, "campfire": 1})
        s = situation(state, meadow({(2, 1, 0): "campfire_out"}))
        steps = PURPOSES["cook"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: DAY, planner=lambda *a: [],
                                                       events=[], db=s.db))
        self.assertEqual(steps[:2], [{"kind": "relight", "target": [2, 1, 0]}, {"kind": "cook", "item": "raw_beef"}])
        rained = situation(pet("rain", inventory={"sticks": 1}), meadow({(2, 1, 0): "campfire_out"}))
        self.assertEqual(relight_steps(rained, 6.0), [])  # one out in the rain stays out


class RoofTests(unittest.TestCase):
    def test_a_pet_that_knows_rain_puts_its_fire_under_a_roof_when_one_is_in_reach(self):
        grid = meadow({(0, 4, 1): "planks"})
        spots = [((1, 1, 0), False), ((0, 1, 1), False), ((-1, 1, 0), False)]
        self.assertTrue(roofed(grid, (0, 1, 1)))
        self.assertFalse(roofed(meadow({(0, 4, 1): "leaves"}), (0, 1, 1)))
        self.assertEqual(roofed_first(situation(pet(), grid), spots)[0], ((0, 1, 1), False))  # gentle: knows it
        wild = situation(pet(), grid, wild=True)
        self.assertEqual(roofed_first(wild, spots), spots)
        know(wild.db, "wild:rain", "lesson", 0.0)
        taught = Situation(wild.state, grid, DAY, 0.0, wild.db)
        self.assertEqual(roofed_first(taught, spots)[0], ((0, 1, 1), False))


if __name__ == "__main__":
    unittest.main()

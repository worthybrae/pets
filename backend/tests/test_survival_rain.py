"""W2: the new blocks, rain putting out a campfire under the open sky, relighting it, and a fire under a roof."""

import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services.block_table import create_block_tables, write_block
from backend.services.blocks import BLOCK_IDS, BLOCK_LIST, hardness, is_solid
from backend.services.crafting import BLOCKS
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Planned
from backend.survival.grid import world_grid
from backend.survival.memory import create_memory_tables, know
from backend.survival.pickers import options
from backend.survival.purposes import PURPOSES
from backend.survival.rain import (
    CAMPFIRES, DOUSED, DOUSED_BLOCK, campfire_rows, campfires_near, douse, relight_steps, roofed, roofed_first,
)
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.structures import missing
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_cooking import meadow
from backend.tests.test_survival_cozy import home_of

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


class CampfireQueryTests(unittest.TestCase):
    """rain.campfires_near's database path (the tick's): one query of the world's blocks a transaction, kept in the
    tick's ActionContext.memo (W2 fix round 4)."""

    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        create_block_tables(self.db)
        for cell, material in (((2, 1, 0), "campfire"), ((60, 1, 0), "campfire"), ((72, 1, 0), "campfire"),
                               ((100, 1, 0), "campfire"), ((3, 1, 0), DOUSED_BLOCK), ((0, 1, 5), "furnace")):
            write_block(self.db, *cell, material)
        flat = patch("backend.survival.grid.block_at", lambda x, y, z, seed: "grass" if y == 0 else "air")
        flat.start()
        self.addCleanup(flat.stop)
        self.grid = world_grid(self.db, "1")  # a meadow whose blocks are the world's, loaded as the tick's are
        self.context = ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[],
                                     db=self.db)

    def test_the_campfires_within_reach_come_from_one_query_a_transaction(self):
        with patch("backend.survival.rain.campfire_rows", wraps=campfire_rows) as queries:
            self.assertEqual(campfires_near(self.context, 0, 0), [(2, 1, 0), (60, 1, 0)])  # 72 and 100 are too far
            self.assertEqual(campfires_near(self.context, 10, 0), [(2, 1, 0), (60, 1, 0), (72, 1, 0)])
            self.assertEqual(queries.call_count, 1)  # 10 blocks on: the query reached DOUSE_MARGIN farther
            self.grid.put(4, 1, 0, "campfire")  # one Mimo puts down in the transaction
            self.assertEqual(campfires_near(self.context, 10, 0), [(2, 1, 0), (4, 1, 0), (60, 1, 0), (72, 1, 0)])
            self.grid.take_changes()  # renewal takes the step's changes: the campfire stays known
            self.assertEqual(campfires_near(self.context, 10, 0), [(2, 1, 0), (4, 1, 0), (60, 1, 0), (72, 1, 0)])
            self.assertEqual(queries.call_count, 1)
            self.assertEqual(campfires_near(self.context, 40, 0), [(2, 1, 0), (4, 1, 0), (60, 1, 0), (72, 1, 0),
                                                                   (100, 1, 0)])
            self.assertEqual(queries.call_count, 2)  # 40 blocks on: asked again round the new spot
        self.assertEqual(campfires_near(SimpleNamespace(grid=self.grid, db=self.db), 0, 0),
                         [(2, 1, 0), (4, 1, 0), (60, 1, 0)])  # a context with no memo asks each time

    def test_the_rain_puts_out_the_campfires_it_found_there_and_forgets_them_when_it_stops(self):
        state = pet()
        douse(state, self.context, 5.0)
        self.assertEqual([self.grid.material(x, 1, 0) for x in (2, 60, 72)], [DOUSED_BLOCK, DOUSED_BLOCK, "campfire"])
        self.assertEqual([row[0] for row in self.db.execute("SELECT material FROM mimo_blocks WHERE x=2")],
                         [DOUSED_BLOCK])
        self.assertIn(CAMPFIRES, self.context.memo)
        douse(pet("clear"), self.context, 6.0)
        self.assertNotIn(CAMPFIRES, self.context.memo)


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

    def test_the_rain_puts_out_homes_fire_and_once_it_stops_mimo_at_home_lights_it_again(self):
        """W2's final review: the campfire by the home's door went out at the first rain, and nothing lit it again
        (a doused campfire still stands for the design's, so the furnishing never came back to it)."""
        yard = home_of((3, 3), "north")
        yard.state.update(inventory={"sticks": 2}, sky={"weather": "rain"})
        fire = yard.home.one("campfire")
        yard.grid.put(*fire, "campfire")
        douse(yard.state, SimpleNamespace(grid=yard.grid, events=[]), 5.0)
        self.assertEqual(yard.grid.material(*fire), DOUSED_BLOCK)
        relight = PURPOSES["relight_fire"]
        self.assertFalse(relight.valid(yard.situation()))  # not while it rains
        yard.state["sky"]["weather"] = "clear"
        s = yard.situation()
        self.assertTrue(relight.valid(s))
        self.assertIn("relight_fire", [option.name for option in options(s)])
        steps = relight.plan(s, yard.context())
        self.assertEqual(steps[-1], {"kind": "relight", "target": list(fire)})
        for step in steps:
            if step["kind"] == "walk":
                yard.state["position"] = dict(zip("xyz", map(float, yard.home.front)))
                continue
            finish_step(start_step(step, yard.state, yard.grid, 10.0), yard.state, yard.grid, 11.0)
        self.assertEqual(yard.grid.material(*fire), "campfire")
        self.assertEqual(yard.state["inventory"], {"sticks": 1})
        self.assertFalse(relight.valid(yard.situation()))
        yard.state["inventory"] = {"sticks": 1}
        yard.grid.put(*fire, DOUSED_BLOCK)
        yard.state["difficulty"] = "wild"
        self.assertFalse(relight.valid(yard.situation()))  # a wild pet once it knows fire
        know(yard.db, "wild:fire", "lesson", 0.0)
        self.assertTrue(relight.valid(yard.situation()))
        yard.state["inventory"] = {}
        self.assertFalse(relight.valid(yard.situation()))  # with a stick


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

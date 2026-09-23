import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places, remember
from backend.survival.purposes import PURPOSES
from backend.survival.senses import ores_around
from backend.survival.situation import Situation
from backend.survival import work  # noqa: F401  (registers the gathering purposes)
from backend.survival.work import dig_heading, sapling_fits, stair
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
LATE = {**DAY, "seconds_into_day": 2100.0}
TREE = (5, 0, 0)  # trunk x, trunk z, ground height: logs at y 1 to 4


def forest():
    """Flat stone with one oak trunk at x=5, z=0 (logs at y 1 to 4)."""
    return Grid(lambda x, y, z: "oak_log" if (x, z) == (5, 0) and 1 <= y <= 4 else ("stone" if y <= 0 else "air"))


def ground(cells=None):
    """Grass at y 0, dirt at y -1 and -2, stone to y -4, bedrock below; `cells` override single cells."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if y <= -5:
            return "bedrock"
        if y <= -3:
            return "stone"
        if y <= -1:
            return "dirt"
        return "grass" if y == 0 else "air"

    return Grid(rule)


def pet(position=(0, 1, 0), **changes):
    state = {"name": "Pip", "world_seed": "1", "inventory": {}, "vitals": dict(START_VITALS), "traits": {},
             "last_tick_at": 0.0, "position": {"x": float(position[0]), "y": float(position[1]), "z": float(position[2])}}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state, grid, places_seen=(), clock=DAY):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell, note in places_seen:
        remember(db, kind, cell, 0.0, note)
    return Situation(state, grid, clock, 0.0, db)


def late_drop(name, state, grid, places_seen=()):
    """How much lower `name` scores late in the day than by day."""
    return (PURPOSES[name].score(situation(state, grid, places_seen))
            - PURPOSES[name].score(situation(state, grid, places_seen, LATE)))


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])


def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}


def walk(x, y, z, reach=0.0):
    return {"kind": "walk", "target": [x, y, z], "reach": reach}


@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class WoodTests(unittest.TestCase):
    def test_chops_the_nearest_tree_bottom_up_until_eight_logs_of_wood(self):
        s = situation(pet(), forest())
        wood = PURPOSES["gather_wood"]
        self.assertTrue(wood.valid(s))
        self.assertEqual(wood.plan(s, context(s.grid)),
                         [walk(5, 1, 0, 2.0), mine(5, 1, 0), mine(5, 2, 0), mine(5, 3, 0), mine(5, 4, 0)])
        full = situation(pet(inventory={"oak_log": 6, "planks": 8}), forest())
        self.assertFalse(wood.valid(full))
        self.assertEqual(wood.plan(full, context(full.grid)), [])

    def test_carried_saplings_are_planted_in_open_ground_before_chopping(self):
        grid = ground({(5, y, 0): "oak_log" for y in (1, 2, 3, 4)})
        s = situation(pet(inventory={"sapling": 3}), grid)
        sapling = lambda x, y, z: {"kind": "plant", "target": [x, y, z], "item": "sapling"}  # noqa: E731
        self.assertEqual(PURPOSES["gather_wood"].plan(s, context(grid)),
                         [sapling(-1, 1, 0), sapling(2, 1, 0), walk(5, 1, 0, 2.0),
                          mine(5, 1, 0), mine(5, 2, 0), mine(5, 3, 0), mine(5, 4, 0)])
        roofed = ground({(-1, 3, 0): "stone", **{(5, y, 0): "oak_log" for y in (1, 2, 3, 4)}})
        s = situation(pet(inventory={"sapling": 1}), roofed)
        self.assertEqual(PURPOSES["gather_wood"].plan(s, context(roofed))[0], sapling(0, 1, -1))

    def test_saplings_go_on_the_natural_surface_and_away_from_home(self):
        logs = {(5, y, 0): "oak_log" for y in (1, 2, 3, 4)}
        sapling = lambda x, y, z: {"kind": "plant", "target": [x, y, z], "item": "sapling"}  # noqa: E731
        # The first stair of a staircase dug west: an open cell on dirt below the grass.
        stairs = situation(pet(inventory={"sapling": 1}), ground({(-1, 0, 0): "air", **logs}))
        self.assertFalse(sapling_fits(stairs, (-1, 0, 0)))
        self.assertTrue(sapling_fits(stairs, (0, 1, -1)))
        home = situation(pet(inventory={"sapling": 1}), ground(logs), places_seen=[("home", (-1, 1, 0), "")])
        self.assertEqual(PURPOSES["gather_wood"].plan(home, context(home.grid))[0], sapling(1, 1, 0))
        sheltered = situation(pet(inventory={"sapling": 1}), ground(logs), places_seen=[("shelter", (1, 1, 0), "")])
        self.assertFalse(sapling_fits(sheltered, (1, 1, 1)))
        self.assertTrue(sapling_fits(sheltered, (-1, 1, 0)))

    def test_a_tree_where_a_step_failed_is_left_alone(self):
        state = pet()
        state["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                    "target": {"x": 5, "y": 1, "z": 0}, "reason": "no way there", "code": "no_path"}]
        self.assertFalse(PURPOSES["gather_wood"].valid(situation(state, forest())))

    def test_a_tree_grown_from_a_planted_sapling_is_chopped_and_a_log_wall_is_not(self):
        placed = ground()
        for y in (1, 2, 3, 4):
            placed.put(9, y, 0, "oak_log")
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: []):
            self.assertFalse(PURPOSES["gather_wood"].valid(situation(pet(), placed)))
            grown = situation(pet(), placed, places_seen=[("tree", (9, 1, 0), "")])
            self.assertEqual(PURPOSES["gather_wood"].plan(grown, context(placed))[:2], [walk(9, 1, 0, 2.0), mine(9, 1, 0)])


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
class StoneTests(unittest.TestCase):
    def test_digs_a_staircase_down_two_blocks_per_stair(self):
        s = situation(pet(inventory={"wooden_pickaxe": 1}), ground())
        stone = PURPOSES["gather_stone"]
        self.assertTrue(stone.valid(s))
        self.assertEqual(stone.plan(s, context(s.grid)),
                         [mine(1, 0, 0), walk(1, 0, 0), mine(2, 0, 0), mine(2, -1, 0), walk(2, -1, 0),
                          mine(3, -1, 0), mine(3, -2, 0), walk(3, -2, 0), mine(4, -2, 0), mine(4, -3, 0), walk(4, -3, 0)])
        self.assertEqual(s.brain["dig_heading"], [1, 0])
        self.assertFalse(stone.valid(situation(pet(), ground())))

    def test_turns_into_a_level_tunnel_deep_down(self):
        s = situation(pet((4, -3, 0), inventory={"wooden_pickaxe": 1}), ground({(4, -3, 0): "air"}))
        s.brain["dig_heading"] = [1, 0]
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)),
                         [mine(5, -3, 0), walk(5, -3, 0), mine(6, -3, 0), walk(6, -3, 0),
                          mine(7, -3, 0), walk(7, -3, 0), mine(8, -3, 0), walk(8, -3, 0)])

    def test_stops_at_the_goal(self):
        s = situation(pet((4, -3, 0), inventory={"wooden_pickaxe": 1, "cobblestone": 11}), ground({(4, -3, 0): "air"}))
        s.brain["dig_heading"] = [1, 0]
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)), [mine(5, -3, 0), walk(5, -3, 0)])
        done = situation(pet(inventory={"wooden_pickaxe": 1, "cobblestone": 12}), ground())
        self.assertFalse(PURPOSES["gather_stone"].valid(done))

    def test_never_digs_into_water(self):
        s = situation(pet(inventory={"wooden_pickaxe": 1}), ground({(1, 0, 0): "water"}))
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid))[0], mine(0, 0, 1))

    def test_never_turns_back_the_way_it_came(self):
        tunnel = {(4, -3, 0): "air", (5, -3, 0): "water", (4, -3, 1): "bedrock", (4, -3, -1): "bedrock"}
        s = situation(pet((4, -3, 0), inventory={"wooden_pickaxe": 1}), ground(tunnel))
        s.brain["dig_heading"] = [1, 0]
        self.assertIsNone(dig_heading(s))  # only the way back is open to digging
        self.assertEqual(PURPOSES["gather_stone"].plan(s, context(s.grid)), [])
        s.brain["dig_heading"] = None
        self.assertEqual(dig_heading(s), (-1, 0))

    def test_a_stair_never_digs_away_the_floor_of_an_open_cell_underground(self):
        inventory = {"wooden_pickaxe": 1}
        step_above = ground({(4, -3, 0): "air", (5, -2, 0): "air"})  # an earlier stair's cell over (5, -3, 0)
        self.assertIsNone(stair(step_above, {}, (4, -3, 0), (1, 0), inventory, "1"))
        self.assertEqual(stair(ground({(4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), inventory, "1"),
                         ([mine(5, -3, 0), walk(5, -3, 0)], (5, -3, 0), 1))
        # Its own upper cell opened by the same stair is fine, and so is open sky over the surface.
        self.assertEqual(stair(ground(), {}, (0, 1, 0), (1, 0), inventory, "1")[0], [mine(1, 0, 0), walk(1, 0, 0)])
        self.assertEqual(stair(ground(), {}, (1, 0, 0), (1, 0), inventory, "1")[0],
                         [mine(2, 0, 0), mine(2, -1, 0), walk(2, -1, 0)])

    def test_a_stair_never_digs_up_farmland_or_a_sapling(self):
        inventory = {"wooden_pickaxe": 1}
        self.assertIsNone(stair(ground({(1, 0, 0): "farmland"}), {}, (0, 1, 0), (1, 0), inventory, "1"))
        self.assertIsNone(stair(ground({(1, 1, 0): "sapling"}), {}, (0, 1, 0), (1, 0), inventory, "1"))

    def test_with_a_stone_pickaxe_it_digs_on_for_iron_until_it_sees_some(self):
        stocked = {"stone_pickaxe": 1, "cobblestone": 12}
        s = situation(pet(inventory=stocked), ground())
        self.assertTrue(PURPOSES["gather_stone"].valid(s))
        self.assertEqual(len(PURPOSES["gather_stone"].plan(s, context(s.grid))), 11)
        seen = situation(pet(inventory=stocked), ground(), [("ore", (9, -3, 9), "iron_ore")])
        self.assertFalse(PURPOSES["gather_stone"].valid(seen))


class OreTests(unittest.TestCase):
    def test_walks_close_to_a_remembered_ore_and_mines_it(self):
        grid = ground({(3, -3, 0): "iron_ore"})
        seen = [("ore", (3, -3, 0), "iron_ore")]
        ore = PURPOSES["mine_ore"]
        self.assertFalse(ore.valid(situation(pet(inventory={"wooden_pickaxe": 1}), grid, seen)))
        s = situation(pet(inventory={"stone_pickaxe": 1}), grid, seen)
        self.assertTrue(ore.valid(s))
        self.assertEqual(ore.plan(s, context(grid)), [walk(3, -3, 0, 3.0), mine(3, -3, 0)])

    def test_an_ore_that_is_gone_is_forgotten(self):
        s = situation(pet(inventory={"stone_pickaxe": 1}), ground(), [("ore", (3, -3, 0), "iron_ore")])
        self.assertEqual(PURPOSES["mine_ore"].plan(s, context(s.grid)), [])
        self.assertEqual(places(s.db), [])

    def test_only_ores_mimo_still_needs_are_wanted(self):
        grid = ground({(2, 0, 0): "coal_ore"})
        seen = [("ore", (2, 0, 0), "coal_ore")]
        self.assertTrue(PURPOSES["mine_ore"].valid(situation(pet(inventory={"wooden_pickaxe": 1}), grid, seen)))
        stocked = pet(inventory={"wooden_pickaxe": 1, "coal": 8})
        self.assertFalse(PURPOSES["mine_ore"].valid(situation(stocked, grid, seen)))

    def test_an_ore_in_the_floor_of_a_stair_is_left_alone(self):
        seen = [("ore", (3, -3, 0), "iron_ore")]
        cut = situation(pet(inventory={"stone_pickaxe": 1}), ground({(3, -3, 0): "iron_ore", (3, -2, 0): "air",
                                                                     (3, -1, 0): "air"}), seen)
        self.assertFalse(PURPOSES["mine_ore"].valid(cut))
        buried = situation(pet(inventory={"stone_pickaxe": 1}), ground({(3, -3, 0): "iron_ore"}), seen)
        self.assertTrue(PURPOSES["mine_ore"].valid(buried))


@patch("backend.survival.purposes.terrain_height", lambda x, z, seed: 0)
class LateDayTests(unittest.TestCase):
    def test_outdoor_work_scores_lower_late_in_the_day(self):
        self.assertEqual(late_drop("gather_wood", pet(), forest()), 30.0)
        picks = {"wooden_pickaxe": 1}
        self.assertEqual(late_drop("gather_stone", pet(inventory=picks), ground()), 30.0)  # starting on the surface
        self.assertEqual(late_drop("gather_stone", pet((4, -3, 0), inventory=picks), ground({(4, -3, 0): "air"})), 0.0)
        near = [("ore", (3, -3, 0), "coal_ore")]
        self.assertEqual(late_drop("mine_ore", pet(inventory=picks), ground({(3, -3, 0): "coal_ore"}), near), 0.0)
        far = [("ore", (30, -3, 0), "coal_ore")]
        self.assertEqual(late_drop("mine_ore", pet(inventory=picks), ground({(30, -3, 0): "coal_ore"}), far), 30.0)


class SensesTests(unittest.TestCase):
    def test_ores_around_a_mined_block(self):
        grid = ground({(1, -3, 0): "coal_ore", (0, -2, 1): "iron_ore"})
        self.assertEqual(ores_around(grid, (0, -3, 0)), [((0, -2, 1), "iron_ore"), ((1, -3, 0), "coal_ore")])


if __name__ == "__main__":
    unittest.main()

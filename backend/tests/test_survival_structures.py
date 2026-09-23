import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.grid import Grid, world_grid
from backend.survival.memory import (
    BUILT, create_memory_tables, finish_structure, forget, places, remember, set_home, structures,
)
from backend.survival.situation import Situation
from backend.survival.structures import blocked, damaged, reserved, start, structure_at, todo
from backend.survival.toolmaking import free_cells
from backend.survival.vitals import START_VITALS
from backend.survival.work import sapling_spots, stair
from backend.survival.world import SurvivalWorld, new_survival_state

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def meadow(cells=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


def hut(grid):
    site = find_site(grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
    return shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")


def memory():
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return db


def finish(grid, design):
    for planned in design.parts("floor", "wall", "roof"):
        if planned.block != "natural":
            grid.put(*planned.cell, "cobblestone")


class MemoryTests(unittest.TestCase):
    def test_set_home_moves_home_and_keeps_the_old_one_as_a_shelter(self):
        db = memory()
        remember(db, "home", (0, -3, 0), 0.0)
        self.assertFalse(remember(db, "home", (9, 1, 9), 1.0))  # remember never moves home
        set_home(db, (9, 1, 9), 2.0)
        homes = places(db, ("home",))
        self.assertEqual([(place["x"], place["note"]) for place in homes], [(9, BUILT)])
        self.assertEqual([(place["kind"], place["x"]) for place in places(db, ("shelter",))], [("shelter", 0)])

    def test_a_built_home_is_never_forgotten(self):
        db = memory()
        set_home(db, (9, 1, 9), 0.0)
        forget(db, "home", (9, 1, 9))
        self.assertEqual(len(places(db, ("home",))), 1)
        remember(db, "shelter", (30, 1, 30), 0.0)
        forget(db, "shelter", (30, 1, 30))
        self.assertEqual(places(db, ("shelter",)), [])

    def test_a_structure_remembers_its_design_and_claims_its_cells(self):
        db, grid = memory(), meadow()
        design = hut(grid)
        number = start(db, grid, design, 5.0)
        found = structures(db)
        self.assertEqual([(row["kind"], row["name"], row["status"]) for row in found],
                         [("shelter", "Pip's Snug Cottage", "building")])
        self.assertEqual(found[0]["data"]["anchor"], [1, 1, 1])
        self.assertEqual(structure_at(db, (1, 1, 1)), number)
        self.assertTrue(grid.claimed((-1, 1, 0)))  # at once, for plans later in the same tick
        finish_structure(db, number, 9.0)
        self.assertEqual((structures(db)[0]["status"], structures(db)[0]["built_at"]), ("done", 9.0))


class WorldClaimsTests(unittest.TestCase):
    def test_a_world_grid_loads_the_claims_of_each_chunk_it_reads(self):
        with tempfile.TemporaryDirectory() as root:
            world = SurvivalWorld.create(Path(root) / "2.sqlite3", new_survival_state(
                name="Pip", seed="7", spawn={"x": 3682, "y": 5, "z": 4143}, born_at=0.0, traits={}))
            with world.transaction() as db:
                db.execute("INSERT INTO structure_cells(x,y,z,structure,part,block) VALUES (3682, 6, 4143, 1, 'wall', 'dirt')")
            with world.connect() as db:
                grid = world_grid(db, "7")
                self.assertTrue(grid.claimed((3682, 6, 4143)))
                self.assertFalse(grid.claimed((3682, 7, 4143)))


class ProgressTests(unittest.TestCase):
    def test_todo_lists_what_is_missing_in_build_order_and_damage_reopens_it(self):
        grid = meadow()
        design = hut(grid)
        self.assertEqual(len(todo(grid, design)), 39)
        finish(grid, design)
        self.assertEqual(todo(grid, design), [])
        self.assertFalse(damaged(grid, design))
        grid.put(-1, 2, 1, "air")
        self.assertEqual([planned.cell for planned in todo(grid, design)], [(-1, 2, 1)])
        self.assertTrue(damaged(grid, design))
        self.assertEqual([planned.cell for planned in todo(grid, design, ("bed", "campfire"))], [(0, 1, 2), (2, 1, -2)])

    def test_something_solid_in_the_door_or_the_way_in_blocks_it(self):
        grid = meadow()
        design = hut(grid)
        finish(grid, design)
        grid.put(1, 1, -2, "furnace")
        grid.put(1, 1, -1, "campfire")  # a campfire can be walked through
        self.assertEqual(blocked(grid, design), [(1, 1, -2)])
        self.assertTrue(damaged(grid, design))


class ReservedTests(unittest.TestCase):
    def setUp(self):
        self.grid = meadow({(6, 0, 0): "farmland"})
        start(memory(), self.grid, hut(self.grid), 0.0)

    def situation(self, position, inventory=None):
        state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                 "inventory": inventory or {}, "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(state)
        return Situation(state, self.grid, DAY, 0.0, memory())

    def test_the_home_its_door_and_the_way_in_are_reserved_and_so_are_plots(self):
        for cell in ((1, 1, 1), (0, 2, 2), (1, 1, -1), (1, 1, -2), (1, 2, -2), (-1, 1, 0), (6, 0, 0)):
            self.assertTrue(reserved(self.grid, cell), cell)
        self.assertFalse(reserved(self.grid, (5, 1, 5)))

    def test_no_stair_is_dug_into_the_house(self):
        inventory = {"wooden_pickaxe": 1}
        self.assertIsNone(stair(self.grid, {}, (1, 1, 1), (1, 0), inventory, "1"))
        self.assertIsNone(stair(self.grid, {}, (4, 1, 0), (-1, 0), inventory, "1"))
        self.assertIsNotNone(stair(self.grid, {}, (4, 1, 0), (1, 0), inventory, "1"))

    def test_no_station_goes_down_inside_or_in_the_way_in(self):
        self.assertEqual(free_cells(self.situation((1, 1, 1))), [])
        self.assertNotIn((1, 1, -2), free_cells(self.situation((1, 1, -3))))

    def test_no_sapling_is_planted_in_the_way_in(self):
        spots = sapling_spots(self.situation((1, 1, -4), {"sapling": 2}))
        self.assertTrue(spots)
        self.assertNotIn((1, 1, -2), spots)


if __name__ == "__main__":
    unittest.main()

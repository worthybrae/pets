"""W2: the hard winter: the ice overlay and the open cell a swimming pet keeps, a path across a frozen lake,
growth that waits for spring, cave mushrooms, thinned herds, fish, and food that keeps longer."""

import sqlite3
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.services.worldgen import SEA_LEVEL
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.spawning import LAND_CAP, WINTER_LAND_CAP, populate
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.pathing import route
from backend.survival.renewal import create_growth_table, renew, schedule, scheduled
from backend.survival.sky import next_season_at
from backend.survival.spoilage import age
from backend.survival.steps import StepFailed, start_step
from backend.survival.winter import freeze

BORN = 1_000_000.0
SCALE = 60.0
WINTER_DAY = 31  # a newborn's first winter


def day_start(day: int) -> float:
    return BORN + (day - 1) * DAY_SECONDS / SCALE


def lake(x0=10, x1=40):
    """A lake from x0 to x1 (water at SEA_LEVEL and one below, sand under), grass at SEA_LEVEL elsewhere, and a
    cave lake at y -3 everywhere under the land."""
    def natural(x, y, z):
        if x0 <= x <= x1:
            return "water" if SEA_LEVEL - 1 <= y <= SEA_LEVEL else "sand" if y < SEA_LEVEL - 1 else "air"
        if y == -3:
            return "water"
        return "grass" if y == SEA_LEVEL else "dirt" if y < SEA_LEVEL else "air"

    grid = Grid(natural)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(x=0, y=SEA_LEVEL + 1, z=0, season="winter"):
    return {"name": "Pip", "world_seed": "7", "born_at": BORN, "position": {"x": float(x), "y": float(y), "z": float(z)},
            "vitals": {"health": 100.0}, "inventory": {}, "sky": {"offset": 0, "season": season}}


def context(grid, db=None):
    return SimpleNamespace(grid=grid, events=[], db=db, clock_at=lambda at: clock_at(BORN, at, SCALE))


class IceTests(unittest.TestCase):
    def test_in_winter_surface_water_reads_as_walkable_ice_and_cave_water_stays(self):
        grid = lake()
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")
        grid.overlay({"frozen": True})
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "ice")
        self.assertTrue(grid.standable((20, SEA_LEVEL + 1, 0)))
        self.assertFalse(grid.swimming((20, SEA_LEVEL + 1, 0)))
        self.assertEqual(grid.material(20, SEA_LEVEL - 1, 0), "water")
        self.assertEqual(grid.material(0, -3, 0), "water")
        self.assertFalse(grid.water((20, SEA_LEVEL, 0)))  # no fishing through the ice
        grid.put(21, SEA_LEVEL, 0, "water")  # an edited cell is no lake's surface
        self.assertEqual(grid.material(21, SEA_LEVEL, 0), "water")
        grid.overlay({"frozen": False})
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")

    def test_the_ice_is_too_thick_to_mine_but_a_taigas_own_ice_is_not(self):
        grid = lake()
        grid.overlay({"frozen": True})
        state = {**pet(19, SEA_LEVEL + 1, 0), "inventory": {"stone_pickaxe": 1}}
        with self.assertRaises(StepFailed) as raised:
            start_step({"kind": "mine", "target": [20, SEA_LEVEL, 0]}, state, grid, 0.0)
        self.assertEqual(str(raised.exception), "the ice is too thick")
        taiga = Grid(lambda x, y, z: "ice" if y == SEA_LEVEL else "air")
        self.assertEqual(start_step({"kind": "mine", "target": [20, SEA_LEVEL, 0]}, state, taiga, 0.0)["block"], "ice")

    def test_the_freeze_comes_at_the_first_winter_dawn_and_a_swimming_pet_keeps_its_water_until_dawn(self):
        grid = lake()
        swimmer = pet(20, SEA_LEVEL + 1, 0)
        grid.herd.add("fish", (25, SEA_LEVEL, 0), 2.0, BORN, BORN, {"home": [25, SEA_LEVEL, 0]})
        freeze(swimmer, context(grid), day_start(WINTER_DAY))
        sky = swimmer["sky"]
        self.assertTrue(sky["frozen"])
        self.assertEqual(sky["open_cells"], [[20, SEA_LEVEL, 0]])
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")
        self.assertEqual(grid.material(21, SEA_LEVEL, 0), "ice")
        fish = grid.herd.near(25, 0, 2)
        self.assertEqual([round(creature["y"]) for creature in fish], [SEA_LEVEL - 1])  # it swam down
        freeze(swimmer, context(grid), day_start(WINTER_DAY + 1) + 1 / SCALE)
        self.assertEqual((sky["open_cells"], grid.material(20, SEA_LEVEL, 0)), ([], "ice"))
        swimmer["sky"]["season"] = "spring"
        freeze(swimmer, context(grid), day_start(41))
        self.assertFalse(sky["frozen"])
        self.assertEqual(grid.material(20, SEA_LEVEL, 0), "water")

    def test_a_fish_with_no_water_under_it_fades(self):
        shallow = lake()
        shallow.put(25, SEA_LEVEL - 1, 0, "sand")
        shallow.herd.add("fish", (25, SEA_LEVEL, 0), 2.0, BORN, BORN, {"home": [25, SEA_LEVEL, 0]})
        freeze(pet(0), context(shallow), day_start(WINTER_DAY))
        self.assertEqual(shallow.herd.near(25, 0, 2), [])

    def test_a_path_crosses_a_frozen_lake_and_the_overlay_costs_the_search_little(self):
        frozen, open_water = lake(), lake()
        frozen.overlay({"frozen": True})
        cells, reached = route(frozen, (0, SEA_LEVEL + 1, 0), (50, SEA_LEVEL + 1, 0))
        self.assertTrue(reached)
        self.assertFalse(any(frozen.swimming(cell) for cell in cells))
        swum, _ = route(open_water, (0, SEA_LEVEL + 1, 0), (50, SEA_LEVEL + 1, 0))
        self.assertTrue(any(open_water.swimming(cell) for cell in swum))

        def timed(frozen_now: bool) -> float:
            grid = lake()
            grid.overlay({"frozen": frozen_now})
            started = time.perf_counter()
            route(grid, (0, SEA_LEVEL + 1, 0), (50, SEA_LEVEL + 1, 0))
            return time.perf_counter() - started

        # The fastest of 15 searches each, taken in turn, so a load spike on a busy machine favours neither.
        times = {True: [], False: []}
        for _ in range(15):
            for frozen_now in (False, True):
                times[frozen_now].append(timed(frozen_now))
        self.assertLessEqual(min(times[True]), min(times[False]) * 1.1)


class GrowthTests(unittest.TestCase):
    def world(self):
        db = sqlite3.connect(":memory:")
        create_growth_table(db)
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "stone" if y < 0 else "air")
        state = {**pet(season="winter"), "world_seed": "7"}
        return db, grid, state

    def test_growth_that_falls_due_in_winter_waits_for_the_first_spring_dawn(self):
        db, grid, state = self.world()
        grid.put(0, 0, 0, "farmland")
        grid.put(0, 1, 0, "wheat_0")
        grid.take_changes()
        due = day_start(WINTER_DAY) + 600 / SCALE
        for cell, block in (((0, 1, 0), "wheat_1"), ((3, 1, 0), "berry_bush_ripe"), ((5, 0, 5), "dirt")):
            schedule(db, cell, block, due)
        schedule(db, (7, 6, 7), "air", due)  # a leaf decaying goes ahead
        with patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0):
            renew(state, SimpleNamespace(db=db, grid=grid, events=[], clock_at=lambda at: clock_at(BORN, at, SCALE)),
                  due + 1)
        spring = next_season_at(state, due, SCALE, "spring")
        self.assertEqual(spring, day_start(41))
        waiting = {cell: (block, ready) for cell, block, ready in scheduled(db)}
        self.assertEqual(waiting, {(0, 1, 0): ("wheat_1", spring), (3, 1, 0): ("berry_bush_ripe", spring),
                                   (5, 0, 5): ("dirt", spring)})
        self.assertEqual(grid.material(0, 1, 0), "wheat_0")

    def test_a_cave_mushroom_comes_back_on_its_spot_in_winter_too(self):
        db, grid, state = self.world()
        cave = (4, -3, 4)
        grid.put(*cave, "air")
        grid.put(4, -4, 4, "stone")
        grid.put(*cave, "brown_mushroom")
        grid.take_changes()
        grid.put(*cave, "air")  # picked
        ctx = SimpleNamespace(db=db, grid=grid, events=[], clock_at=lambda at: clock_at(BORN, at, SCALE))
        picked = day_start(WINTER_DAY) + 100 / SCALE
        with patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0):
            renew(state, ctx, picked)
            self.assertEqual([(cell, block) for cell, block, _ in scheduled(db)], [(cave, "brown_mushroom")])
            renew(state, ctx, picked + DAY_SECONDS / SCALE)
        self.assertEqual(grid.material(*cave), "brown_mushroom")


class AnimalTests(unittest.TestCase):
    def scene(self, season, herd):
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        grid.herd = herd
        state = {**pet(0, 1, 0, season), "world_seed": "4"}
        return Scene(grid, herd, "4", state, 100.0, 1.0, events=[], clock={"phase": "day", "time_scale": 1.0})

    def test_in_winter_a_new_chunk_rolls_one_herd_at_most_and_the_land_cap_is_twelve(self):
        found = {}
        for season in ("spring", "winter"):
            db = sqlite3.connect(":memory:")
            create_creature_tables(db)
            herd = Herd(db)
            with patch("backend.survival.creatures.spawning.terrain_height", lambda x, z, seed: 0), \
                    patch("backend.survival.creatures.spawning.biome_at", lambda x, z, seed: "meadow"):
                found[season] = []
                for _ in range(8):  # NEW_CHUNKS a call: every chunk within reach in a few calls
                    found[season] += populate(self.scene(season, herd), herd.near(0, 0, 48), 1.0)
                rolled = [row["herds"] for row in herd.chunks((-9, -9), (9, 9)).values()]
            self.assertLessEqual(max(rolled), 1 if season == "winter" else 2)
        self.assertLessEqual(len(found["winter"]), WINTER_LAND_CAP)
        self.assertGreater(len(found["spring"]), WINTER_LAND_CAP)
        self.assertLessEqual(len(found["spring"]), LAND_CAP)

    def test_no_fish_come_back_in_winter(self):
        state = {"fish": {"1,1": {"stock": 4, "since": 0.0}}}
        nature.recover_fish(state, 3 * DAY_SECONDS, 1.0, grows=False)
        self.assertEqual(state["fish"]["1,1"], {"stock": 4, "since": 3 * DAY_SECONDS})
        nature.recover_fish(state, 5 * DAY_SECONDS, 1.0)
        self.assertEqual(state["fish"]["1,1"]["stock"], 6)


class SpoilageTests(unittest.TestCase):
    def test_in_winter_food_goes_off_a_third_as_fast(self):
        worn = {}
        for season in ("autumn", "winter"):
            state = {**pet(season=season), "difficulty": "wild", "inventory": {"raw_beef": 1}, "lots": {"raw_beef": [[1, 0.0]]}}
            age(state, SimpleNamespace(events=[], db=None), 600.0, 0.0)
            worn[season] = state["lots"]["raw_beef"][0][1]
        self.assertAlmostEqual(worn["winter"] * 3, worn["autumn"])


if __name__ == "__main__":
    unittest.main()

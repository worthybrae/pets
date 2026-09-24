import math
import random
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import tick
from backend.survival.actions import ActionContext
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import DEAD_KEEP, MAX_ACTS, simulate
from backend.survival.creatures.spawning import (
    FISH_PER_REGION, NEW_CHUNKS, PASSIVE_CAP, SIM_REACH, chunks_near, herd_count, plan_herd, populate,
)
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid, world_grid
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.tick import advance_world
from backend.survival.world import SurvivalWorld

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
BORN = 1_000_000.0


def flat(water=()):
    """Grass at y 0, or water in the `water` columns."""
    return Grid(lambda x, y, z: ("water" if (x, z) in water else "grass") if y == 0 else "dirt" if y < 0 else "air")


def pet(x=8, z=8):
    return {"name": "Pip", "world_seed": "1", "position": {"x": float(x), "y": 1.0, "z": float(z)}, "brain": {}}


def herd():
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    return Herd(db)


def context(grid, db):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)


def flatland(test):
    """Flat meadow for the spawner: ground at y 0 everywhere, sea level 2 (so no natural water)."""
    for target, value in (("terrain_height", lambda x, z, seed: 0), ("biome_at", lambda x, z, seed: "meadow"),
                          ("SEA_LEVEL", -9)):
        patcher = patch(f"backend.survival.creatures.spawning.{target}", value)
        patcher.start()
        test.addCleanup(patcher.stop)


class SpawnTests(unittest.TestCase):
    def setUp(self):
        flatland(self)

    def test_chunks_within_reach_nearest_first_when_populating(self):
        near = chunks_near(8, 8, SIM_REACH)
        self.assertIn((0, 0), near)
        self.assertIn((3, 0), near)
        self.assertNotIn((4, 4), near)  # its nearest column is 56 blocks off on each axis
        self.assertEqual(len(near), len(set(near)))

    def test_a_chunk_rolls_the_same_herds_every_time(self):
        grid = flat()
        counts = {herd_count("1", (cx, 0)) for cx in range(40)}
        self.assertEqual(counts, {0, 1, 2})
        first = plan_herd(grid, "1", (3, 5), 0)
        self.assertEqual(plan_herd(flat(), "1", (3, 5), 0), first)
        kind, cells = first
        self.assertIn(kind.name, ("rabbit", "chicken", "sheep", "cow"))
        self.assertTrue(kind.herd[0] <= len(cells) <= kind.herd[1])
        self.assertTrue(all(3 * 16 - 1 <= x <= 4 * 16 and y == 1 for x, y, _ in cells))

    def test_herds_spawn_once_per_chunk_as_mimo_comes_near_and_stop_at_the_cap(self):
        grid, creatures = flat(), herd()
        state = pet()
        scene = Scene(grid, creatures, "1", state, 10.0)
        added = populate(scene, [], 1.0)
        self.assertTrue(added)
        noted = creatures.chunks((-9, -9), (9, 9))
        self.assertEqual(len(noted), NEW_CHUNKS)  # the rest wait for the next call
        self.assertLessEqual(len(added), PASSIVE_CAP)
        for _ in range(10):
            added += populate(Scene(grid, creatures, "1", state, 10.0), creatures.near(8, 8, SIM_REACH), 1.0)
        self.assertEqual(set(creatures.chunks((-9, -9), (9, 9))), set(chunks_near(8, 8, SIM_REACH)))
        self.assertEqual(len(creatures.near(8, 8, SIM_REACH)), PASSIVE_CAP)
        for creature in added:
            self.assertEqual(creature["state"]["home"], list(cell_of(creature)))
            self.assertTrue(grid.standable(cell_of(creature)))
            self.assertEqual(creature["health"], KINDS[creature["kind"]].health)
        self.assertEqual(populate(Scene(grid, creatures, "1", state, 11.0), creatures.near(8, 8, SIM_REACH), 1.0), [])

    def test_a_school_of_fish_spawns_in_natural_water_and_a_region_holds_at_most_six(self):
        with patch("backend.survival.creatures.spawning.SEA_LEVEL", 0), \
                patch("backend.survival.creatures.spawning.terrain_height", lambda x, z, seed: -1):
            lake = {(x, z) for x in range(-40, 60) for z in range(-40, 60)}
            grid, creatures = flat(lake), herd()
            for _ in range(10):
                populate(Scene(grid, creatures, "1", pet(), 10.0), creatures.near(8, 8, SIM_REACH), 1.0)
        fish = [creature for creature in creatures.near(8, 8, 100) if creature["kind"] == "fish"]
        self.assertTrue(fish)
        for creature in fish:
            self.assertTrue(grid.water(cell_of(creature)))
        regions = {}
        for creature in fish:
            key = (int(creature["x"]) // 16, int(creature["z"]) // 16)
            regions[key] = regions.get(key, 0) + 1
        self.assertLessEqual(max(regions.values()), FISH_PER_REGION)

    def test_a_chunk_whose_animals_were_all_hunted_gets_a_herd_back_after_three_game_days(self):
        grid, creatures = flat(), herd()
        with patch("backend.survival.creatures.spawning.chunks_near", lambda x, z, reach: [(0, 0)]), \
                patch("backend.survival.creatures.spawning.herd_count", lambda seed, chunk: 1):
            first = populate(Scene(grid, creatures, "1", pet(), 0.0), [], 1.0)
            self.assertTrue(first)
            for creature in first:
                creatures.remove(creature["id"])
                creatures.lost([0, 0], 100.0)
            again = populate(Scene(grid, creatures, "1", pet(), 100.0 + 3 * DAY_SECONDS - 1), [], 1.0)
            self.assertEqual(again, [])
            back = populate(Scene(grid, creatures, "1", pet(), 100.0 + 3 * DAY_SECONDS), [], 1.0)
        self.assertTrue(back)
        self.assertEqual(creatures.chunks((0, 0), (0, 0))[(0, 0)]["animals"], len(back))


class SimulateTests(unittest.TestCase):
    def setUp(self):
        flatland(self)

    def test_only_creatures_near_mimo_take_turns_and_at_most_max_acts_a_call(self):
        grid, creatures = flat(), herd()
        with patch("backend.survival.creatures.simulate.populate", lambda scene, loaded, scale: []):
            near = [creatures.add("cow", (x, 1, 0), 10.0, 0.0, 0.0, {"home": [x, 1, 0]}) for x in range(-15, 15)]
            far = creatures.add("cow", (300, 1, 0), 10.0, 0.0, 0.0, {"home": [300, 1, 0]})
            grid.herd = creatures
            simulate(pet(0, 0), context(grid, creatures.db), 5.0)
        turned = [creature for creature in near if creatures.get(creature["id"])["next_at"] > 5.0]
        self.assertEqual(len(turned), MAX_ACTS)
        self.assertEqual(creatures.get(far["id"])["next_at"], 0.0)

    def test_dead_creatures_stay_for_the_puff_then_go(self):
        grid, creatures = flat(), herd()
        grid.herd = creatures
        body = creatures.add("cow", (0, 1, 0), 0.0, 0.0, 99.0, {"pose": "dead", "dead_at": 100.0})
        with patch("backend.survival.creatures.simulate.populate", lambda scene, loaded, scale: []):
            simulate(pet(0, 0), context(grid, creatures.db), 100.0 + DEAD_KEEP)
            self.assertTrue(dead(creatures.get(body["id"])))
            simulate(pet(0, 0), context(grid, creatures.db), 100.0 + DEAD_KEEP + 1)
        self.assertIsNone(creatures.get(body["id"]))

    def test_without_a_database_nothing_happens(self):
        simulate(pet(), context(flat(), None), 5.0)


class TickTests(unittest.TestCase):
    def hatched(self, root):
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(3), timestamp=BORN)
        return SurvivalWorld(registry.world_path(life))

    def creatures_of(self, world):
        with world.connect() as db:
            return [tuple(row) for row in db.execute("SELECT id, kind, x, y, z, health, next_at FROM creatures "
                                                    "ORDER BY id").fetchall()]

    def test_the_tick_spawns_and_moves_animals_near_mimo_the_same_way_every_time(self):
        runs = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as root:
                world = self.hatched(root)
                for second in range(1, 301):
                    advance_world(world, BORN + second, 1.0)
                runs.append(self.creatures_of(world))
                with world.connect() as db:
                    grid, state = world_grid(db, world.seed), world.state()
                    found = grid.herd.near(state["position"]["x"], state["position"]["z"], SIM_REACH)
                    land = [creature for creature in found if not KINDS[creature["kind"]].water]
                    self.assertTrue(land)
                    self.assertLessEqual(len(land), PASSIVE_CAP)
                    self.assertTrue(any(creature["state"].get("path") for creature in land))
                    for creature in found:
                        cell = cell_of(creature)
                        self.assertTrue(grid.water(cell) if creature["kind"] == "fish" else grid.standable(cell))
        self.assertEqual(runs[0], runs[1])

    def test_a_crashing_creature_hook_never_stops_the_tick(self):
        with tempfile.TemporaryDirectory() as root:
            world = self.hatched(root)
            with patch("backend.survival.tick.simulate", side_effect=RuntimeError("boom")), \
                    self.assertLogs("backend.survival.tick", "ERROR"):
                state = advance_world(world, BORN + 30, 1.0)
        self.assertEqual(state["last_tick_at"], BORN + 30)

    def test_creatures_cost_well_under_twenty_milliseconds_a_slice(self):
        spent = []

        def timed(*args):
            start = time.perf_counter()
            real(*args)
            spent.append(time.perf_counter() - start)

        real = tick.simulate
        with tempfile.TemporaryDirectory() as root:
            world = self.hatched(root)
            with patch("backend.survival.tick.simulate", timed):
                for minute in range(1, 61):
                    advance_world(world, BORN + 60 * minute, 1.0)
        self.assertLess(sum(spent) / 60, 0.020)


if __name__ == "__main__":
    unittest.main()

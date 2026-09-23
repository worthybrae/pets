import logging
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.block_table import write_block
from backend.survival.actions import ActionContext
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.renewal import create_growth_table, renew, schedule, scheduled
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld

DAY = 3600.0
BORN = 1_000_000.0


def field(cells=None):
    """Grass at y 0 over dirt, air above, with `cells` overriding single cells."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("grass" if y == 0 else "dirt" if y < 0 else "air"))


def world(grid=None, scale=1.0):
    """A tick's context with a growth table, over `grid`."""
    db = sqlite3.connect(":memory:")
    create_growth_table(db)
    return ActionContext(grid=grid or field(), clock_at=lambda at: {"time_scale": scale}, planner=lambda *args: [],
                         events=[], db=db)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "7", "position": {"x": 8.0, "y": 1.0, "z": 0.0}, "inventory": {}}
    state.update(changes)
    return state


class GrowthTests(unittest.TestCase):
    def test_a_picked_bush_is_ripe_again_after_two_game_days(self):
        ctx, state = world(), pet()
        ctx.grid.put(3, 1, 0, "berry_bush")
        renew(state, ctx, 100.0)
        self.assertEqual(scheduled(ctx.db), [((3, 1, 0), "berry_bush_ripe", 100.0 + 2 * DAY)])
        renew(state, ctx, 100.0 + 2 * DAY - 1)
        self.assertEqual(ctx.grid.material(3, 1, 0), "berry_bush")
        renew(state, ctx, 100.0 + 2 * DAY)
        self.assertEqual(ctx.grid.material(3, 1, 0), "berry_bush_ripe")
        self.assertEqual(scheduled(ctx.db), [])

    def test_the_time_scale_speeds_regrowth_up(self):
        ctx = world(scale=60.0)
        ctx.grid.put(3, 1, 0, "berry_bush")
        renew(pet(), ctx, 0.0)
        self.assertEqual(scheduled(ctx.db)[0][2], 2 * DAY / 60)

    def test_crops_grow_a_stage_every_12_game_minutes_near_water_and_36_without(self):
        wet = world(field({(0, 0, 0): "farmland", (4, 0, 0): "water"}))
        dry = world(field({(0, 0, 0): "farmland"}))
        for ctx in (wet, dry):
            ctx.grid.put(0, 1, 0, "wheat_0")
            renew(pet(), ctx, 0.0)
        self.assertEqual(scheduled(wet.db), [((0, 1, 0), "wheat_1", 720.0)])
        self.assertEqual(scheduled(dry.db), [((0, 1, 0), "wheat_1", 2160.0)])
        renew(pet(), wet, 2159.0)
        self.assertEqual(wet.grid.material(0, 1, 0), "wheat_2")
        renew(pet(), wet, 2160.0)
        self.assertEqual((wet.grid.material(0, 1, 0), scheduled(wet.db)), ("wheat_3", []))
        renew(pet(), dry, 3 * 2160.0)
        self.assertEqual(dry.grid.material(0, 1, 0), "wheat_3")

    def test_farmland_without_a_crop_turns_back_to_dirt_after_two_game_days(self):
        ctx = world()
        ctx.grid.put(0, 0, 0, "farmland")
        ctx.grid.put(1, 0, 0, "farmland")
        ctx.grid.put(1, 1, 0, "carrot_0")
        renew(pet(), ctx, 0.0)
        renew(pet(), ctx, 2 * DAY)
        self.assertEqual((ctx.grid.material(0, 0, 0), ctx.grid.material(1, 0, 0)), ("dirt", "farmland"))

    def test_harvesting_starts_the_farmland_clock_again(self):
        ctx = world(field({(0, 0, 0): "farmland", (0, 1, 0): "carrot_3"}))
        ctx.grid.put(0, 1, 0, "air")
        renew(pet(), ctx, 50.0)
        self.assertEqual(scheduled(ctx.db), [((0, 0, 0), "dirt", 50.0 + 2 * DAY)])

    def test_an_entry_whose_cell_changed_is_dropped(self):
        ctx = world()
        schedule(ctx.db, (5, 1, 5), "berry_bush_ripe", 10.0)
        schedule(ctx.db, (6, 1, 5), "wheat_2", 10.0)
        renew(pet(), ctx, 20.0)
        self.assertEqual((ctx.grid.material(5, 1, 5), ctx.grid.material(6, 1, 5)), ("air", "air"))
        self.assertEqual(scheduled(ctx.db), [])

    def test_fish_stocks_recover_in_the_renewal_pass(self):
        state = pet(fish={"0,0": {"stock": 5, "since": 0.0}})
        renew(state, world(), 2 * DAY)
        self.assertEqual(state["fish"]["0,0"], {"stock": 7, "since": 2 * DAY})

    def test_the_grid_keeps_each_change_until_it_is_taken(self):
        grid = field({(1, 1, 0): "tall_grass"})
        grid.put(1, 1, 0, "air")
        grid.put(1, 0, 0, "farmland")
        self.assertEqual(grid.take_changes(), [((1, 1, 0), "tall_grass", "air"), ((1, 0, 0), "grass", "farmland")])
        self.assertEqual(grid.take_changes(), [])


class RenewalTickTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        position = self.world.state()["position"]
        self.cell = (round(position["x"]) + 3, round(position["y"]), round(position["z"]))
        with self.world.transaction() as db:
            write_block(db, *self.cell, "berry_bush")
            schedule(db, self.cell, "berry_bush_ripe", BORN + 30)

    def tearDown(self):
        self.directory.cleanup()

    def test_the_tick_applies_growth_that_is_due(self):
        tick_life(self.registry, BORN + 20, scale=1)
        self.assertEqual(self.world.material_at(*self.cell), "berry_bush")
        tick_life(self.registry, BORN + 40, scale=1)
        self.assertEqual(self.world.material_at(*self.cell), "berry_bush_ripe")

    def test_a_crashing_renewal_is_logged_once_and_the_tick_goes_on(self):
        def boom(state, context, at):
            raise RuntimeError("boom")

        forget_logged()
        with patch("backend.survival.tick.renew", boom), self.assertLogs("backend.survival.tick", logging.ERROR) as logs:
            tick_life(self.registry, BORN + 20, scale=1)
            state = tick_life(self.registry, BORN + 40, scale=1)
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(state["last_tick_at"], BORN + 40)


if __name__ == "__main__":
    unittest.main()

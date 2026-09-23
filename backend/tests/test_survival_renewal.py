import logging
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.block_table import write_block
from backend.services.worldgen import is_leaf
from backend.survival.actions import ActionContext
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import create_memory_tables, remember
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.renewal import MAX_APPLIED, apply_entry, create_growth_table, renew, schedule, scheduled
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
    create_memory_tables(db)
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


class RenewalSafetyTests(unittest.TestCase):
    """Task 6/7 review fixes: a failing entry must not lose the batch or corrupt change
    tracking, and a batch is capped at MAX_APPLIED with the rest waiting for the next call."""

    def test_a_failing_apply_leaves_its_row_scheduled_and_still_applies_the_others(self):
        ctx = world(field({(3, 1, 0): "berry_bush", (5, 1, 0): "berry_bush"}))
        state = pet()
        schedule(ctx.db, (3, 1, 0), "berry_bush_ripe", 5.0)
        schedule(ctx.db, (5, 1, 0), "berry_bush_ripe", 5.0)
        real_apply = apply_entry

        def flaky(db, grid, state, entry, scale, events):
            if entry[0] == (3, 1, 0):
                raise RuntimeError("boom")
            return real_apply(db, grid, state, entry, scale, events)

        forget_logged()
        with patch("backend.survival.renewal.apply_entry", side_effect=flaky), \
                self.assertLogs("backend.survival.renewal", logging.ERROR):
            renew(state, ctx, 10.0)
        self.assertEqual(ctx.grid.material(5, 1, 0), "berry_bush_ripe")
        self.assertEqual(ctx.grid.material(3, 1, 0), "berry_bush")
        # Kept, but not due again for 10 game minutes, so the same catch-up does not retry it.
        self.assertEqual(scheduled(ctx.db), [((3, 1, 0), "berry_bush_ripe", 610.0)])

    def test_a_row_that_keeps_failing_costs_a_few_queries_and_goes_after_five_failures(self):
        ctx = world(field({(3, 1, 0): "berry_bush"}), scale=60.0)
        state = pet()
        schedule(ctx.db, (3, 1, 0), "berry_bush_ripe", 5.0)
        statements = []
        ctx.db.set_trace_callback(statements.append)
        forget_logged()
        with patch("backend.survival.renewal.apply_entry", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.renewal", logging.ERROR):
            renew(state, ctx, 10.0)
            self.assertLessEqual(len(statements), 8)
            self.assertEqual(scheduled(ctx.db), [((3, 1, 0), "berry_bush_ripe", 20.0)])
            for at in (20.0, 30.0, 40.0):
                renew(state, ctx, at)
            self.assertEqual(scheduled(ctx.db), [((3, 1, 0), "berry_bush_ripe", 50.0)])
            renew(state, ctx, 50.0)
        self.assertEqual(scheduled(ctx.db), [])

    def test_the_failure_count_column_is_added_to_an_older_growth_table(self):
        db = sqlite3.connect(":memory:")
        db.execute("CREATE TABLE growth (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, "
                   "block TEXT NOT NULL, ready_at REAL NOT NULL, PRIMARY KEY (x, y, z))")
        schedule(db, (1, 1, 0), "berry_bush_ripe", 5.0)
        create_growth_table(db)
        create_growth_table(db)
        self.assertIn("failures", [row[1] for row in db.execute("PRAGMA table_info(growth)")])
        self.assertEqual(scheduled(db), [((1, 1, 0), "berry_bush_ripe", 5.0)])

    def test_a_crash_does_not_make_the_next_react_reschedule_renewals_own_writes(self):
        ctx = world(field({(0, 0, 0): "farmland", (0, 1, 0): "wheat_1", (3, 1, 0): "berry_bush"}))
        state = pet()
        schedule(ctx.db, (0, 1, 0), "wheat_2", 5.0)
        schedule(ctx.db, (3, 1, 0), "berry_bush_ripe", 5.0)
        real_apply = apply_entry

        def flaky(db, grid, state, entry, scale, events):
            if entry[0] == (3, 1, 0):
                raise RuntimeError("boom")
            return real_apply(db, grid, state, entry, scale, events)

        forget_logged()
        with patch("backend.survival.renewal.apply_entry", side_effect=flaky), \
                self.assertLogs("backend.survival.renewal", logging.ERROR):
            renew(state, ctx, 10.0)
        self.assertEqual(ctx.grid.material(0, 1, 0), "wheat_2")
        first_pass = {cell: (block, ready_at) for cell, block, ready_at in scheduled(ctx.db)}
        self.assertEqual(first_pass[(0, 1, 0)], ("wheat_3", 2165.0))

        renew(state, ctx, 8.0)  # a later call, at an earlier `at`: must not touch the crop's own schedule
        second_pass = {cell: (block, ready_at) for cell, block, ready_at in scheduled(ctx.db)}
        self.assertEqual(second_pass[(0, 1, 0)], ("wheat_3", 2165.0))

    def test_more_than_max_applied_entries_wait_for_the_next_call(self):
        excess = MAX_APPLIED + 1
        cells = {(i, 1, 0): "berry_bush" for i in range(excess)}
        ctx, state = world(field(cells)), pet()
        for i in range(excess):
            schedule(ctx.db, (i, 1, 0), "berry_bush_ripe", 5.0)
        renew(state, ctx, 10.0)
        ripe = sum(1 for i in range(excess) if ctx.grid.material(i, 1, 0) == "berry_bush_ripe")
        self.assertEqual(ripe, MAX_APPLIED)
        self.assertEqual(len(scheduled(ctx.db)), 1)
        renew(state, ctx, 10.0)
        ripe = sum(1 for i in range(excess) if ctx.grid.material(i, 1, 0) == "berry_bush_ripe")
        self.assertEqual(ripe, excess)
        self.assertEqual(scheduled(ctx.db), [])


def forest(extra=None):
    """Grass at y 0 with one tree like worldgen's rooted at (0, 0): logs at y 1 to 4, leaves at 5 and 6."""
    extra = extra or {}

    def rule(x, y, z):
        if (x, y, z) in extra:
            return extra[(x, y, z)]
        if (x, z) == (0, 0) and 1 <= y <= 4:
            return "oak_log"
        if is_leaf(x, y, z):
            return "leaves"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"

    return Grid(rule)


def chop(grid, heights=(1, 2, 3, 4)):
    for y in heights:
        grid.put(0, y, 0, "air")


class TreeTests(unittest.TestCase):
    def test_chopping_the_last_log_lets_the_canopy_decay_one_to_six_game_minutes_later(self):
        ctx, state = world(forest()), pet()
        chop(ctx.grid, (1, 2, 3))
        renew(state, ctx, 0.0)
        self.assertEqual(scheduled(ctx.db), [])  # the top log still holds the canopy
        chop(ctx.grid, (4,))
        renew(state, ctx, 10.0)
        leaves = scheduled(ctx.db)
        self.assertEqual(len(leaves), 26)
        self.assertTrue(all(block == "air" and 70.0 <= ready_at <= 370.0 for _, block, ready_at in leaves))
        renew(state, ctx, 370.0)
        self.assertEqual((ctx.grid.material(1, 5, 0), ctx.grid.material(0, 6, 0)), ("air", "air"))
        self.assertEqual((len(state["decays"]), scheduled(ctx.db)), (24, []))
        self.assertEqual(sorted(state["decays"][0]), ["at", "x", "y", "z"])

    def test_leaves_that_still_reach_a_log_stay(self):
        ctx = world(forest({(3, 5, 0): "oak_log"}))
        chop(ctx.grid)
        renew(pet(), ctx, 0.0)
        cells = [cell for cell, _, _ in scheduled(ctx.db)]
        self.assertNotIn((2, 5, 0), cells)
        self.assertIn((-2, 5, 0), cells)

    def test_a_decaying_leaf_drops_saplings_and_apples_to_mimo_nearby(self):
        near, far = pet(), pet(position={"x": 40.0, "y": 1.0, "z": 0.0})
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            for state in (near, far):
                ctx = world(forest())
                chop(ctx.grid)
                renew(state, ctx, 0.0)
                renew(state, ctx, 60.0)
        self.assertEqual(near["inventory"], {"sapling": 26, "apple": 26})
        self.assertEqual((far["inventory"], len(far["decays"])), ({}, 24))

    def test_a_sapling_grows_into_a_tree_after_a_game_day(self):
        ctx = world()
        ctx.grid.put(0, 1, 0, "sapling")
        renew(pet(), ctx, 0.0)
        self.assertEqual(scheduled(ctx.db), [((0, 1, 0), "oak_log", 3600.0)])
        renew(pet(), ctx, 3600.0)
        self.assertEqual([ctx.grid.material(0, y, 0) for y in range(1, 7)], ["oak_log"] * 4 + ["leaves", "leaves"])
        self.assertEqual(ctx.grid.material(2, 5, 1), "leaves")
        self.assertEqual(ctx.events[-1][1:], ("grow", "A sapling grew into a tree."))
        self.assertEqual(scheduled(ctx.db), [])

    def test_a_tree_never_grows_into_mimo_its_headroom_or_its_home(self):
        for position, shelter in (((2.0, 4.0, 1.0), None),  # the canopy would fill Mimo's headroom
                                  ((1.0, 5.0, 0.0), None),  # or Mimo's own cell
                                  ((8.0, 1.0, 0.0), ("home", (2, 4, -1))),
                                  ((8.0, 1.0, 0.0), ("shelter", (1, 5, 0)))):
            ctx = world()
            if shelter:
                remember(ctx.db, *shelter, 0.0)
            state = pet(position=dict(zip("xyz", position)))
            ctx.grid.put(0, 1, 0, "sapling")
            renew(state, ctx, 0.0)
            renew(state, ctx, 3600.0)
            self.assertEqual(ctx.grid.material(0, 1, 0), "sapling", (position, shelter))
            self.assertEqual(scheduled(ctx.db), [((0, 1, 0), "oak_log", 4200.0)])
        ctx = world()
        remember(ctx.db, "home", (3, 5, 0), 0.0)  # beside the canopy, not in it
        ctx.grid.put(0, 1, 0, "sapling")
        renew(pet(), ctx, 0.0)
        renew(pet(), ctx, 3600.0)
        self.assertEqual(ctx.grid.material(0, 1, 0), "oak_log")

    def test_a_sapling_without_room_tries_again_later(self):
        ctx = world(field({(0, 3, 0): "stone"}))
        ctx.grid.put(0, 1, 0, "sapling")
        renew(pet(), ctx, 0.0)
        renew(pet(), ctx, 3600.0)
        self.assertEqual(ctx.grid.material(0, 1, 0), "sapling")
        self.assertEqual(scheduled(ctx.db), [((0, 1, 0), "oak_log", 4200.0)])
        standing = world()
        standing.grid.put(0, 1, 0, "sapling")
        renew(pet(position={"x": 0.0, "y": 2.0, "z": 0.0}), standing, 0.0)
        renew(pet(position={"x": 0.0, "y": 2.0, "z": 0.0}), standing, 3600.0)
        self.assertEqual(standing.grid.material(0, 1, 0), "sapling")


@patch("backend.survival.renewal.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.renewal.biome_at", lambda x, z, seed: "forest")
class MushroomTests(unittest.TestCase):
    def test_a_picked_mushroom_comes_back_on_forest_floor_one_per_chunk_per_game_day(self):
        ctx = world(field({(3, 1, 3): "brown_mushroom", (5, 1, 9): "red_mushroom"}))
        ctx.grid.put(3, 1, 3, "air")
        renew(pet(), ctx, 0.0)
        ctx.grid.put(5, 1, 9, "air")
        renew(pet(), ctx, 10.0)
        coming = scheduled(ctx.db)
        self.assertEqual([(block, ready_at) for _, block, ready_at in coming],
                         [("brown_mushroom", 3600.0), ("red_mushroom", 7200.0)])
        self.assertTrue(all(0 <= cell[0] < 16 and 0 <= cell[2] < 16 and cell[1] == 1 for cell, _, _ in coming))
        renew(pet(), ctx, 3600.0)
        self.assertEqual(ctx.grid.material(*coming[0][0]), "brown_mushroom")

    def test_a_chunk_holds_at_most_three_mushrooms(self):
        ctx = world(field({(1, 1, 1): "brown_mushroom", (2, 1, 2): "red_mushroom", (3, 1, 3): "brown_mushroom"}))
        schedule(ctx.db, (9, 1, 9), "brown_mushroom", 5.0)
        renew(pet(), ctx, 10.0)
        self.assertEqual(ctx.grid.material(9, 1, 9), "air")

    def test_two_same_chunk_picks_in_one_batch_get_different_respawn_cells(self):
        ctx = world(field({(3, 1, 3): "brown_mushroom", (5, 1, 5): "red_mushroom"}))
        ctx.grid.put(3, 1, 3, "air")
        ctx.grid.put(5, 1, 5, "air")
        renew(pet(), ctx, 10.0)
        coming = scheduled(ctx.db)
        self.assertEqual(len(coming), 2)
        cells = [cell for cell, _, _ in coming]
        self.assertEqual(len(set(cells)), 2)


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

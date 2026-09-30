"""W2: thunderstorms: where lightning strikes, when it hits Mimo, fires in the trees, their spread, caps and
burning out, the heat, the way round them, the flee_fire reflex and what a storm costs the tick."""

import gc
import math
import os
import random
import sqlite3
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import backend.survival.brain  # noqa: F401  (every reflex registered, flee_fire among them)
from backend.services.block_table import create_block_tables
from backend.services.crafting import LOGS
from backend.services.worldgen import LEGACY_RADIUS, terrain_height
from backend.survival import rain, sky, storms
from backend.survival.actions import ActionContext, ensure_actions, landing, start_hazard
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.building import finish_if_built
from backend.survival.clock import clock_at
from backend.survival.creatures.defense import threats_payload
from backend.survival.creatures.gear import hurt_lately as gear_hurt
from backend.survival.creatures.harm import armor_wanted, last_blow
from backend.survival.episodes import near_death_words
from backend.survival.grid import CHUNK, Grid, world_grid
from backend.survival.hatch import hatch
from backend.survival.life_goals import hurt_lately as goal_hurt
from backend.survival.memory import BUILT, create_memory_tables, remember
from backend.survival.pathing import route
from backend.survival.reflexes import by_name, fall_depth
from backend.survival.registry import LifeRegistry
from backend.survival.situation import Situation
from backend.survival.storms import (
    FIRE_CELLS, FIRES, HOME_CLEAR, STRUCK_DAMAGE, burn_pet, highest, home_now, hot_cells, ignite, spread, storm,
)
from backend.survival.structures import start
from backend.survival.tick import FIGHT_SLICES_MAX, death_words, tick_life
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0
X0 = 1000  # far from the legacy clearing


def forest(trees=(), pillar=None, saved=None):
    """Grass at y 0 over dirt; oaks (logs y 1-4, leaves y 5-6) at `trees`; a stone pillar 6 high at `pillar`. With
    `saved` ({cell: material}), those edits are the world's, loaded one chunk at a time as world_grid loads them."""
    logs = {(x, y, z) for x, z in trees for y in range(1, 5)}
    leaves = {(x + dx, y, z + dz) for x, z in trees for y in (5, 6) for dx in range(-2, 3) for dz in range(-2, 3)
              if abs(dx) + abs(dz) <= 3}

    def natural(x, y, z):
        if (x, y, z) in logs:
            return "oak_log"
        if (x, y, z) in leaves:
            return "leaves"
        if pillar is not None and (x, z) == pillar and 0 < y <= 6:
            return "stone"
        return "grass" if y == 0 else "dirt" if y < 0 else "air"

    if saved is None:
        return Grid(natural)
    return Grid(natural, lambda cx, cz: {cell: material for cell, material in saved.items()
                                         if (cell[0] // CHUNK, cell[2] // CHUNK) == (cx, cz)})


def pet(x=X0, y=1, z=0, weather="storm"):
    return {"name": "Pip", "world_seed": "7", "born_at": BORN, "position": {"x": float(x), "y": float(y), "z": float(z)},
            "vitals": dict(START_VITALS), "inventory": {}, "sky": {"weather": weather}}


def context(grid, db=None):
    return SimpleNamespace(grid=grid, events=[], db=db, clock_at=lambda at: clock_at(BORN, at, SCALE))


def home_db(cell):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    remember(db, "home", cell, 0.0, BUILT)
    return db


def always():
    """Every roll 0: a strike on Mimo that may hit hits, every burning cell spreads each round (to the first
    neighbour it may, in storms.FACES' order: east, west, up, down, south, north), and a cell burns 20 s."""
    return patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0)


def spread_for(state, grid, seconds, db=None):
    """The fire's spread rounds, every 10 game seconds for `seconds`."""
    ctx = context(grid, db)
    spread(state, ctx, BORN)
    for second in range(10, seconds + 1, 10):
        spread(state, ctx, BORN + second / SCALE)
    return ctx


class Flat(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.storms.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)


class StrikeTests(Flat):
    def test_a_storm_strikes_once_a_game_minute_and_keeps_the_last_five(self):
        state, grid = pet(), forest()
        ctx = context(grid)
        for second in range(0, 400, 20):
            storm(state, ctx, BORN + second / SCALE)
        self.assertEqual(len(state["sky"]["strikes"]), 5)
        self.assertEqual([round((strike["at"] - BORN) * SCALE) for strike in state["sky"]["strikes"]],
                         [120, 180, 240, 300, 360])
        self.assertEqual([kind for _, kind, _ in ctx.events].count("storm"), 1)
        self.assertEqual(ctx.events[0][2], "A thunderstorm rolled in.")

    def test_no_strike_near_the_home_mimo_built_or_in_the_legacy_clearing(self):
        grid, db = forest(), home_db((X0, 1, 0))
        for step in range(300):
            state = pet(X0 + step % 7, 1, step % 5)
            state["sky"]["strike_at"] = None
            storm(state, context(grid, db), BORN + step)
            for strike in state["sky"]["strikes"]:
                self.assertGreater(math.hypot(strike["x"] - X0, strike["z"]), HOME_CLEAR)
        clearing = pet(0, 1, 0)
        storm(clearing, context(grid), BORN)
        self.assertEqual(clearing["sky"]["strikes"], [])

    def test_mimo_is_struck_only_when_it_is_the_highest_under_the_open_sky(self):
        with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0):
            flat = pet()
            storm(flat, context(forest()), BORN)
            self.assertEqual(flat["vitals"]["health"], 100.0)
            pillar = forest(pillar=(X0, 0))
            self.assertTrue(highest(pillar, "7", (X0, 7, 0)))
            # A tree's top counts (fix round 4: this read flat ground, where it never is, tree or none): an oak
            # whose leaves (y 6) are as high as the block Mimo stands on atop the pillar, within 8 blocks, and Mimo
            # is not the highest; the same oak 12 blocks off is out of reach, and Mimo is again.
            self.assertFalse(highest(forest(trees=((X0 + 5, 0),), pillar=(X0, 0)), "7", (X0, 7, 0)))
            self.assertTrue(highest(forest(trees=((X0 + 12, 0),), pillar=(X0, 0)), "7", (X0, 7, 0)))
            top = pet(X0, 7, 0)
            ctx = context(pillar)
            storm(top, ctx, BORN)
            self.assertEqual((top["vitals"]["health"], top["hurt_by"]), (100.0 - STRUCK_DAMAGE, "lightning"))
            self.assertIn((BORN, "struck", "Lightning struck Pip!"), ctx.events)
            roofed = forest(pillar=(X0, 0))
            roofed.put(X0, 9, 0, "planks")
            under = pet(X0, 7, 0)
            storm(under, context(roofed), BORN)
            self.assertEqual(under["vitals"]["health"], 100.0)
        self.assertEqual(death_words("lightning"), "was struck by lightning")
        self.assertEqual(death_words("fire"), "was caught in a fire")

    def test_the_skys_hurts_are_no_creatures_blow(self):
        """W2's final review: storms.hurt set hurt_at and hurt_by, so iron armor, gear and armor after a recent hurt
        answered lightning, and the near-death words read "a lightning almost got me"."""
        def felt(state, at):
            s = Situation(state, forest(), clock_at(BORN, at, SCALE), at)
            return (armor_wanted(state), gear_hurt(s), goal_hurt(s), near_death_words(state, at, SCALE)[0],
                    threats_payload(s)["defense"]["last_hurt_by"])

        for source, words in (("lightning", "I nearly died: the lightning struck me."),
                              ("fire", "I nearly died in a fire.")):
            state = pet()
            storms.hurt(state, STRUCK_DAMAGE, source, BORN, None)
            self.assertEqual((state["hurt_at"], state["hurt_by"]), (BORN, source))  # the flash, the tick's cause
            self.assertEqual(felt(state, BORN + 1), (False, False, False, words, None))
        state = {**pet(), "hurt_at": BORN, "hurt_by": "skitter"}  # a creature's blow, then the sky
        storms.hurt(state, 2.0, "fire", BORN + 5, None)
        storms.hurt(state, 2.0, "fire", BORN + 6, None)
        self.assertEqual(last_blow(state), (BORN, "skitter"))
        self.assertEqual(felt(state, BORN + 7), (True, True, True, "I nearly died in a fire.", "skitter"))
        self.assertEqual(near_death_words({**state, "hurt_by": "skitter", "hurt_at": BORN}, BORN + 7, SCALE)[0],
                         "I nearly died: a skitter almost got me.")

    def test_the_cheap_roll_on_mimo_comes_before_the_height_check(self):
        """Fix round 4: `highest` reads 17 x 17 columns; the 0.05 roll comes first, so 19 strikes in 20 on a pet
        under the open sky never pay for it."""
        for rolled, checks in ((0.5, 0), (0.0, 1)):
            with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0, rolled=rolled: rolled), \
                    patch("backend.survival.storms.highest", MagicMock(return_value=True)) as height:
                storm(pet(X0, 7, 0), context(forest(pillar=(X0, 0))), BORN)
            self.assertEqual(height.call_count, checks, rolled)


class FireTests(Flat):
    def test_a_strike_on_a_tree_sets_its_top_burning(self):
        grid = forest(trees=((X0 + 20, 0),))
        state, ctx = pet(), context(grid)
        with patch("backend.survival.storms.column_top", lambda grid, seed, x, z: (X0 + 20, 6, 0)):
            storm(state, ctx, BORN)
        self.assertEqual(grid.material(X0 + 20, 6, 0), "fire")
        self.assertEqual(len(state["sky"]["fires"]), 1)
        self.assertIn((BORN, "fire", "Lightning set a tree on fire near Pip."), ctx.events)

    def burn(self, seed, always=False):
        """A fire lit in a wood of oaks, spread for 15 game minutes: the most cells it held, and the grid."""
        grid = forest(trees=[(X0 + dx, dz) for dx in range(0, 30, 4) for dz in range(0, 30, 4)])
        state = {**pet(weather="clear"), "world_seed": str(seed)}
        ignite(state, context(grid), (X0, 6, 0), BORN, None)
        most, ctx = 0, context(grid)
        with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0) if always else nullcontext():
            spread(state, ctx, BORN)
            for second in range(10, 900, 10):
                spread(state, ctx, BORN + second / SCALE)
                most = max(most, len(state["sky"]["fires"]))
        self.assertEqual(state["sky"]["fires"], [])  # every cell burned out
        return most, grid

    def test_a_fire_spreads_through_natural_leaves_burns_at_most_24_cells_and_burns_out(self):
        spreads = [self.burn(seed)[0] for seed in range(7, 15)]
        self.assertGreater(max(spreads), 1)
        most, grid = self.burn(7, always=True)  # every roll spreads
        burned = [cell for cell, material in grid.edits.items() if material == "air"]
        self.assertEqual(len(burned), FIRE_CELLS)
        self.assertLessEqual(most, FIRE_CELLS)
        self.assertEqual(grid.material(X0, 6, 0), "air")

    def test_rain_slows_the_spread_and_at_most_two_fires_burn(self):
        wet, dry = [], []
        for seed in range(12):
            for weather, found in (("rain", wet), ("clear", dry)):
                grid = forest(trees=[(X0 + dx, dz) for dx in range(0, 30, 4) for dz in range(0, 30, 4)])
                state = {**pet(weather=weather), "world_seed": str(seed)}
                ignite(state, context(grid), (X0, 6, 0), BORN, None)
                ctx = context(grid)
                spread(state, ctx, BORN)
                spread(state, ctx, BORN + 30 / SCALE)
                found.append(len(state["sky"]["fires"]) + sum(1 for entry in state["sky"]["fires"] if entry["x"] != X0))
        self.assertLess(sum(wet), sum(dry))
        state, grid = pet(), forest(trees=((X0, 0), (X0 + 10, 0), (X0 + 20, 0)))
        lit = [ignite(state, context(grid), (x, 6, 0), BORN, None) for x in (X0, X0 + 10, X0 + 20)]
        self.assertEqual(lit, [True, True, False])
        self.assertEqual(len({entry["fire"] for entry in state["sky"]["fires"]}), FIRES)

    def test_fire_never_enters_a_built_edited_or_claimed_cell_or_comes_near_home(self):
        grid = forest(trees=((X0, 0),))
        grid.put(X0 + 1, 6, 0, "leaves")  # edited
        grid.claims.add((X0 - 1, 6, 0))  # claimed
        grid.take_changes()
        state = pet(weather="clear")
        ignite(state, context(grid), (X0, 6, 0), BORN, None)
        with always():  # east first, then west: each guarded cell is the first the fire would take without its guard
            spread_for(state, grid, 40)
        # Fix round 4: a cell that caught at 10 s burned out by 30 s and is no longer among the fires at 40 s, so
        # the guarded cells are checked in the grid: the fire never touched them, and they keep their leaves.
        touched = {cell for cell, _, _ in grid.take_changes()}
        self.assertIn((X0, 5, 0), touched)  # the fire did spread: down, once east and west were barred
        self.assertFalse(touched & {(X0 + 1, 6, 0), (X0 - 1, 6, 0)})
        self.assertEqual((grid.material(X0 + 1, 6, 0), grid.material(X0 - 1, 6, 0)), ("leaves", "leaves"))
        near_home = forest(trees=((X0, 0),))
        homely = pet(weather="clear")
        db = home_db((X0 + 6, 1, 0))
        with patch("backend.survival.storms.column_top", lambda grid, seed, x, z: (X0, 6, 0)):
            storm({**homely, "sky": {"weather": "storm"}}, context(near_home, db), BORN)
        self.assertEqual(near_home.material(X0, 6, 0), "leaves")

    def test_fire_never_enters_an_edited_cell_in_a_chunk_nothing_has_read_yet(self):
        """Fix round 4: a world's grid (world_grid) loads its edits one chunk at a time. The guard asked
        grid.edits before the material loaded the chunk, so the first cell the fire tried in a chunk not read yet
        passed for natural, and a log Mimo placed, or the leaves of a sapling renewal grew, burned."""
        edge = (X0 // CHUNK + 1) * CHUNK - 1  # the last column of its chunk: the cells east of it are the next's
        for placed in ("oak_log", "leaves"):
            saved = {(edge + 1, 6, 0): placed}  # beside the fire's first cell, in a chunk nothing has read
            grid = forest(trees=((edge, 0),), saved=saved)
            state = pet(weather="clear")
            ignite(state, context(grid), (edge, 6, 0), BORN, None)
            with always():  # east first: the edited cell is the first the fire tries
                spread_for(state, grid, 60)
            touched = {cell for cell, _, _ in grid.changes}
            self.assertIn((edge - 1, 6, 0), touched)  # it spread west instead
            self.assertNotIn((edge + 1, 6, 0), touched)
            self.assertEqual(grid.material(edge + 1, 6, 0), placed)

    def test_a_fire_by_the_legacy_clearing_never_burns_a_leaf_inside_it(self):
        """Fix round 4: strikes kept out of the clearing but the spread did not, and a rim tree's canopy reaches
        in."""
        rim = -(LEGACY_RADIUS + 1)  # an oak just west of the clearing: its leaves east of it are inside
        grid = forest(trees=((rim, 0),))
        state = pet(rim - 3, weather="clear")
        ignite(state, context(grid), (rim, 6, 0), BORN, None)
        with always():  # east first: into the clearing, were it let
            spread_for(state, grid, 120)
        touched = {cell for cell, _, _ in grid.changes}
        self.assertGreater(len(touched), 3)  # the fire spread, outside
        self.assertEqual([cell for cell in touched if math.hypot(cell[0], cell[2]) <= LEGACY_RADIUS], [])
        self.assertEqual(grid.material(rim + 1, 6, 0), "leaves")

    def test_mimo_beside_a_burning_cell_takes_two_health_a_game_second_and_paths_go_round(self):
        grid = forest(trees=((X0 + 1, 0),))
        state = pet(weather="clear")
        ignite(state, context(grid), (X0 + 1, 1, 0), BORN, None)
        ctx = context(grid)
        burn_pet(state, ctx, BORN)
        burn_pet(state, ctx, BORN + 5 / SCALE)
        self.assertAlmostEqual(state["vitals"]["health"], 90.0)
        self.assertEqual(state["hurt_by"], "fire")
        grid.hot = hot_cells(state)
        cells, reached = route(grid, (X0 - 3, 1, 0), (X0 + 5, 1, 0))
        self.assertTrue(reached)
        self.assertFalse(set(cells) & grid.hot)

    def test_a_pet_on_a_burning_canopy_leaf_falls_the_whole_way(self):
        """Fix round 4: `hot` was in Grid.passable, which falls and landings read too, so a pet on a canopy leaf
        that caught fell 0 blocks and hung by the fire (each fall emptying its flee) until the leaf burned out."""
        grid = forest(trees=((X0, 0),))
        state = {**pet(X0 + 2, 7, 0, weather="clear"), "last_tick_at": BORN}  # on the canopy's edge (leaves y 5, 6)
        ensure_actions(state)
        for leaf in ((X0 + 2, 6, 0), (X0 + 2, 5, 0)):
            ignite(state, context(grid), leaf, BORN, None)
        grid.hot = hot_cells(state)
        self.assertEqual(landing(grid, (X0 + 2, 7, 0)), (X0 + 2, 1, 0))
        self.assertTrue(start_hazard(state, grid, BORN))
        self.assertEqual((state["action"]["kind"], state["action"]["blocks"]), ("fall", 6))
        self.assertEqual({axis: state["action"]["path"][-1][axis] for axis in "xyz"}, {"x": X0 + 2, "y": 1, "z": 0})

    def test_a_fall_past_hot_cells_counts_the_real_drop_and_a_route_still_keeps_out_of_them(self):
        """Fix round 4: the heat is a route's (pathing.moves), not the body's: reflexes.fall_depth counts the drop
        through hot cells, and a route still goes round them."""
        grid = forest()
        grid.hot = {(X0, y, 0) for y in range(1, 8)}  # the column beside a fire
        self.assertEqual(fall_depth(grid, (X0, 7, 0)), (6, False))
        self.assertTrue(grid.standable((X0, 1, 0)))
        grid.hot = {(X0 + 2, 1, dz) for dz in range(-3, 4)}  # a hot wall across the way, in open air
        cells, reached = route(grid, (X0, 1, 0), (X0 + 4, 1, 0))
        self.assertTrue(reached)
        self.assertFalse(set(cells) & grid.hot)
        self.assertGreater(len(cells), 4)  # round the wall, not through it

    def test_the_heat_follows_the_burning_cells_and_is_worked_out_again_only_when_they_change(self):
        """Fix round 4: a fire of 24 cells is 168 hot cells, worked out each step; the tick's context keeps them
        while the burning cells stay the same."""
        grid = forest(trees=((X0, 0),))
        ctx = ActionContext(grid=grid, clock_at=lambda at: clock_at(BORN, at, SCALE), planner=lambda *args: [],
                            events=[])
        state = pet(X0 + 10, weather="clear")
        ignite(state, ctx, (X0, 6, 0), BORN, None)
        with patch("backend.survival.storms.hot_cells", wraps=hot_cells) as worked:
            storm(state, ctx, BORN)
            first = grid.hot
            storm(state, ctx, BORN + 1 / SCALE)
            self.assertIs(grid.hot, first)
            self.assertEqual((worked.call_count, first), (1, hot_cells(state)))
            ignite(state, ctx, (X0, 5, 0), BORN + 2 / SCALE, 1)
            storm(state, ctx, BORN + 2 / SCALE)
            self.assertEqual((worked.call_count, grid.hot), (2, hot_cells(state)))
            self.assertIn((X0, 4, 0), grid.hot)  # below the new burning cell
            state["sky"]["fires"] = []  # burned out
            storm(state, ctx, BORN + 3 / SCALE)
            self.assertEqual(grid.hot, set())

    def test_a_transactions_grid_keeps_out_of_the_fires_from_the_start(self):
        """Carried N2 of W2's fourth task: world_grid started each transaction with no hot cells until the storm's
        effect ran, so a plan made before it (the chooser's grid) could route through a fire."""
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        create_block_tables(db)
        fires = [{"x": X0, "y": 5, "z": 0, "fire": 1, "caught": BORN, "until": BORN + 1}]
        grid = world_grid(db, "7", {"fires": fires})
        self.assertEqual(grid.hot, hot_cells({"sky": {"fires": fires}}))
        self.assertIn((X0, 4, 0), grid.hot)
        self.assertEqual(world_grid(db, "7", {}).hot, set())

    def test_the_winters_overlay_each_sky_step_leaves_the_heat_alone(self):
        """The fix wave's re-review: winter.freeze runs grid.overlay every sky step, and rebuilding the heat there
        undid the storm's memo (7 builds over 300 steps became 605)."""
        grid = forest(trees=((X0, 0),))
        ctx = ActionContext(grid=grid, clock_at=lambda at: clock_at(BORN, at, SCALE), planner=lambda *args: [],
                            events=[])
        state = pet(X0 + 10, weather="clear")
        ignite(state, ctx, (X0, 6, 0), BORN, None)
        with patch("backend.survival.storms.hot_cells", wraps=hot_cells) as worked:
            for step in range(5):
                grid.overlay(state["sky"])  # what winter.freeze does each sky step
                storm(state, ctx, BORN + step / SCALE)
            self.assertEqual(worked.call_count, 1)

    def test_flee_fire_runs_from_a_fire_beside_mimo(self):
        grid = forest(trees=((X0 + 1, 0),))
        state = pet(weather="clear")
        ignite(state, context(grid), (X0 + 1, 1, 0), BORN, None)
        s = Situation({**state, "brain": None}, grid, clock_at(BORN, BORN, SCALE), BORN, None)
        reflex = by_name("flee_fire")
        self.assertTrue(reflex.trigger(s))
        walk = reflex.plan(s, None)[0]
        self.assertEqual(walk["kind"], "walk")
        self.assertLess(walk["target"][0], X0)  # away from the fire
        self.assertFalse(reflex.trigger(Situation({**pet(X0 - 10), "brain": None, "sky": state["sky"]}, grid,
                                                  clock_at(BORN, BORN, SCALE), BORN, None)))


class HomeTests(unittest.TestCase):
    def test_the_home_is_read_once_a_transaction_and_again_once_mimo_moves_into_one_it_built(self):
        """Fix round 4: `built_home` queried memory_places every step (sixty times a transaction by a fire); the
        tick's context keeps it (ActionContext.memo), and building clears that when Mimo moves in, so a strike
        later in the same transaction still keeps HOME_CLEAR from the new home."""
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        create_memory_tables(db)
        grid = forest()
        ctx = ActionContext(grid=grid, clock_at=lambda at: clock_at(BORN, at, SCALE), planner=lambda *args: [],
                            events=[], db=db)
        with patch("backend.survival.storms.built_home", wraps=storms.built_home) as read:
            self.assertIsNone(home_now(ctx))
            self.assertIsNone(home_now(ctx))
            self.assertEqual(read.call_count, 1)
            site = find_site(grid, (X0, 1, 0), (3, 3), ("north",), "flat", reach=0)
            cottage = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Cottage")
            number = start(db, grid, cottage, BORN)
            for planned in cottage.parts("floor", "wall", "roof"):
                grid.put(*planned.cell, "cobblestone")
            state = {**pet(), "last_tick_at": BORN, "traits": {}}
            ensure_actions(state)
            finish_if_built(state, ctx, number, BORN)
            self.assertEqual(ctx.events[-1][1], "built")
            self.assertEqual(home_now(ctx), (cottage.anchor[0], cottage.anchor[2]))
            self.assertEqual(read.call_count, 2)


def burning_tree(world) -> tuple[int, int, int]:
    """Stand Mimo 3 blocks west of the natural oak nearest it, at the height of the trunk's lowest log, and set that
    log alight for good (its `until` past any run): every transaction takes the fire's short steps (tick.fire_near)
    while Mimo stays out of its heat. The fire's cell."""
    with world.transaction() as db:
        state = read_state(db)
        seed = state["world_seed"]
        grid = world_grid(db, seed, state.get("sky"))
        x0, z0 = round(state["position"]["x"]), round(state["position"]["z"])
        for _, x, z in sorted((abs(dx) + abs(dz), x0 + dx, z0 + dz) for dx in range(-24, 25) for dz in range(-24, 25)):
            base = terrain_height(x, z, seed) + 1
            stand = (x - 3, terrain_height(x - 3, z, seed) + 1, z)
            if grid.material(x, base, z) in LOGS and grid.standable(stand) and abs(stand[1] - base) <= 1:
                break
        else:
            raise AssertionError("no oak near the hatching spot")
        fire = (x, max(base, stand[1]), z)
        state["position"] = dict(zip("xyz", map(float, stand)))
        ctx = SimpleNamespace(grid=grid, events=[], db=db, clock_at=lambda at: clock_at(state["born_at"], at, SCALE))
        ignite(state, ctx, fire, state["last_tick_at"], None)
        state["sky"]["fires"][0]["until"] = state["last_tick_at"] + 10 ** 6
        write_state(db, state)
    return fire


class TickTests(unittest.TestCase):
    TRANSACTIONS = 100  # a run: its p99 is the 99th of 100 (fix round 4: it was the 2nd largest of 30)
    WARM = 5  # transactions before the first run: a process's first strikes read worldgen's cold caches

    def setUp(self):
        self.registry, self.world = self.hatched()

    def hatched(self, difficulty: str = "gentle"):
        """A registry and the world of a life hatched in it, seed 8."""
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        registry = LifeRegistry(Path(root.name) / "data", Path(root.name) / "no-legacy.sqlite3")
        return registry, SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN,
                                                                 difficulty=difficulty)))

    def edit(self, change) -> dict:
        """`change(state, db)` in a transaction of its own; the state as it was saved."""
        with self.world.transaction() as db:
            state = read_state(db)
            change(state, db)
            write_state(db, state)
        return state

    def ticks(self, count: int, before=None) -> dict:
        """`count` transactions of 60 game seconds in a storm (`before()` ahead of each), the creatures left out:
        only the sky is under test, and a pet resting by a fire through the night would be the dark's."""
        with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "storm"), \
                patch("backend.survival.tick.run_creatures", lambda *args, **kwargs: None):
            start = self.world.state()["last_tick_at"]
            for call in range(1, count + 1):
                if before is not None:
                    before()
                state = tick_life(self.registry, start + call, scale=SCALE, action_scale=SCALE)
        return state

    def test_a_storm_by_a_burning_forest_costs_the_sky_little_a_transaction(self):
        """Spec cost criterion 10: the sky hook at most 2 ms mean and 8 ms p99 a transaction over a storm near a
        forest with fires burning, measured like L5's budget (test_survival_frontier_run): the hook's time summed
        over each 60-game-second transaction. A real hatched world, a storm pinned, and Mimo 3 blocks from an oak
        whose lowest log is kept burning for good (`burning_tree`), so each transaction is the fire's 60 short steps
        while the fire spreads from it through the tree, up to its 24 cells, and those cells burn out; the best of up
        to 3 runs (backend.tests.budget's rule). Fix round 4 measured it on a loaded machine, runs of 100: before its
        cuts (the home and the campfires read from the database each step, the heat's cells and the sky's defaults
        worked out each step) 1.6 to 2.8 ms mean, p99 2.6 to 9.0 ms; after them 1.0 to 1.9 ms mean, p99 1.6 to 5.5
        ms but for one load spike. With 24 cells kept burning beside Mimo it was 3.5 to 4.1 ms mean before and 1.4
        to 2.4 ms after. W2's final wave: a gentle pet and a wild one are each timed (carried N1: a wild pet by a fire
        learned fire for sure at every step, a row written each, sky_wild.fire_known), and the measure is the wall
        clock's, so it flakes under load: it runs with MIMO_SLOW_TESTS=1, as the gate's criterion 10 runs it
        (wild_gate.cost_rows)."""
        if not os.environ.get("MIMO_SLOW_TESTS"):
            self.skipTest("a wall-clock budget: set MIMO_SLOW_TESTS=1 (the W2 gate's criterion 10 does)")
        for difficulty in ("gentle", "wild"):
            if difficulty != "gentle":
                self.registry, self.world = self.hatched(difficulty)
            with self.subTest(difficulty):
                self.storm_budget()

    def storm_budget(self) -> None:
        burning_tree(self.world)
        real = sky.advance
        spent, steps = [], []

        def timed(state, context, at):
            started = time.perf_counter()
            real(state, context, at)
            spent[-1] += time.perf_counter() - started
            steps[-1] += 1

        def run(count: int) -> tuple[float, float]:
            spent.clear()
            steps.clear()
            self.edit(lambda state, db: state.update(vitals=dict(START_VITALS)))  # fed: resting never starves it
            gc.collect()  # garbage left by earlier tests is not this code's cost
            with patch("backend.survival.tick.sky.advance", timed):
                self.ticks(count, before=lambda: (spent.append(0.0), steps.append(0)))
            ordered = sorted(spent)
            return sum(ordered) / len(ordered), ordered[math.ceil(len(ordered) * 0.99) - 1]

        run(self.WARM)
        runs = []
        for _ in range(3):
            runs.append(run(self.TRANSACTIONS))
            self.assertEqual(set(steps), {FIGHT_SLICES_MAX})  # every transaction took the fire's short steps
            if runs[-1][0] < 0.002 and runs[-1][1] < 0.008:
                break
        self.assertTrue(any(mean < 0.002 and p99 < 0.008 for mean, p99 in runs), runs)
        state = self.world.state()
        self.assertIsNone(state["died_at"])
        self.assertTrue(state["sky"]["strikes"] and state["sky"]["fires"])
        with self.world.connect() as db:  # a wild pet learned fire by the fire (a gentle one knew it from the start)
            known = db.execute("SELECT 1 FROM memory_knowledge WHERE subject='wild:fire' AND fact='lesson'").fetchone()
        self.assertIsNotNone(known)

    def test_the_sky_reads_the_home_and_the_campfires_once_a_transaction(self):
        """Fix round 4: by a fire every transaction is 60 short steps, and the storm's home and the rain's
        campfires were each a query a step."""
        burning_tree(self.world)
        with patch("backend.survival.storms.built_home", wraps=storms.built_home) as homes, \
                patch("backend.survival.rain.campfire_rows", wraps=rain.campfire_rows) as campfires:
            self.ticks(3)
        self.assertEqual((homes.call_count, campfires.call_count), (3, 3))

    def test_lightning_that_takes_mimos_last_health_kills_it_at_once(self):
        """The tick's death check right after sky.advance: struck at a step's start, Mimo dies then, of
        lightning, before the step's vitals could heal it."""
        state = self.edit(lambda state, db: state["vitals"].update(health=STRUCK_DAMAGE - 5))
        struck = [patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0),
                  patch("backend.survival.storms.sky_open", lambda grid, seed, cell: True),
                  patch("backend.survival.storms.highest", lambda grid, seed, cell: True)]
        for hit in struck:
            hit.start()
            self.addCleanup(hit.stop)
        dead = self.ticks(1)
        self.assertEqual((dead["died_at"], dead["cause"], dead["vitals"]["health"]),
                         (state["last_tick_at"], "lightning", 0.0))
        self.assertIn(f"{state['name']} was struck by lightning on day 1.",
                      [event["text"] for event in self.world.events(50)])

    def test_a_fire_that_takes_mimos_last_health_kills_it_at_once(self):
        """The same check for the fire's heat: Mimo beside a burning cell for 5 game seconds before the tick, with
        8 health, dies at the first step's start, of the fire."""
        def beside_a_fire(state, db):
            x, y, z = (round(state["position"][axis]) for axis in "xyz")
            ctx = SimpleNamespace(grid=world_grid(db, state["world_seed"]), events=[],
                                  clock_at=lambda at: clock_at(state["born_at"], at, SCALE))
            ignite(state, ctx, (x + 1, y, z), state["last_tick_at"] - 10 / SCALE, None)
            state["sky"]["burned_at"] = state["last_tick_at"] - 5 / SCALE
            state["vitals"]["health"] = 8.0

        state = self.edit(beside_a_fire)
        dead = self.ticks(1)
        self.assertEqual((dead["died_at"], dead["cause"], dead["vitals"]["health"]),
                         (state["last_tick_at"], "fire", 0.0))
        self.assertIn(f"{state['name']} was caught in a fire on day 1.",
                      [event["text"] for event in self.world.events(50)])


if __name__ == "__main__":
    unittest.main()

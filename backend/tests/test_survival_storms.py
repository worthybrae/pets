"""W2: thunderstorms: where lightning strikes, when it hits Mimo, fires in the trees, their spread, caps and
burning out, the heat, the way round them, the flee_fire reflex and what a storm costs the tick."""

import math
import random
import sqlite3
import tempfile
import time
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every reflex registered, flee_fire among them)
from backend.survival import sky
from backend.survival.clock import clock_at
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import BUILT, create_memory_tables, remember
from backend.survival.pathing import route
from backend.survival.reflexes import by_name
from backend.survival.registry import LifeRegistry
from backend.survival.situation import Situation
from backend.survival.storms import (
    FIRE_CELLS, FIRES, HOME_CLEAR, STRUCK_DAMAGE, burn_pet, highest, hot_cells, ignite, spread, storm,
)
from backend.survival.tick import death_words, tick_life
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0
SCALE = 60.0
X0 = 1000  # far from the legacy clearing


def forest(trees=(), pillar=None):
    """Grass at y 0 over dirt; oaks (logs y 1-4, leaves y 5-6) at `trees`; a stone pillar 6 high at `pillar`."""
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

    return Grid(natural)


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
            self.assertFalse(highest(forest(trees=((X0 + 5, 0),), pillar=(X0, 0)), "7", (X0 + 1, 1, 0)))
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


class FireTests(Flat):
    def test_a_strike_on_a_tree_sets_its_top_burning(self):
        grid = forest(trees=((X0 + 20, 0),))
        state, ctx = pet(), context(grid)
        with patch("backend.survival.storms.column_top", lambda grid, seed, x, z: (X0 + 20, 6, 0)):
            storm(state, ctx, BORN)
        self.assertEqual(grid.material(X0 + 20, 6, 0), "fire")
        self.assertEqual(len(state["sky"]["fires"]), 1)
        self.assertIn((BORN, "fire", "Lightning set a tree on fire near Pip."), ctx.events)

    def spread_for(self, state, grid, seconds, db=None):
        ctx = context(grid, db)
        spread(state, ctx, BORN)
        for second in range(10, seconds + 1, 10):
            spread(state, ctx, BORN + second / SCALE)
        return ctx

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
        state = pet(weather="clear")
        ignite(state, context(grid), (X0, 6, 0), BORN, None)
        with patch("backend.survival.storms.roll", lambda seed, cell, channel, salt=0: 0.0):
            self.spread_for(state, grid, 40)
        burned = {(entry["x"], entry["y"], entry["z"]) for entry in state["sky"]["fires"]}
        self.assertNotIn((X0 + 1, 6, 0), burned)
        self.assertNotIn((X0 - 1, 6, 0), burned)
        near_home = forest(trees=((X0, 0),))
        homely = pet(weather="clear")
        db = home_db((X0 + 6, 1, 0))
        with patch("backend.survival.storms.column_top", lambda grid, seed, x, z: (X0, 6, 0)):
            storm({**homely, "sky": {"weather": "storm"}}, context(near_home, db), BORN)
        self.assertEqual(near_home.material(X0, 6, 0), "leaves")

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


class TickTests(unittest.TestCase):
    def test_a_storm_near_a_forest_costs_the_tick_little(self):
        """Spec cost criterion: the sky hook at most 2 ms mean and 8 ms p99 a transaction over a storm near a
        forest with fires burning (a real hatched world, a storm pinned, fires lit round Mimo)."""
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            timings: list[float] = []
            real = sky.advance

            def timed(state, context, at):
                started = time.perf_counter()
                real(state, context, at)
                timings.append(time.perf_counter() - started)

            def measure() -> list[float]:
                timings.clear()
                with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "storm"), \
                        patch("backend.survival.tick.sky.advance", timed):
                    start = world.state()["last_tick_at"]
                    for call in range(1, 31):
                        tick_life(registry, start + call, scale=SCALE, action_scale=SCALE)
                return timings

            runs = []  # (mean, p99) of up to 3 runs, stopping at one within both (backend.tests.budget's rule)
            for _ in range(3):
                ordered = sorted(measure())
                runs.append((sum(ordered) / len(ordered), ordered[int(len(ordered) * 0.99) - 1]))
                if runs[-1][0] < 0.002 and runs[-1][1] < 0.008:
                    break
            self.assertTrue(any(mean < 0.002 and p99 < 0.008 for mean, p99 in runs), runs)
            self.assertTrue(world.state()["sky"]["strikes"])


if __name__ == "__main__":
    unittest.main()

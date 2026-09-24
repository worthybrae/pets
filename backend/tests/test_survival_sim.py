"""Seeded headless runs of the real brain: the BRAIN mind in the tick plus the worker's Chooser.

Each run hatches a life on a fixed seed and ticks it for a game day at 1x in coarse steps, the
way the worker would (tick, then let the chooser answer), once with the utility picker and once
with a fake Jev that answers at once with a seeded random pick and never touches the network.
Set MIMO_SLOW_TESTS=1 for longer runs on more seeds.
"""

import logging
import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import JEV_HOUR_CAP, Chooser, InlineExecutor, cap
from backend.survival.escape import TRAPPED_LIMIT, reachable_count
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import cell_of, places
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.steps import as_cell
from backend.survival.tick import tick_life
from backend.survival.triggers import HOUR
from backend.survival.world import SurvivalWorld, read_state

BORN = 1_000_000.0
DAY = 3600.0
SLOW = os.environ.get("MIMO_SLOW_TESTS") == "1"
SEEDS = (3, 11, 5, 21) if SLOW else (3, 11)
LENGTH = 2 * DAY if SLOW else DAY
STEP = 5.0 if SLOW else 15.0  # real seconds per tick: coarse, so a game day takes a few seconds
SAMPLE = 30.0  # game seconds between reachability checks
# The first hour is busy: wood, tools, stone, ores, better tools, from M4 food work (forage,
# fish, farm, cook, eat) and from M5 building (a shelter in a few goes, furnishing it, storage,
# dropping junk, a farm, torches), each a change of purpose and a change back.
# Slow-mode seeds reached 46 at baseline; the higher limit here catches real 58-116/hour floods.
# L1 adds a hunt, cooking its meat, putting away hides, wool and feathers, and swords (with all
# of L1, seeds 3, 11, 5 and 21 and both pickers reached 47, and 52 in slow mode).
# L3 adds pens, creature seeds and flint, more kinds to carry (birch and spruce wood, gold, the
# seeds), wider passages and hostiles near Mimo however deep it digs. With all of L3 the busiest
# hours reached 46, and 54 to 58 in slow mode as L2's last fixes landed, where seed 11's Jev pet
# goes two days without a chest: its arms stay full, and it swings between digging stone and
# dropping the loose blocks.
# Fix round 1: that 54-58 spread was partly `utility_pick`'s jitter following the purpose
# registry's import order (defect 4), not a real change of behaviour -- offered() now returns
# purposes in name order, the same however the test modules happen to import, and test_survival_sim
# gives the same numbers run alone and under discover. With the order pinned down, the busiest
# hours are 44-50 by default (the reviewer's probe also saw at most 50) and 38-51 in slow mode
# (seed 21, Jev, at 51), so the default budget holds with margin at 52 and the slow one comes down
# from 60 to 55.
PURPOSE_EVENTS_PER_HOUR = 55 if SLOW else 52
TRAPPED_AT_MOST = 180.0  # game seconds


class FakeJev:
    """Picks one of the offered purposes at random and notes the game time of every call."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.now = 0.0
        self.calls: list[float] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(self.now)
        offered = sorted(body["questions"]["purpose"]["criteria"])
        return {"answers": {"purpose": {"choice": self.rng.choice(offered)}}}


class Errors(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def most_in_an_hour(times: list[float]) -> int:
    """The most of `times` (game seconds) in any rolling game hour."""
    return max((sum(1 for other in times if at - HOUR < other <= at) for at in times), default=0)


def sample(world: SurvivalWorld) -> tuple[int, int | None]:
    """How many cells Mimo can reach, and how many its home can (None while it has no home)."""
    with world.connect() as db:
        state = read_state(db)
        grid = world_grid(db, state["world_seed"])
        homes = places(db, ("home",))
        here = reachable_count(grid, as_cell(state["position"]), TRAPPED_LIMIT)
        home = reachable_count(grid, cell_of(homes[0]), TRAPPED_LIMIT) if homes else None
    return here, home


def run_life(seed: int, jev: bool) -> dict:
    forget_logged()
    errors = Errors()
    logging.getLogger("backend").addHandler(errors)
    try:
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(seed), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            fake = FakeJev(seed)
            chooser = Chooser(env={"TYPESAFE_API_KEY": "k"} if jev else {}, http=fake, executor=InlineExecutor(),
                              rng=random.Random(seed), scale=1.0)
            t, trapped_since, trapped_longest, homes = 0.0, None, 0.0, []
            while t < LENGTH:
                t += STEP
                state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
                if state is None or state["died_at"] is not None:
                    break
                fake.now = t
                chooser.poll(registry, BORN + t)
                if t % SAMPLE < STEP:
                    here, home = sample(world)
                    if here < TRAPPED_LIMIT:
                        trapped_since = t if trapped_since is None else trapped_since
                        trapped_longest = max(trapped_longest, t - trapped_since)
                    else:
                        trapped_since = None
                    if home is not None:
                        homes.append(home)
            events = world.events(100_000)
            return {"state": world.state(), "calls": fake.calls, "trapped": trapped_longest, "homes": homes,
                    "purposes": [event["at"] - BORN for event in events if event["kind"] == "purpose"],
                    "errors": [record.getMessage() for record in errors.records]}
    finally:
        logging.getLogger("backend").removeHandler(errors)


class HeadlessBrainTests(unittest.TestCase):
    def check(self, run: dict, seed: int) -> None:
        self.assertIsNone(run["state"]["died_at"])
        self.assertEqual(run["errors"], [])
        self.assertLessEqual(run["trapped"], TRAPPED_AT_MOST)
        self.assertTrue(run["homes"], f"seed {seed} found no home")
        self.assertTrue(all(home >= TRAPPED_LIMIT for home in run["homes"]), run["homes"])
        self.assertLessEqual(most_in_an_hour(run["purposes"]), PURPOSE_EVENTS_PER_HOUR)

    def test_the_utility_brain_lives_a_day_with_its_home_in_reach(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                run = run_life(seed, jev=False)
                self.check(run, seed)
                self.assertEqual(run["calls"], [])

    def test_a_fake_jev_is_asked_at_most_the_hourly_budget_in_any_game_hour(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                run = run_life(seed, jev=True)
                self.check(run, seed)
                self.assertGreater(len(run["calls"]), 0)
                self.assertLessEqual(most_in_an_hour(run["calls"]), cap({}, JEV_HOUR_CAP))


if __name__ == "__main__":
    unittest.main()

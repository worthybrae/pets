"""Seeded headless runs of the real brain: the BRAIN mind in the tick plus the worker's Chooser.

Each run hatches a life on a fixed seed and ticks it for a game day at 1x in coarse steps, the
way the worker would (tick, then let the chooser answer). The fake Jev answers at once with a
seeded random pick among the offered purposes and never touches the network.
"""

import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.triggers import HOUR

BORN = 1_000_000.0
DAY = 3600.0
STEP = 10.0  # real seconds per tick: coarse, so a game day takes a few seconds
SEEDS = (3, 11)
MODEL_BUDGET = 8


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


def most_in_an_hour(times: list[float]) -> int:
    """The most calls in any rolling game hour."""
    return max((sum(1 for other in times if at - HOUR < other <= at) for at in times), default=0)


def run_life(seed: int, jev: bool, seconds: float = DAY, step: float = STEP) -> dict:
    with tempfile.TemporaryDirectory() as root:
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        hatch(registry, random.Random(seed), timestamp=BORN)
        fake = FakeJev(seed)
        chooser = Chooser(env={"TYPESAFE_API_KEY": "k"} if jev else {}, http=fake, executor=InlineExecutor(),
                          rng=random.Random(seed), scale=1.0)
        t = 0.0
        while t < seconds:
            t += step
            state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
            if state is None or state["died_at"] is not None:
                break
            fake.now = t
            chooser.poll(registry, BORN + t)
        return {"calls": fake.calls, "state": state}


class HeadlessBrainTests(unittest.TestCase):
    def test_a_fake_jev_is_asked_at_most_eight_times_in_any_game_hour(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                run = run_life(seed, jev=True)
                self.assertGreater(len(run["calls"]), 0)
                self.assertLessEqual(most_in_an_hour(run["calls"]), MODEL_BUDGET)


if __name__ == "__main__":
    unittest.main()

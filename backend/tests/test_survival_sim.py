"""Seeded headless runs of the real brain: the BRAIN mind in the tick plus the worker's Chooser.

Each run hatches a life on a fixed seed and ticks it for a game day at 1x in coarse steps, the
way the worker would (tick, then let the chooser answer), once with the utility picker and once
with a fake Jev that answers at once with a seeded random pick and never touches the network.
Set MIMO_SLOW_TESTS=1 for longer runs on more seeds. L4: each run is made once and shared by the
tests, which also check that goals leave fewer aimless changes of purpose than before them, that
every explore goes for a reason, and that once home stands every game day brings a discovery and
Mimo rests or sleeps at most half the time. L4a final fix wave: in slow mode, a few lives run six game
days, and on days 4 and 5 they still walk new ground and rest at most a little over half the time.
"""

import functools
import logging
import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import JEV_HOUR_CAP, Chooser, InlineExecutor, cap
from backend.survival.escape import way_out
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
# Follow-up fix, item 1: with dig_heading only picking a heading whose batch mines something, seed
# 21's utility pet reaches 56 in its busy first slow-mode hour (was 55): one more real change of
# purpose in normal startup work, not a new loop (no death, no error, every other seed and picker
# stayed at 52 or under). The slow budget holds with a little more margin at 58.
PURPOSE_EVENTS_PER_HOUR = 58 if SLOW else 52
TRAPPED_AT_MOST = 180.0  # game seconds
# L4: goals fill the day with work, and a change toward a goal (its event says ", toward ...") is
# that work, so the flood guard above now counts the other changes, and all changes get a looser
# cap of their own. Every explore trip has a reason and ends early on a find, so a trip is a change
# to explore and one to the purpose that follows up on the find (with all of L4 on L3, the busiest
# game hour reached 55, and 75 in slow mode, at most 31 of them toward no goal).
ALL_EVENTS_PER_HOUR = 90
# L4: changes of purpose to rest or explore that work toward no goal, per game hour, over every
# seed and both pickers, measured on these runs before L4 (bd765f2): 4.5 (4.56 in slow mode).
# With goals they must fall by at least a quarter; measured with L4, 0.0 (0.81 in slow mode).
# An explore says what it goes for ("decided to explore to look for trees."), and one that serves no
# goal still counts here.
AIMLESS_BEFORE_GOALS = 4.56 if SLOW else 4.5
AIMLESS_SHARE = 0.75
AIMLESS = (" decided to rest.", " decided to explore")  # a change toward a goal says ", toward ..."
# L4: once home stands, the share of ticks Mimo spends resting or asleep (its purpose rest or sleep,
# or asleep), over every seed and both pickers: 70-80 % before L4 (the controller's measure), and
# the night alone is a third of a game day.
REST_AT_MOST = 0.5
# L4a final fix wave, I4: 6-day lives in slow mode. By day 4 a pet had walked all the land within a
# fixed 90 blocks and settled back into resting (82-93 % of days 4-5 on some seeds, 1-12 new patches
# a day); now the day trips' reach grows with the land walked. LONG_RUNS (seed, Jev) live LONG_DAYS
# game days; on each of days 4 and 5 every one walks at least NEW_GROUND_LATE patches it never walked
# before, and once home stands they rest or sleep at most LONG_REST_AT_MOST of the ticks. The floors
# are the final fix wave's measure with margin (its report).
LONG_DAYS = 6
LONG_RUNS = ((3, False), (21, True))
LATE_DAYS = (3, 4)  # days 4 and 5, counted from 0
NEW_GROUND_LATE = 40
LONG_REST_AT_MOST = 0.55


class FakeJev:
    """Picks one of the offered purposes (or goals) at random and notes the game time of every call."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.now = 0.0
        self.calls: list[float] = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(self.now)
        # Every question it is asked gets a random pick among its choices.
        return {"answers": {question: {"choice": self.rng.choice(sorted(asked["criteria"]))}
                            for question, asked in body["questions"].items()}}


class Errors(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record):
        self.records.append(record)


def most_in_an_hour(times: list[float]) -> int:
    """The most of `times` (game seconds) in any rolling game hour."""
    return max((sum(1 for other in times if at - HOUR < other <= at) for at in times), default=0)


def aimless(text: str) -> bool:
    """L4: a change of purpose to rest or explore that works toward no goal."""
    return any(words in text for words in AIMLESS) and ", toward " not in text


def unreasoned(text: str) -> bool:
    """L4: a change of purpose to explore that does not say what for ("decided to explore to ...")."""
    return " decided to explore" in text and " decided to explore to " not in text


def dull_days(home_at: float | None, discoveries: list[float], end: float) -> list[int]:
    """L4: the game days, from the one home first stood in on, that brought no discovery."""
    if home_at is None:
        return []
    return [day for day in range(int(home_at // DAY), int(end // DAY) + (end % DAY > 0))
            if not any(max(home_at, day * DAY) <= at < (day + 1) * DAY for at in discoveries)]


def sample(world: SurvivalWorld) -> tuple[bool, bool | None]:
    """Whether Mimo can walk to the natural surface or home, and whether its home can walk to the
    surface (None while it has no home). L3 final fix wave: this was "fewer than 256 cells reachable",
    blind to a bigger pocket with no way up (escape.way_out). Making wave 2: an expedition's camp (L4b, an
    "outpost" place) counts as home for the night: Mimo digs in there and puts a roof over its head on
    purpose, and takes it off in the morning (camp.leave_camp). This check predates camps; the seed-3 Jev
    life first camped inside these two game days once a goal finished on the side was reached (its mood
    and choices moved on from there), and its night in camp read as 1,620 s trapped."""
    with world.connect() as db:
        state = read_state(db)
        seed = state["world_seed"]
        grid = world_grid(db, seed)
        homes = [cell_of(place) for place in places(db, ("home",))]
        camps = [cell_of(place) for place in places(db, ("outpost",))]
        here = way_out(grid, as_cell(state["position"]), seed, set(homes) | set(camps))
        home = way_out(grid, homes[0], seed) if homes else None
    return here, home


def patches_walked(world: SurvivalWorld) -> int:
    with world.connect() as db:
        return db.execute("SELECT COUNT(*) FROM memory_explored").fetchone()[0]


@functools.lru_cache(maxsize=None)
def run_life(seed: int, jev: bool, length: float = LENGTH) -> dict:
    """One headless run, made once per seed, picker and length and shared by the tests (call it with
    jev=...)."""
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
            t, trapped_since, trapped_longest, homes, unreasoned_walks = 0.0, None, 0.0, [], 0
            home_at, seen, discoveries, resting, lived = None, 0, [], 0, 0
            walked_by_day = [0]  # patches walked by the end of each game day (L4a final fix wave)
            while t < length:
                t += STEP
                if t // DAY > len(walked_by_day) - 1:
                    walked_by_day.append(patches_walked(world))
                state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
                if state is None or state["died_at"] is not None:
                    break
                action = state.get("action") or {}
                if action.get("purpose") == "explore" and not (state["brain"].get("trip") or {}).get("reason"):
                    unreasoned_walks += 1  # L4: an explore step under way with no reason in the brain
                if home_at is not None:
                    lived += 1
                    resting += state["brain"].get("purpose") in ("rest", "sleep") or action.get("kind") == "sleep"
                count = (state["brain"].get("curiosity") or {}).get("seen", 0)
                if count > seen:
                    seen = count
                    discoveries.append(t)  # L4: a discovery (curiosity counts them)
                fake.now = t
                chooser.poll(registry, BORN + t)
                if t % SAMPLE < STEP:
                    here, home = sample(world)
                    if not here:
                        trapped_since = t if trapped_since is None else trapped_since
                        trapped_longest = max(trapped_longest, t - trapped_since)
                    else:
                        trapped_since = None
                    if home is not None:
                        homes.append(home)
                        home_at = t if home_at is None else home_at
            events = world.events(100_000)
            purposes = [event for event in events if event["kind"] == "purpose"]
            return {"state": world.state(), "calls": fake.calls, "trapped": trapped_longest, "homes": homes,
                    "purposes": [event["at"] - BORN for event in purposes],
                    "free": [event["at"] - BORN for event in purposes if ", toward " not in event["text"]],
                    "aimless": [event["at"] - BORN for event in purposes if aimless(event["text"])],
                    "unreasoned": [event["text"] for event in purposes if unreasoned(event["text"])],
                    "unreasoned_walks": unreasoned_walks,
                    "dull_days": dull_days(home_at, discoveries, t),
                    "resting": resting, "lived": lived,
                    "new_ground": [after - before for before, after in zip(walked_by_day, walked_by_day[1:])],
                    "hours": t / HOUR,
                    "errors": [record.getMessage() for record in errors.records]}
    finally:
        logging.getLogger("backend").removeHandler(errors)


class HeadlessBrainTests(unittest.TestCase):
    def check(self, run: dict, seed: int) -> None:
        self.assertIsNone(run["state"]["died_at"])
        self.assertEqual(run["errors"], [])
        self.assertLessEqual(run["trapped"], TRAPPED_AT_MOST)
        self.assertTrue(run["homes"], f"seed {seed} found no home")
        self.assertTrue(all(run["homes"]), run["homes"])
        self.assertLessEqual(most_in_an_hour(run["free"]), PURPOSE_EVENTS_PER_HOUR)
        self.assertLessEqual(most_in_an_hour(run["purposes"]), ALL_EVENTS_PER_HOUR)

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

    def test_goals_leave_fewer_aimless_rests_and_explores_than_before_them(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        per_hour = sum(len(run["aimless"]) for run in runs) / sum(run["hours"] for run in runs)
        self.assertLessEqual(per_hour, AIMLESS_SHARE * AIMLESS_BEFORE_GOALS)

    def test_once_home_stands_every_game_day_brings_a_discovery(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        self.assertEqual([run["dull_days"] for run in runs], [[]] * len(runs))

    def test_once_home_stands_mimo_rests_and_sleeps_at_most_half_the_time(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        share = sum(run["resting"] for run in runs) / sum(run["lived"] for run in runs)
        self.assertLessEqual(share, REST_AT_MOST)

    @unittest.skipUnless(SLOW, "6-day lives run in slow mode only (MIMO_SLOW_TESTS=1)")
    def test_six_days_on_mimo_still_walks_new_ground_and_rests_at_most_a_little_over_half_the_time(self):
        runs = {(seed, jev): run_life(seed, jev=jev, length=LONG_DAYS * DAY) for seed, jev in LONG_RUNS}
        for key, run in runs.items():
            self.assertIsNone(run["state"]["died_at"], key)
            self.assertEqual(run["errors"], [], key)
        late = {key: [run["new_ground"][day] for day in LATE_DAYS] for key, run in runs.items()}
        self.assertTrue(all(min(days) >= NEW_GROUND_LATE for days in late.values()), late)
        share = sum(run["resting"] for run in runs.values()) / sum(run["lived"] for run in runs.values())
        self.assertLessEqual(share, LONG_REST_AT_MOST)

    def test_every_explore_goes_for_a_reason(self):
        runs = [run_life(seed, jev=jev) for seed in SEEDS for jev in (False, True)]
        self.assertEqual([text for run in runs for text in run["unreasoned"]], [])
        self.assertEqual(sum(run["unreasoned_walks"] for run in runs), 0)


if __name__ == "__main__":
    unittest.main()

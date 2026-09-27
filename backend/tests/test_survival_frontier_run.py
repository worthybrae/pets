"""Headless frontier runs (L5): the real brain and the rules' Chooser take a pet to the far wilds.

Each run hatches a life on a fixed seed, stands a finished cottage of cobblestone with a bed beside
where it hatched and makes it the home it built (its first shelter reached, so the rings centre there,
its goals open and it sleeps in it), hands it gear and food, and ticks it at 1x in coarse steps, the
way the worker would. A first version only named the hatching spot home, with no shelter: build_shelter
stayed on offer everywhere, and a pet far out built there and slept out. A geared pet (a stone sword, a leather cap and tunic,
a bow and 16 arrows, food) starts with riches farther out as its goal; an ungeared one (the sword and
the food, no armor) is left to choose. Each run is made once and shared by the tests. Set
MIMO_SLOW_TESTS=1 for four game days on three seeds, in finer steps: over four days a pet left without
armor may make its own (L2's make_gear) and is geared from then on, so the check that holds in both
modes is that no riches trip ever runs while a pet is not geared. A last check times the creatures near
a geared pet in the far wilds at night: at most 20 ms a slice, like L2's budget.
"""

import functools
import logging
import math
import os
import random
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.worldgen import terrain_height
from backend.survival import tick
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.creatures.combat import SWORDS, weapon
from backend.survival.creatures.harm import armor_cut
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.table import Herd
from backend.survival.goals import REACHED, adopt_goal
from backend.survival.hatch import hatch
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.frontier import DETOUR, LEAD_SLACK, far_lead, past_readiness, reach_limit
from backend.survival.grid import world_grid
from backend.survival.memory import finish_structure, know, set_home
from backend.survival.once import forget_logged
from backend.survival.pathing import WALK_SECONDS
from backend.survival.purposes import HOMEWARD, homeward_from
from backend.survival.registry import LifeRegistry
from backend.survival.rings import BOW_INSTEAD, READY, ring_here
from backend.survival.ruins import LOOT
from backend.survival.situation import NIGHTFALL, Situation
from backend.survival.structures import start
from backend.survival.tick import MAX_STEP_SECONDS, tick_life
from backend.survival.trips import REASONS, targets
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.budget import best_mean
from backend.tests.no_model import NoModel, no_model
from backend.tests.test_survival_sim import Errors

BORN = 1_000_000.0
DAY = 3600.0
SLOW = os.environ.get("MIMO_SLOW_TESTS") == "1"
# Slow mode runs three seeds, to keep it within a quarter of an hour. Seed 3 was left out while its pet,
# with this cottage and with or without L5, got stuck 87 blocks from home and starved on day 4 (before
# L4a's final fix wave); since that wave its runs pass too.
SEEDS = (8, 11, 5) if SLOW else (8,)
DAYS = 4 if SLOW else 1
STEP = 5.0 if SLOW else 15.0
GEAR = {"stone_sword": 1, "leather_cap": 1, "leather_tunic": 1, "bow": 1, "arrow": 16, "bread": 6, "cooked_beef": 4}
UNGEARED = {"stone_sword": 1, "bread": 6, "cooked_beef": 4}
FAR_LOOT = {item for item, *_ in LOOT[2]} - {item for item, *_ in LOOT[1]}  # what only the far wilds' ruins hold
CLOCK = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def home_of_its_own(db, state: dict) -> None:
    """A finished cottage beside where Mimo hatched, with a bed, made its home; Mimo stands inside."""
    grid = world_grid(db, state["world_seed"])
    here = tuple(round(state["position"][axis]) for axis in "xyz")
    sides = ("north", "east", "south", "west")
    site = find_site(grid, here, (3, 3), sides, "flat")
    design = shelter(site, Style("flat", "cobblestone", "planks", "none", sides), f"{state['name']}'s Snug Cottage")
    for planned in design.parts("floor", "wall", "roof", "bed"):
        grid.put(*planned.cell, "bed" if planned.part == "bed" else "cobblestone")
    finish_structure(db, start(db, grid, design, BORN), BORN)
    set_home(db, design.anchor, BORN)
    know(db, "first_shelter", REACHED, BORN)
    state["position"] = dict(zip("xyz", map(float, design.anchor)))


def armed_and_armored(inventory: dict) -> bool:
    """Armed and armored for the far wilds (rings.READY[2]), health and food aside."""
    sword = weapon(inventory)
    armed = (sword is not None and SWORDS[sword] >= READY[2].sword) or \
        (inventory.get("bow", 0) > 0 and inventory.get("arrow", 0) >= BOW_INSTEAD)
    return armed and armor_cut(inventory) >= READY[2].armor - 1e-9


@functools.lru_cache(maxsize=None)
def run_trip(seed: int, geared: bool) -> dict:
    """One headless run (see the module docstring), shared by the tests."""
    forget_logged()
    errors = Errors()
    logging.getLogger("backend").addHandler(errors)
    try:
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(seed), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                home_of_its_own(db, state)
                state["inventory"].update(GEAR if geared else UNGEARED)
                if geared:
                    adopt_goal(state, "frontier", "utility", "Old ruins stand out in the far wilds.", BORN)
                write_state(db, state)
            model = NoModel()  # Task 9 review: a model called in a headless run fails the tests (run["model_calls"])
            chooser = Chooser(env={}, http=model, executor=InlineExecutor(), rng=random.Random(seed), scale=1.0)
            t, deepest, at_nightfall, lowest, ungeared_riches = 0.0, 0, [], 100.0, 0
            while t < DAYS * DAY:
                t += STEP
                state = tick_life(registry, BORN + t, scale=1.0, mind=BRAIN, action_scale=1.0)
                if state is None or state["died_at"] is not None:
                    break
                chooser.poll(registry, BORN + t)
                deepest = max(deepest, ring_here(state))
                brain = state.get("brain") or {}
                if (brain.get("purpose") == "explore" and (brain.get("trip") or {}).get("reason") == "riches"
                        and not armed_and_armored(state["inventory"])):
                    ungeared_riches += 1  # a riches trip under way while Mimo is not geared for it
                lowest = min(lowest, state["vitals"]["health"])
                if t % DAY == NIGHTFALL:  # pre-flight: a night in an expedition's camp (L4b) is no riches trip's
                    out = ((state.get("brain") or {}).get("goal") or {}).get("name") == "expedition"
                    at_nightfall.append(None if out else ring_here(state))
            events = world.events(100_000)
            return {"state": world.state(), "deepest": deepest, "at_nightfall": at_nightfall, "lowest": lowest,
                    "ungeared_riches": ungeared_riches, "model_calls": list(model.calls),
                    "texts": [event["text"] for event in events], "kinds": [event["kind"] for event in events],
                    "errors": [record.getMessage() for record in errors.records]}
    finally:
        logging.getLogger("backend").removeHandler(errors)


class LeadAndFenceTests(unittest.TestCase):
    """Task 9 review (carried to the L5 final fix wave): the runs above would not notice the far lead or the fence
    gone (their trips stay near 220 blocks, where the base lead home suffices, and riches_value zeroes the land past
    readiness by itself), so these check both on the runs' own world: seed 8's hatched life, geared as above, in
    the cottage it built."""

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.TemporaryDirectory()
        registry = LifeRegistry(Path(cls.root.name) / "data", Path(cls.root.name) / "no-legacy.sqlite3")
        cls.world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))
        with cls.world.transaction() as db:
            state = read_state(db)
            home_of_its_own(db, state)
            state["inventory"].update(GEAR)
            state["frontier"] = {"center": [state["position"]["x"], state["position"]["z"]]}
            write_state(db, state)

    @classmethod
    def tearDownClass(cls):
        cls.root.cleanup()

    def out(self, db, blocks: float) -> Situation:
        """The pet `blocks` east of home, by day."""
        state = read_state(db)
        x, z = state["frontier"]["center"]
        state["position"] = {"x": float(round(x + blocks)), "y": float(terrain_height(round(x + blocks), round(z),
                                                                                       state["world_seed"]) + 1),
                             "z": float(z)}
        return Situation(state, world_grid(db, state["world_seed"]), CLOCK, BORN + 100.0, db)

    def test_far_out_the_walk_home_starts_sooner_by_the_walk_itself(self):
        with self.world.connect() as db:
            near, far = self.out(db, 100), self.out(db, 200)
            self.assertEqual((far_lead(near), homeward_from(near)), (0.0, HOMEWARD))
            self.assertAlmostEqual(far_lead(far), 200 * WALK_SECONDS * DETOUR + LEAD_SLACK, delta=1.0)
            self.assertAlmostEqual(homeward_from(far), HOMEWARD - far_lead(far), delta=1e-6)

    def test_no_wander_out_past_the_far_wilds_heads_past_readiness(self):
        with self.world.connect() as db:
            s = self.out(db, 250)  # ready for the far wilds, not the frontier: its limit is 240 blocks
            self.assertEqual(reach_limit(s), 240.0)
            aims = targets(s, REASONS["wander"])
            self.assertTrue(aims)
            x, z = s.state["frontier"]["center"]
            self.assertLessEqual(max(math.hypot(aim.cell[0] - x, aim.cell[2] - z) for aim in aims), 240.0)
            self.assertTrue(past_readiness(s, (round(x) + 280, 5, round(z))))


class FrontierRunTests(unittest.TestCase):
    def test_a_geared_pet_goes_to_the_far_wilds_loots_a_ruin_and_is_home_by_nightfall(self):
        for seed in SEEDS:
            run = run_trip(seed, True)
            self.assertIsNone(run["state"]["died_at"], (seed, run["state"]["cause"]))
            self.assertEqual(run["errors"], [], seed)
            self.assertEqual(run["model_calls"], [], seed)
            self.assertGreaterEqual(run["deepest"], 2, seed)
            opened = [text for text in run["texts"] if "opened an old chest in a ruin" in text]
            self.assertTrue(opened, seed)
            self.assertTrue(any(item.replace("_", " ") in text for text in opened for item in FAR_LOOT), (seed, opened))
            self.assertIn(f"{run['state']['name']} reached a goal: riches farther out.", run["texts"], seed)
            nights = [ring for ring in run["at_nightfall"] if ring is not None]  # an expedition's camp left out
            self.assertTrue(nights and set(nights) == {0}, (seed, run["at_nightfall"]))  # home ground every night

    def test_an_ungeared_pet_is_never_offered_riches(self):
        for seed in SEEDS:
            run = run_trip(seed, False)
            self.assertIsNone(run["state"]["died_at"], (seed, run["state"]["cause"]))
            self.assertEqual(run["errors"], [], seed)
            self.assertEqual(run["model_calls"], [], seed)
            self.assertEqual(run["ungeared_riches"], 0, seed)
            if not SLOW:  # in its first game day it makes no armor: it never leaves the near wilds
                self.assertLessEqual(run["deepest"], 1, seed)
                self.assertFalse([text for text in run["texts"] if "seek riches" in text or "riches farther out" in text])
        self.assertEqual([run_trip(seed, True)["ungeared_riches"] for seed in SEEDS], [0] * len(SEEDS))

    def test_creatures_cost_well_under_twenty_milliseconds_a_slice_in_the_far_wilds_at_night(self):
        """A geared pet in the far wilds early in the first night, a toughened gloomling, skitter and
        thornback beside it and the dark free to bring more (the cap is 10 out there), caught up a
        60-game-second transaction at a time; best of up to 3 runs (backend.tests.budget)."""
        def run() -> list[float]:
            spent = [0.0] * 5

            def timed(*args, **kwargs):
                start = time.perf_counter()
                real(*args, **kwargs)
                spent[call - 1] += time.perf_counter() - start

            with tempfile.TemporaryDirectory() as root:
                registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
                life = hatch(registry, random.Random(3), timestamp=BORN)
                world = SurvivalWorld(registry.world_path(life))
                with world.transaction() as db:
                    state = read_state(db)
                    state["born_at"] = BORN - 2450.0  # early in the first night
                    state["inventory"].update(GEAR)
                    x, _, z = (round(state["position"][axis]) for axis in "xyz")
                    state["frontier"] = {"birthplace": [x - 150, z]}  # 150 blocks out: the far wilds
                    write_state(db, state)
                    for kind, cx in (("gloomling", x + 3), ("skitter", x - 3), ("thornback", x + 6)):
                        cell = (cx, terrain_height(cx, z, state["world_seed"]) + 1, z)
                        Herd(db).add(kind, cell, KINDS[kind].health * 1.7, BORN, BORN,
                                     {"home": list(cell), "turn": 0, "ring": 2, "most": KINDS[kind].health * 1.7})
                chooser = Chooser(env={}, http=no_model(self), executor=InlineExecutor(), rng=random.Random(3), scale=1.0)
                with patch("backend.survival.tick.simulate", timed):
                    for call in range(1, 6):
                        at = BORN + call * MAX_STEP_SECONDS
                        state = tick_life(registry, at, scale=1.0, mind=BRAIN, action_scale=1.0)
                        self.assertIsNone(state["died_at"], state["cause"])
                        self.assertEqual(state["frontier"]["ring"], 2)
                        chooser.poll(registry, at)
            return spent

        real = tick.simulate
        self.assertLess(best_mean(run, 0.020), 0.020)


if __name__ == "__main__":
    unittest.main()

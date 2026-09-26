import logging
import math
import random
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import tick
from backend.survival.creatures import darkness
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.darkness import (
    DESPAWN_REACH, HOSTILE_CAP, SPAWN_EVERY, SPAWN_FAR, SPAWN_NEAR, spawn_hostiles, spots,
)
from backend.survival.creatures.hostiles import LOITER
from backend.survival.creatures.kinds import KINDS, kind_of
from backend.survival.creatures.simulate import (
    HOSTILE_ACTS, MAX_ACTS, TURNS_EACH, UNKNOWN_WAIT, populate, take_turns,
)
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables, dead
from backend.survival.grid import Grid, world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import places
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.vitals import START_VITALS
from backend.survival.tick import FIGHT_SLICES_MAX, advance_world, tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.budget import best_mean

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
DAY = {**NIGHT, "phase": "day", "seconds_into_day": 1000.0}
BORN = 1_000_000.0


def land(blocks=None, cave=False):
    """Grass at y 0 over stone; with `cave`, an open cave at y -4..-3 everywhere; `blocks` placed."""
    def natural(x, y, z):
        if y == 0:
            return "grass"
        if y < 0:
            return "air" if cave and -4 <= y <= -3 else "stone"
        return "air"

    grid = Grid(natural)
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet():
    return {"name": "Pip", "world_seed": "4", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
            "vitals": {"health": 100.0}, "died_at": None}


def scene(grid, state, at=100.0, clock=NIGHT):
    return Scene(grid, grid.herd, "4", state, at, 1.0, events=[], clock=clock)


class SpawnTests(unittest.TestCase):
    def setUp(self):
        for target in ("backend.survival.creatures.darkness.terrain_height", "backend.survival.light.terrain_height"):
            patcher = patch(target, lambda x, z, seed: 0)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_at_night_a_gloomling_comes_out_on_dark_ground_sixteen_to_forty_blocks_away(self):
        grid, state = land(), pet()
        born = spawn_hostiles(scene(grid, state))
        self.assertEqual([creature["kind"] for creature in born], ["gloomling"])
        x, y, z = cell_of(born[0])
        self.assertTrue(SPAWN_NEAR <= math.hypot(x, z) <= SPAWN_FAR + 1, (x, z))
        self.assertEqual((y, born[0]["next_at"]), (1, 101.0))
        self.assertEqual(spawn_hostiles(scene(grid, state, at=100.0 + SPAWN_EVERY - 1)), [])
        self.assertEqual(len(spawn_hostiles(scene(grid, state, at=100.0 + SPAWN_EVERY))), 1)

    def test_by_day_the_open_ground_is_lit_and_only_caves_spawn_them_mostly_skitters(self):
        self.assertEqual(spawn_hostiles(scene(land(), pet(), clock=DAY)), [])
        kinds = []
        for minute in range(60):
            found = spawn_hostiles(scene(land(cave=True), pet(), at=100.0 + 60 * minute, clock=DAY))
            self.assertEqual([cell_of(creature)[1] for creature in found], [-4])
            kinds += [creature["kind"] for creature in found]
        self.assertEqual(set(kinds), {"skitter", "gloomling"})
        # fix round 1: SKITTER_SHARE (0.6) of the covered-place spawns should be skitters, not just "some".
        share = kinds.count("skitter") / len(kinds)
        self.assertTrue(0.45 <= share <= 0.75, share)

    def test_the_spawn_salt_does_not_repeat_within_one_server_second_at_a_high_time_scale(self):
        # fix round 1: at MIMO_TIME_SCALE=60, two legitimate chances (SPAWN_EVERY game seconds
        # apart) can land within the same integer server second; salting by game seconds instead
        # keeps them from rolling the identical cell (and stacking a second hostile on the first).
        fast = {**NIGHT, "time_scale": 60.0}
        grid, state = land(), pet()
        first = spawn_hostiles(Scene(grid, grid.herd, "4", state, 100.0, 1.0, events=[], clock=fast))
        second = spawn_hostiles(Scene(grid, grid.herd, "4", state, 100.9, 1.0, events=[], clock=fast))
        self.assertEqual((len(first), len(second)), (1, 1))
        self.assertNotEqual(cell_of(first[0]), cell_of(second[0]))

    def test_torches_keep_the_ground_near_them_safe_and_nothing_spawns_where_mimo_built(self):
        with patch("backend.survival.creatures.darkness.roll", lambda *args: 0.0):  # every try: 16 blocks east
            self.assertEqual([cell_of(creature) for creature in spawn_hostiles(scene(land(), pet()))],
                             [(16, 1, 0)])
            self.assertEqual(spawn_hostiles(scene(land({(16, 1, 2): "torch"}), pet())), [])
            claimed = land()
            claimed.claims.add((16, 1, 0))
            self.assertEqual(spawn_hostiles(scene(claimed, pet())), [])

    def test_no_more_than_eight_hostiles_alive_near_mimo(self):
        grid, state = land(), pet()
        near = [grid.herd.add("gloomling", (20 + n, 1, 0), 20.0, 0.0, 0.0, {}) for n in range(HOSTILE_CAP)]
        self.assertEqual(spawn_hostiles(scene(grid, state)), [])
        near[0]["state"]["pose"] = "dead"
        grid.herd.save(near[0])
        # fix round 2: dark_spawn_at is now set on the capped call too, so the next chance is at
        # least SPAWN_EVERY game seconds later, not on the very next call at the same moment.
        self.assertEqual(len(spawn_hostiles(scene(grid, state, at=100.0 + SPAWN_EVERY))), 1)

    def test_the_spawn_window_stays_shut_while_the_cap_holds_so_the_sweep_and_count_run_once(self):
        # fix round 2: dark_spawn_at used to stay unset for as long as HOSTILE_CAP hostiles were
        # alive (the cap-blocked return came before the assignment), so the cheap window check kept
        # passing and despawn_far/hostiles_alive (each a table scan) ran on every call regardless.
        grid, state = land(), pet()
        [grid.herd.add("gloomling", (20 + n, 1, 0), 20.0, 0.0, 0.0, {}) for n in range(HOSTILE_CAP)]
        swept = []
        real_despawn_far = darkness.despawn_far

        def counted(scene):
            swept.append(scene.at)
            return real_despawn_far(scene)

        with patch("backend.survival.creatures.darkness.despawn_far", counted):
            for at in (100.0, 105.0, 110.0, 115.0, 120.0, 125.0):  # all within one SPAWN_EVERY (30) window
                self.assertEqual(spawn_hostiles(scene(grid, state, at=at)), [])
        self.assertEqual(swept, [100.0])  # only the first call actually swept; the window then stayed shut

    def test_hostiles_far_from_mimo_go_at_night_and_out_of_its_reach_by_day_but_animals_stay(self):
        grid = land()
        far = grid.herd.add("gloomling", (int(DESPAWN_REACH) + 5, 1, 0), 20.0, 0.0, 0.0, {})
        beyond = grid.herd.add("skitter", (60, 1, 0), 12.0, 0.0, 0.0, {})
        near = grid.herd.add("skitter", (40, 1, 0), 12.0, 0.0, 0.0, {})
        cow = grid.herd.add("cow", (70, 1, 0), 10.0, 0.0, 0.0, {})
        spawn_hostiles(scene(grid, pet()))
        self.assertEqual([grid.herd.get(creature["id"]) is None for creature in (far, beyond, near, cow)],
                         [True, False, False, False])
        spawn_hostiles(scene(grid, pet(), clock=DAY))
        self.assertEqual([grid.herd.get(creature["id"]) is None for creature in (beyond, near, cow)],
                         [True, False, False])

    def test_at_night_a_hostile_left_out_of_reach_fades_so_it_cannot_hold_the_cap(self):
        # Final fix wave: 48 to 64 blocks away a hostile is neither simulated (it never loiters
        # and fades) nor despawned, so frozen ones could hold the cap of 8 all night. One that has
        # not had a turn for LOITER game seconds out there fades like a loiterer near Mimo.
        grid, at = land(), 1000.0
        frozen = [grid.herd.add("gloomling", (50 + n, 1, 0), 20.0, 0.0, 0.0, {}) for n in range(HOSTILE_CAP)]
        lately = grid.herd.add("skitter", (0, 1, 55), 12.0, 0.0, at - LOITER / 2, {})  # acted just now
        close = grid.herd.add("skitter", (40, 1, 0), 12.0, 0.0, 0.0, {})  # in reach: it fades on its own turn
        born = spawn_hostiles(scene(grid, pet(), at=at))
        self.assertTrue(all(grid.herd.get(creature["id"]) is None for creature in frozen))
        self.assertIsNotNone(grid.herd.get(lately["id"]))
        self.assertIsNotNone(grid.herd.get(close["id"]))
        self.assertEqual(len(born), 1)  # the cap is free again

    def test_a_column_offers_its_ground_and_its_caves_but_not_leaves_torches_or_water(self):
        grid = land({(3, 1, 0): "leaves", (4, 1, 0): "torch", (5, 0, 0): "water"}, cave=True)
        self.assertEqual(spots(grid, "4", 0, 0, 1), [(0, 1, 0), (0, -4, 0)])
        self.assertEqual(spots(grid, "4", 3, 0, 1), [(3, -4, 0)])
        self.assertEqual(spots(grid, "4", 4, 0, 1), [(4, -4, 0)])
        self.assertEqual(spots(grid, "4", 5, 0, 1), [(5, -4, 0)])
        self.assertEqual(spots(grid, "4", 0, 0, 8), [(0, 1, 0)])  # the cave is too far below Mimo
        self.assertEqual(spots(grid, "4", 0, 0, -10), [(0, -4, 0)])  # and the ground too far above


class TurnTests(unittest.TestCase):
    def add(self, grid, kind, cell):
        return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 0.0, {"home": list(cell), "turn": 0, "pose": "idle"})

    def test_a_hostile_takes_each_turn_due_in_a_call_at_its_own_time_but_not_long_ago(self):
        grid, state = land(), {**pet(), "vitals": dict(START_VITALS)}
        gloom, cow = self.add(grid, "gloomling", (1, 1, 0)), self.add(grid, "cow", (0, 1, 6))
        take_turns(scene(grid, state, at=10.0), [gloom, cow])
        self.assertEqual(state["vitals"]["health"], 94.0)  # at 8.0 and 9.2: LATE seconds back at most
        self.assertEqual(grid.herd.get(gloom["id"])["state"]["struck_at"], 9.2)
        self.assertEqual(grid.herd.get(cow["id"])["state"]["turn"], 1)  # an animal takes one turn
        skitter = self.add(grid, "skitter", (0, 1, 1))
        with patch("backend.survival.creatures.simulate.LATE", 100.0):
            take_turns(scene(grid, state, at=20.0), [skitter])
        self.assertEqual(state["vitals"]["health"], 94.0 - 2.0 * TURNS_EACH)  # no more than TURNS_EACH a call

    def test_every_overdue_animal_gets_turns_across_calls_not_just_the_lowest_ids(self):
        # fix round 1: ordering only by the clamped time (shared by every long-overdue creature)
        # and then id let ids past MAX_ACTS starve forever; the raw next_at breaks that tie by
        # staleness, so the ones skipped in an earlier call are the first ones picked next call.
        grid, state = land(), {**pet(), "vitals": dict(START_VITALS)}
        cows = [self.add(grid, "cow", (n, 1, 0)) for n in range(30)]
        for call in range(1, 11):
            take_turns(scene(grid, state, at=10.0 * call), cows)
        self.assertTrue(all(cow["state"]["turn"] >= 1 for cow in cows), [cow["state"]["turn"] for cow in cows])
        self.assertTrue(all(grid.herd.get(cow["id"])["state"]["turn"] >= 1 for cow in cows))

    def test_the_hostile_and_animal_turn_budgets_are_separate_in_one_call(self):
        # fix round 1: HOSTILE_ACTS (32) and MAX_ACTS (24) are tracked independently, so a glut of
        # overdue hostiles wanting up to TURNS_EACH turns each never eats into the animals' budget
        # (or the other way round) within the same call.
        grid, state = land(), {**pet(), "vitals": dict(START_VITALS)}
        hostiles = [self.add(grid, "gloomling", (n, 1, 0)) for n in range(11)]  # 11 * TURNS_EACH(3) = 33 > 32
        animals = [self.add(grid, "cow", (0, 1, n)) for n in range(30)]  # 30 > MAX_ACTS(24)
        calls = {"hostile": 0, "animal": 0}

        def fake_act(creature, sc):
            kind = kind_of(creature["kind"])
            hostile = kind is not None and kind.hostile
            calls["hostile" if hostile else "animal"] += 1
            creature["state"]["turn"] = creature["state"].get("turn", 0) + 1
            creature["next_at"] = sc.at + 0.5  # still due, so a hostile may take another turn now
            return "fake"

        with patch("backend.survival.creatures.simulate.act", fake_act):
            take_turns(scene(grid, state, at=10.0), hostiles + animals)
        self.assertEqual(calls, {"hostile": HOSTILE_ACTS, "animal": MAX_ACTS})

    def test_a_crashing_creature_does_not_stop_the_others_from_taking_their_turn(self):
        # fix round 1: saves used to wait until the whole call finished, so one creature's crash
        # (a raising action) used to propagate out of take_turns and lose every earlier creature's
        # turn in the same call -- and leave an already-struck hostile's cooldown unsaved, free to
        # strike again next call.
        # fix round 2: the crash is now caught around that one creature (logged once, backed off
        # with UNKNOWN_WAIT), so it also does not cost every LATER queued creature its turn this
        # call -- one bad creature no longer freezes the rest.
        grid, state = land(), {**pet(), "vitals": dict(START_VITALS)}
        first = self.add(grid, "cow", (0, 1, 0))
        second = self.add(grid, "cow", (0, 1, 1))
        third = self.add(grid, "cow", (0, 1, 2))

        def fake_act(creature, sc):
            if creature["id"] == second["id"]:
                raise RuntimeError("boom")
            creature["state"]["turn"] = creature["state"].get("turn", 0) + 1
            creature["next_at"] = sc.at + 5.0
            return "fake"

        forget_logged()
        with patch("backend.survival.creatures.simulate.act", fake_act), \
                self.assertLogs("backend.survival.creatures.simulate", level=logging.ERROR) as logs:
            take_turns(scene(grid, state, at=10.0), [first, second, third])
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(grid.herd.get(first["id"])["next_at"], 15.0)  # acted, before the crash
        self.assertEqual(grid.herd.get(third["id"])["next_at"], 15.0)  # still acted, after the crash
        self.assertEqual(grid.herd.get(second["id"])["next_at"], 10.0 + UNKNOWN_WAIT)  # backed off, not stuck


class TickTests(unittest.TestCase):
    def hatched(self, root):
        registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(3), timestamp=BORN)
        return registry, life, SurvivalWorld(registry.world_path(life))

    def test_a_gloomlings_blow_that_takes_mimos_last_health_kills_it(self):
        with tempfile.TemporaryDirectory() as root:
            registry, life, world = self.hatched(root)
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2500.0  # deep in the first night
                state["vitals"]["health"] = 2.0
                write_state(db, state)
                x, y, z = (round(state["position"][axis]) for axis in "xyz")
                Herd(db).add("gloomling", (x + 1, y, z), 20.0, BORN, BORN, {"home": [x + 1, y, z], "turn": 0})
            state = tick_life(registry, BORN + 5, scale=1)
            self.assertEqual((state["status"], state["cause"], state["died_at"]), ("dead", "gloomling", BORN + 1))  # a second in: steps are short near it
            self.assertEqual(registry.get(life["id"])["cause"], "gloomling")
            self.assertEqual(world.events()[0]["text"], f"{life['name']} was caught by a gloomling on day 1.")
            with world.connect() as db:
                self.assertEqual([place["note"] for place in places(db, ("danger",))], ["gloomling"])

    def test_while_a_hostile_could_reach_mimo_the_tick_runs_in_one_second_steps(self):
        for near in (True, False):
            calls = []
            real = tick.simulate

            def track(*args, **kwargs):
                calls.append(args[2])
                return real(*args, **kwargs)

            with tempfile.TemporaryDirectory() as root:
                _, _, world = self.hatched(root)
                with world.transaction() as db:
                    state = read_state(db)
                    state["born_at"] = BORN - 2500.0 / 60  # the first night, at 60x
                    write_state(db, state)
                    x, y, z = (round(state["position"][axis]) for axis in "xyz")
                    if near:
                        Herd(db).add("gloomling", (x + 1, y, z), 20.0, BORN, BORN, {"home": [x + 1, y, z], "turn": 0})
                with patch("backend.survival.tick.simulate", track), \
                        patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                        patch("backend.survival.creatures.hostiles.hurt_pet", lambda *args: 0.0):
                    advance_world(world, BORN + 1.0, 60.0, action_scale=60.0)
            self.assertEqual(len(calls), 60 if near else 1, near)  # a game second a step, else one 60-s step

    def test_a_low_time_scale_with_a_high_action_scale_does_not_balloon_the_short_steps(self):
        # fix round 1: FIGHT_SLICE / action_scale * scale shrinks toward nothing at a low
        # MIMO_TIME_SCALE with a high MIMO_ACTION_SCALE; without FIGHT_SLICES_MAX a 60-game-second
        # transaction here became 3600 separate creature calls (MIMO_TIME_SCALE=1,
        # MIMO_ACTION_SCALE=60: each short step is only 1/60 of a game second).
        calls = []
        real = tick.simulate

        def track(*args, **kwargs):
            calls.append(args[2])
            return real(*args, **kwargs)

        with tempfile.TemporaryDirectory() as root:
            _, _, world = self.hatched(root)
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2500.0  # deep in the first night
                write_state(db, state)
                x, y, z = (round(state["position"][axis]) for axis in "xyz")
                Herd(db).add("gloomling", (x + 1, y, z), 20.0, BORN, BORN, {"home": [x + 1, y, z], "turn": 0})
            with patch("backend.survival.tick.simulate", track), \
                    patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                    patch("backend.survival.creatures.hostiles.hurt_pet", lambda *args: 0.0):
                advance_world(world, BORN + 60.0, 1.0, action_scale=60.0)
        self.assertGreaterEqual(len(calls), FIGHT_SLICES_MAX, calls)  # the short-step phase still ran
        self.assertLessEqual(len(calls), FIGHT_SLICES_MAX + 5, calls)  # then catch-up falls back to long steps
        self.assertLess(len(calls), 3600)

    def test_hostiles_come_out_at_night_stay_few_and_cost_little(self):
        # fix round 1: while a hostile is near, one 60-game-second slice is up to FIGHT_SLICE_MAX
        # separate `tick.simulate` calls; averaging cost per call (as this test used to) hides a
        # slice whose calls are each cheap but whose total is not. Sum a slice's calls instead.
        # Final fix wave: the 20 ms budget is per 60-game-second transaction (the catch-up cadence;
        # at the live 1x cadence the same creatures cost about 1.3 ms a real second), and it is
        # the best of up to 3 runs (backend.tests.budget), so a loaded machine does not fail it.
        counts = []

        def run() -> list[float]:
            slices = []
            counts.clear()

            def timed(*args, **kwargs):
                start = time.perf_counter()
                result = real(*args, **kwargs)
                slices[-1] += time.perf_counter() - start
                return result

            with tempfile.TemporaryDirectory() as root:
                _, _, world = self.hatched(root)
                with patch("backend.survival.tick.simulate", timed), \
                        patch("backend.survival.creatures.hostiles.hurt_pet", lambda *args: 0.0):
                    for minute in range(1, 61):
                        slices.append(0.0)
                        state = advance_world(world, BORN + 60 * minute, 1.0)
                        with world.connect() as db:
                            found = world_grid(db, world.seed).herd.near(state["position"]["x"],
                                                                         state["position"]["z"], 48)
                        counts.append(sum(1 for creature in found
                                          if KINDS[creature["kind"]].hostile and not dead(creature)))
            return slices

        real = tick.simulate
        self.assertLess(best_mean(run, 0.020), 0.020)
        self.assertLessEqual(max(counts), HOSTILE_CAP)
        night, day = counts[41:57], counts[:37]  # night falls 40 game minutes in
        self.assertGreater(sum(night) / len(night), sum(day) / len(day))

    def test_a_gloomling_beside_mimo_at_night_still_costs_little_a_slice(self):
        # fix round 1: the worst case for the per-slice budget -- a hostile right next to Mimo
        # keeps every slice in FIGHT_SLICE stepping (a call a game second), so the gating in
        # spawn_hostiles and saving once a call (not once a turn) must hold the per-slice mean
        # under budget here too.
        # fix round 2: the short steps are what multiply the herd cost (backend.survival.creatures
        # .spawning, L1) -- animals were acting, and herds spawning, on every one of the short
        # steps instead of once a slice, which a re-review measured at 33-38 ms mean, 77 ms peak.
        # Herds are on here (not held off) so this test covers exactly that: `fight_step` now keeps
        # `populate` and every animal's turn to the slice's one final call (backend.survival.tick,
        # backend.survival.creatures.simulate), so this must hold budget with herds about too.
        # Final fix wave: a slice is one 60-game-second transaction (the catch-up cadence), and the
        # budget is the best of up to 3 runs (backend.tests.budget): it flaked once under load.
        # Making wave 2 (the final fix wave's re-review, Minor 7): it still failed at a load of 20 to 30, on
        # every tree alike. What the fix round-2 regression did is counted instead: each slice makes its
        # one ordinary call (the rest are fight steps, which spawn no herds and move no animals), and no
        # herd spawns while the gloomling is beside Mimo. The wall-clock bound stays, generous, for a
        # regression of a wholly other size.
        calls = []
        spawned = []

        def run() -> list[float]:
            slices = []
            calls.clear()
            spawned.clear()

            def timed(*args, **kwargs):
                start = time.perf_counter()
                calls.append(kwargs.get("fight_step", False))
                result = real(*args, **kwargs)
                slices[-1] += time.perf_counter() - start
                return result

            def counted_populate(*args, **kwargs):
                spawned.append(1)
                return real_populate(*args, **kwargs)

            with tempfile.TemporaryDirectory() as root:
                _, _, world = self.hatched(root)
                with world.transaction() as db:
                    state = read_state(db)
                    state["born_at"] = BORN - 2500.0  # deep in the first night
                    write_state(db, state)
                    x, y, z = (round(state["position"][axis]) for axis in "xyz")
                    Herd(db).add("gloomling", (x + 1, y, z), 20.0, BORN, BORN, {"home": [x + 1, y, z], "turn": 0})
                with patch("backend.survival.tick.simulate", timed), \
                        patch("backend.survival.creatures.simulate.populate", counted_populate), \
                        patch("backend.survival.creatures.hostiles.hurt_pet", lambda *args: 0.0):
                    for minute in range(1, 11):
                        slices.append(0.0)
                        advance_world(world, BORN + 60 * minute, 1.0)
            return slices

        real = tick.simulate
        real_populate = populate
        self.assertLess(best_mean(run, 0.020), 0.500)
        self.assertEqual(calls.count(False), 10)  # one ordinary call a slice...
        self.assertGreater(calls.count(True), 10)  # ...and the fight steps, beside the gloomling
        self.assertEqual(spawned, [])  # no herd spawns while it is near

    def test_a_crashing_hostile_near_check_falls_back_to_a_long_step(self):
        # fix round 1: hostile_near (backend.survival.tick.creature_nearby) had no crash guard, so
        # a bad query would stop the whole tick instead of just widening the step like run_creatures.
        forget_logged()
        with tempfile.TemporaryDirectory() as root:
            _, _, world = self.hatched(root)
            with patch("backend.survival.tick.hostile_near", side_effect=RuntimeError("boom")), \
                    patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                    self.assertLogs("backend.survival.tick", level=logging.ERROR) as logs:
                state = advance_world(world, BORN + 60.0, 1.0)
        self.assertEqual(len(logs.output), 1)
        self.assertIsNone(state["died_at"])
        self.assertEqual(state["last_tick_at"], BORN + 60.0)


if __name__ == "__main__":
    unittest.main()

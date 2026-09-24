import math
import random
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.worldgen import terrain_height
from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import BRAIN, brain_plan
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.creatures.defense import FIGHT_KEEP, FLEE_REACH, QUIET, armed, clear_line, fight_target, threats
from backend.survival.creatures.harm import hurt_pet
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import simulate
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import add_structure, create_memory_tables, remember, set_home
from backend.survival.registry import LifeRegistry
from backend.survival.reflexes import by_name, reflex_hook
from backend.survival.situation import Situation
from backend.survival.tick import MAX_STEP_SECONDS, tick_life
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld, read_state, write_state

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
BORN = 1_000_000.0
FLEE, FIGHT = by_name("flee"), by_name("fight")
SWORD = {"stone_sword": 1}


def meadow(blocks=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "status": "idle", "last_thought": "", "last_tick_at": 0.0,
             "born_at": 0.0, "died_at": None, "brain": new_brain(0.0)}
    state["brain"]["pending"] = None
    state.update(changes)
    ensure_actions(state)
    return state


def situation(grid, state, at=100.0):
    return Situation(state, grid, NIGHT, at, grid.herd.db)


def hostile(grid, kind="gloomling", cell=(3, 1, 0), **state):
    return grid.herd.add(kind, cell, KINDS[kind].health, 0.0, 1e9, {"home": list(cell), "turn": 0, "pose": "idle",
                                                                     **state})


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: NIGHT, planner=brain_plan, events=[], db=grid.herd.db,
                         interrupt=reflex_hook)


class ThreatTests(unittest.TestCase):
    def test_threats_are_living_hostiles_that_could_come_after_mimo_nearest_first(self):
        grid = meadow()
        far, near = hostile(grid, cell=(10, 1, 0)), hostile(grid, "skitter", (0, 1, 5))
        hostile(grid, cell=(2, 1, 0), pose="dead")
        hostile(grid, cell=(20, 1, 0))
        hostile(grid, cell=(3, -6, 0))  # in the rock far below
        grid.herd.add("cow", (1, 1, 0), 10.0, 0.0, 1e9, {})
        self.assertEqual([creature["id"] for creature in threats(situation(grid, pet()))], [near["id"], far["id"]])

    def test_inside_its_own_shelter_mimo_has_nothing_to_fear(self):
        grid = meadow()
        hostile(grid)
        add_structure(grid.herd.db, "shelter", "Pip's Hut", (0, 1, 0), 0.0, {},
                      [((0, 1, 0), "room", "air"), ((0, 1, -1), "door", "door")])
        grid.claims.update({(0, 1, 0), (0, 1, -1)})
        self.assertEqual(threats(situation(grid, pet())), [])
        in_the_doorway = pet(position={"x": 0.0, "y": 1.0, "z": -1.0})
        self.assertEqual(len(threats(situation(grid, in_the_doorway))), 1)

    def test_a_weapon_is_a_sword_or_a_bow_with_arrows(self):
        self.assertFalse(armed(situation(meadow(), pet())))
        self.assertTrue(armed(situation(meadow(), pet(inventory={"wooden_sword": 1}))))
        self.assertFalse(armed(situation(meadow(), pet(inventory={"bow": 1}))))
        self.assertTrue(armed(situation(meadow(), pet(inventory={"bow": 1, "arrow": 1}))))

    def test_a_wall_blocks_the_line_of_sight(self):
        grid = meadow({(3, 1, 0): "cobblestone"})
        self.assertFalse(clear_line(grid, (0, 1, 0), (6, 1, 0)))
        self.assertTrue(clear_line(grid, (0, 1, 1), (6, 1, 1)))


class FleeTests(unittest.TestCase):
    def test_an_unarmed_or_badly_hurt_pet_flees_from_a_threat(self):
        grid = meadow()
        hostile(grid, cell=(5, 1, 0))
        self.assertTrue(FLEE.trigger(situation(grid, pet())))
        self.assertFalse(FLEE.trigger(situation(grid, pet(inventory=SWORD))))
        far = meadow()
        hostile(far, cell=(10, 1, 0))
        self.assertFalse(FLEE.trigger(situation(far, pet())))
        hurt = {**START_VITALS, "health": 30.0}
        self.assertTrue(FLEE.trigger(situation(far, pet(inventory=SWORD, vitals=hurt))))
        self.assertFalse(FLEE.trigger(situation(meadow(), pet(vitals=hurt))))  # nothing to run from

    def test_it_runs_home_unless_the_threat_is_nearer_home_and_else_straight_away(self):
        grid = meadow()
        hostile(grid, cell=(5, 1, 0))
        set_home(grid.herd.db, (-10, 1, 0), 0.0)
        self.assertEqual(FLEE.plan(situation(grid, pet()), context(grid)),
                         [{"kind": "walk", "target": [-10, 1, 0], "reach": 0.0}])
        cut_off = meadow()
        hostile(cut_off, cell=(-5, 1, 0))
        set_home(cut_off.herd.db, (-10, 1, 0), 0.0)
        self.assertEqual(FLEE.plan(situation(cut_off, pet()), context(cut_off)),
                         [{"kind": "walk", "target": [12, 1, 0], "reach": FLEE_REACH}])

    def test_a_home_it_only_found_is_no_refuge_it_runs_away_instead(self):
        # Final fix wave, critical: a found home (a sheltered spot, not a shelter Mimo built) keeps
        # nothing out. Standing on it, the old plan walked to Mimo's own cell, which ended at once,
        # and flee fired again every 2 s while Mimo was struck.
        grid = meadow()
        hostile(grid, cell=(1, 1, 0))
        remember(grid.herd.db, "home", (0, 1, 0), 0.0)  # found, not built
        self.assertEqual(FLEE.plan(situation(grid, pet()), context(grid)),
                         [{"kind": "walk", "target": [-12, 1, 0], "reach": FLEE_REACH}])
        elsewhere = meadow()
        hostile(elsewhere, cell=(5, 1, 0))
        remember(elsewhere.herd.db, "home", (-6, 1, 0), 0.0)
        self.assertEqual(FLEE.plan(situation(elsewhere, pet()), context(elsewhere)),
                         [{"kind": "walk", "target": [-12, 1, 0], "reach": FLEE_REACH}])

    def test_a_built_home_under_its_feet_is_no_run_either(self):
        grid = meadow()
        hostile(grid, cell=(1, 1, 0))
        set_home(grid.herd.db, (0, 1, 0), 0.0)  # built, but Mimo is on its cell outside any room
        self.assertEqual(FLEE.plan(situation(grid, pet()), context(grid))[0]["target"], [-12, 1, 0])

    def test_a_run_that_failed_lately_turns_another_way(self):
        # The run's far end takes its height from the generated ground, so it can be out of reach
        # (a tree, a pit, a wall Mimo built): after a run there failed, the next one turns aside.
        grid = meadow()
        hostile(grid, cell=(5, 1, 0))
        state = pet()
        state["recent_actions"] = [{"kind": "walk", "target": {"x": -12, "y": 1, "z": 0}, "purpose": "flee",
                                    "ended_at": 99.0, "result": "failed", "code": "no_path"}]
        target = FLEE.plan(situation(grid, state), context(grid))[0]["target"]
        self.assertGreater(math.hypot(target[0] + 12, target[2]), 4.0)
        self.assertGreater(math.hypot(target[0] - 5, target[2]), 12.0)  # still away from the threat

    def test_a_flight_goes_on_while_the_threat_is_still_close(self):
        grid = meadow()
        hostile(grid, cell=(7, 1, 0))
        state = pet()
        self.assertFalse(FLEE.trigger(situation(grid, state)))  # 7 blocks: too far to start running
        state["brain"]["reflex_ends"]["flee"] = 100.0 - 1.0  # it ran a moment ago
        self.assertTrue(FLEE.trigger(situation(grid, state)))
        far = meadow()
        hostile(far, cell=(9, 1, 0))
        self.assertFalse(FLEE.trigger(situation(far, state)))  # past FLEE_CLEAR: the flight is over
        state["brain"]["reflex_ends"]["flee"] = 100.0 - 60.0
        self.assertFalse(FLEE.trigger(situation(grid, state)))  # a flight long over does not count

    def test_a_flight_is_short_to_restart_and_ends_the_purpose(self):
        self.assertLessEqual(FLEE_REACH, 2.0)
        self.assertLessEqual(FLEE.cooldown, 0.5)
        self.assertTrue(FLEE.ends_purpose)
        self.assertTrue(FLEE.paced)

    def test_the_restart_is_paced_like_the_blows_it_runs_from(self):
        # At MIMO_ACTION_SCALE 60 a hostile strikes 60 times as often: a flee cooldown in plain
        # seconds would let dozens of blows land between two runs.
        grid = meadow()
        hostile(grid, cell=(4, 1, 0))
        state = pet()
        state["brain"]["reflex_ends"]["flee"] = 100.0 - 0.1
        self.assertIsNone(reflex_hook(state, context(grid), 100.0))
        fast = context(grid)
        fast.action_scale = 60.0
        self.assertEqual(reflex_hook(state, fast, 100.0), "flee")

    def test_after_a_flight_it_does_not_lie_down_again_while_a_threat_is_near(self):
        grid = meadow()
        hostile(grid, cell=(10, 1, 0))
        state = pet()
        state["brain"].update(reflex="flee", purpose="sleep", planned_at=90.0,
                              set_aside=[{"kind": "sleep", "purpose": "sleep"}])
        steps = brain_plan(state, context(grid), 100.0)
        self.assertEqual(steps, [{"kind": "wait", "seconds": 1.0}])
        self.assertIsNone(state["brain"]["purpose"])
        clear = pet()  # nothing about: a purpose-less night is slept as before
        self.assertEqual(brain_plan(clear, context(meadow()), 100.0)[0]["kind"], "sleep")

    def test_from_its_own_doorway_it_runs_deeper_in_not_out_past_the_threat(self):
        # The smallest M5 shelter's door sits exactly AT_HOME (2 blocks) from the home cell: a
        # doorway must still send Mimo home, not just when it is strictly farther than that.
        grid = meadow()
        hostile(grid, cell=(0, 1, -6))
        add_structure(grid.herd.db, "shelter", "Pip's Hut", (0, 1, 0), 0.0, {},
                      [((0, 1, 0), "passage", "air"), ((0, 1, -1), "passage", "air"),
                       ((0, 1, -2), "door", "door")])
        grid.claims.update({(0, 1, 0), (0, 1, -1), (0, 1, -2)})
        set_home(grid.herd.db, (0, 1, 0), 0.0)
        doorway = pet(position={"x": 0.0, "y": 1.0, "z": -2.0})
        self.assertEqual(FLEE.plan(situation(grid, doorway), context(grid)),
                         [{"kind": "walk", "target": [0, 1, 0], "reach": 0.0}])


class FightTests(unittest.TestCase):
    def test_armed_and_healthy_it_fights_a_hostile_within_four_blocks_then_flees_when_hurt(self):
        grid = meadow()
        gloom = hostile(grid, cell=(3, 1, 0))
        self.assertEqual(fight_target(situation(grid, pet(inventory=SWORD)))["id"], gloom["id"])
        self.assertIsNone(fight_target(situation(grid, pet())))
        hurt = pet(inventory=SWORD, vitals={**START_VITALS, "health": 40.0})
        self.assertIsNone(fight_target(situation(grid, hurt)))
        hurt["brain"]["reflex_ends"]["fight"] = 100.0 - FIGHT_KEEP  # a fight is on: it goes on down to 35
        self.assertEqual(fight_target(situation(grid, hurt))["id"], gloom["id"])
        hurt["vitals"]["health"] = 30.0
        self.assertIsNone(fight_target(situation(grid, hurt)))
        self.assertTrue(FLEE.trigger(situation(grid, hurt)))

    def test_armed_between_35_and_50_it_fights_back_what_has_it_at_bay(self):
        # Final fix wave: at 35-49 health neither reflex fired (fight wants 50, flee under 35), so a
        # skitter struck an armed pet down to the flee line unanswered.
        grid = meadow()
        biter = hostile(grid, "skitter", cell=(1, 1, 1), chasing=True)
        hurt = {**START_VITALS, "health": 40.0}
        self.assertEqual(fight_target(situation(grid, pet(inventory=SWORD, vitals=hurt)))["id"], biter["id"])
        self.assertIsNone(fight_target(situation(grid, pet(vitals=hurt))))  # unarmed: never
        idle = meadow()
        hostile(idle, "skitter", cell=(1, 1, 1))
        self.assertIsNone(fight_target(situation(idle, pet(inventory=SWORD, vitals=hurt))))  # not after Mimo
        coming = meadow()
        hostile(coming, "skitter", cell=(3, 1, 1), chasing=True)
        self.assertIsNone(fight_target(situation(coming, pet(inventory=SWORD, vitals=hurt))))  # not yet in reach
        weak = {**START_VITALS, "health": 34.0}
        self.assertIsNone(fight_target(situation(grid, pet(inventory=SWORD, vitals=weak))))  # flee's turn

    def test_it_strikes_in_reach_steps_up_to_strike_and_shoots_from_afar(self):
        grid = meadow()
        close = hostile(grid, cell=(2, 1, 0))
        self.assertEqual(FIGHT.plan(situation(grid, pet(inventory=SWORD)), context(grid)),
                         [{"kind": "attack", "creature": close["id"], "target": [2, 1, 0]}])
        step_up = meadow()
        farther = hostile(step_up, cell=(4, 1, 0))
        self.assertEqual(FIGHT.plan(situation(step_up, pet(inventory=SWORD)), context(step_up)),
                         [{"kind": "walk", "target": [4, 1, 0], "reach": 2.0},
                          {"kind": "attack", "creature": farther["id"], "target": [4, 1, 0]}])
        archer = pet(inventory={**SWORD, "bow": 1, "arrow": 3})
        bow = meadow()
        coming = hostile(bow, cell=(9, 1, 0), chasing=True)
        self.assertEqual(FIGHT.plan(situation(bow, archer), context(bow)),
                         [{"kind": "shoot", "creature": coming["id"], "target": [9, 1, 0]}])
        walled = meadow({(5, 1, 0): "cobblestone", (5, 2, 0): "cobblestone"})
        hostile(walled, cell=(9, 1, 0), chasing=True)
        self.assertIsNone(fight_target(situation(walled, archer)))
        idle = meadow()
        hostile(idle, cell=(9, 1, 0))
        self.assertIsNone(fight_target(situation(idle, archer)))  # not after Mimo: left alone

    def test_a_step_up_is_checked_without_spending_a_search_of_the_tick(self):
        # Final fix wave: the step-up's look ahead spent one of the tick's searches and the walk
        # itself another, so a fight step's walks ran out of searches twice as fast.
        grid = meadow()
        farther = hostile(grid, cell=(4, 1, 0))
        ctx = context(grid)
        ctx.searches_left = 0
        self.assertEqual(FIGHT.plan(situation(grid, pet(inventory=SWORD)), ctx),
                         [{"kind": "walk", "target": [4, 1, 0], "reach": 2.0},
                          {"kind": "attack", "creature": farther["id"], "target": [4, 1, 0]}])
        self.assertEqual(ctx.searches_left, 0)

    def test_a_melee_target_behind_a_wall_within_reach_gets_no_fight_takeover(self):
        walled = meadow({(2, 1, 0): "cobblestone", (2, 2, 0): "cobblestone", (2, 3, 0): "cobblestone"})
        hostile(walled, cell=(4, 1, 0))  # within FIGHT_REACH in a straight line, but through a wall
        self.assertIsNone(fight_target(situation(walled, pet(inventory=SWORD))))
        self.assertEqual(FIGHT.plan(situation(walled, pet(inventory=SWORD)), context(walled)), [])

    def test_a_fight_logs_its_event_once_an_encounter(self):
        grid = meadow()
        hostile(grid, cell=(2, 1, 0))
        state = pet(inventory=SWORD)
        ctx = context(grid)
        for at in (100.0, 101.0, 101.0 + QUIET + 1.0):
            self.assertEqual(reflex_hook(state, ctx, at), "fight")
            state["brain"].update(reflex=None)
            state["brain"]["reflex_ends"]["fight"] = at
        self.assertEqual([event[2] for event in ctx.events], ["Pip stood its ground against a creature."] * 2)


class InTheTickTests(unittest.TestCase):
    def night(self, grid, state, until):
        ctx = context(grid)
        at = 0.0
        with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):
            while at < until:
                at += 0.25
                advance_actions(state, ctx, at)
                simulate(state, ctx, at)
                ctx.searches_left = 2
        return ctx

    def test_an_armed_pet_fights_off_a_gloomling_that_comes_for_it(self):
        grid = meadow()
        gloom = hostile(grid, cell=(6, 1, 0))
        gloom["next_at"] = 0.0
        grid.herd.save(gloom)
        state = pet(inventory={"iron_sword": 1})
        ctx = self.night(grid, state, 20.0)
        self.assertIn(("fight", "Pip fought off a gloomling."), [event[1:] for event in ctx.events])
        body = grid.herd.get(gloom["id"])
        self.assertTrue(body is None or dead(body))  # cleared away once its puff is over
        self.assertGreater(state["vitals"]["health"], 50.0)

    def test_an_unarmed_pet_runs_from_a_gloomling_and_gets_away(self):
        grid = meadow()
        gloom = hostile(grid, cell=(4, 1, 0))
        gloom["next_at"] = 0.0
        grid.herd.save(gloom)
        state = pet()
        ctx = self.night(grid, state, 10.0)
        self.assertIn("Pip ran from a creature.", [event[2] for event in ctx.events])
        chaser = grid.herd.get(gloom["id"])
        self.assertGreater(math.hypot(state["position"]["x"] - chaser["x"], state["position"]["z"] - chaser["z"]), 6.0)
        self.assertGreater(state["vitals"]["health"], 90.0)

    def test_an_unarmed_pet_on_a_found_home_gets_away_from_a_gloomling_beside_it(self):
        grid = meadow()
        remember(grid.herd.db, "home", (0, 1, 0), 0.0)
        gloom = hostile(grid, cell=(1, 1, 0))
        gloom["next_at"] = 0.0
        grid.herd.save(gloom)
        state = pet()
        ctx = self.night(grid, state, 20.0)
        self.assertIn("Pip ran from a creature.", [event[2] for event in ctx.events])
        chaser = grid.herd.get(gloom["id"])
        self.assertGreater(math.hypot(state["position"]["x"] - chaser["x"], state["position"]["z"] - chaser["z"]), 6.0)
        self.assertGreaterEqual(state["vitals"]["health"], 94.0)  # a blow at most before it got going

    def test_an_unarmed_pet_at_30_health_outruns_a_skitter_to_the_home_it_built(self):
        grid = meadow()
        room = [(-10, 1, 0), (-10, 1, 1), (-11, 1, 0), (-11, 1, 1)]
        add_structure(grid.herd.db, "shelter", "Pip's Hut", room[0], 0.0, {}, [(cell, "room", "air") for cell in room])
        grid.claims.update(room)
        set_home(grid.herd.db, room[0], 0.0)
        skitter = hostile(grid, "skitter", cell=(3, 1, 0), chasing=True)
        skitter["next_at"] = 0.0
        grid.herd.save(skitter)
        state = pet(vitals={**START_VITALS, "health": 30.0})
        ctx = self.night(grid, state, 30.0)
        self.assertIn("Pip ran from a creature.", [event[2] for event in ctx.events])
        self.assertEqual(tuple(round(state["position"][axis]) for axis in "xyz"), room[0])
        self.assertGreaterEqual(state["vitals"]["health"], 28.0)  # one blow at most

    def test_an_armed_pet_at_45_health_fights_off_a_skitter_that_has_it_at_bay(self):
        grid = meadow()
        skitter = hostile(grid, "skitter", cell=(5, 1, 0))
        skitter["next_at"] = 0.0
        grid.herd.save(skitter)
        state = pet(inventory=SWORD, vitals={**START_VITALS, "health": 45.0})
        ctx = self.night(grid, state, 60.0)
        self.assertIn(("fight", "Pip fought off a skitter."), [event[1:] for event in ctx.events])
        self.assertGreater(state["vitals"]["health"], 35.0)

    def test_a_collapse_flee_keeps_preempting_still_rests_once_not_every_time(self):
        # Fix round 1, defect 2: flee (30) keeps cutting off collapse (70) as the gloomling comes
        # and goes; each cut-off must start collapse's own cooldown and quiet, or it fires again
        # (and logs again) the instant flee lets go, unbounded.
        grid = meadow()
        gloom = hostile(grid, cell=(4, 1, 0))
        gloom["next_at"] = 0.0
        grid.herd.save(gloom)
        state = pet(vitals={**START_VITALS, "energy": 5.0})
        ctx = self.night(grid, state, 120.0)
        collapses = [event for event in ctx.events if event[1] == "reflex" and "collapsed" in event[2]]
        self.assertLessEqual(len(collapses), 5)  # collapse's own 30 s cooldown bounds it; the bug logs 16+


class HatchedWorldTests(unittest.TestCase):
    """The whole brain in the real tick, at 1x, a second a tick, on the first night of a new world."""

    def night_with(self, inventory, kind="gloomling", health=None, seconds=60, seed=3):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(seed), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2500.0  # deep in the first night
                state["inventory"].update(inventory)
                if health is not None:
                    state["vitals"]["health"] = health
                write_state(db, state)
                x, y, z = (round(state["position"][axis]) for axis in "xyz")
                Herd(db).add(kind, (x + 5, y, z), KINDS[kind].health, BORN, BORN, {"home": [x + 5, y, z], "turn": 0})
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(seed), scale=1.0)
            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []):
                for second in range(1, seconds + 1):
                    state = tick_life(registry, BORN + second, scale=1.0, mind=BRAIN, action_scale=1.0)
                    if state["died_at"] is not None:
                        break
                    chooser.poll(registry, BORN + second)
            return state, [event["kind"] for event in world.events(500)]

    def night_with_a_gloomling(self, inventory):
        return self.night_with(inventory)

    def test_an_armed_pet_wakes_and_fights_the_gloomling_off(self):
        state, kinds = self.night_with_a_gloomling({"stone_sword": 1})
        self.assertIsNone(state["died_at"])
        self.assertIn("fight", kinds)
        self.assertGreater(state["vitals"]["health"], 80.0)

    def test_an_unarmed_pet_keeps_away_from_it_all_night(self):
        state, kinds = self.night_with_a_gloomling({})
        self.assertIsNone(state["died_at"])
        self.assertNotIn("hurt", kinds)
        self.assertEqual(kinds.count("reflex"), 1)  # one "ran from a creature" for the whole encounter

    def among_two_hostiles(self, calls: int, scale: float) -> tuple[dict, int, float]:
        """An unarmed pet deep in the first night with a gloomling and a skitter 3 blocks either
        side, run `calls` ticks of one 60-game-second transaction each: a catch-up minute at a
        time (scale 1) or MIMO_TIME_SCALE = MIMO_ACTION_SCALE = 60 (scale 60, a real second a
        tick). Returns the state, the blows it took and the slowest tick in seconds."""
        blows = []
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(3), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2450.0 / scale  # early in the first night
                for sword in ("wooden_sword", "stone_sword", "iron_sword", "bow", "arrow"):
                    state["inventory"].pop(sword, None)
                write_state(db, state)
                x, _, z = (round(state["position"][axis]) for axis in "xyz")
                for kind, cx in (("gloomling", x + 3), ("skitter", x - 3)):
                    cell = (cx, terrain_height(cx, z, state["world_seed"]) + 1, z)
                    Herd(db).add(kind, cell, KINDS[kind].health, BORN, BORN, {"home": list(cell), "turn": 0})
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(3), scale=scale)
            real_hurt, slowest = hurt_pet, 0.0

            def counted(scene, damage, source):
                blows.append(scene.at)
                return real_hurt(scene, damage, source)

            with patch("backend.survival.creatures.simulate.spawn_hostiles", lambda scene: []), \
                    patch("backend.survival.creatures.hostiles.hurt_pet", counted):
                for call in range(1, calls + 1):
                    at = BORN + call * MAX_STEP_SECONDS / scale
                    started = time.perf_counter()
                    state = tick_life(registry, at, scale=scale, mind=BRAIN, action_scale=scale)
                    slowest = max(slowest, time.perf_counter() - started)
                    if state["died_at"] is not None:
                        break
                    chooser.poll(registry, at)
        return state, len(blows), slowest

    def test_caught_up_a_minute_at_a_time_an_unarmed_pet_still_runs_from_two_hostiles(self):
        # Final fix wave: a 60-game-second transaction's 60 fight steps shared its 2 searches, so
        # the flee walk waited in the queue (29 searches refused) while Mimo was struck to death at
        # 36 game seconds. Each fight step now has a small search of its own.
        state, blows, slowest = self.among_two_hostiles(calls=5, scale=1.0)
        self.assertIsNone(state["died_at"], state["cause"])
        self.assertLessEqual(blows, 6)
        # One transaction, 60 fight steps and their searches: far inside the owner's 10 s write
        # window (about 0.3 s here; generous, for a loaded machine).
        self.assertLess(slowest, 5.0)

    def test_at_sixty_times_an_unarmed_pet_still_runs_from_two_hostiles(self):
        state, blows, slowest = self.among_two_hostiles(calls=5, scale=60.0)
        self.assertIsNone(state["died_at"], state["cause"])
        self.assertLessEqual(blows, 6)
        self.assertLess(slowest, 5.0)

    def test_an_armed_pet_at_45_health_lives_ten_minutes_with_a_skitter_about(self):
        # Final fix wave: at 45 health neither reflex fired, so the skitter struck it down to the
        # flee line and the short runs that followed never shook it off (4 of 6 armored pets died).
        state, kinds = self.night_with({"stone_sword": 1}, "skitter", health=45.0, seconds=600, seed=7)
        self.assertIsNone(state["died_at"], state["cause"])
        self.assertIn("fight", kinds)


if __name__ == "__main__":
    unittest.main()

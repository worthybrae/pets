import math
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import BRAIN, brain_plan
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.creatures.defense import FIGHT_KEEP, QUIET, armed, clear_line, fight_target, threats
from backend.survival.creatures.kinds import KINDS
from backend.survival.creatures.simulate import simulate
from backend.survival.creatures.table import Herd, create_creature_tables, dead
from backend.survival.grid import Grid
from backend.survival.hatch import hatch
from backend.survival.memory import add_structure, create_memory_tables, set_home
from backend.survival.registry import LifeRegistry
from backend.survival.reflexes import by_name, reflex_hook
from backend.survival.situation import Situation
from backend.survival.tick import tick_life
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
                         [{"kind": "walk", "target": [12, 1, 0], "reach": 4.0}])


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


class HatchedWorldTests(unittest.TestCase):
    """The whole brain in the real tick, at 1x, a second a tick, on the first night of a new world."""

    def night_with_a_gloomling(self, inventory):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(3), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["born_at"] = BORN - 2500.0  # deep in the first night
                state["inventory"].update(inventory)
                write_state(db, state)
                x, y, z = (round(state["position"][axis]) for axis in "xyz")
                Herd(db).add("gloomling", (x + 5, y, z), 20.0, BORN, BORN, {"home": [x + 5, y, z], "turn": 0})
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(3), scale=1.0)
            for second in range(1, 61):
                state = tick_life(registry, BORN + second, scale=1.0, mind=BRAIN, action_scale=1.0)
                chooser.poll(registry, BORN + second)
            return state, [event["kind"] for event in world.events(500)]

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


if __name__ == "__main__":
    unittest.main()

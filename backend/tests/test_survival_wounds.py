"""W1: wounds that fester and cold nights, for a wild pet only."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and step registered)
from backend.survival.ailments import (
    FESTER_DRAIN, ailing, dress, open_wound, sickness, tend, tend_night, wound_of,
)
from backend.survival.care import give_care
from backend.survival.creatures.harm import hurt_pet
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.registry import LifeRegistry
from backend.survival.steps import finish_step, start_step
from backend.survival.tick import tick_life
from backend.survival.wild import thing, wild_state
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_cooking import situation
from backend.tests.test_survival_hostiles import meadow, pet, scene

BORN = 1_000_000.0


def wild_pet(**changes):
    return pet(difficulty="wild", **changes)


def after(state, seconds, step=30.0):
    context = SimpleNamespace(events=[], db=None)
    for _ in range(int(seconds / step)):
        tend(state, context, step, "working", 0.0)
    return context.events


class WoundTests(unittest.TestCase):
    def test_a_blow_of_two_or_more_opens_a_wound_three_times_in_ten(self):
        grid = meadow()
        state = wild_pet()
        with patch("backend.survival.wounds.roll", return_value=0.3):
            where = scene(grid, state)
            hurt_pet(where, 4.0, "skitter")
        self.assertIsNotNone(wound_of(state))
        self.assertIn((10.0, "wound", "A skitter cut Pip."), where.events)
        gentle, small, lucky = pet(), wild_pet(), wild_pet()
        with patch("backend.survival.wounds.roll", return_value=0.3):
            hurt_pet(scene(grid, gentle), 4.0, "skitter")
            hurt_pet(scene(grid, small), 1.5, "skitter")
        with patch("backend.survival.wounds.roll", return_value=0.4):
            hurt_pet(scene(grid, lucky), 4.0, "skitter")
        self.assertEqual([wound_of(found) for found in (gentle, small, lucky)], [None, None, None])
        self.assertEqual(wild_state(state)["night_blows"], 1)

    def test_undressed_it_festers_after_ten_game_minutes_and_heals_in_a_game_day(self):
        state = wild_pet()
        open_wound(state, 0.0)
        self.assertEqual(ailing(state).heals, False)
        self.assertEqual(after(state, 570), [])
        self.assertEqual(after(state, 30), [(0.0, "festering", "Pip's wound is festering.")])
        self.assertEqual((ailing(state).drain, ailing(state).mood), (FESTER_DRAIN, 10.0))
        after(state, 3000)
        self.assertIsNone(wound_of(state))
        self.assertIsNone(ailing(state))
        self.assertAlmostEqual(state["wild"]["lost"], 3000 * FESTER_DRAIN)  # what festering took, a hazard's

    def test_a_dressed_wound_stops_festering_at_once_and_closes_five_minutes_later(self):
        state = wild_pet()
        open_wound(state, 0.0)
        after(state, 900)
        self.assertTrue(dress(state))
        self.assertEqual(ailing(state).drain, 0.0)
        after(state, 270)
        self.assertIsNotNone(wound_of(state))
        after(state, 30)
        self.assertIsNone(wound_of(state))

    def test_the_dress_step_uses_a_bandage_or_a_sunleaf(self):
        for item, words in (("bandage", "Pip wrapped its wound in a bandage."), ("sunleaf", "Pip pressed sunleaf on its wound.")):
            state = wild_pet(inventory={item: 1})
            open_wound(state, 0.0)
            step = start_step({"kind": "dress", "item": item}, state, meadow(), 0.0)
            self.assertEqual(finish_step(step, state, meadow(), 2.0), ("dressed", words))
            self.assertEqual((state["inventory"], wound_of(state)["dressed_age"]), ({}, 0.0))

    def test_dress_wound_makes_a_bandage_from_wool_once_mimo_knows_how(self):
        s = situation({"wool": 1})
        s.state["difficulty"] = "wild"
        open_wound(s.state, 0.0)
        self.assertFalse(is_valid(PURPOSES["dress_wound"], s))
        know(s.db, thing("bandage"), "lesson", 0.0)
        s.__dict__.pop("lessons", None)
        self.assertTrue(is_valid(PURPOSES["dress_wound"], s))
        self.assertEqual(PURPOSES["dress_wound"].plan(s, None),
                         [{"kind": "craft", "recipe": "bandage"}, {"kind": "dress", "item": "bandage"}])

    def test_the_owners_care_bandage_dresses_a_wound(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                open_wound(state, BORN)
                write_state(db, state)
            give_care(world, "bandage", BORN)
            self.assertEqual(world.state()["ailments"]["wound"]["dressed_age"], 0.0)


class ColdNightTests(unittest.TestCase):
    def night(self, state, minutes_cold, froze=False, floor=False):
        context = SimpleNamespace(events=[], db=None)
        state["vitals"]["warmth"] = 30.0 if minutes_cold else 80.0
        for _ in range(minutes_cold or 10):
            tend_night(state, context, 60.0, ("night", "night"), "sleeping" if floor else "idle", floor, 1.0)
        if froze:
            state["vitals"]["warmth"] = 10.0
            tend_night(state, context, 1.0, ("night", "night"), "idle", False, 1.0)
        tend_night(state, context, 1.0, ("pre_dawn", "dawn"), "idle", False, 2.0)
        return context.events

    def test_fifteen_cold_minutes_or_any_freezing_give_a_chill_at_dawn(self):
        state = wild_pet()
        self.assertEqual(self.night(state, 15), [(2.0, "chill", "Pip caught a chill in the night.")])
        self.assertEqual(sickness(state)["kind"], "chill")
        frozen = wild_pet()
        self.night(frozen, 0, froze=True)
        self.assertEqual(sickness(frozen)["kind"], "chill")

    def test_five_cold_minutes_give_a_chill_six_times_in_ten_and_a_warm_night_none(self):
        for chance, caught in ((0.5, True), (0.7, False)):
            state = wild_pet()
            with patch("backend.survival.ailments.roll", return_value=chance):
                self.night(state, 5)
            self.assertEqual(sickness(state) is not None, caught)
        warm = wild_pet()
        self.assertEqual(self.night(warm, 0), [])
        self.assertEqual(wild_state(warm)["night_cold"], 0.0)

    def test_a_night_asleep_on_a_sheltered_floor_is_counted_and_a_gentle_pet_never_is(self):
        state = wild_pet()
        self.night(state, 0, floor=True)
        self.night(state, 0, floor=True)
        self.assertEqual(wild_state(state)["floor_nights"], 2)
        gentle = pet()
        self.night(gentle, 20)
        self.assertNotIn("wild", gentle)

    def test_a_wild_pet_out_in_the_open_catches_a_chill_on_its_first_night(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            for second in range(1, 62):
                tick_life(registry, BORN + second, scale=60.0)
            kinds = [event["kind"] for event in world.events(500)]
        self.assertIn("chill", kinds)


if __name__ == "__main__":
    unittest.main()

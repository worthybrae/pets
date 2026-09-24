import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, know, mark_explored, patch_of, remember
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, Purpose, land_refuge, meal, offered, register
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
DUSK = {**DAY, "phase": "dusk", "seconds_into_day": 2300.0}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
SIMPLE = ("rest", "sleep", "explore", "go_home", "eat")


def flat(cells=None):
    """Stone at y <= 0 and air above, with `cells` overriding single cells."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state=None, clock=DAY, grid=None, places=()):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell in places:
        remember(db, kind, cell, 0.0)
    return Situation(state or pet(), grid or flat(), clock, 0.0, db)


def context(grid=None):
    return ActionContext(grid=grid or flat(), clock_at=lambda at: DAY, planner=lambda *args: [], events=[])


def names(s):
    """The simple purposes on offer, in name order (fix round 1: offered() no longer follows
    registration order; other test modules may have registered more)."""
    return [purpose.name for purpose in offered(s) if purpose.name in SIMPLE]


class RegistryTests(unittest.TestCase):
    def test_registering_adds_a_purpose_and_a_crashing_check_is_not_offered(self):
        def boom(s):
            raise RuntimeError("boom")

        extra = Purpose("test_extra", "test", "A test purpose.", lambda s: True, lambda s: "", lambda s: 1.0,
                        lambda s, context: [], ("Hm.",))
        broken = Purpose("test_broken", "break", "A broken purpose.", boom, lambda s: "", lambda s: 1.0,
                         lambda s, context: [], ("Oops.",))
        forget_logged()
        try:
            register(extra)
            register(broken)
            with self.assertLogs("backend.survival.purposes", level="ERROR"):
                offered_names = [purpose.name for purpose in offered(situation())]
            self.assertIn("test_extra", offered_names)
            self.assertNotIn("test_broken", offered_names)
        finally:
            PURPOSES.pop("test_extra", None)
            PURPOSES.pop("test_broken", None)

    def test_m3_registers_the_simple_purposes(self):
        for name in SIMPLE:
            self.assertIn(name, PURPOSES)


class SimplePurposeTests(unittest.TestCase):
    def test_by_day_rest_and_explore_are_offered(self):
        self.assertEqual(names(situation()), ["explore", "rest"])

    def test_at_night_mimo_goes_home_then_sleeps(self):
        away = situation(clock=NIGHT, places=[("home", (20, 1, 0))])
        self.assertEqual(names(away), ["go_home", "rest", "sleep"])
        self.assertEqual(PURPOSES["go_home"].plan(away, context()), [{"kind": "walk", "target": [20, 1, 0], "reach": 0.0}])
        self.assertGreater(PURPOSES["go_home"].score(away), PURPOSES["sleep"].score(away))
        near = situation(clock=NIGHT, places=[("home", (5, 1, 0))])
        self.assertEqual(PURPOSES["sleep"].plan(near, context()),
                         [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}, {"kind": "sleep"}])
        near.state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                                      "cell": {"x": 5, "y": 1, "z": 0}, "purpose": "sleep", "at": 0.0, "seq": 1}
        self.assertEqual(PURPOSES["sleep"].plan(near, context()), [{"kind": "sleep"}])
        home = situation(clock=NIGHT, places=[("home", (1, 1, 0))])
        self.assertEqual(names(home), ["rest", "sleep"])
        self.assertEqual(PURPOSES["sleep"].plan(home, context()), [{"kind": "sleep"}])

    def test_at_dusk_mimo_waits_at_home_for_nightfall(self):
        home = situation(clock=DUSK, places=[("home", (1, 1, 0))])
        self.assertEqual(names(home), ["rest", "sleep"])
        self.assertEqual(PURPOSES["sleep"].plan(home, context()), [{"kind": "wait", "seconds": 60.0}])

    def test_sleep_is_on_offer_at_home_from_the_head_home_window_until_night(self):
        window = {**DAY, "seconds_into_day": 2040.0}
        self.assertIn("sleep", names(situation(clock=window, places=[("home", (1, 1, 0))])))
        self.assertEqual(PURPOSES["sleep"].plan(situation(clock=window, places=[("home", (1, 1, 0))]), context()),
                         [{"kind": "wait", "seconds": 60.0}])
        self.assertNotIn("sleep", names(situation(clock={**DAY, "seconds_into_day": 2030.0},
                                                  places=[("home", (1, 1, 0))])))
        self.assertNotIn("sleep", names(situation(clock=window, places=[("home", (30, 1, 0))])))

    def test_sleep_and_rest_never_start_afloat_they_swim_for_a_known_home_first(self):
        # Followup fix: a flee run never picks a target on water (creatures.defense.run_away), but
        # Mimo can still wander into it on its own; asleep there it was an easy catch.
        afloat = flat(cells={(0, 0, 0): "water"})  # Mimo's cell (0,1,0) floats on water below
        s = situation(clock=NIGHT, grid=afloat, places=[("home", (5, 1, 0))])
        self.assertEqual(PURPOSES["sleep"].plan(s, context()), [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}])
        self.assertEqual(PURPOSES["rest"].plan(s, context()), [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}])
        # Even after a failed attempt to reach a bed, land comes first, not sleeping where it floats.
        s.state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                                   "cell": {"x": 5, "y": 1, "z": 0}, "purpose": "sleep", "at": 0.0, "seq": 1}
        self.assertEqual(PURPOSES["sleep"].plan(s, context()), [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}])
        # Once Mimo is on dry ground, sleep and rest behave as before.
        dry = situation(clock=NIGHT, places=[("home", (5, 1, 0))])
        self.assertEqual(PURPOSES["sleep"].plan(dry, context()),
                         [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0}, {"kind": "sleep"}])

    def test_land_refuge_prefers_a_known_home_then_the_nearest_shore(self):
        dry = situation()
        self.assertIsNone(land_refuge(dry))  # on dry ground already: nothing to do
        afloat = flat(cells={(0, 0, 0): "water"})
        homeless = situation(grid=afloat)
        with patch("backend.survival.purposes.shores_near", lambda grid, seed, here, radius: [((9, 1, 0), (10, 1, 0))]):
            self.assertEqual(land_refuge(homeless), {"kind": "walk", "target": [9, 1, 0], "reach": 0.0})
        with patch("backend.survival.purposes.shores_near", lambda grid, seed, here, radius: []):
            self.assertIsNone(land_refuge(homeless))  # nowhere dry found nearby either
        homed = situation(grid=afloat, places=[("home", (5, 1, 0))])
        self.assertEqual(land_refuge(homed), {"kind": "walk", "target": [5, 1, 0], "reach": 0.0})  # home first

    def test_rest_lasts_until_a_trigger_for_at_most_ten_game_minutes(self):
        s = situation()
        s.brain.update(pending=None, chosen_at=0.0, batches=12)
        self.assertEqual(PURPOSES["rest"].plan(s, context()), [{"kind": "wait", "seconds": 10.0}])
        fast = situation(clock={**DAY, "time_scale": 60.0})
        fast.brain.update(pending=None, chosen_at=0.0)
        self.assertEqual(PURPOSES["rest"].plan(fast, context()), [{"kind": "wait", "seconds": 1.0}])
        s.brain["pending"] = {"id": 3, "reasons": ["idle"], "since": 0.0, "urgent": False}
        self.assertEqual(PURPOSES["rest"].plan(s, context()), [{"kind": "wait", "seconds": 10.0}])
        s.brain["pending"]["reasons"] = ["idle", "hour"]
        self.assertEqual(PURPOSES["rest"].plan(s, context()), [])
        s.brain["pending"] = None
        self.assertEqual(PURPOSES["rest"].plan(Situation(s.state, s.grid, DAY, 600.0, s.db), context()), [])
        fast_later = Situation(fast.state, fast.grid, fast.clock, 10.0, fast.db)  # 600 game seconds at 60x
        self.assertEqual(PURPOSES["rest"].plan(fast_later, context()), [])

    def test_explore_walks_whole_to_new_ground_each_time(self):
        state = pet()
        s = situation(state)
        with patch("backend.survival.exploring.terrain_height", lambda x, z, seed: 0):
            first = PURPOSES["explore"].plan(s, context())[0]
            x, _, z = first["target"]
            mark_explored(s.db, [patch_of(x + dx, z + dz) for dx in (-8, 0, 8) for dz in (-8, 0, 8)], 0.0)
            second = PURPOSES["explore"].plan(Situation(state, s.grid, DAY, 0.0, s.db), context())[0]
        self.assertEqual((first["kind"], first["reach"], first["whole"]), ("walk", 3.0, True))
        self.assertGreater(math.dist(first["target"], second["target"]), 8)
        self.assertEqual(state["brain"]["explored"], 2)

    def test_explore_chains_three_walks_per_choice(self):
        s = situation()
        with patch("backend.survival.exploring.terrain_height", lambda x, z, seed: 0):
            for batches in range(3):
                s.brain["batches"] = batches
                self.assertEqual(len(PURPOSES["explore"].plan(s, context())), 1)
            s.brain["batches"] = 3
            self.assertEqual(PURPOSES["explore"].plan(s, context()), [])

    def test_explore_scores_higher_with_no_trees_near(self):
        s = situation()
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: []):
            lonely = PURPOSES["explore"].score(s)
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            wooded = PURPOSES["explore"].score(s)
        self.assertEqual(lonely - wooded, 25.0)

    def test_explore_never_scores_below_zero_late_in_the_day(self):
        late = {**DAY, "seconds_into_day": 2100.0}
        s = situation(pet(traits={"curiosity": 0}), clock=late)
        with patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            self.assertEqual(PURPOSES["explore"].score(s), 0.0)

    def test_eat_is_offered_with_food_and_eats_the_best_first(self):
        hungry = pet(inventory={"berries": 3, "bread": 1}, vitals={**START_VITALS, "hunger": 50.0})
        self.assertIn("eat", names(situation(hungry)))
        self.assertNotIn("eat", names(situation(pet(inventory={"berries": 3}))))
        self.assertEqual(PURPOSES["eat"].plan(situation(hungry), context()),
                         [{"kind": "eat", "item": "bread"}, {"kind": "eat", "item": "berries"},
                          {"kind": "eat", "item": "berries"}])
        self.assertEqual(meal({"berries": 1}, 10.0), [{"kind": "eat", "item": "berries"}])

    def test_food_known_to_be_poisonous_is_never_eaten(self):
        hungry = pet(inventory={"red_mushroom": 2, "berries": 1}, vitals={**START_VITALS, "hunger": 20.0})
        s = situation(hungry)
        # Untried food that can make Mimo sick is tasted once per meal, never eaten by the handful.
        self.assertEqual(PURPOSES["eat"].plan(s, context()),
                         [{"kind": "eat", "item": "berries"}, {"kind": "eat", "item": "red_mushroom"}])
        self.assertEqual(meal({"red_mushroom": 3}, 10.0), [{"kind": "eat", "item": "red_mushroom"}])
        know(s.db, "red_mushroom", "poisonous", 0.0)
        s = Situation(hungry, s.grid, DAY, 0.0, s.db)
        self.assertEqual(PURPOSES["eat"].plan(s, context()), [{"kind": "eat", "item": "berries"}])
        only_red = situation(pet(inventory={"red_mushroom": 1}, vitals={**START_VITALS, "hunger": 20.0}))
        know(only_red.db, "red_mushroom", "poisonous", 0.0)
        self.assertNotIn("eat", names(only_red))
        self.assertEqual(meal({"red_mushroom": 3}, 10.0, avoid=("red_mushroom",)), [])



class SituationTests(unittest.TestCase):
    def test_memory_is_read_once_and_traits_default_to_fifty(self):
        s = situation(places=[("home", (3, 1, 0))])
        self.assertEqual(s.places[0]["kind"], "home")
        s.db.execute("DELETE FROM memory_places")
        self.assertEqual(len(s.places), 1)
        self.assertEqual((s.here, s.trait("curiosity"), s.night), ((0, 1, 0), 50.0, False))
        self.assertEqual(s.seconds_to(2400.0), 1400.0)


if __name__ == "__main__":
    unittest.main()

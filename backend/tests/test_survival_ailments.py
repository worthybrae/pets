"""W1: a wild pet's sicknesses: a tummy ache and a chill, what they drain, and sunleaf."""

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and reflex registered)
from backend.survival import ailments
from backend.survival.ailments import AILMENTS, HERB_HUNGER, ailing, ailments_view, fall_sick, sickness, tend
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.reflexes import by_name
from backend.survival.registry import LifeRegistry
from backend.survival.replies import in_my_voice
from backend.survival.snapshot import survival_view
from backend.survival.steps import finish_step, start_step
from backend.survival.tick import death_words, tick_life
from backend.survival.vitals import START_VITALS, Surroundings, step_vitals
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_cooking import meadow, situation

BORN = 1_000_000.0
QUIET = Surroundings(biome="meadow", sheltered=True)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "difficulty": "wild"}
    state.update(changes)
    return state


def run(state, seconds, activity="working", step=10.0):
    """Vitals and the sickness's time for `seconds` game seconds, in steps like the tick's."""
    events = []
    for _ in range(int(seconds / step)):
        ill = ailing(state)
        state["vitals"], cause = step_vitals(state["vitals"], step, night=False, activity=activity, surroundings=QUIET,
                                             ailing=ill)
        tend(state, SimpleNamespace(events=events, db=None), step, activity, 0.0, ill)
        if cause:
            return cause
    return None


class SicknessTests(unittest.TestCase):
    def test_a_tummy_ache_lasts_twelve_game_minutes_and_takes_eighteen_health(self):
        state = pet()
        self.assertTrue(fall_sick(state, "tummy", 0.0))
        self.assertEqual(state["last_thought"], "My tummy hurts.")
        run(state, 12 * 60)
        self.assertIsNone(sickness(state))
        self.assertAlmostEqual(state["vitals"]["health"], 100 - 12 * 60 / 40, places=3)
        self.assertAlmostEqual(state["wild"]["lost"], 12 * 60 / 40, places=3)  # lost to a hazard

    def test_a_chill_takes_thirty_seven_and_a_half_and_passes_twice_as_fast_resting_warm(self):
        state = pet()
        fall_sick(state, "chill", 0.0)
        run(state, 25 * 60)
        self.assertAlmostEqual(state["vitals"]["health"], 100 - 25 * 60 / 40, places=3)
        warm = pet()
        fall_sick(warm, "chill", 0.0)
        run(warm, 12.5 * 60 + 10, activity="sleeping")
        self.assertIsNone(sickness(warm))

    def test_no_health_comes_back_while_sick_and_hunger_or_energy_drains_faster(self):
        well, ill = pet(), pet()
        for state in (well, ill):
            state["vitals"]["health"] = 80.0
        fall_sick(ill, "tummy", 0.0)
        run(well, 60, activity="idle")
        run(ill, 60, activity="idle")
        self.assertGreater(well["vitals"]["health"], 80.0)
        self.assertLess(ill["vitals"]["health"], 80.0)
        self.assertAlmostEqual(100 - ill["vitals"]["hunger"], 1.5 * (100 - well["vitals"]["hunger"]), places=6)
        chilled, rested = pet(), pet()
        fall_sick(chilled, "chill", 0.0)
        run(chilled, 60, activity="idle")
        run(rested, 60, activity="idle")
        self.assertAlmostEqual(100 - chilled["vitals"]["energy"], 1.5 * (100 - rested["vitals"]["energy"]), places=6)

    def test_one_sickness_at_a_time_the_longer_stays(self):
        state = pet()
        fall_sick(state, "tummy", 0.0)
        self.assertFalse(fall_sick(state, "chill", 1.0))
        self.assertEqual((sickness(state)["kind"], sickness(state)["left"]), ("chill", AILMENTS["chill"].lasts))
        fall_sick(state, "tummy", 2.0)
        self.assertEqual(sickness(state)["kind"], "chill")

    def test_sickness_can_kill_and_the_memorial_says_so(self):
        state = pet()
        state["vitals"]["health"] = 3.0
        fall_sick(state, "tummy", 0.0)
        self.assertEqual(run(state, 12 * 60, activity="idle"), "sickness")
        self.assertEqual(death_words("sickness"), "fell sick and never got better")

    def test_a_gentle_pet_is_never_ailing(self):
        self.assertIsNone(ailing({"vitals": dict(START_VITALS)}))
        self.assertEqual(ailments_view({}), {"sick": None, "wound": None})


class SunleafTests(unittest.TestCase):
    def test_eating_sunleaf_ends_any_sickness(self):
        state = pet(inventory={"sunleaf": 1})
        fall_sick(state, "chill", 0.0)
        step = start_step({"kind": "eat", "item": "sunleaf"}, state, meadow(), 0.0)
        self.assertEqual(finish_step(step, state, meadow(), 1.6), ("cured", "Pip ate sunleaf and felt better."))
        self.assertIsNone(sickness(state))
        self.assertEqual(state["inventory"], {})

    def test_take_herb_eats_a_carried_sunleaf_once_mimo_knows_it(self):
        s = situation({"sunleaf": 1})
        s.state["difficulty"] = "wild"
        fall_sick(s.state, "tummy", 0.0)
        reflex = by_name("take_herb")
        self.assertEqual(reflex.priority, 45)
        self.assertFalse(reflex.trigger(s))
        know(s.db, thing("sunleaf"), "lesson", 0.0)
        s.__dict__.pop("lessons", None)
        self.assertTrue(reflex.trigger(s))
        self.assertEqual(reflex.plan(s, None), [{"kind": "eat", "item": "sunleaf"}])

    def test_find_herb_and_nibble_walk_to_a_sunleaf_they_see(self):
        grid = meadow({(10, 1, 0): "sunleaf"})
        s = situation({}, grid)
        s.state["difficulty"] = "wild"
        fall_sick(s.state, "tummy", 0.0)
        s.state["ailments"]["sick"]["nibble"] = True
        self.assertTrue(is_valid(PURPOSES["nibble"], s))
        self.assertFalse(is_valid(PURPOSES["find_herb"], s))
        self.assertEqual(PURPOSES["nibble"].plan(s, None)[-2:],
                         [{"kind": "pick", "target": [10, 1, 0]},
                          {"kind": "eat", "item": "sunleaf", "seen_as": "a little yellow herb"}])
        know(s.db, thing("sunleaf"), "lesson", 0.0)
        taught = situation({}, grid)
        taught.state.update(difficulty="wild", ailments=s.state["ailments"])
        taught.db = s.db
        self.assertTrue(is_valid(PURPOSES["find_herb"], taught))
        self.assertFalse(is_valid(PURPOSES["nibble"], taught))
        self.assertEqual(PURPOSES["find_herb"].score(taught), 75.0)

    def test_an_untaught_nibble_names_a_little_yellow_herb_and_fills_two_hunger(self):
        # The final fix wave (7): Mimo cannot name an herb it does not know, in the log nor in its memory's words;
        # carried item 3: a sunleaf fills HERB_HUNGER.
        grid = meadow({(1, 1, 0): "sunleaf"})
        s = situation({}, grid, 50.0)
        s.state["difficulty"] = "wild"
        fall_sick(s.state, "tummy", 0.0)
        s.state["ailments"]["sick"]["nibble"] = True
        eat = PURPOSES["nibble"].plan(s, None)[-1]
        s.state["inventory"]["sunleaf"] = 1  # picked
        kind, text = finish_step(start_step(eat, s.state, grid, 0.0), s.state, grid, 1.6)
        self.assertEqual((kind, text), ("cured", "Pip ate a little yellow herb and felt better."))
        self.assertEqual(in_my_voice(text, "Pip"), "I ate a little yellow herb and felt better.")
        self.assertEqual(s.state["vitals"]["hunger"], 50.0 + HERB_HUNGER)

    def test_w2_fix_t_a_pet_with_full_arms_eats_the_sunleaf_it_picked_at_once(self):
        """W2 fix T: on the W2 gate an untaught pet with 16 full stacks and a chill walked to a sunleaf three times,
        left it behind each time ("no sunleaf to eat") and died of the chill the nibble was rolled to cure."""
        from backend.survival.carrying import CARRY_STACKS, after_step
        grid = meadow({(1, 1, 0): "sunleaf", (2, 1, 0): "sunleaf"})
        arms = {f"item_{n}": 1 for n in range(CARRY_STACKS)}  # nothing that gives way
        s = situation(dict(arms), grid, 50.0)
        s.state["difficulty"] = "wild"
        fall_sick(s.state, "chill", 0.0)
        s.state["ailments"]["sick"]["nibble"] = True
        pick, eat = PURPOSES["nibble"].plan(s, None)[-2:]
        s.state["queue"] = [eat]
        before = dict(s.state["inventory"])
        finish_step(start_step(pick, s.state, grid, 0.0), s.state, grid, 1.0)
        events = []
        after_step(s.state, before, 1.0, events)
        self.assertEqual(events, [(1.0, "cured", "Pip ate a little yellow herb and felt better.")])
        self.assertIsNone(sickness(s.state))
        self.assertEqual((s.state["inventory"], s.state["queue"]), (arms, []))
        self.assertEqual(s.state["vitals"]["hunger"], 50.0 + HERB_HUNGER)
        before = dict(s.state["inventory"])  # a sunleaf picked to carry (gather_herbs) with no room still stays behind
        finish_step(start_step({"kind": "pick", "target": [2, 1, 0]}, s.state, grid, 2.0), s.state, grid, 3.0)
        after_step(s.state, before, 3.0, [])
        self.assertEqual(s.state["inventory"], arms)

    def test_a_pet_that_knows_sunleaf_carries_two(self):
        grid = meadow({(3, 1, 0): "sunleaf", (5, 1, 0): "sunleaf", (7, 1, 0): "sunleaf"})
        s = situation({}, grid)
        s.state["difficulty"] = "wild"
        self.assertFalse(is_valid(PURPOSES["gather_herbs"], s))
        know(s.db, thing("sunleaf"), "lesson", 0.0)
        s.__dict__.pop("lessons", None)
        self.assertTrue(is_valid(PURPOSES["gather_herbs"], s))
        picks = [step["target"] for step in PURPOSES["gather_herbs"].plan(s, None) if step["kind"] == "pick"]
        self.assertEqual(picks, [[3, 1, 0], [5, 1, 0]])


class GraceTests(unittest.TestCase):
    """W2 fix T, a newborn's grace (built and measured by W1's Fix B): for its first 4 game days a wild pet's sickness
    and festering drains never take its health below GRACE_FLOOR; poison and blows still land. On W2's code a W1R
    newborn died on day 4.15 of two wounds festering one after the other."""

    def sick_and_festering(self, health):
        from backend.survival.ailments import open_wound
        state = pet()
        state["vitals"]["health"] = health
        fall_sick(state, "tummy", 0.0)
        open_wound(state, 0.0)
        state["ailments"]["wound"]["festering"] = True
        return state

    def aged(self, state, seconds, age, step=10.0):
        """Vitals and ailments for `seconds` game seconds from `age` game seconds into the pet's life, as the tick."""
        for index in range(int(seconds / step)):
            ill = ailments.ailing_now(state, step, age + index * step)
            state["vitals"], cause = step_vitals(state["vitals"], step, night=False, activity="idle",
                                                 surroundings=QUIET, ailing=ill)
            tend(state, SimpleNamespace(events=[], db=None), step, "idle", 0.0, ill)
            if cause:
                return cause
        return None

    def test_a_newborns_sickness_and_festering_stop_at_its_floor(self):
        from backend.survival.ailments import GRACE, GRACE_FLOOR
        from backend.survival.clock import DAY_SECONDS
        self.assertEqual(GRACE, 4 * DAY_SECONDS)  # four game days: no death from a sickness before day 5
        newborn = self.sick_and_festering(40.0)
        self.assertIsNone(self.aged(newborn, 12 * 60, GRACE - 13 * 60))
        self.assertAlmostEqual(newborn["vitals"]["health"], GRACE_FLOOR, places=6)
        self.assertAlmostEqual(newborn["wild"]["lost"], 40.0 - GRACE_FLOOR, places=6)  # only what the drain took
        older = self.sick_and_festering(40.0)
        self.aged(older, 12 * 60, GRACE)  # four game days old: no grace
        self.assertLess(older["vitals"]["health"], GRACE_FLOOR - 10)
        self.assertEqual(ailments.ailing_now(newborn).drain, ailing(newborn).drain)  # no age given: no grace

    def test_the_tick_gives_a_newborn_its_grace(self):
        from backend.survival.ailments import GRACE_FLOOR
        from backend.survival.clock import DAY_SECONDS

        def health_after_twelve_minutes(born_days_ago):
            with tempfile.TemporaryDirectory() as root:
                registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
                life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
                world = SurvivalWorld(registry.world_path(life))
                with world.transaction() as db:
                    state = read_state(db)
                    state["born_at"] = BORN - born_days_ago * DAY_SECONDS
                    state["vitals"]["health"] = 30.0
                    fall_sick(state, "tummy", BORN)
                    write_state(db, state)
                return tick_life(registry, BORN + 12 * 60, scale=1.0)["vitals"]["health"]

        self.assertAlmostEqual(health_after_twelve_minutes(3), GRACE_FLOOR, places=6)
        self.assertLess(health_after_twelve_minutes(4), GRACE_FLOOR)


class StreamTests(unittest.TestCase):
    def test_a_malformed_ailment_counts_as_nothing_in_the_tick_and_is_logged_once(self):
        # The final fix wave (10): the tick reads `ailing` guarded, so a broken save never stops the world.
        forget_logged()
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["ailments"] = {"sick": None, "wound": {"since": BORN}}  # no age, no festering
                write_state(db, state)
            with self.assertLogs("backend.survival.ailments", "ERROR") as logged:
                state = tick_life(registry, BORN + 120, scale=1.0)
        self.assertEqual(state["last_tick_at"], BORN + 120)
        self.assertEqual(len([line for line in logged.output if "ailing crashed" in line]), 1)

    def test_the_tick_reads_what_ails_mimo_once_a_vitals_step(self):
        # Carried item 3: `ailing` was read twice a vitals step, by the tick and again by `tend`.
        counted = {"ailing": 0, "tend": 0}

        def counting(name, real):
            def wrapper(*args):
                counted[name] += 1
                return real(*args)
            return wrapper

        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                fall_sick(state, "tummy", BORN)
                write_state(db, state)
            with patch("backend.survival.ailments.ailing", counting("ailing", ailments.ailing)), \
                    patch("backend.survival.ailments.tend", counting("tend", ailments.tend)):
                tick_life(registry, BORN + 120, scale=1.0)
        self.assertGreater(counted["tend"], 0)
        self.assertEqual(counted["ailing"], counted["tend"])

    def test_api_mimo_shows_the_sickness_and_the_tick_runs_it(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN, difficulty="wild")
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                fall_sick(state, "tummy", BORN)
                write_state(db, state)
            tick_life(registry, BORN + 60, scale=1.0)
            view = survival_view(world, BORN + 60, 1.0)
        self.assertEqual(view["ailments"]["sick"], {"kind": "tummy", "label": "Tummy ache", "words": "My tummy hurts.",
                                                    "minutes": 11})
        self.assertLess(view["vitals"]["health"], 100.0)


if __name__ == "__main__":
    unittest.main()

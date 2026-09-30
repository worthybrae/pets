"""W2: a wild pet learns the weather's and the seasons' lessons alone (knocks) and asks about them (wonders); the
storm and fog lessons send it home, and fog holds its trips back."""

import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every hook, wonder and reflex registered)
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.knocks import KNOCKS, knows_lesson
from backend.survival.lessons import claims
from backend.survival.memory import BUILT, create_memory_tables, know, remember
from backend.survival.reflexes import by_name
from backend.survival.situation import Situation
from backend.survival.sky_wild import at_dawn, blown, doused, meet_sky, spoils, struck
from backend.survival.trips import held_back
from backend.survival.vitals import START_VITALS
from backend.survival.wild import thing, wild_state
from backend.survival.wonders import WONDERS
from backend.tests.test_survival_cooking import meadow

BORN = 1_000_000.0
SCALE = 60.0
W2_KNOCKS = {"winter": (0.30, 0.15), "cloak": (0.30, 0.15), "hearth": (0.25, 0.15), "smoking": (0.25, 0.15),
             "rain": (0.50, 0.25), "storm": (0.50, 0.25), "fog": (0.35, 0.15)}


def day_at(day: int, seconds: float = 1000.0) -> float:
    return BORN + ((day - 1) * DAY_SECONDS + seconds) / SCALE


def world(season="spring", weather="clear", difficulty="wild", **changes):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    state = {"name": "Pip", "world_seed": "1", "born_at": BORN, "position": {"x": 0.0, "y": 1.0, "z": 0.0},
             "inventory": {}, "vitals": dict(START_VITALS), "difficulty": difficulty, "traits": {"curiosity": 50},
             "sky": {"offset": 0, "season": season, "weather": weather}}
    state.update(changes)
    context = SimpleNamespace(db=db, events=[], grid=meadow(), clock_at=lambda at: clock_at(BORN, at, SCALE))
    return state, context


def knows(context, name):
    return context.db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='lesson'",
                              (thing(name),)).fetchone() is not None


def always():
    return patch("backend.survival.knocks.roll", return_value=0.0)


class KnockTests(unittest.TestCase):
    def test_the_table_of_w2s_knocks(self):
        self.assertEqual({name: (KNOCKS[name].first, KNOCKS[name].step) for name in W2_KNOCKS}, W2_KNOCKS)

    def test_a_hungry_winter_day_knocks_winter_and_smoking_and_a_winter_lived_through_teaches_winter(self):
        state, context = world("winter", vitals={**START_VITALS, "hunger": 20.0})
        know(context.db, thing("fire"), "lesson", 0.0)
        with always():
            meet_sky(state, context, day_at(31))
        self.assertTrue(knows(context, "winter") and knows(context, "smoking"))
        lived, where = world("winter")
        meet_sky(lived, where, day_at(35))
        lived["sky"]["season"] = "spring"
        meet_sky(lived, where, day_at(41, 0.0))
        self.assertTrue(knows(where, "winter"))
        self.assertIn("figured", [kind for _, kind, _ in where.events])

    def test_freezing_two_game_minutes_with_the_wool_at_hand_knocks_the_cloak(self):
        state, context = world("winter", inventory={"wool": 5}, vitals={**START_VITALS, "warmth": 10.0})
        with always():
            for second in range(0, 121, 60):
                meet_sky(state, context, day_at(32, 3000.0 + second))
        self.assertTrue(knows(context, "cloak"))

    def test_the_rain_putting_its_fire_out_knocks_rain_and_is_a_wonder(self):
        state, context = world()
        with always():
            doused(state, context, (1, 1, 0), day_at(2))
        self.assertTrue(knows(context, "rain"))
        self.assertIn("fire_out", wild_state(state)["wonders"])

    def test_a_strike_near_knocks_storm_and_being_struck_teaches_it(self):
        state, context = world(weather="storm")
        with patch("backend.survival.knocks.roll", return_value=0.99):
            struck(state, context, (10, 5, 0), False, day_at(2))
        self.assertFalse(knows(context, "storm"))
        self.assertEqual(wild_state(state)["knocks"]["storm"], 1)
        struck(state, context, (40, 5, 0), False, day_at(2))  # too far to knock
        self.assertEqual(wild_state(state)["knocks"]["storm"], 1)
        struck(state, context, (0, 1, 0), True, day_at(2))
        self.assertTrue(knows(context, "storm"))

    def test_a_blow_in_fog_by_day_knocks_fog_and_a_cold_night_at_home_the_hearth(self):
        state, context = world(weather="fog")
        scene = SimpleNamespace(night=False, state=state, herd=SimpleNamespace(db=context.db), events=context.events,
                                at=day_at(2))
        with always():
            blown(scene, 3.0, "gloomling")
        self.assertTrue(knows(context, "fog"))
        cold, home = world("winter")
        remember(home.db, "home", (0, 1, 0), 0.0, BUILT)
        know(home.db, thing("fire"), "lesson", 0.0)
        with always():
            at_dawn(cold, home, {"chill": True, "froze": False, "cold": 900.0, "blows": 0, "floor": False}, day_at(33))
            spoils(cold, home, "raw_beef", 1, "arms", day_at(33))
        self.assertTrue(knows(home, "hearth") and knows(home, "smoking"))

    def test_standing_near_a_fire_in_the_trees_teaches_fire_for_sure(self):
        state, context = world(sky={"offset": 0, "season": "summer", "weather": "clear",
                                    "fires": [{"x": 4, "y": 5, "z": 0, "fire": 1, "caught": 0.0, "until": 9e9}]})
        meet_sky(state, context, day_at(12))
        self.assertTrue(knows(context, "fire"))

    def test_by_a_fire_a_pet_that_knows_fire_writes_nothing_and_reads_its_lesson_once_a_transaction(self):
        """Carried N1 of W2's fourth task: by a fire each step is a short one, and `sure` wrote the fire lesson's row
        again at every one of them (an INSERT a step)."""
        state, context = world(sky={"offset": 0, "season": "summer", "weather": "clear",
                                    "fires": [{"x": 4, "y": 5, "z": 0, "fire": 1, "caught": 0.0, "until": 9e9}]})
        context.memo = {}
        meet_sky(state, context, day_at(12))
        self.assertTrue(knows(context, "fire"))
        with patch("backend.survival.sky_wild.sure") as taught, \
                patch("backend.survival.sky_wild.knows_lesson", wraps=knows_lesson) as looked:
            for second in range(60):
                meet_sky(state, context, day_at(12, 1000.0 + second))
            context.memo = {}  # the next transaction
            meet_sky(state, context, day_at(12, 1100.0))
        self.assertEqual((taught.call_count, looked.call_count), (0, 1))


class WonderTests(unittest.TestCase):
    def test_the_six_wonders_and_the_fogs_yes_and_no(self):
        for wonder_id in ("colder", "fire_out", "storm", "fog", "freezing", "winter_food"):
            self.assertIn(wonder_id, WONDERS)
            self.assertTrue(any(chip.false for chip in WONDERS[wonder_id].chips), wonder_id)
        fog = WONDERS["fog"]
        self.assertEqual((claims(fog.yes).doubtful, claims(fog.no).taught), (True, (thing("fog"),)))

    def test_what_a_wild_pet_meets_and_a_gentle_one_never(self):
        state, context = world("autumn", weather="storm")
        state["sky"]["told"] = {"colder": 23}
        meet_sky(state, context, day_at(23, 2300.0))
        state["sky"]["weather"] = "fog"
        meet_sky(state, context, day_at(23, 2400.0))
        state["sky"].update(season="winter", weather="snow")
        state["vitals"].update(warmth=10.0, hunger=40.0)
        meet_sky(state, context, day_at(31))
        self.assertEqual(set(wild_state(state)["wonders"]), {"colder", "storm", "fog", "freezing", "winter_food"})
        gentle, where = world("winter", weather="storm", difficulty="gentle", vitals={**START_VITALS, "warmth": 5.0})
        meet_sky(gentle, where, day_at(31))
        self.assertEqual((gentle.get("wild") or {}).get("wonders"), None)


class CoverTests(unittest.TestCase):
    def situation(self, weather, difficulty="gentle", at=None, home=(0, 1, 0), position=(30.0, 1.0, 0.0)):
        state, context = world(weather=weather, difficulty=difficulty,
                               position=dict(zip("xyz", position)), brain=None)
        if home is not None:
            remember(context.db, "home", home, 0.0, BUILT)
        at = day_at(2) if at is None else at
        return Situation(state, meadow(), clock_at(BORN, at, SCALE), at, context.db)

    def test_a_storm_sends_a_pet_that_knows_it_home_once_a_spell(self):
        cover = by_name("take_cover")
        with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "storm"):
            s = self.situation("storm")
            self.assertTrue(cover.trigger(s))
            self.assertEqual(cover.plan(s, None), [{"kind": "walk", "target": [0, 1, 0], "reach": 0.0}])
            self.assertFalse(cover.trigger(s))  # once a spell
            self.assertFalse(cover.trigger(self.situation("storm", position=(10.0, 1.0, 0.0))))  # near home: safe
            self.assertFalse(cover.trigger(self.situation("storm", difficulty="wild")))  # it does not know yet
            self.assertFalse(cover.trigger(self.situation("clear")))

    def test_a_long_spell_sends_it_home_once_and_the_next_spell_again(self):
        """Carried from W2's ninth task: the spell's start was looked for 12 segments back at most, so in a spell over
        2 game hours it moved on each segment and take_cover sent Mimo home again every 10 game minutes."""
        cover = by_name("take_cover")
        storm_until = 40  # segments of storm from the life's first, then clear, then a storm again from 45
        weather = lambda seed, offset, segment: "storm" if segment < storm_until or segment >= 45 else "clear"  # noqa
        with patch("backend.survival.sky.weather_at", weather):
            s = self.situation("storm", at=BORN + 20 * 600 / SCALE)
            self.assertTrue(cover.trigger(s))
            cover.plan(s, None)
            brain_state = s.brain
            for segment in (21, 33, 34, 39):  # 13 and more segments into the spell: still the same one
                later = self.situation("storm", at=BORN + segment * 600 / SCALE)
                later.state["brain"] = brain_state
                self.assertFalse(cover.trigger(later), segment)
            again = self.situation("storm", at=BORN + 46 * 600 / SCALE)
            again.state["brain"] = brain_state
            self.assertTrue(cover.trigger(again))  # a new spell

    def test_fog_sends_it_home_and_holds_its_trips_back(self):
        cover = by_name("take_cover")
        with patch("backend.survival.sky.weather_at", lambda seed, offset, segment: "fog"):
            self.assertTrue(cover.trigger(self.situation("fog")))
            self.assertFalse(cover.trigger(self.situation("fog", position=(20.0, 1.0, 0.0))))
        self.assertTrue(held_back(self.situation("fog")))
        self.assertFalse(held_back(self.situation("fog", difficulty="wild")))
        self.assertFalse(held_back(self.situation("clear")))


if __name__ == "__main__":
    unittest.main()

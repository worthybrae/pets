"""W1: a wild pet learns its survival lessons alone, by knocks."""

import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every observer and hook registered)
from backend.survival import knocks
from backend.survival.knocks import KNOCKS, OWNER_ONLY, after_step, at_dawn, blown, knock, knows_lesson, spoils, sure
from backend.survival.memory import create_memory_tables, know
from backend.survival.vitals import START_VITALS
from backend.survival.wild import survival_view, thing, wild_state


def world(**changes):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "difficulty": "wild", "traits": {"curiosity": 50}}
    state.update(changes)
    return state, SimpleNamespace(db=db, events=[])


def knows(context, name):
    return context.db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='lesson'",
                              (thing(name),)).fetchone() is not None


class KnockTests(unittest.TestCase):
    def test_the_chance_grows_with_every_knock_and_curiosity(self):
        state, context = world()
        with patch("backend.survival.knocks.roll", return_value=0.31):
            self.assertFalse(knock(state, context.db, context.events, 1.0, "light"))  # 0.10
            self.assertFalse(knock(state, context.db, context.events, 2.0, "light"))  # 0.20
            self.assertFalse(knock(state, context.db, context.events, 3.0, "light"))  # 0.30
            self.assertTrue(knock(state, context.db, context.events, 4.0, "light"))  # 0.40
        self.assertEqual(wild_state(state)["knocks"]["light"], 4)
        curious, where = world(traits={"curiosity": 100})
        with patch("backend.survival.knocks.roll", return_value=0.11):
            self.assertTrue(knock(curious, where.db, where.events, 1.0, "light"))  # 0.10 x 1.2 = 0.12
        dull, there = world(traits={"curiosity": 0})
        with patch("backend.survival.knocks.roll", return_value=0.09):
            self.assertFalse(knock(dull, there.db, there.events, 1.0, "light"))  # 0.10 x 0.8 = 0.08

    def test_a_lesson_worked_out_is_a_figured_event_journalled_as_worked_out(self):
        state, context = world()
        self.assertTrue(sure(state, context.db, context.events, 5.0, "cooking"))
        self.assertEqual(context.events, [(5.0, "figured", "Pip worked out that cooking makes meat safe.")])
        self.assertTrue(state["brain"]["journal"]["words"][thing("cooking")].startswith("I worked it out myself: "))
        self.assertEqual({entry["name"]: entry["source"] for entry in survival_view(context.db)}["cooking"], "figured")
        self.assertFalse(sure(state, context.db, context.events, 6.0, "cooking"))  # once

    def test_the_table_of_knocks(self):
        self.assertEqual({name: (rule.first, rule.step) for name, rule in KNOCKS.items()},
                         {"nightberries": (0.25, 0.15), "fire": (0.15, 0.15),
                          "cooking": (0.25, 0.15), "keeping": (0.20, 0.15), "light": (0.10, 0.10),
                          "shelter": (0.25, 0.20), "bed": (0.10, 0.10)})

    def test_sunleaf_and_bandages_are_never_learned_alone(self):
        state, context = world(inventory={"wool": 1})
        self.assertEqual(OWNER_ONLY, ("sunleaf", "bandage"))
        with patch("backend.survival.knocks.roll", return_value=0.0):
            for name in OWNER_ONLY:
                self.assertFalse(sure(state, context.db, context.events, 1.0, name))
                self.assertFalse(knock(state, context.db, context.events, 1.0, name))
            after_step(state, {"kind": "eat", "item": "sunleaf", "cured": True}, context, 2.0)  # a nibble cured it
        self.assertFalse(knows(context, "sunleaf") or knows(context, "bandage"))
        self.assertEqual(context.events, [])

    def test_a_gentle_pet_never_knocks(self):
        state, context = world(difficulty="gentle")
        with patch("backend.survival.knocks.roll", return_value=0.0):
            self.assertFalse(knock(state, context.db, context.events, 1.0, "fire"))
        self.assertFalse(sure(state, context.db, context.events, 1.0, "berries"))


class WhereKnocksAreHeardTests(unittest.TestCase):
    def test_eating_teaches_the_food_lessons(self):
        state, context = world()
        after_step(state, {"kind": "eat", "item": "berries"}, context, 1.0)
        self.assertTrue(knows(context, "berries"))
        after_step(state, {"kind": "eat", "item": "red_mushroom", "sick": True}, context, 2.0)
        self.assertTrue(knows(context, "red_mushroom"))
        wild_state(state)["shun"]["red_berries"] = 3.0
        with patch("backend.survival.knocks.roll", return_value=0.0):
            after_step(state, {"kind": "eat", "item": "nightberries", "sick": True}, context, 4.0)
        self.assertTrue(knows(context, "nightberries"))
        self.assertNotIn("red_berries", wild_state(state)["shun"])  # it can tell them apart now

    def test_a_raw_meal_teaches_cooking_only_once_mimo_knows_fire(self):
        state, context = world()
        with patch("backend.survival.knocks.roll", return_value=0.0):
            after_step(state, {"kind": "eat", "item": "raw_beef", "raw": True, "sick": True}, context, 1.0)
            self.assertFalse(knows(context, "cooking"))
            know(context.db, thing("fire"), "lesson", 1.0)
            after_step(state, {"kind": "eat", "item": "raw_beef", "raw": True, "sick": True}, context, 2.0)
        self.assertTrue(knows(context, "cooking"))

    def test_smelting_teaches_fire_for_sure(self):
        state, context = world()
        after_step(state, {"kind": "smelt", "item": "iron_ore"}, context, 1.0)
        self.assertTrue(knows(context, "fire"))

    def test_nights_blows_and_spoiled_food_knock(self):
        state, context = world()
        with patch("backend.survival.knocks.roll", return_value=0.0):
            at_dawn(state, context, {"chill": True, "blows": 0, "floor": True, "cold": 900.0, "froze": False}, 1.0)
            spoils(state, context, "raw_beef", 1, "arms", 3.0)
            scene = SimpleNamespace(night=True, state=state, herd=SimpleNamespace(db=context.db), events=context.events,
                                    at=4.0)
            blown(scene, 3.0, "gloomling")
        for name in ("fire", "shelter", "bed", "keeping", "light"):
            self.assertTrue(knows(context, name), name)

    def test_a_red_mushroom_eaten_teaches_it_whatever_marks_the_step(self):
        # Carried item 6: a wild pet's red mushroom always makes it sick (meals.POISONOUS), so the sure knock reads no
        # mark; `knows_lesson` is the renamed `known`, which shadowed memory.known. The final fix wave (8): the
        # LEARNED hook nothing registered is gone.
        state, context = world()
        self.assertFalse(knows_lesson(context.db, "red_mushroom"))
        after_step(state, {"kind": "eat", "item": "red_mushroom"}, context, 1.0)
        self.assertTrue(knows_lesson(context.db, "red_mushroom"))
        self.assertFalse(hasattr(knocks, "LEARNED") or hasattr(knocks, "known"))


if __name__ == "__main__":
    unittest.main()

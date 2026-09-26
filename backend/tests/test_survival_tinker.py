import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.curiosity import curiosity_state
from backend.survival.journal import LESSONS
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.tinker import (
    DEEP_COPPER, MANUAL_CHANNEL, MANUAL_ODDS, SPARK, TINKER_REST, next_idea, observe_tinker, tinker_state,
)
from backend.tests.test_survival_machines import wired
from backend.tests.test_survival_signals import machine
from backend.tests.test_survival_workshop import NIGHT, Yard

MAKING_LESSONS = (SPARK, "clock", "latch", "adder")


def curious(yard, value=60.0):
    curiosity_state(yard.state, 0.0)["value"] = value  # the journal starts with curiosity
    return yard


def lessons(yard):
    return Situation(yard.state, yard.grid, {"time_scale": 1.0, "phase": "day"}, 0.0, yard.db).lessons


def deep(lucky: bool, y: int = -2):
    """A cell of copper at height y where the manual's roll is (or is not) lucky."""
    return next((x, y, 0) for x in range(400)
                if (nature.roll("1", (x, y, 0), MANUAL_CHANNEL) < 1 / MANUAL_ODDS) == lucky)


class LessonTests(unittest.TestCase):
    def test_the_making_lessons_are_journal_lessons_so_the_owner_can_teach_them(self):
        for thing in MAKING_LESSONS:
            lesson = LESSONS[thing]
            self.assertEqual(lesson.kind, "making", thing)
            self.assertTrue(lesson.unlocks and len(lesson.lines) == 2, thing)
        self.assertEqual(LESSONS[SPARK].unlocks, "wires up machines")

    def test_deep_copper_sometimes_holds_an_old_manual(self):
        yard = curious(Yard())
        def mine(cell):
            step = {"kind": "mine", "block": "copper_ore", "target": list(cell)}
            observe_tinker(yard.state, step, yard.context(), 5.0)

        mine(deep(False))
        mine(deep(True, y=DEEP_COPPER + 3))  # shallow copper holds no manual
        self.assertNotIn(SPARK, lessons(yard))
        mine(deep(True))
        self.assertIn(SPARK, lessons(yard))
        self.assertIn((5.0, "found", "Pip found an old manual in the copper seam."), yard.events)


class TinkerTests(unittest.TestCase):
    def test_nothing_to_tinker_with_without_copper_and_never_at_night(self):
        tinker = PURPOSES["tinker"]
        self.assertFalse(tinker.valid(curious(Yard({"planks": 4})).situation()))
        yard = curious(wired(lesson=False))
        self.assertEqual(next_idea(yard.situation()), SPARK)
        self.assertTrue(tinker.valid(yard.situation()))
        self.assertFalse(tinker.valid(yard.situation(NIGHT)))
        self.assertIn("what copper does", tinker.facts(yard.situation()))

    def test_it_lays_out_a_lever_wire_and_lamp_throws_the_lever_and_works_out_the_spark(self):
        yard = curious(wired(lesson=False))
        steps = yard.plan("tinker")
        places = [step for step in steps if step["kind"] == "place" and step["block"] in ("lever", "copper_wire",
                                                                                          "lamp")]
        self.assertEqual([step["block"] for step in places][-3:], ["lever", "copper_wire", "lamp"])
        wait = next(index for index, step in enumerate(steps) if step["kind"] == "wait")
        self.assertEqual(steps[wait - 1], {"kind": "flip", "target": places[-3]["target"]})
        self.assertEqual([step.get("keep") for step in steps[wait + 1:]], [True, True, True])
        yard.carry_out(steps[:wait], "tinker")
        with patch("backend.survival.tinker.lucky", lambda state, at: True):
            observe_tinker(yard.state, {**steps[wait], "purpose": "tinker"}, yard.context(), 5.0)
        self.assertIn(SPARK, lessons(yard))
        self.assertEqual([yard.grid.material(*step["target"]) for step in places[-3:]],
                         ["lever_on", "copper_wire_lit", "lamp_lit"])
        yard.carry_out(steps[wait + 1:], "tinker")
        self.assertEqual([yard.grid.material(*step["target"]) for step in places[-3:]], ["air"] * 3)
        self.assertEqual([yard.state["inventory"].get(item) for item in ("lever", "copper_wire", "lamp")], [1, 12, 1])

    def test_a_session_that_finds_nothing_waits_before_the_next(self):
        yard = curious(wired(lesson=False))
        tinker = PURPOSES["tinker"]
        tinker.plan(yard.situation(), yard.context())
        with patch("backend.survival.tinker.lucky", lambda state, at: False):
            observe_tinker(yard.state, {"kind": "wait", "purpose": "tinker"}, yard.context(), 0.0)
        self.assertNotIn(SPARK, lessons(yard))
        self.assertEqual(tinker_state(yard.state)["tried"], 0.0)
        self.assertFalse(tinker.valid(yard.situation()))
        later = yard.situation()
        later.at = TINKER_REST + 1.0
        self.assertTrue(tinker.valid(later))

    def test_later_lessons_come_from_watching_the_machine_before(self):
        yard = curious(wired())
        self.assertIsNone(next_idea(yard.situation()))  # no night-light yet to learn the clock from
        machine(yard, ("S n>* ",), name="night_light")
        self.assertEqual(next_idea(yard.situation()), "clock")
        steps = yard.plan("tinker")
        self.assertEqual([step["kind"] for step in steps], ["walk", "wait"])
        self.assertIn("a clock from its night light", PURPOSES["tinker"].facts(yard.situation()))
        with patch("backend.survival.tinker.lucky", lambda state, at: True):
            observe_tinker(yard.state, {**steps[-1], "purpose": "tinker"}, yard.context(), 5.0)
        self.assertIn("clock", lessons(yard))
        self.assertIsNone(next_idea(yard.situation()))  # the latch waits for a clock


if __name__ == "__main__":
    unittest.main()

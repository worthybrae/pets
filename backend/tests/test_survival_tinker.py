import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.curiosity import curiosity_state
from backend.survival.goals import GOALS, advancing
from backend.survival.journal import LESSONS
from backend.survival.lessons import claims
from backend.survival.making import needs, raw_needs
from backend.survival.memory import know, remember
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.tinker import (
    BENCH, DEEP_COPPER, MANUAL_CHANNEL, MANUAL_ODDS, SPARK, TINKER_REST, bench_needs, next_idea, observe_tinker,
    tinker_state,
)
from backend.survival.work import MAKING_ORE_RANGE, ORE_RANGE, ore_targets, prospecting
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

    def test_a_second_lucky_deep_copper_find_teaches_and_discounts_nothing_once_the_spark_is_known(self):
        # Minor 2, the guard at tinker.py:92-94: taught(db, SPARK) is already true, so a second
        # lucky roll never fires the manual again.
        yard = curious(Yard())

        def mine(cell):
            step = {"kind": "mine", "block": "copper_ore", "target": list(cell)}
            observe_tinker(yard.state, step, yard.context(), 5.0)

        first = deep(True)
        mine(first)
        self.assertIn(SPARK, lessons(yard))
        events, value = list(yard.events), curiosity_state(yard.state, 5.0)["value"]

        second = next((x, -2, 0) for x in range(first[0] + 1, 400)
                      if nature.roll("1", (x, -2, 0), MANUAL_CHANNEL) < 1 / MANUAL_ODDS)
        mine(second)
        self.assertEqual(yard.events, events)  # no second "found" or "learned" event
        self.assertEqual(curiosity_state(yard.state, 5.0)["value"], value)  # no second curiosity discount

    def test_the_adder_words_no_longer_make_a_line_about_two_of_something_else_doubtful(self):
        # Fix round 1, Important 1: words="counting in twos" registered the bare word "two" as an
        # adder subject (lessons.keys_of widens a multi-word `words` to its own last word too), so
        # any owner line starting "Two ..." was doubted about the adder instead of judged on its
        # own words. It fits no lesson now, so the strongest true statement is that it is not
        # doubtful (neither the latch nor any other lesson names "two inverters" or "a bit").
        found = claims("Two inverters can hold a bit.")
        self.assertEqual((found.taught, found.doubtful), ((), False), found)
        # A natural line about the adder's own words still teaches it.
        self.assertEqual(claims("a counter counts in twos").taught, ("adder",))


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



class CopperFirstTests(unittest.TestCase):
    """The Making final fix wave, C2: the first circuits wanted copper only once the spark was known, and
    the spark needs copper (the bench, or the manual in deep copper), so only the owner could break the
    loop."""

    KIT = {"stone_pickaxe": 1, "iron_pickaxe": 1, "coal": 8, "sticks": 4, "cobblestone": 12, "planks": 12,
           "oak_log": 4}

    def test_without_copper_or_the_spark_mine_ore_goes_after_the_copper_it_remembers(self):
        yard = curious(Yard(dict(self.KIT)))
        self.assertEqual(bench_needs(yard.situation()), {})  # not while the first circuits are not its goal
        yard.goal("first_circuits")
        s = yard.situation()
        self.assertEqual(bench_needs(s), {item: 1 for item in BENCH})
        self.assertEqual(raw_needs(s), {"copper_ore": 2})  # a wire's ingot and a lamp's
        self.assertIsNone(next_idea(s))  # no copper to tinker with yet
        cell = deep(True)  # deep copper, where the old manual may turn up
        yard.grid.put(*cell, "copper_ore")
        remember(yard.db, "ore", cell, 0.0, "copper_ore")
        s = yard.situation()
        self.assertEqual([(place["x"], place["y"], place["z"]) for place in ore_targets(s)], [cell])
        self.assertTrue(PURPOSES["mine_ore"].valid(s))
        self.assertIn("mine_ore", advancing(s, GOALS["first_circuits"]))
        mine = PURPOSES["mine_ore"].plan(s, yard.context())[-1]
        self.assertEqual(mine, {"kind": "mine", "target": list(cell)})
        observe_tinker(yard.state, {**mine, "block": "copper_ore"}, yard.context(), 5.0)
        self.assertIn(SPARK, lessons(yard))  # the manual, on its own
        self.assertEqual(bench_needs(yard.situation()), {})

    def test_copper_seen_only_far_off_or_underfoot_is_gone_after_or_dug_for(self):
        """On the gate's route check the copper a pet had seen lay 67 blocks and more from home, or was the floor
        of a passage: mine_ore (48 blocks) never went for it, and gather_stone did not dig on for more, since
        copper had been "seen". An ore making wants is worth a trip of MAKING_ORE_RANGE (96)."""
        yard = curious(Yard(dict(self.KIT)))
        yard.goal("first_circuits")
        remember(yard.db, "ore", (140, -2, 1), 0.0, "copper_ore")  # too far even so
        self.assertEqual((ore_targets(yard.situation()), prospecting(yard.situation())), ([], True))
        floor = (12, -2, 6)  # the floor of a passage: never mined, so it counts as none
        yard.grid.put(*floor, "copper_ore")
        yard.grid.put(12, -1, 6, "air")
        remember(yard.db, "ore", floor, 0.0, "copper_ore")
        self.assertEqual((ore_targets(yard.situation()), prospecting(yard.situation())), ([], True))
        remember(yard.db, "ore", (82, -2, 1), 0.0, "copper_ore")  # 70 blocks off
        s = yard.situation()
        self.assertEqual([(place["x"], place["z"]) for place in ore_targets(s)], [(82, 1)])
        self.assertFalse(prospecting(s))
        self.assertEqual(ORE_RANGE, 48)  # iron, coal, gold and diamonds for their own sake: still 48
        self.assertEqual(MAKING_ORE_RANGE, 96)

    def test_with_the_copper_mined_it_tinkers_on_its_own(self):
        yard = curious(Yard({**self.KIT, "copper_ore": 2}))
        yard.goal("first_circuits")
        s = yard.situation()
        self.assertEqual(raw_needs(s), {})
        self.assertEqual(needs(s), {item: 1 for item in BENCH})
        self.assertEqual(next_idea(s), SPARK)
        self.assertTrue(PURPOSES["tinker"].valid(s))
        self.assertIn("tinker", advancing(s, GOALS["first_circuits"]))
        know(yard.db, SPARK, "lesson", 0.0)
        self.assertEqual(bench_needs(yard.situation()), {})


if __name__ == "__main__":
    unittest.main()

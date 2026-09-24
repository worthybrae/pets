import unittest
from contextlib import contextmanager
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose)
from backend.survival.goals import (
    ADVANCES, GOALS, URGES, Goal, Milestone, adopt_goal, complete, counted, is_open, meets_need, progress_of,
    register_goal, toward,
)
from backend.survival.memory import know
from backend.survival.models import criteria
from backend.survival.pickers import Option, options
from backend.survival.situation import DUSK
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_pickers import DAY, TREE, situation

WOOD = Goal("woodpile", "A woodpile", "Wood makes everything else.",
            (Milestone("Carry 4 logs", lambda s: s.count("oak_log") / 4, ("gather_wood",)),
             Milestone("Make a pickaxe", lambda s: float(s.count("wooden_pickaxe") > 0), ("craft_tools",)),
             Milestone("Grow a forest", lambda s: 0.0, ("grow_forest",)),  # no such purpose: skipped
             Milestone("Make a moon pickaxe", lambda s: 0.0, ("craft_tools",), items=("moon_pickaxe",))),  # no recipe
            score=lambda s: 50.0, thought="Wood first.")
STONE = Goal("quarry", "A quarry", "Stone lasts.", (Milestone("Dig stone", lambda s: 0.0, ("gather_stone",)),),
             score=lambda s: 40.0, thought="Stone next.", after=("woodpile",))
LATER = Goal("later", "Later", "Some day.", (Milestone("Dig stone", lambda s: 0.0, ("gather_stone",)),),
             score=lambda s: 30.0, thought="Some day.")


@contextmanager
def only_goals(*goals):
    """The registry holds just these goals for the test."""
    saved = dict(GOALS)
    GOALS.clear()
    for goal in goals:
        register_goal(goal)
    try:
        yield
    finally:
        GOALS.clear()
        GOALS.update(saved)


def goal_situation(goal=None, **changes):
    s = situation(**changes)
    if goal is not None:
        adopt_goal(s.state, goal, "utility", "", 0.0)
    return s


class ProgressTests(unittest.TestCase):
    def test_only_milestones_with_a_registered_purpose_and_known_recipes_count(self):
        self.assertEqual([index for index, _ in counted(WOOD)], [0, 1])
        some = situation(inventory={"oak_log": 2})
        self.assertAlmostEqual(progress_of(some, WOOD), 0.25)
        self.assertFalse(complete(some, WOOD))
        done = situation(inventory={"oak_log": 9, "wooden_pickaxe": 1})
        self.assertEqual((progress_of(done, WOOD), complete(done, WOOD)), (1.0, True))  # a share stops at 1

    def test_a_crashing_milestone_counts_nothing_and_is_logged_once(self):
        broken = Goal("broken", "Broken", "It breaks.", (Milestone("Break", lambda s: 1 / 0, ("gather_wood",)),),
                      score=lambda s: 10.0, thought="Oops.")
        with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
            self.assertEqual(progress_of(situation(), broken), 0.0)
            self.assertEqual(progress_of(situation(), broken), 0.0)
        self.assertEqual(len(logs.output), 1)

    def test_a_goal_opens_once_the_goals_before_it_are_settled_and_until_it_is_reached(self):
        with only_goals(WOOD, STONE):
            s = situation()
            self.assertEqual((is_open(s, WOOD), is_open(s, STONE)), (True, False))
            s = situation(inventory={"oak_log": 4, "wooden_pickaxe": 1})  # the woodpile is complete: settled
            self.assertEqual((is_open(s, WOOD), is_open(s, STONE)), (False, True))
            s = situation()
            know(s.db, "woodpile", "goal", 0.0)  # reached earlier in this life
            self.assertEqual((is_open(s, WOOD), is_open(s, STONE)), (False, True))

    def test_a_goal_that_repeats_is_on_offer_again_once_reached(self):
        again = Goal("again", "Again", "Once more.", WOOD.milestones, score=lambda s: 10.0, thought="", repeat=True)
        with only_goals(WOOD, again):
            s = situation()
            know(s.db, "woodpile", "goal", 0.0)
            know(s.db, "again", "goal", 0.0)
            self.assertEqual((is_open(s, WOOD), is_open(s, again)), (False, True))

    def test_a_new_goal_starts_from_nothing_and_asks_for_a_new_purpose(self):
        with only_goals(WOOD):
            s = situation()
            s.brain["pending"] = None
            state = s.state
            self.assertTrue(adopt_goal(state, "woodpile", "jev", "Wood first.", 10.0))
            brain = state["brain"]
            self.assertEqual({key: brain["goal"][key] for key in ("name", "since", "picker", "plan", "best_at")},
                             {"name": "woodpile", "since": 10.0, "picker": "jev", "plan": None, "best_at": 10.0})
            self.assertEqual((brain["pending"]["reasons"], brain["goal_due"], state["last_thought"]),
                             (["goal"], None, "Wood first."))
            self.assertFalse(adopt_goal(state, "woodpile", "utility", "Again.", 20.0))  # kept, not started over
            self.assertEqual((brain["goal"]["since"], brain["goal"]["picker"]), (10.0, "utility"))
            self.assertFalse(adopt_goal(state, None, "utility", "", 30.0))  # none open: the tick asks again later
            self.assertEqual((brain["goal"]["name"], brain["goal_idle_at"]), ("woodpile", 30.0))


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class SteerTests(unittest.TestCase):
    def test_without_a_goal_every_purpose_is_offered_at_its_own_score(self):
        with only_goals(WOOD):
            found = {option.name: option for option in options(goal_situation())}
        self.assertLessEqual({"gather_wood", "rest"}, set(found))
        self.assertEqual(found["gather_wood"].score, 72.5)
        self.assertFalse(any(option.goal for option in found.values()))

    def test_purposes_that_advance_the_goal_score_more_and_nothing_else_is_offered(self):
        with only_goals(WOOD):
            found = options(goal_situation("woodpile"))
        self.assertEqual([(option.name, option.score, option.goal) for option in found],
                         [("gather_wood", 80.0, "A woodpile")])  # 72.5 + 15, no higher than 80

    def test_a_need_is_still_offered_and_late_in_the_day_the_goal_waits(self):
        with only_goals(WOOD):
            hungry = goal_situation("woodpile", inventory={"berries": 2}, vitals={**START_VITALS, "hunger": 40.0})
            self.assertEqual({(option.name, option.score) for option in options(hungry)},
                             {("gather_wood", 80.0), ("eat", 60.0)})
            late = goal_situation("woodpile", clock={**DAY, "seconds_into_day": DUSK - 100.0})
            self.assertEqual([(option.name, option.score) for option in options(late)], [("gather_wood", 42.5)])

    def test_while_nothing_for_the_goal_is_on_offer_another_open_goal_is_worked_toward(self):
        with only_goals(WOOD, LATER):
            s = goal_situation("later")  # no pickaxe: nothing digs stone
            found = options(s)
            self.assertEqual([(option.name, option.goal) for option in found], [("gather_wood", "A woodpile")])
            self.assertEqual(toward(s, {"rest"}), None)

    def test_a_tie_between_open_goals_is_broken_by_name_not_registration_order(self):
        current = Goal("current", "Current", "", (Milestone("Rest on it", lambda s: 0.0, ("rest",)),),
                        score=lambda s: 10.0, thought="")
        first = Goal("aaa_goal", "First", "", (Milestone("Wood", lambda s: 0.0, ("gather_wood",)),),
                     score=lambda s: 40.0, thought="")
        second = Goal("bbb_goal", "Second", "", (Milestone("Stone", lambda s: 0.0, ("gather_stone",)),),
                      score=lambda s: 40.0, thought="")
        offered_now = {"gather_wood", "gather_stone"}
        with only_goals(current, first, second):
            picked = toward(goal_situation("current"), offered_now)
        with only_goals(current, second, first):  # registered in the opposite order
            picked_again = toward(goal_situation("current"), offered_now)
        self.assertEqual(picked[0].name, "aaa_goal")  # the earlier name wins on the tie, not the earlier import
        self.assertEqual(picked_again[0].name, "aaa_goal")

    def test_a_purpose_with_a_check_of_its_own_advances_the_goal_only_when_it_says_so(self):
        def boom(s, goal):
            raise RuntimeError("boom")

        with only_goals(WOOD):
            s = goal_situation("woodpile")
            with patch.dict(ADVANCES, {"gather_wood": lambda s, goal: False}):
                self.assertIsNone(toward(s, {"gather_wood"}))
            s = goal_situation("woodpile")
            with patch.dict(ADVANCES, {"gather_wood": boom}), \
                    self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                self.assertIsNone(toward(s, {"gather_wood"}))
            self.assertEqual(len(logs.output), 1)
            self.assertEqual(toward(goal_situation("woodpile"), {"gather_wood"})[1], {"gather_wood"})

    def test_a_purpose_meets_a_need_while_mimo_feels_its_urge(self):
        def boom(s):
            raise RuntimeError("boom")

        s = situation()
        self.assertEqual((meets_need(s, "eat", 60.0), meets_need(s, "eat", 40.0), meets_need(s, "rest", 60.0)),
                         (True, False, False))
        with patch.dict(URGES, {"rest": lambda s: True}):
            self.assertEqual((meets_need(s, "rest", 60.0), meets_need(s, "rest", 40.0)), (True, False))
        with patch.dict(URGES, {"rest": boom}), self.assertLogs("backend.survival.goals", level="ERROR") as logs:
            self.assertFalse(meets_need(s, "rest", 60.0))
            self.assertFalse(meets_need(s, "rest", 60.0))
        self.assertEqual(len(logs.output), 1)

    def test_the_model_is_told_which_choices_work_toward_the_goal(self):
        told = criteria([Option("gather_wood", "gather wood", "Chop a tree.", "a tree near", 80.0, "A woodpile"),
                         Option("rest", "rest", "Rest a while.", "mood 70", 15.0)])
        self.assertEqual(told, {"gather_wood": "Chop a tree. Now: a tree near. It works toward the goal: A woodpile.",
                                "rest": "Rest a while. Now: mood 70."})


if __name__ == "__main__":
    unittest.main()

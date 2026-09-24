import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.choosing import (
    Ask, Choice, Chooser, InlineExecutor, prepare, prepare_goal, store_choice, store_goal,
)
from backend.survival.goals import Goal, adopt_goal, ask_for_goal, goal_state, offers
from backend.survival.hatch import hatch
from backend.survival.models import GOAL_INSTRUCTIONS, ask_jev
from backend.survival.once import forget_logged
from backend.survival.pickers import Option
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_choosing import JEV_URL, FakeHttp
from backend.tests.test_survival_goals import LATER, WOOD, goal_situation, only_goals

BORN = 1_000_000.0
JEV = {"TYPESAFE_API_KEY": "k"}
NO_CALLS = {"model": 0, "luna": 0, "reflections": 0}


class Recorder:
    """A model endpoint that gives one answer and keeps every request body."""

    def __init__(self, answer):
        self.answer, self.bodies = answer, []

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        return self.answer


class GoalChoiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.path = self.registry.world_path(self.life)
        self.world = SurvivalWorld(self.path)
        self.name = self.life["name"]

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def brain(self):
        return goal_state(self.world.state())

    def chooser(self, env=None, answers=None):
        return Chooser(env=env or {}, http=FakeHttp(answers or {}), executor=InlineExecutor(), rng=random.Random(1),
                       scale=1.0)

    def ask(self, env=None):
        return prepare_goal(SurvivalWorld(self.path, read_only=True), BORN + 5, 1.0, env or {})

    def test_nothing_is_asked_until_the_tick_asks_for_a_goal(self):
        with only_goals(WOOD, LATER):
            self.assertIsNone(self.ask(JEV))

    def test_jev_chooses_among_the_open_goals_and_the_call_counts(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask(JEV)
            self.assertEqual((ask.kind, ask.route, [option.name for option in ask.options]),
                             ("goal", "jev", ["woodpile", "later"]))
            self.assertIn("goals_reached", ask.payload)
            http = FakeHttp({JEV_URL: {"answers": {"goal": {"choice": "later"}}}})
            chooser = Chooser(env=JEV, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0)
            self.assertEqual(chooser.poll(self.registry, BORN + 5), "later")
        brain = self.brain()
        self.assertEqual((brain["goal"]["name"], brain["goal"]["picker"], brain["goal_due"]), ("later", "jev", None))
        self.assertEqual((brain["calls"]["model"], len(brain["jev_calls"]), brain["last_call_at"]), (1, 1, None))
        self.assertEqual(self.world.events(1)[0]["text"], f'{self.name} set a new goal: later. "Some day."')

    def test_jev_is_asked_the_goal_question(self):
        http = Recorder({"answers": {"goal": {"choice": "later"}}})
        choices = [Option("woodpile", "A woodpile", "Wood.", "0% done", 70.0),
                   Option("later", "Later", "Some day.", "", 50.0)]
        self.assertEqual(ask_jev({}, choices, JEV, http, question="goal", instructions=GOAL_INSTRUCTIONS), "later")
        self.assertEqual(http.bodies[0]["questions"], {"goal": {
            "type": "choice", "instructions": GOAL_INSTRUCTIONS,
            "criteria": {"woodpile": "Wood. Now: 0% done.", "later": "Some day. Now: ."}}})

    def test_the_rules_pick_the_best_goal_and_then_the_purpose_in_the_same_poll(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            purpose = self.chooser().poll(self.registry, BORN + 5)
        brain = self.brain()
        self.assertEqual((brain["goal"]["name"], brain["goal"]["picker"]), ("woodpile", "utility"))
        self.assertEqual(purpose, brain["purpose"])
        self.assertIsNotNone(purpose)

    def test_a_goal_that_repeats_is_always_among_the_offers(self):
        many = [Goal(f"g{n}", f"G{n}", "", WOOD.milestones, score=lambda s, n=n: 60.0 + n, thought="") for n in range(5)]
        again = Goal("again", "Again", "", WOOD.milestones, score=lambda s: 1.0, thought="", repeat=True)
        with only_goals(*many, again):
            names = [goal.name for goal, _, _ in offers(goal_situation())]
        self.assertEqual(names, ["g4", "g3", "g2", "again"])  # L4's discovery goals are always on offer

    def test_a_single_open_goal_is_taken_without_a_model_call(self):
        with only_goals(WOOD):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.assertEqual(self.ask(JEV).route, "utility")

    def test_the_rules_keep_the_current_goal_at_dawn(self):
        with only_goals(WOOD, LATER):
            def keep_later(state):
                adopt_goal(state, "later", "jev", "Some day.", BORN)
                ask_for_goal(state, "dawn", BORN + 1)
            self.edit(keep_later)
            ask = self.ask()
            self.assertEqual(ask.options[0].name, "later")  # the current goal leads
            self.assertIn("(its goal now)", ask.options[0].facts)
            self.chooser().poll(self.registry, BORN + 5)
        brain = self.brain()
        self.assertEqual((brain["goal"]["name"], brain["goal"]["since"], brain["goal"]["picker"]),
                         ("later", BORN, "utility"))
        self.assertFalse(any("set a new goal" in event["text"] for event in self.world.events(100)))

    def test_a_stale_goal_answer_is_thrown_away(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask()
            self.edit(lambda state: goal_state(state).update(goal_due={"id": 99, "reasons": ["dawn"], "since": BORN}))
            self.assertIsNone(store_goal(self.world, ask, Choice("later", "utility", "Some day.", NO_CALLS), BORN + 6))
        self.assertIsNone(self.brain()["goal"])

    def test_with_no_goal_open_the_ask_is_answered_at_once(self):
        with only_goals():
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.assertIsNone(self.ask())
        brain = self.brain()
        self.assertEqual((brain["goal"], brain["goal_due"], brain["goal_idle_at"]), (None, None, BORN + 5))

    def test_with_a_goal_a_purpose_that_ended_as_usual_is_rechosen_by_the_rules(self):
        with only_goals(WOOD, LATER):
            def ended(state):
                ensure_brain(state).update(last_chosen="gather_wood", pending=None)
                mark_trigger(state, "plan_done", BORN)
            self.edit(ended)
            self.assertEqual(prepare(SurvivalWorld(self.path, read_only=True), BORN + 90, 1.0, JEV).route, "jev")
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: ensure_brain(state).update(pending={"id": 50, "reasons": ["plan_done"],
                                                                        "since": BORN, "urgent": False}))
            self.assertEqual(prepare(SurvivalWorld(self.path, read_only=True), BORN + 90, 1.0, JEV).route, "utility")

    def test_a_purpose_toward_a_goal_says_which(self):
        forget_logged()
        self.edit(lambda state: ensure_brain(state).update(pending={"id": 7, "reasons": ["goal"], "since": BORN,
                                                                     "urgent": False}))
        ask = Ask(7, "utility", False, (Option("gather_wood", "gather wood", "Chop.", "", 80.0, "A woodpile"),), {},
                  BORN + 1)
        store_choice(self.world, ask, Choice("gather_wood", "utility", "Wood.", NO_CALLS), BORN + 1)
        self.assertEqual(self.world.events(1)[0]["text"],
                         f'{self.name} decided to gather wood, toward a woodpile. "Wood."')


if __name__ == "__main__":
    unittest.main()

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.survival import goals

from backend.survival.choosing import (
    Ask, Choice, Chooser, InlineExecutor, prepare, prepare_goal, store_choice, store_goal,
)
from backend.survival.goals import (
    REACHED, Goal, adopt_goal, ask_for_goal, give_up_goal, goal_state, offers, reach_goal,
)
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.models import GOAL_INSTRUCTIONS, ModelError, ask_jev
from backend.survival.once import forget_logged
from backend.survival.pickers import Option
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_choosing import JEV_URL, FakeHttp, HeldExecutor
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

    def test_the_goal_payload_says_why_it_is_asked(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.assertEqual(self.ask(JEV).payload["goal_trigger"], "none open")

            def dawn_only(state):
                goal_state(state).update(goal_due=None)  # a fresh ask: dawn alone, not "no_goal" too
                adopt_goal(state, "later", "jev", "Some day.", BORN)
                ask_for_goal(state, "dawn", BORN + 1)
            self.edit(dawn_only)
            self.assertEqual(self.ask(JEV).payload["goal_trigger"], "dawn")

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

    def test_the_daily_cap_sends_the_goal_choice_to_utility(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.assertEqual(self.ask({**JEV, "MIMO_MAX_DECISIONS_PER_DAY": "0"}).route, "utility")

    def test_the_hourly_jev_budget_sends_the_goal_choice_to_utility(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            sixty = [5.0 - index for index in range(60)]  # 60 goal-game seconds before game_at (~5.0)
            self.edit(lambda state: ensure_brain(state).update(jev_calls=sixty))
            self.assertEqual(self.ask(JEV).route, "utility")  # the default budget (60) is spent
            self.edit(lambda state: ensure_brain(state).update(jev_calls=sixty[1:]))  # one below the cap
            self.assertEqual(self.ask(JEV).route, "jev")

    def test_a_failed_jev_goal_call_falls_back_to_the_rules_and_still_counts(self):
        forget_logged()
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            http = FakeHttp({JEV_URL: ModelError("request failed: down")})
            chooser = Chooser(env=JEV, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0)
            with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
                stored = chooser.poll(self.registry, BORN + 5)
            self.assertEqual(len(logs.output), 1)
            self.assertIn(stored, ("woodpile", "later"))
        brain = self.brain()
        self.assertEqual((brain["goal"]["picker"], brain["calls"]["model"], len(brain["jev_calls"])),
                         ("utility", 1, 1))

    def test_a_goal_jev_did_not_offer_falls_back_to_the_rules_and_still_counts(self):
        forget_logged()
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            http = FakeHttp({JEV_URL: {"answers": {"goal": {"choice": "nonexistent"}}}})
            chooser = Chooser(env=JEV, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0)
            with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
                stored = chooser.poll(self.registry, BORN + 5)
            self.assertEqual(len(logs.output), 1)
            self.assertIn(stored, ("woodpile", "later"))
        brain = self.brain()
        self.assertEqual((brain["goal"]["picker"], brain["calls"]["model"], len(brain["jev_calls"])),
                         ("utility", 1, 1))

    def test_a_hung_jev_goal_call_is_given_up_after_35_s_and_the_rules_answer_is_stored(self):
        forget_logged()
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            stuck, fresh = HeldExecutor(), []

            def new_executor():
                fresh.append(InlineExecutor())
                return fresh[-1]

            http = FakeHttp({JEV_URL: {"answers": {"goal": {"choice": "later"}}}})
            chooser = Chooser(env=JEV, http=http, executor=stuck, rng=random.Random(1), scale=1.0,
                              executor_factory=new_executor)
            self.assertIsNone(chooser.poll(self.registry, BORN + 1))
            self.assertIsNone(chooser.poll(self.registry, BORN + 1 + 34))  # under the 35 s deadline
            with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
                self.assertIsNotNone(chooser.poll(self.registry, BORN + 1 + 35.5))
            self.assertEqual(len(logs.output), 1)
        brain = self.brain()
        self.assertEqual((brain["goal"]["picker"], brain["calls"]["model"], len(brain["jev_calls"])),
                         ("utility", 1, 1))
        self.assertEqual((stuck.shut, len(fresh)), (True, 1))

    def test_an_urgent_purpose_choice_goes_first_not_a_slow_goal_call(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            self.edit(lambda state: ensure_brain(state).update(
                pending={"id": 50, "reasons": ["hunger_15"], "since": BORN, "urgent": True}))
            held = HeldExecutor()
            http = FakeHttp({JEV_URL: {"answers": {"purpose": {"choice": "rest"}, "goal": {"choice": "later"}}}})
            chooser = Chooser(env=JEV, http=http, executor=held, rng=random.Random(1), scale=1.0)
            self.assertIsNone(chooser.poll(self.registry, BORN + 5))
        self.assertEqual(len(held.held), 1)
        self.assertEqual(held.held[0][2][0].kind, "purpose")  # the urgent purpose goes first, not the goal
        self.assertIsNotNone(self.brain()["goal_due"])  # the goal ask still waits

    def test_a_goal_that_repeats_is_always_among_the_offers(self):
        many = [Goal(f"g{n}", f"G{n}", "", WOOD.milestones, score=lambda s, n=n: 60.0 + n, thought="") for n in range(5)]
        again = Goal("again", "Again", "", WOOD.milestones, score=lambda s: 1.0, thought="", repeat=True)
        with only_goals(*many, again):
            names = [goal.name for goal, _, _ in offers(goal_situation())]
        self.assertEqual(names, ["g4", "g3", "g2", "again"])  # L4's discovery goals are always on offer

    def test_offers_works_out_what_can_be_done_for_each_goal_once(self):
        """L4a final fix wave, minor: offers() asked workable() twice per goal (its facts and its
        score, 58-505 ms cold); once per goal per call now, with the same facts and scores."""
        many = [Goal(f"g{n}", f"G{n}", "", WOOD.milestones, score=lambda s, n=n: 60.0 + n, thought="") for n in range(3)]
        with only_goals(*many):
            s = goal_situation()
            asked = []
            real = goals.workable
            with patch("backend.survival.goals.workable", lambda s, goal: asked.append(goal.name) or real(s, goal)):
                found = offers(s)
            self.assertEqual(sorted(asked), ["g0", "g1", "g2"])
            self.assertEqual([(goal.name, facts, score) for goal, facts, score in found],
                             [(goal.name, goals.goal_facts(s, goal), goals.rules_score(s, goal)) for goal, _, _ in found])

    def test_a_tie_in_score_is_broken_by_name_not_registration_order(self):
        first = Goal("aaa", "First", "", WOOD.milestones, score=lambda s: 40.0, thought="")
        second = Goal("bbb", "Second", "", WOOD.milestones, score=lambda s: 40.0, thought="")
        with only_goals(second, first):  # registered in reverse name order
            names = [goal.name for goal, _, _ in offers(goal_situation())]
        self.assertEqual(names, ["aaa", "bbb"])

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

    def test_a_goal_that_holds_is_kept_at_dawn_with_no_jev_call(self):
        """L4b final fix wave, I2: a goal that holds (an expedition out from home) is offered alone,
        so the dawn choice goes to the rules, which keep it: Jev, which would switch, is never asked."""
        hold = {"on": True}
        trek = Goal("trek", "A trek", "Far away.", LATER.milestones, score=lambda s: 10.0, thought="",
                    holds=lambda s: hold["on"])

        def dawn(state):
            adopt_goal(state, "trek", "jev", "Off we go.", BORN)
            ensure_brain(state)["pending"] = None  # no purpose choice waits: this is about the goal
            ask_for_goal(state, "dawn", BORN + 1)

        with only_goals(WOOD, trek):
            self.edit(dawn)
            ask = self.ask(JEV)
            self.assertEqual((ask.route, [option.name for option in ask.options]), ("utility", ["trek"]))
            http = Recorder({"answers": {"goal": {"choice": "woodpile"}}})  # Jev would switch, were it asked
            Chooser(env=JEV, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0).poll(
                self.registry, BORN + 5)
            brain = self.brain()
            self.assertEqual((brain["goal"]["name"], brain["goal"]["since"], brain["goal_due"]), ("trek", BORN, None))
            self.assertFalse(any("goal" in body["questions"] for body in http.bodies))
            self.assertEqual(brain["calls"]["model"], 0)
            hold["on"] = False  # home again: the dawn choice is Jev's as before
            self.edit(lambda state: ask_for_goal(state, "dawn", BORN + 10))
            ask = self.ask(JEV)
            self.assertEqual((ask.route, [option.name for option in ask.options]), ("jev", ["trek", "woodpile"]))

    def test_a_crashing_holds_offers_the_goals_as_usual_and_is_logged_once(self):
        forget_logged()
        trek = Goal("trek", "A trek", "Far away.", LATER.milestones, score=lambda s: 10.0, thought="",
                    holds=lambda s: 1 / 0)
        with only_goals(WOOD, trek):
            with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                s = goal_situation()
                adopt_goal(s.state, "trek", "jev", "", 0.0)
                self.assertEqual([goal.name for goal, _, _ in offers(s)], ["trek", "woodpile"])
                self.assertEqual([goal.name for goal, _, _ in offers(s)], ["trek", "woodpile"])
        self.assertEqual(len(logs.output), 1)

    def test_a_stale_goal_answer_is_thrown_away(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask()
            self.edit(lambda state: goal_state(state).update(goal_due={"id": 99, "reasons": ["dawn"], "since": BORN}))
            self.assertIsNone(store_goal(self.world, ask, Choice("later", "utility", "Some day.", NO_CALLS), BORN + 6))
        self.assertIsNone(self.brain()["goal"])

    def test_reaching_the_goal_gives_a_pending_ask_a_fresh_id_so_a_stale_answer_is_thrown_away(self):
        with only_goals(WOOD):
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: ask_for_goal(state, "dawn", BORN + 1))
            ask = self.ask()  # Jev is asked whether to keep or switch, with this pending id
            with self.world.transaction() as db:
                state = read_state(db)
                reach_goal(state, SimpleNamespace(db=db, events=[]), WOOD, BORN + 2)
                write_state(db, state)
            stored = store_goal(self.world, ask, Choice("woodpile", "utility", "Keep it.", NO_CALLS), BORN + 6)
        self.assertIsNone(stored)
        brain = self.brain()
        self.assertIsNone(brain["goal"])
        self.assertNotEqual(brain["goal_due"]["id"], ask.pending_id)

    def test_giving_up_the_goal_gives_a_pending_ask_a_fresh_id_so_a_stale_answer_is_thrown_away(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: ask_for_goal(state, "dawn", BORN + 1))
            ask = self.ask()
            self.edit(lambda state: give_up_goal(state, SimpleNamespace(events=[]), "woodpile", BORN + 2,
                                                 "it cannot be done now", 1.0))
            stored = store_goal(self.world, ask, Choice("woodpile", "utility", "Keep it.", NO_CALLS), BORN + 6)
        self.assertIsNone(stored)
        brain = self.brain()
        self.assertIsNone(brain["goal"])
        self.assertNotEqual(brain["goal_due"]["id"], ask.pending_id)

    def test_a_fresh_answer_naming_a_penalized_goal_is_refused_and_asked_again(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask()  # both goals on offer, no current goal

            def penalize(state):
                goal_state(state)["goal_penalties"]["woodpile"] = BORN + 3600.0
            self.edit(penalize)  # set aside by some other path after the ask, before the answer
            stored = store_goal(self.world, ask, Choice("woodpile", "utility", "Wood first.", NO_CALLS), BORN + 6, 1.0)
        self.assertIsNone(stored)
        brain = self.brain()
        self.assertIsNone(brain["goal"])
        self.assertEqual(brain["goal_due"]["id"], ask.pending_id)  # not stale: still asked, unanswered

    def test_a_fresh_answer_naming_a_goal_no_longer_open_is_refused(self):
        with only_goals(WOOD, LATER):
            self.edit(lambda state: ask_for_goal(state, "no_goal", BORN))
            ask = self.ask()
            with self.world.transaction() as db:
                state = read_state(db)
                know(db, "woodpile", REACHED, BORN + 2)  # reached some other way: no longer open
                write_state(db, state)
            stored = store_goal(self.world, ask, Choice("woodpile", "utility", "Wood first.", NO_CALLS), BORN + 6, 1.0)
        self.assertIsNone(stored)
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
        with only_goals(WOOD):
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: ensure_brain(state).update(pending={"id": 7, "reasons": ["goal"], "since": BORN,
                                                                        "urgent": False}))
            ask = Ask(7, "utility", False, (Option("gather_wood", "gather wood", "Chop.", "", 80.0, "A woodpile"),),
                      {}, BORN + 1)
            store_choice(self.world, ask, Choice("gather_wood", "utility", "Wood.", NO_CALLS), BORN + 1)
        self.assertEqual(self.world.events(1)[0]["text"],
                         f'{self.name} decided to gather wood, toward a woodpile. "Wood."')

    def test_a_purpose_answer_in_flight_when_the_goal_is_reached_is_dropped(self):
        forget_logged()
        with only_goals(WOOD):
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: mark_trigger(state, "plan_done", BORN + 1))
            ask = prepare(SurvivalWorld(self.path, read_only=True), BORN + 2, 1.0, {})
            purpose = next((option.name for option in ask.options if option.goal), None)
            self.assertIsNotNone(purpose)  # something on offer works toward the goal
            # the woodpile is reached while this purpose answer is still being worked out
            with self.world.transaction() as db:
                state = read_state(db)
                reach_goal(state, SimpleNamespace(db=db, events=[]), WOOD, BORN + 3)
                write_state(db, state)
            stored = store_choice(SurvivalWorld(self.path), ask, Choice(purpose, "utility", "Chop away.", NO_CALLS),
                                  BORN + 6)
        # reach_goal gave the pending purpose ask a fresh id, so this stale answer is thrown away
        # (per the fix, a stale answer is either dropped, or, if the id somehow still matched,
        # stored without the stale "toward": see
        # test_a_purpose_toward_a_goal_that_has_since_ended_drops_the_stale_toward for that guard
        # in isolation, and test_a_purpose_toward_another_open_goal_meanwhile_keeps_the_aim for why
        # the guard cannot simply require the named goal to be the ACTIVE one).
        self.assertIsNone(stored)
        self.assertFalse(any("toward" in event["text"] for event in self.world.events(5)))

    def test_a_purpose_toward_a_goal_that_has_since_ended_drops_the_stale_toward(self):
        forget_logged()
        with only_goals(WOOD, LATER):
            self.edit(lambda state: adopt_goal(state, "woodpile", "utility", "", BORN))
            self.edit(lambda state: ensure_brain(state).update(pending={"id": 7, "reasons": ["goal"], "since": BORN,
                                                                        "urgent": False}))
            ask = Ask(7, "utility", False, (Option("gather_wood", "gather wood", "Chop.", "", 80.0, "A woodpile"),),
                      {}, BORN + 1)

            def end_it(state):
                # the woodpile is given up (and so penalized) without this pending purpose choice's
                # id changing (as if some other path let a stale answer through)
                give_up_goal(state, SimpleNamespace(events=[]), "woodpile", BORN + 2, "it cannot be done now", 1.0)
                ensure_brain(state).update(pending={"id": 7, "reasons": ["goal"], "since": BORN, "urgent": False})
            self.edit(end_it)
            stored = store_choice(self.world, ask, Choice("gather_wood", "utility", "Wood.", NO_CALLS), BORN + 6)
        self.assertEqual(stored, "gather_wood")  # the choice itself still stands
        text = self.world.events(1)[0]["text"]
        self.assertEqual(text, f'{self.name} decided to gather wood. "Wood."')
        self.assertNotIn("toward", text)

    def test_a_purpose_toward_another_open_goal_meanwhile_keeps_the_aim(self):
        """Resolution 8: while the active goal has nothing on offer, a purpose that advances a
        different open goal is steered toward that one instead (goals.toward, pickers.steer). The
        aim must not be mistaken for staleness just because it does not name the active goal."""
        forget_logged()
        with only_goals(WOOD, LATER):
            # "later" is active but has nothing on offer (no pickaxe digs stone); "woodpile" is open
            # and does have something on offer (gather_wood), so steer works toward it meanwhile.
            self.edit(lambda state: adopt_goal(state, "later", "utility", "Some day.", BORN))
            self.edit(lambda state: mark_trigger(state, "plan_done", BORN + 1))
            ask = prepare(SurvivalWorld(self.path, read_only=True), BORN + 2, 1.0, {})
            purpose = next((option for option in ask.options if option.goal), None)
            self.assertIsNotNone(purpose)  # something on offer works toward the other goal
            self.assertEqual(purpose.goal, "A woodpile")
            stored = store_choice(SurvivalWorld(self.path), ask,
                                  Choice(purpose.name, "utility", "Wood, meanwhile.", NO_CALLS), BORN + 6)
        self.assertEqual(stored, purpose.name)
        text = self.world.events(1)[0]["text"]
        self.assertIn(", toward a woodpile.", text)


if __name__ == "__main__":
    unittest.main()

import random
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import (
    DECISION_CAP, JEV_HOUR_CAP, LUNA_CAP, LUNA_HOUR_CAP, Ask, Choice, Chooser, InlineExecutor, cap, deadline,
    prepare, store_choice,
)
from backend.survival.hatch import hatch
from backend.survival.models import ModelError
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.workers.mimo_worker import run_once

BORN = 1_000_000.0
JEV_URL = "https://api.typesafe.ai/v1/systemone"
LUNA_URL = "https://api.openai.com/v1/chat/completions"
JEV_REST = {"answers": {"purpose": {"choice": "rest"}}}
# L4: a hatched pet's first goal is a home of its own, and while wood advances it rest is not offered.
JEV_WOOD = {"answers": {"purpose": {"choice": "gather_wood"}}}


class FakeHttp:
    """Answers by URL; an exception is raised instead of returned."""

    def __init__(self, answers):
        self.answers, self.urls = answers, []

    def __call__(self, url, headers, body, timeout):
        self.urls.append(url)
        answer = self.answers[url]
        if isinstance(answer, Exception):
            raise answer
        return answer


class HeldExecutor:
    """Keeps submitted work until the test runs it, like a slow model call."""

    def __init__(self):
        self.held = []
        self.shut = False

    def submit(self, fn, *args):
        future = Future()
        self.held.append((future, fn, args))
        return future

    def shutdown(self, wait=True, cancel_futures=False):
        self.shut = True

    def run(self):
        for future, fn, args in self.held:
            future.set_result(fn(*args))
        self.held.clear()


class ChoosingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.path = self.registry.world_path(self.life)
        self.world = SurvivalWorld(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def brain(self):
        return self.world.state()["brain"]

    def chooser(self, env=None, answers=None, executor=None):
        return Chooser(env=env or {}, http=FakeHttp(answers or {}), executor=executor or InlineExecutor(),
                       rng=random.Random(1), scale=1.0)

    def ask(self, now, env, scale=1.0):
        return prepare(SurvivalWorld(self.path, read_only=True), now, scale, env)

    def test_without_keys_the_utility_picker_answers_at_once(self):
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        purpose = self.chooser().poll(self.registry, BORN + 1)
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["pending"]), (purpose, "utility", None))
        self.assertIn(self.world.state()["last_thought"], PURPOSES[purpose].thoughts)
        self.assertEqual(self.world.events(1)[0]["kind"], "purpose")
        self.assertEqual((brain["calls"]["model"], brain["last_call_at"]), (0, None))

    def test_jev_answers_in_the_background_and_the_answer_is_stored(self):
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        held = HeldExecutor()
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: JEV_WOOD}, held)
        self.assertIsNone(chooser.poll(self.registry, BORN + 1))
        self.assertIsNotNone(self.brain()["pending"])
        self.assertIsNone(chooser.poll(self.registry, BORN + 2))
        self.assertEqual(len(held.held), 1)
        held.run()
        self.assertEqual(chooser.poll(self.registry, BORN + 3), "gather_wood")
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["calls"]["model"], brain["last_call_at"]),
                         ("gather_wood", "jev", 1, BORN + 1))

    def test_the_gap_and_the_daily_caps_send_choices_to_utility(self):
        now = BORN + 100
        env = {"TYPESAFE_API_KEY": "k"}
        self.edit(lambda state: ensure_brain(state).update(last_call_at=now - 30))
        self.assertEqual(self.ask(now, env).route, "utility")
        self.edit(lambda state: mark_trigger(state, "hunger_30", now, urgent=True))
        self.assertEqual(self.ask(now, env).route, "jev")
        self.edit(lambda state: ensure_brain(state).update(last_call_at=now - 90))
        self.assertEqual(self.ask(now, {**env, "MIMO_MAX_DECISIONS_PER_DAY": "0"}).route, "utility")
        self.assertEqual(self.ask(now, {"OPENAI_API_KEY": "sk"}).route, "luna")
        self.assertEqual(self.ask(now, {"OPENAI_API_KEY": "sk", "MIMO_MAX_LUNA_DECISIONS_PER_DAY": "0"}).route,
                         "utility")
        self.assertEqual(self.ask(now, {}).route, "utility")

    def test_jev_can_make_up_to_the_configured_number_of_calls_per_rolling_game_hour(self):
        now = BORN + 5000
        env = {"TYPESAFE_API_KEY": "k"}
        gap = 60.0  # an hour split evenly across the default budget of 60
        sixty = [4990.0 - gap * index for index in range(60)]  # game seconds since birth, newest first

        def spent(state):
            ensure_brain(state).update(jev_calls=sixty, last_call_at=None)
            mark_trigger(state, "health_30", now, urgent=True)

        self.edit(spent)
        self.assertEqual(self.ask(now, env).route, "utility")  # the default budget (60) is spent
        self.assertEqual(self.ask(now, {**env, "MIMO_JEV_CALLS_PER_HOUR": "61"}).route, "jev")  # raised
        self.assertEqual(self.ask(now + gap, env).route, "jev")  # the oldest call left the hour
        self.assertEqual(self.ask(BORN + 83.4, env, scale=60.0).route, "utility")  # 5004 game s at 60x
        self.assertEqual(cap({}, JEV_HOUR_CAP), 60)
        self.assertEqual(cap({}, DECISION_CAP), 2000)

    def test_luna_stays_capped_at_eight_calls_per_rolling_game_hour(self):
        now = BORN + 5000
        env = {"OPENAI_API_KEY": "sk"}
        eight = [4990.0 - 400 * index for index in range(8)]  # game seconds since birth, newest first

        def spent(state):
            ensure_brain(state).update(luna_calls=eight, last_call_at=None)
            mark_trigger(state, "health_30", now, urgent=True)

        self.edit(spent)
        self.assertEqual(self.ask(now, env).route, "utility")
        self.assertEqual(self.ask(now, {**env, "MIMO_LUNA_CALLS_PER_HOUR": "9"}).route, "luna")  # raised
        self.assertEqual(self.ask(now + 2200, env).route, "luna")  # the oldest call left the hour
        self.assertEqual(cap({}, LUNA_HOUR_CAP), 8)

    def test_invalid_or_non_finite_env_values_fall_back_to_defaults(self):
        for setting in (DECISION_CAP, LUNA_CAP, JEV_HOUR_CAP, LUNA_HOUR_CAP):
            name, default = setting
            for junk in ("nan", "inf", "-inf", "abc", "1.5", ""):
                self.assertEqual(cap({name: junk}, setting), default, (name, junk))

    def test_a_short_purpose_ending_routinely_is_rechosen_by_utility(self):
        now = BORN + 100
        env = {"TYPESAFE_API_KEY": "k"}

        def ended(last, *reasons):
            def change(state):
                ensure_brain(state).update(last_chosen=last, pending={"id": 9, "reasons": list(reasons),
                                                                     "since": now, "urgent": False})
            return change

        for last in ("rest", "explore", "eat", "go_home"):
            self.edit(ended(last, "plan_done", "idle"))
            self.assertEqual(self.ask(now, env).route, "utility", last)
        self.edit(ended("rest", "reflex_ended"))
        self.assertEqual(self.ask(now, env).route, "utility")
        for reason in ("dawn", "dusk", "discovery", "hello", "plan_failed", "hour", "hunger_50"):
            self.edit(ended("rest", "plan_done", reason))
            self.assertEqual(self.ask(now, env).route, "jev", reason)
        self.edit(ended("gather_wood", "plan_done"))
        self.assertEqual(self.ask(now, env).route, "jev")

    def test_jev_calls_are_remembered_in_game_time_for_one_game_hour(self):
        self.edit(lambda state: ensure_brain(state).update(jev_calls=[10.0, 2000.0]))
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: JEV_REST})
        chooser.poll(self.registry, BORN + 4000)
        self.assertEqual(self.brain()["jev_calls"], [2000.0, 4000.0])
        self.assertEqual(self.brain()["luna_calls"], [])
        self.assertEqual(self.brain()["last_chosen"], "rest")

    def test_a_failed_model_call_falls_back_to_utility_is_counted_and_logged_once(self):
        forget_logged()
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: ModelError("request failed: down")})
        with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
            self.assertIsNotNone(chooser.poll(self.registry, BORN + 1))
        self.assertEqual(len(logs.output), 1)
        brain = self.brain()
        self.assertEqual((brain["picker"], brain["calls"]["model"], brain["last_call_at"]), ("utility", 1, BORN + 1))

    def test_a_hung_model_call_is_given_up_and_utility_answers_in_its_place(self):
        forget_logged()
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        stuck, fresh = HeldExecutor(), []

        def new_executor():
            fresh.append(InlineExecutor())
            return fresh[-1]

        chooser = Chooser(env={"TYPESAFE_API_KEY": "k"}, http=FakeHttp({JEV_URL: JEV_WOOD}), executor=stuck,
                          rng=random.Random(1), scale=1.0, executor_factory=new_executor)
        self.assertIsNone(chooser.poll(self.registry, BORN + 1))
        self.assertIsNone(chooser.poll(self.registry, BORN + 36))  # 35 s: Jev's 20 s timeout plus 15 s
        with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
            self.assertIsNotNone(chooser.poll(self.registry, BORN + 36.5))
        self.assertEqual(len(logs.output), 1)
        brain = self.brain()
        self.assertEqual((brain["pending"], brain["picker"], brain["calls"]["model"], brain["last_call_at"]),
                         (None, "utility", 1, BORN + 1))
        self.assertEqual((stuck.shut, len(fresh)), (True, 1))
        self.edit(lambda state: mark_trigger(state, "hello", BORN + 200))
        self.assertEqual(chooser.poll(self.registry, BORN + 200), "gather_wood")  # new work skips the stuck thread
        self.assertEqual(self.brain()["picker"], "jev")

    def test_the_wait_for_a_model_covers_its_timeouts_and_a_reflection(self):
        def ask(route, reflect=False):
            return Ask(1, route, reflect, (), {}, 0.0)

        self.assertEqual((deadline(ask("jev")), deadline(ask("luna")), deadline(ask("jev", True))), (35.0, 60.0, 80.0))

    def test_a_stale_answer_is_thrown_away_but_its_calls_count(self):
        ask = self.ask(BORN + 1, {"TYPESAFE_API_KEY": "k"})
        self.edit(lambda state: mark_trigger(state, "health_50", BORN + 2, urgent=True))
        choice = Choice("rest", "jev", "Hm.", {"model": 1, "luna": 0, "reflections": 0})
        self.assertIsNone(store_choice(self.world, ask, choice, BORN + 3))
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["calls"]["model"]), (None, 1))
        self.assertEqual(self.world.events(1)[0]["kind"], "birth")

    def test_a_purpose_event_is_logged_only_for_a_new_purpose_or_a_models_new_thought(self):
        none = {"model": 0, "luna": 0, "reflections": 0}

        def store(pending_id, choice, at):
            """The purpose events the choice logged."""
            def waiting(state):
                ensure_brain(state).update(pending={"id": pending_id, "reasons": ["plan_done"], "since": at,
                                                    "urgent": False}, purpose=None)
            self.edit(waiting)
            before = {event["id"] for event in self.world.events(50)}
            store_choice(self.world, self.ask(at, {}), choice, at)
            return [event["text"] for event in self.world.events(50) if event["id"] not in before]

        self.assertEqual(len(store(5, Choice("rest", "utility", "Hm.", none), BORN + 1)), 1)
        self.assertEqual(store(6, Choice("rest", "utility", "Hm.", none), BORN + 2), [])
        self.assertEqual(store(7, Choice("rest", "jev", "Hm.", {**none, "model": 1}), BORN + 3), [])
        self.assertEqual(store(8, Choice("rest", "jev", "Ahh.", {**none, "model": 1}), BORN + 4),
                         ['Pip decided to rest. "Ahh."'.replace("Pip", self.life["name"])])
        self.assertEqual(len(store(9, Choice("explore", "utility", "Go.", none), BORN + 5)), 1)
        self.assertEqual(self.brain()["last_chosen"], "explore")

    def test_a_dead_life_is_left_alone(self):
        ask = self.ask(BORN + 1, {})
        self.edit(lambda state: state.update(died_at=BORN + 2, cause="fall"))
        self.assertIsNone(self.ask(BORN + 3, {}))
        self.assertIsNone(store_choice(self.world, ask, Choice("rest", "utility", "Hm.", {"model": 0, "luna": 0,
                                                                                          "reflections": 0}), BORN + 3))

    def test_reflections_ride_with_hello_choices_up_to_twelve_a_day(self):
        env = {"TYPESAFE_API_KEY": "k", "OPENAI_API_KEY": "sk"}
        reflection = {"choices": [{"finish_reason": "stop", "message": {"content": '{"thought": "Hello, friend!"}'}}]}
        self.edit(lambda state: mark_trigger(state, "hello", BORN + 1))
        self.chooser(env, {JEV_URL: JEV_REST, LUNA_URL: reflection}).poll(self.registry, BORN + 1)
        brain = self.brain()
        self.assertEqual(self.world.state()["last_thought"], "Hello, friend!")
        self.assertEqual((brain["calls"]["model"], brain["calls"]["luna"], brain["calls"]["reflections"]), (1, 1, 1))

        def spent(state):
            mark_trigger(state, "hello", BORN + 100)
            state["brain"]["calls"]["reflections"] = 12

        self.edit(spent)
        self.chooser(env, {JEV_URL: JEV_REST, LUNA_URL: reflection}).poll(self.registry, BORN + 100)
        self.assertIn(self.world.state()["last_thought"], PURPOSES["rest"].thoughts)

    def test_a_new_purpose_clears_the_plan_and_stops_a_wait(self):
        def busy(state):
            ensure_brain(state).update(purpose="explore", pending={"id": 7, "reasons": ["hour"], "since": BORN,
                                                                    "urgent": False})
            state["queue"] = [{"kind": "walk", "target": [1, 2, 3], "purpose": "explore"}]
            state["action"] = {"kind": "wait", "started_at": BORN, "ends_at": BORN + 60}

        self.edit(busy)
        ask = self.ask(BORN + 1, {})
        self.assertEqual(store_choice(self.world, ask, Choice("rest", "utility", "Hm.",
                                                              {"model": 0, "luna": 0, "reflections": 0}), BORN + 1), "rest")
        state = self.world.state()
        self.assertEqual((state["queue"], state["action"], state["brain"]["purpose"]), ([], None, "rest"))

    def test_a_new_purpose_keeps_cleanup_steps_whose_station_is_down(self):
        placed = {"kind": "place", "target": [1, 2, 3], "block": "crafting_table", "purpose": "craft_tools"}
        craft = {"kind": "craft", "recipe": "wooden_pickaxe", "purpose": "craft_tools"}
        mine_back = {"kind": "mine", "target": [1, 2, 3], "keep": True, "purpose": "craft_tools"}
        none = {"model": 0, "luna": 0, "reflections": 0}

        def crafting(queue, reflex=None):
            def change(state):
                ensure_brain(state).update(purpose="craft_tools", pending={"id": 7, "reasons": ["hour"],
                                                                            "since": BORN, "urgent": False})
                state["brain"]["reflex"] = reflex
                state["queue" if reflex is None else "action"] = queue if reflex is None else None
                state["brain"]["set_aside"] = queue if reflex else []
            return change

        for queue, kept in (([placed, craft, mine_back], []), ([craft, mine_back], [mine_back])):
            for reflex in (None, "warm_up"):
                self.edit(crafting(queue, reflex))
                store_choice(self.world, self.ask(BORN + 1, {}), Choice("rest", "utility", "Hm.", none), BORN + 1)
                state = self.world.state()
                self.assertEqual(state["brain"]["set_aside"] if reflex else state["queue"], kept)

    def test_a_new_purpose_wakes_mimo_from_a_sleep_it_took_while_waiting(self):
        def dozing(state):
            ensure_brain(state).update(pending={"id": 7, "reasons": ["plan_done"], "since": BORN, "urgent": False})
            state["action"] = {"kind": "sleep", "started_at": BORN}

        self.edit(dozing)
        ask = self.ask(BORN + 1, {})
        store_choice(self.world, ask, Choice("go_home", "utility", "Hm.", {"model": 0, "luna": 0, "reflections": 0}),
                     BORN + 1)
        state = self.world.state()
        self.assertIsNone(state["action"])
        self.assertEqual(state["recent_actions"][-1]["result"], "interrupted")

        def sleeping_on_purpose(state):
            ensure_brain(state).update(pending={"id": 8, "reasons": ["hour"], "since": BORN, "urgent": False})
            state["action"] = {"kind": "sleep", "started_at": BORN, "purpose": "sleep"}

        self.edit(sleeping_on_purpose)
        ask = self.ask(BORN + 2, {})
        store_choice(self.world, ask, Choice("rest", "utility", "Hm.", {"model": 0, "luna": 0, "reflections": 0}),
                     BORN + 2)
        self.assertEqual(self.world.state()["action"]["kind"], "sleep")

    def test_the_worker_ticks_the_brain_and_answers_its_triggers(self):
        line = run_once(self.registry, None, BORN + 1, mind=BRAIN, chooser=self.chooser())
        self.assertIn(self.life["name"], line)
        self.assertIsNotNone(self.brain()["purpose"])


if __name__ == "__main__":
    unittest.main()

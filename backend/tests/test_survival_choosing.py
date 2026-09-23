import random
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Choice, Chooser, InlineExecutor, prepare, store_choice
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

    def submit(self, fn, *args):
        future = Future()
        self.held.append((future, fn, args))
        return future

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

    def ask(self, now, env):
        return prepare(SurvivalWorld(self.path, read_only=True), now, 1.0, env)

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
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: JEV_REST}, held)
        self.assertIsNone(chooser.poll(self.registry, BORN + 1))
        self.assertIsNotNone(self.brain()["pending"])
        self.assertIsNone(chooser.poll(self.registry, BORN + 2))
        self.assertEqual(len(held.held), 1)
        held.run()
        self.assertEqual(chooser.poll(self.registry, BORN + 3), "rest")
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["picker"], brain["calls"]["model"], brain["last_call_at"]),
                         ("rest", "jev", 1, BORN + 1))

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

    def test_a_failed_model_call_falls_back_to_utility_is_counted_and_logged_once(self):
        forget_logged()
        tick_life(self.registry, BORN + 1, scale=1, mind=BRAIN)
        chooser = self.chooser({"TYPESAFE_API_KEY": "k"}, {JEV_URL: ModelError("request failed: down")})
        with self.assertLogs("backend.survival.choosing", level="ERROR") as logs:
            self.assertIsNotNone(chooser.poll(self.registry, BORN + 1))
        self.assertEqual(len(logs.output), 1)
        brain = self.brain()
        self.assertEqual((brain["picker"], brain["calls"]["model"], brain["last_call_at"]), ("utility", 1, BORN + 1))

    def test_a_stale_answer_is_thrown_away_but_its_calls_count(self):
        ask = self.ask(BORN + 1, {"TYPESAFE_API_KEY": "k"})
        self.edit(lambda state: mark_trigger(state, "health_50", BORN + 2, urgent=True))
        choice = Choice("rest", "jev", "Hm.", {"model": 1, "luna": 0, "reflections": 0})
        self.assertIsNone(store_choice(self.world, ask, choice, BORN + 3))
        brain = self.brain()
        self.assertEqual((brain["purpose"], brain["calls"]["model"]), (None, 1))
        self.assertEqual(self.world.events(1)[0]["kind"], "birth")

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

    def test_the_worker_ticks_the_brain_and_answers_its_triggers(self):
        line = run_once(self.registry, None, BORN + 1, mind=BRAIN, chooser=self.chooser())
        self.assertIn(self.life["name"], line)
        self.assertIsNotNone(self.brain()["purpose"])


if __name__ == "__main__":
    unittest.main()

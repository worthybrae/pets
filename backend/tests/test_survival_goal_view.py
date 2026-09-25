import hashlib
import os
import random
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import get_life, hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.choosing import Ask, decide
from backend.survival.goals import adopt_goal
from backend.survival.memory import know
from backend.survival.pickers import context_payload, options
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import ensure_brain
from backend.survival.trips import best_trip, start_trip
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_goal_choice import Recorder
from backend.tests.test_survival_goals import WOOD, goal_situation, only_goals
from backend.tests.test_survival_purposes import situation
from backend.tests.test_survival_trips import flat_ground, only_reasons, test_reason


class GoalPayloadTests(unittest.TestCase):
    def test_the_model_is_told_the_goal_its_progress_and_what_comes_next(self):
        with only_goals(WOOD):
            self.assertIsNone(context_payload(goal_situation(), [])["goal"])
            s = goal_situation("woodpile", inventory={"oak_log": 2})
            self.assertEqual(context_payload(s, [])["goal"], {
                "title": "A woodpile", "why": "Wood makes everything else.", "progress": 0.25,
                "next_steps": ["Carry 4 logs", "Make a pickaxe"], "days_on_it": 0})


class TripPayloadTests(unittest.TestCase):
    def setUp(self):
        flat_ground(self)

    def test_the_model_is_told_what_a_trip_would_look_for_where_and_why(self):
        with only_reasons(test_reason()):
            s = situation()
            payload = context_payload(s, [])
            self.assertIsNone(payload["trip"])
            [reason] = payload["explore_reasons"]
            self.assertEqual((reason["reason"], reason["why"], len(reason["directions"])), ("look for things", "I need them", 3))
            self.assertEqual(reason["directions"][0], {"direction": "east", "blocks": 64, "toward": "east land"})
            s.brain["purpose"] = "explore"
            start_trip(s.brain, best_trip(s), 5.0, "jev")
            self.assertEqual(context_payload(s, [])["trip"], {"reason": "things", "words": "look for things",
                                                               "why": "I need them", "direction": "east", "found": None})
            self.assertIsNone(payload["curiosity"])  # not tended yet
            s.brain["curiosity"] = {"value": 30.0, "new_at": None}
            self.assertEqual(context_payload(s, [])["curiosity"], {"level": 30, "feeling": "curious; nothing new yet"})

    def test_jev_picks_the_reason_in_the_same_call_as_the_purpose(self):
        with only_reasons(test_reason("wood", score=60.0), test_reason("iron", score=45.0)):
            s = situation()
            found = tuple(options(s))
        jev = Recorder({"answers": {"purpose": {"choice": "explore"}, "explore_reason": {"choice": "iron"}}})
        choice = decide(Ask(1, "jev", False, found, {}, 0.0), {"TYPESAFE_API_KEY": "k"}, jev, random.Random(1))
        self.assertEqual((choice.purpose, choice.picker, choice.trip.reason, choice.error), ("explore", "jev", "iron", None))
        self.assertEqual(choice.thought, "Heading east to look for iron. I need them.")
        [body] = jev.bodies
        asked = body["questions"]["explore_reason"]
        self.assertEqual(sorted(body["questions"]), ["explore_reason", "purpose"])
        self.assertRegex(asked["criteria"]["iron"], r"^Go and look for iron: I need them\. Now: east 64 blocks, east land; ")
        explore = tuple(option for option in found if option.name == "explore")
        rules = decide(Ask(2, "utility", False, explore, {}, 0.0), {}, jev, random.Random(1))
        self.assertEqual((rules.trip.reason, len(jev.bodies)), ("wood", 1))  # the rules' reason, and no call
        with only_reasons(test_reason("wood")):
            single = tuple(options(situation()))
        one = Recorder({"answers": {"purpose": {"choice": "explore"}}})
        self.assertEqual(decide(Ask(3, "jev", False, single, {}, 0.0), {"TYPESAFE_API_KEY": "k"}, one,
                                random.Random(1)).trip.reason, "wood")
        self.assertEqual(list(one.bodies[0]["questions"]), ["purpose"])  # one reason: nothing to ask


class GoalApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "mimo.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()
        hatch_egg()
        registry = LifeRegistry()
        self.life = registry.active_life()
        self.world = SurvivalWorld(registry.world_path(self.life))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_goal_and_its_day_plan_are_streamed_and_reading_them_writes_nothing(self):
        self.assertIsNone(get_mimo()["goal"])
        with self.world.transaction() as db:
            state = read_state(db)
            adopt_goal(state, "iron_tools", "jev", "I want iron tools.", 5.0)
            state["brain"]["goal"].update(progress=0.4, plan=[{"text": "Find iron ore", "done": True, "step": 2},
                                                              {"text": "Mine 3 iron ore", "done": False, "step": 3}])
            write_state(db, state)
        before = hashlib.sha256(self.world.path.read_bytes()).hexdigest()
        goal = get_mimo()["goal"]
        self.assertEqual(hashlib.sha256(self.world.path.read_bytes()).hexdigest(), before)
        self.assertEqual(goal, {"name": "iron_tools", "title": "Iron tools",
                                "why": "Stone only goes so far: an iron pickaxe digs anything and opens the way to "
                                       "better gear.",
                                "progress": 0.4, "picker": "jev", "since": 5.0,
                                "plan": [{"text": "Find iron ore", "done": True},
                                         {"text": "Mine 3 iron ore", "done": False}]})

    def test_curiosity_is_streamed_with_how_mimo_feels(self):
        self.assertIsNone(get_mimo()["curiosity"])  # not tended yet
        with self.world.transaction() as db:
            state = read_state(db)
            ensure_brain(state)["curiosity"] = {"value": 64.4, "at": 0.0, "new_at": None, "noticed_at": None,
                                                "seen": 0, "met_at": None}
            write_state(db, state)
        self.assertEqual(get_mimo()["curiosity"], {"level": 64, "feeling": "restless; nothing new yet"})

    def test_the_trip_is_streamed_while_mimo_explores(self):
        self.assertIsNone(get_mimo()["trip"])
        with self.world.transaction() as db:
            state = read_state(db)
            ensure_brain(state).update(purpose="explore", trip={"reason": "iron", "words": "look for iron",
                                                           "why": "my pickaxe needs it", "direction": "north",
                                                           "since": 1.0, "picker": "utility", "found": "a sinkhole",
                                                           "done": False})
            write_state(db, state)
        self.assertEqual(get_mimo()["trip"], {"reason": "iron", "words": "look for iron", "why": "my pickaxe needs it",
                                              "direction": "north", "found": "a sinkhole"})

    def test_the_memorial_lists_the_goals_reached_with_their_day(self):
        born = self.life["born_at"]
        with self.world.transaction() as db:
            know(db, "first_shelter", "goal", born + 100.0)
            know(db, "iron_tools", "goal", born + 3700.0)
            state = read_state(db)
            state.update(died_at=time.time(), cause="cold", status="dead")
            write_state(db, state)
        LifeRegistry().mark_dead(self.life["id"], time.time(), "cold")
        reached = [{"name": "first_shelter", "title": "A home of its own", "day": 1},
                   {"name": "iron_tools", "title": "Iron tools", "day": 2}]
        self.assertEqual(get_mimo()["last_life"]["goals_reached"], reached)
        self.assertEqual(get_life(self.life["id"])["goals_reached"], reached)
        self.assertEqual(get_life(1)["goals_reached"], [])  # the retired legacy life set none


if __name__ == "__main__":
    unittest.main()

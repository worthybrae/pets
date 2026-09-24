import json
import random
import sqlite3
import unittest
from unittest.mock import patch
from urllib.error import URLError

from backend.survival import brain  # noqa: F401  (registers every M3 purpose)
from backend.survival.actions import ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, mark_explored, remember
from backend.survival.models import ModelError, ask_jev, ask_luna, luna_reflect, post_json
from backend.survival.pickers import Option, context_payload, options, utility_pick
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
TREE = (5, 0, 0)
CHOICES = [Option("gather_wood", "gather wood", "Chop a tree.", "a tree 5 blocks away", 72.5),
           Option("rest", "rest", "Rest a while.", "mood 70", 15.0)]
PAYLOAD = {"name": "Pip", "traits": {"curiosity": 80}}


def forest():
    return Grid(lambda x, y, z: "oak_log" if (x, z) == (5, 0) and 1 <= y <= 4 else ("stone" if y <= 0 else "air"))


def situation(clock=DAY, places=(), **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell in places:
        remember(db, kind, cell, 0.0)
    return Situation(state, forest(), clock, 0.0, db)


def picks(s):
    """What the utility picker chooses for `s` under 20 different random seeds."""
    return {utility_pick(options(s), random.Random(seed)) for seed in range(20)}


class FakeHttp:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, body, timeout))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def luna_answer(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
@patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [TREE])
@patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [TREE])
class UtilityTests(unittest.TestCase):
    def test_a_day_goes_wood_then_tools_then_stone(self):
        self.assertEqual(picks(situation()), {"gather_wood"})
        self.assertEqual(picks(situation(inventory={"oak_log": 3})), {"craft_tools"})
        self.assertEqual(picks(situation(inventory={"oak_log": 4, "wooden_pickaxe": 1})), {"craft_tools"})  # a sword
        self.assertEqual(picks(situation(inventory={"oak_log": 4, "wooden_pickaxe": 1, "wooden_sword": 1})),
                         {"gather_stone"})

    def test_needs_come_first(self):
        self.assertEqual(picks(situation(NIGHT, places=[("home", (20, 1, 0))])), {"go_home"})
        self.assertEqual(picks(situation(NIGHT)), {"sleep"})
        hungry = situation(inventory={"berries": 2}, vitals={**START_VITALS, "hunger": 20.0})
        self.assertEqual(picks(hungry), {"eat"})

    def test_a_recent_failure_scores_thirty_lower(self):
        s = situation()
        before = {option.name: option.score for option in options(s)}
        s.brain["penalties"]["gather_wood"] = 100.0
        after = {option.name: option.score for option in options(s)}
        self.assertEqual(before["gather_wood"] - after["gather_wood"], 30.0)
        self.assertEqual(before["rest"], after["rest"])

    def test_the_model_payload_carries_needs_traits_places_and_events(self):
        s = situation(places=[("home", (3, 1, 4))], traits={"curiosity": 80})
        payload = context_payload(s, [{"text": f"event {n}"} for n in range(10)])
        self.assertEqual(set(payload), {"name", "traits", "mood", "vitals", "phase", "day", "inventory",
                                        "known_places", "recent_events", "trigger", "building", "exploration",
                                        "threats", "defense"})
        self.assertEqual(payload["building"], {"home": "found", "built": [], "blocks_short": 0,
                                               "shelter": "no shelter of its own yet; a small shelter would need 38 "
                                                          "blocks, carrying 0 (short 38)"})
        self.assertEqual(payload["known_places"], [{"kind": "home", "note": "", "distance": 5}])
        self.assertEqual(len(payload["recent_events"]), 8)
        self.assertEqual(payload["traits"], {"curiosity": 80})
        self.assertEqual(payload["trigger"], ["born"])
        exploration = payload["exploration"]
        self.assertEqual((exploration["explored_share"], exploration["last_new_ground_at"]), (0.0, None))
        self.assertEqual(exploration["found"], {"ore": 0, "water": 0, "food": 0, "farm": 0, "home": 1})
        self.assertEqual([set(way) for way in exploration["unexplored_directions"]], [{"direction", "blocks"}] * 3)

    def test_the_model_is_told_how_much_mimo_explored_and_which_way_is_new(self):
        s = situation(places=[("home", (3, 1, 4)), ("food", (30, 1, 0)), ("food", (-30, 1, 0))])
        mark_explored(s.db, [(rx, rz) for rx in range(-9, 9) for rz in range(-9, 9) if rz >= 0 or rx < 0], 0.0)
        s.brain["new_ground_at"] = -30.0
        exploration = context_payload(s, [])["exploration"]
        self.assertEqual([way["direction"] for way in exploration["unexplored_directions"]][0], "northeast")
        self.assertEqual(len(exploration["unexplored_directions"]), 3)
        self.assertGreater(exploration["explored_share"], 0.6)
        self.assertLess(exploration["explored_share"], 0.9)
        self.assertEqual(exploration["found"], {"ore": 0, "water": 0, "food": 2, "farm": 0, "home": 1})
        self.assertEqual(exploration["last_new_ground_at"], 30)
        self.assertLess(len(json.dumps(exploration)), 400)


class JevTests(unittest.TestCase):
    def test_jev_gets_one_choice_question_over_the_offered_purposes(self):
        http = FakeHttp({"answers": {"purpose": {"choice": "gather_wood"}}})
        self.assertEqual(ask_jev(PAYLOAD, CHOICES, {"TYPESAFE_API_KEY": "k"}, http), "gather_wood")
        url, headers, body, timeout = http.calls[0]
        self.assertEqual((url, headers["Authorization"], timeout), ("https://api.typesafe.ai/v1/systemone", "Bearer k", 20.0))
        self.assertEqual((body["model"], body["state"]), ("jev-latest", PAYLOAD))
        question = body["questions"]["purpose"]
        self.assertEqual((question["type"], sorted(question["criteria"])), ("choice", ["gather_wood", "rest"]))
        self.assertIn("a tree 5 blocks away", question["criteria"]["gather_wood"])

    def test_jev_answers_outside_the_choices_or_failures_raise(self):
        env = {"TYPESAFE_API_KEY": "k", "TYPESAFE_MODEL": "jev-9", "TYPESAFE_API_URL": "http://jev.test"}
        for answer in ({"answers": {"purpose": {"choice": "build_shelter"}}}, {"answers": {}},
                       ModelError("request failed: boom")):
            with self.assertRaises(ModelError, msg=answer):
                ask_jev(PAYLOAD, CHOICES, env, FakeHttp(answer))
        http = FakeHttp({"answers": {"purpose": {"choice": "rest"}}})
        ask_jev(PAYLOAD, CHOICES, env, http)
        self.assertEqual((http.calls[0][0], http.calls[0][2]["model"]), ("http://jev.test", "jev-9"))


class LunaTests(unittest.TestCase):
    def test_luna_picks_with_structured_output_limited_to_the_choices(self):
        http = FakeHttp(luna_answer('{"purpose": "rest"}'))
        self.assertEqual(ask_luna(PAYLOAD, CHOICES, {"OPENAI_API_KEY": "sk"}, http), "rest")
        url, headers, body, timeout = http.calls[0]
        self.assertEqual((url, headers["Authorization"], timeout, body["model"]),
                         ("https://api.openai.com/v1/chat/completions", "Bearer sk", 45.0, "gpt-6-luna"))
        schema = body["response_format"]["json_schema"]
        self.assertTrue(schema["strict"])
        self.assertEqual(schema["schema"]["properties"]["purpose"]["enum"], ["gather_wood", "rest"])
        fenced = FakeHttp(luna_answer('```json\n{"purpose": "gather_wood"}\n```'))
        self.assertEqual(ask_luna(PAYLOAD, CHOICES, {"OPENAI_API_KEY": "sk"}, fenced), "gather_wood")

    def test_bad_luna_answers_raise_and_reflections_are_one_short_line(self):
        env = {"OPENAI_API_KEY": "sk"}
        for answer in (luna_answer('{"purpose": "fish"}'), luna_answer("not json"),
                       {"choices": [{"finish_reason": "length", "message": {"content": ""}}]}, {"oops": 1}):
            with self.assertRaises(ModelError, msg=answer):
                ask_luna(PAYLOAD, CHOICES, env, FakeHttp(answer))
        long = "What   a\nlovely tree. " * 20
        thought = luna_reflect(PAYLOAD, CHOICES[0], env, FakeHttp(luna_answer(json.dumps({"thought": long}))))
        self.assertEqual(len(thought), 160)
        self.assertTrue(thought.startswith("What a lovely tree. What a lovely tree."))
        with self.assertRaises(ModelError):
            luna_reflect(PAYLOAD, CHOICES[0], env, FakeHttp(luna_answer('{"thought": "  "}')))

    def test_post_json_turns_network_errors_into_model_errors(self):
        with patch("backend.survival.models.urlopen", side_effect=URLError("down")):
            with self.assertRaises(ModelError):
                post_json("http://example.test", {}, {}, 1.0)


if __name__ == "__main__":
    unittest.main()

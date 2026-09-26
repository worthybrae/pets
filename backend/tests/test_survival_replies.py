import random
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.replies import (
    MOOD, MOOD_LINES, REPLIES, REPLY_LIMIT, SHOWN, Heard, candidates, clip, first_person, gerund, reply_options,
    rules_pick,
)
from backend.survival.situation import from_db
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
NOW = BORN + 300


def sentences(text):
    return [part for part in re.split(r"(?<=[.!?])(?<!\.\.\.)\s+", text) if part]


class ReplyWordsTests(unittest.TestCase):
    def test_a_reply_is_at_most_two_sentences_and_two_hundred_characters(self):
        self.assertEqual(clip("One.  Two!\nThree? Four."), "One. Two!")
        self.assertEqual(clip("Mmm... so cozy. Talk later? Bye."), "Mmm... so cozy. Talk later?")
        long = clip("word " * 100)
        self.assertLessEqual(len(long), REPLY_LIMIT)
        self.assertTrue(long.endswith("..."))

    def test_events_in_mimos_own_voice_and_purposes_as_doing_words(self):
        self.assertEqual(first_person("Pip met its first skitter.", "Pip"), "I met my first skitter.")
        self.assertEqual(first_person("Pip is starving.", "Pip"), "I am starving.")
        self.assertEqual(first_person("A sapling grew into a tree.", "Pip"), "A sapling grew into a tree.")
        self.assertEqual(gerund("gather wood"), "gathering wood")
        self.assertEqual(gerund("explore"), "exploring")
        self.assertEqual(gerund("put things away"), "putting things away")
        self.assertEqual(gerund("drop what it cannot use"), "dropping what I cannot use")
        self.assertEqual(gerund("go home"), "going home")

    def test_the_table_has_a_line_for_every_mood_and_doing(self):
        for band in ("happy", "okay", "low"):
            for doing in ("sleep", "food", "build", "explore", "work", "rest", "danger", "idle"):
                self.assertLessEqual(len(sentences(MOOD_LINES[(band, doing)])), 2)


class ReplyTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            ensure_brain(state)
            change(state, db)
            write_state(db, state)

    def replies(self, text, **known):
        heard = Heard(text, **known)
        with self.world.connect() as db:
            s = from_db(db, read_state(db), NOW, 1.0)
            found = candidates(s, heard)
        return found, heard

    def test_at_most_six_lines_each_short_with_the_table_line_among_them(self):
        found, _ = self.replies("hello there, how are you doing? any news?")
        self.assertLessEqual(len(found), SHOWN)
        self.assertIn(MOOD, [reply.topic for reply in found])
        for reply in found:
            self.assertLessEqual(len(reply.text), REPLY_LIMIT)
            self.assertLessEqual(len(sentences(reply.text)), 2, reply.text)
        options = reply_options(found)
        self.assertEqual([option.name for option in options], [reply.topic for reply in found])
        self.assertTrue(options[0].description.startswith('Say: "'))

    def test_the_rules_answer_what_the_words_ask_about_else_with_the_table(self):
        found, heard = self.replies("How are you feeling?")
        self.assertEqual(rules_pick(found, heard), "feel")
        found, heard = self.replies("What are you doing?")
        self.assertEqual(rules_pick(found, heard), "doing")
        found, heard = self.replies("purple elephants")
        self.assertEqual(rules_pick(found, heard), MOOD)
        found, heard = self.replies("My name is Sam!")
        self.assertEqual(rules_pick(found, heard), "name_ack")
        self.assertEqual(found[0].text, "Nice to meet you, Sam! I'll remember that.")

    def test_how_it_feels_and_the_table_follow_its_vitals_mood_and_doing(self):
        def hungry_and_working(state, db):
            state["vitals"].update(hunger=20, energy=50, mood=80)
            state["brain"]["purpose"] = "gather_wood"
        self.edit(hungry_and_working)
        found, _ = self.replies("how do you feel")
        lines = {reply.topic: reply.text for reply in found}
        self.assertEqual(lines["feel"], "I'm really hungry and a little tired, but happy.")
        self.assertEqual(lines[MOOD], MOOD_LINES[("happy", "work")])

    def test_the_owners_name_and_the_bond_set_the_greeting(self):
        self.edit(lambda state, db: state["brain"].update(purpose="gather_wood"))
        texts = {bond: {reply.topic: reply.text for reply in self.replies("hi!", owner="Sam", bond=bond)[0]}["greet"]
                 for bond in (10.0, 40.0, 80.0)}
        self.assertEqual(texts[10.0], "Oh, hello, Sam. I'm gathering wood.")
        self.assertEqual(texts[40.0], "Hi, Sam! I'm gathering wood.")
        self.assertEqual(texts[80.0], "Sam, I missed you! I'm gathering wood.")

    def test_what_it_is_doing_says_why(self):
        def exploring(state, db):
            state["brain"].update(purpose="explore", trip={"reason": "iron", "words": "look for iron",
                                                         "why": "my pickaxe needs it", "direction": "north"})
        self.edit(exploring)
        lines = {reply.topic: reply.text for reply in self.replies("what are you up to")[0]}
        self.assertEqual(lines["doing"], "I'm exploring to look for iron. My pickaxe needs it.")

    def test_its_goal_todays_plan_and_the_newest_notable_thing(self):
        def goal_and_news(state, db):
            state["brain"]["goal"] = {"name": "iron_tools", "since": BORN, "picker": "utility", "progress": 0.4,
                                      "plan": [{"text": "Find iron ore", "done": True, "step": 2},
                                               {"text": "Mine 3 iron ore", "done": False, "step": 3},
                                               {"text": "Make an iron pickaxe", "done": False, "step": 4}]}
            log_event(db, NOW - 100, "found", f"{state['name']} met its first skitter.")
        self.edit(goal_and_news)
        found, _ = self.replies("what's your goal and plan for today? any news?")
        lines = {reply.topic: reply.text for reply in found}
        self.assertEqual(lines["goal"], "I'm working toward iron tools: 40% done. Next: mine 3 iron ore.")
        self.assertEqual(lines["plan"], "Today I want to mine 3 iron ore and make an iron pickaxe.")
        self.assertEqual(lines["news"], "Guess what? I met my first skitter.")

    def test_a_close_mimo_shares_its_news_unasked(self):
        self.edit(lambda state, db: log_event(db, NOW - 100, "found", f"{state['name']} met its first skitter."))
        found, heard = self.replies("purple elephants", bond=80.0)
        self.assertEqual(rules_pick(found, heard), "news")
        found, heard = self.replies("purple elephants", bond=40.0)
        self.assertEqual(rules_pick(found, heard), MOOD)

    def test_what_it_remembers_and_asks_about_the_owner(self):
        lines = {reply.topic: reply.text for reply in self.replies("do you remember me?")[0]}
        self.assertEqual(lines.get("ask_back"), "What should I call you?")
        lines = {reply.topic: reply.text for reply in self.replies(
            "do you remember me?", owner="Sam", facts=(("likes", "the lake"), ("name", "Sam")))[0]}
        self.assertEqual(lines["remember"], "I remember you like the lake!")
        self.assertNotIn("ask_back", lines)

    def test_what_it_learned_once_the_journal_is_in(self):
        self.edit(lambda state, db: know(db, "gravel", "lesson", NOW - 5))
        journal = types.ModuleType("backend.survival.journal")
        journal.LESSONS = {"gravel": types.SimpleNamespace(fact="Gravel sometimes hides flint.")}
        with patch.dict(sys.modules, {"backend.survival.journal": journal}):
            lines = {reply.topic: reply.text for reply in self.replies("what did you learn?")[0]}
        self.assertEqual(lines["journal"], "I learned something new: gravel sometimes hides flint.")

    def test_a_writer_that_crashes_is_left_out_and_logged_once(self):
        def broken(s, heard):
            raise RuntimeError("boom")
        with patch.dict(REPLIES, {"feel": broken}):
            with self.assertLogs("backend.survival.replies", level="ERROR") as logs:
                found, _ = self.replies("how are you")
                self.replies("how are you")
        self.assertNotIn("feel", [reply.topic for reply in found])
        self.assertEqual(len(logs.records), 1)


if __name__ == "__main__":
    unittest.main()

import random
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival.goals import GOALS
from backend.survival.hatch import hatch
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.replies import (
    MOOD, MOOD_LINES, REPLIES, REPLY_LIMIT, SHOWN, Heard, Reply, candidates, clip, echoed, first_person, gerund,
    goal_line, reply_options, rules_pick, voiced,
)
from backend.survival.situation import from_db
from backend.survival.triggers import ensure_brain
from backend.survival.trips import REASONS
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
NOW = BORN + 300
# A line that speaks of Mimo as "it" or in a broken first person.
LEAK = re.compile(r"\bits\b|\bit (knows|has|does|is)\b|\bI (knows|has|does|is)\b")
VERB_TITLED = {"armor_up", "cave", "far_hills", "map_land", "new_creature", "new_land", "water"}


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

    def test_mimos_own_texts_are_said_in_its_own_voice(self):
        self.assertEqual(voiced("travel past the lands it knows"), "travel past the lands I know")
        self.assertEqual(voiced("A home of its own"), "A home of my own")
        self.assertEqual(voiced("Meet a creature it has never met"), "Meet a creature I have never met")
        self.assertEqual(voiced("Find water it does not know"), "Find water I do not know")
        self.assertEqual(voiced("Find a site for it"), "Find a site for it")  # the site's "it" is not Mimo
        self.assertEqual(gerund("come home from its expedition"), "coming home from my expedition")
        texts = ([reason.words for reason in REASONS.values()] + [purpose.phrase for purpose in PURPOSES.values()]
                 + [goal.title for goal in GOALS.values()]
                 + [milestone.text for goal in GOALS.values() for milestone in goal.milestones])
        for text in texts:
            self.assertIsNone(LEAK.search(voiced(text)), f"{text!r} -> {voiced(text)!r}")

    def test_a_line_is_quoted_for_jev_without_nested_quotes(self):
        [option] = reply_options([Reply("like_ack", 'Ooh, the "big" lake? I\'ll remember that you like it.')])
        self.assertEqual(option.description, 'Say: "Ooh, the \'big\' lake? I\'ll remember that you like it."')
        self.assertEqual(option.phrase, 'Ooh, the "big" lake? I\'ll remember that you like it.')

    def test_the_owners_words_are_turned_around_when_mimo_says_them(self):
        for said, echo in (("watching you explore", "watching me explore"), ("your little house", "my little house"),
                           ("it when you get hurt", "it when I get hurt"), ("when you're sad", "when I'm sad"),
                           ("when you are sad", "when I am sad"), ("talking to you", "talking to me"),
                           ("my dog", "your dog"), ("I work nights", "you work nights"),
                           ("I am from Leeds", "you are from Leeds"), ("the lake", "the lake")):
            self.assertEqual(echoed(said), echo, said)

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
        self.assertEqual(lines["doing"], "I'm heading north to look for iron. My pickaxe needs it.")

    def test_on_the_expedition_every_line_speaks_as_i_and_the_why_is_not_said_twice(self):
        def trekking(state, db):
            state["brain"].update(purpose="explore", reflex=None, trip={
                "reason": "expedition", "words": "travel past the lands it knows", "direction": "east",
                "why": "I want to see what lies past the lands I know"})
            state["brain"]["goal"] = {"name": "expedition", "since": BORN, "picker": "jev", "progress": 0.35,
                                      "plan": [{"text": "Pack food and torches", "done": True, "step": 0},
                                               {"text": "Travel past the lands it knows", "done": False, "step": 1},
                                               {"text": "Come home with its finds", "done": False, "step": 2}]}
        self.edit(trekking)
        for text in ("hi!", "what are you doing?", "what's your goal?", "what's the plan for today?"):
            found, _ = self.replies(text)
            for reply in found:
                self.assertNotIn(" it knows", reply.text)
                self.assertNotIn(" its ", f" {reply.text} ")
                self.assertIsNone(LEAK.search(reply.text), reply.text)
        lines = {reply.topic: reply.text for reply in self.replies("where are you going?")[0]}
        self.assertEqual(lines["doing"], "I'm heading east to travel past the lands I know.")
        self.assertEqual(lines["plan"], "Today I want to travel past the lands I know and come home with my finds.")

    def test_the_rules_answer_common_lines_with_the_topic_they_ask_about(self):
        def trekking(state, db):
            state["vitals"].update(hunger=55, energy=45, mood=62)
            state["brain"].update(purpose="explore", reflex=None, trip={
                "reason": "expedition", "words": "travel past the lands it knows", "direction": "east",
                "why": "I want to see what lies past the lands I know"})
            state["brain"]["goal"] = {"name": "expedition", "since": BORN, "picker": "jev", "progress": 0.35,
                                      "plan": [{"text": "Travel past the lands it knows", "done": False, "step": 1}]}
            log_event(db, NOW - 100, "found", f"{state['name']} met its first skitter.")
        self.edit(trekking)
        for text, topic in (("hi Pebble!", "greet"), ("I'm back!", "greet"), ("how are you feeling?", "feel"),
                            ("how's it going?", "feel"), ("what are you up to?", "doing"),
                            ("where are you going?", "doing"), ("what\u2019s your goal?", "goal"),
                            ("what's the plan for today?", "plan"), ("any news?", "news"),
                            ("tell me about your day", "news"), ("what did you learn lately?", "journal"),
                            ("what's the capital of France?", MOOD), ("good night!", "farewell"), ("bye", "farewell"),
                            ("see you later", "farewell"), ("good job!", "affection"), ("do you like me?", "affection"),
                            ("thanks for waiting for me", "welcome"), ("what do you like?", "fond"),
                            ("are you scared of the dark?", "fond"), ("what's your name?", "self"),
                            ("do you know my name?", "ask_back")):
            found, heard = self.replies(text)
            self.assertEqual(rules_pick(found, heard), topic, text)
        lines = {reply.topic: reply.text for reply in self.replies("good night!", owner="Sam")[0]}
        self.assertEqual(lines["farewell"], "Good night, Sam! Sleep well.")
        found, heard = self.replies("do you know my name?", owner="Sam", facts=(("name", "Sam"),))
        self.assertEqual((rules_pick(found, heard), found[0].text), ("remember", "Of course! You're Sam."))
        found, heard = self.replies("do you know my name?")
        self.assertEqual(found[0].text, "Not yet! What should I call you?")
        found, heard = self.replies("what did you learn lately?")
        self.assertEqual(found[0].text, "Nothing new yet. I'm still looking!")
        self.assertNotIn("journal", [reply.topic for reply in self.replies("hi!")[0]])  # not said unasked

    def test_every_goal_line_is_grammatical(self):
        for name, goal in GOALS.items():
            def working(state, db, name=name, goal=goal):
                state["brain"]["goal"] = {"name": name, "since": BORN, "picker": "rules", "progress": 0.1,
                                          "plan": [{"text": milestone.text, "done": False, "step": step}
                                                   for step, milestone in enumerate(goal.milestones)]}
            self.edit(working)
            with self.world.connect() as db:
                line = goal_line(from_db(db, read_state(db), NOW, 1.0), Heard("goal?"))
            self.assertRegex(line, r"^I'm working (toward|to) ")
            self.assertIsNone(LEAK.search(line), line)
            self.assertTrue(line.startswith("I'm working to " if name in VERB_TITLED else "I'm working toward "), line)

    def test_what_the_owner_likes_is_said_back_in_mimos_words(self):
        for text, like in (("I like your little house", "Ooh, my little house? I'll remember that you like it."),
                           ("I love watching you explore!", "Ooh, watching me explore? I'll remember that you like it."),
                           ("I hate it when you get hurt", "You don't like it when I get hurt? I'll remember that."),
                           ("I dont like the dark", "You don't like the dark? I'll remember that."),
                           ("I cant stand spiders", "You don't like spiders? I'll remember that."),
                           ("I love you so much", None), ("I love you too", None), ("I like it here", None)):
            found, heard = self.replies(text)
            lines = {reply.topic: reply.text for reply in found}
            self.assertEqual(lines.get("like_ack"), like, text)
        found, heard = self.replies("I love you so much")
        self.assertEqual(rules_pick(found, heard), "affection")

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
        for facts, said in (((("about", "I work nights."),), "I remember you said you work nights."),
                            ((("likes", "watching you explore"),), "I remember you like watching me explore!"),
                            ((("dislikes", "it when you get hurt"),), "I remember you don't like it when I get hurt.")):
            lines = {reply.topic: reply.text for reply in self.replies("do you remember me?", facts=facts)[0]}
            self.assertEqual(lines["remember"], said)
            self.assertNotIn('"', said)

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

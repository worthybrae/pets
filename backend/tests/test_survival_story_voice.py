"""Bond's final fix wave, group 1: the story and the inbox tell the day truly, in Mimo's voice.

I2 (the plan of the goal it names), m15 (a promise kept, a day's goals in one sentence, ranked), m3
(danger by kind), I1's meals and the computer told once, m1 (a seed hatching), m2 (one table of bond
levels), m16 (a long absence told whole), I4 (a present owner's closing), and the chat's news for an
owner asking about the day.
"""

import json
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival import bonding  # noqa: F401  (every Bond writer registers)
from backend.survival import brain  # noqa: F401  (every machine registers, the computer among them)
from backend.survival.bond import FEELINGS, visit
from backend.survival.choosing import InlineExecutor
from backend.survival.diary import day_highlights, rules_story, story_job
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.machines import MACHINES, title_of
from backend.survival.owner_facts import remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.replies import CLOSE, SHY, Heard, news
from backend.survival.situation import from_db
from backend.survival.talker import Talker, run_chores
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0  # a game day is a real minute
LUNA = {"MIMO_MODEL_API_KEY": "k", "MIMO_MODEL_URL": "https://luna.test/v1/chat/completions"}


def day(events, name="Pip", brain=None, until=None, kept=None):
    """One day's highlight sentences for events given as (kind, text)."""
    found = [{"id": number + 1, "at": BORN + number, "kind": kind, "text": text, "day": 1}
             for number, (kind, text) in enumerate(events)]
    extra = {key: value for key, value in (("until", until), ("kept", kept)) if value is not None}
    return [text for _, text in day_highlights(found, {"name": name, "brain": brain or {}}, **extra)]


class HighlightTests(unittest.TestCase):
    def test_the_plan_told_is_the_days_last_and_belongs_to_the_goal_it_names(self):
        """I2: plan A, then a new goal B and B's plan: the story tells B's steps, never A's."""
        found = day([("plan", "Pip's plan for today: fit bars, a hatch, a seat and a sign."),
                     ("plan", 'Pip set a new goal: an expedition. "Off I go."'),
                     ("plan", "Pip's plan for today: pack food and torches, travel past the lands it knows.")])
        self.assertIn("I set myself a new goal: an expedition.", found)
        self.assertIn("My plan was to pack food and torches, travel past the lands I know.", found)
        self.assertFalse(any("fit bars" in text for text in found), found)

    def test_a_plan_overtaken_by_a_new_goal_or_a_goal_reached_is_left_out(self):
        self.assertFalse(any(text.startswith("My plan") for text in day(
            [("plan", "Pip's plan for today: fit bars, a hatch, a seat and a sign."),
             ("plan", 'Pip set a new goal: an expedition. "Off I go."')])))
        self.assertFalse(any(text.startswith("My plan") for text in day(
            [("plan", "Pip's plan for today: gather wood."), ("goal", "Pip reached a goal: a home of its own.")])))

    def test_no_progress_line_for_a_goal_taken_up_after_the_day_told(self):
        """I2: the goal chosen at this dawn is no part of yesterday's story; one taken up before is, said now."""
        brain = {"goal": {"name": "iron_tools", "progress": 0.4, "plan": [], "since": BORN + 100}}
        self.assertEqual(day([], brain=brain, until=BORN + 60), [])
        self.assertEqual(day([], brain=brain, until=BORN + 160), ["Now I'm working toward iron tools: 40% done."])
        herd = {"goal": {"name": "herd", "progress": 0.5, "plan": [], "since": BORN}}
        self.assertEqual(day([], brain=herd, until=BORN + 60), ["Now I'm working toward a herd of my own: 50% done."])

    def test_a_promise_kept_leads_and_a_days_goals_share_one_sentence(self):
        """m15: the promise first, the other goals in one sentence, a goal set and reached that day not "set"."""
        found = day([("plan", 'Pip set a new goal: look into a cave. "Caves!"'),
                     ("goal", "Pip reached a goal: a home of its own."),
                     ("goal", "Pip reached a goal: look into a cave."),
                     ("goal", "Pip reached a goal: iron tools."),
                     ("goal", "Pip reached a goal: iron tools.")],
                    kept={3: "You asked me to look into a cave, and I did it!"})
        self.assertEqual(found, ["You asked me to look into a cave, and I did it!",
                                 "I reached two goals: a home of my own and iron tools."])

    def test_one_days_story_keeps_its_most_telling_highlights(self):
        """m15: ranked as a long absence's are, not the first four in time."""
        found = day([("ate", "Pip ate bread."), ("plan", "Pip's plan for today: gather wood."),
                     ("threat", "Pip saw a gloomling coming."), ("found", "Pip met its first skitter."),
                     ("built", "Pip finished building Pip's Round Cottage and moved in."),
                     ("goal", "Pip reached a goal: a home of its own.")])
        self.assertEqual(found[:4], ["I reached a goal: a home of my own.",
                                     "I finished building my Round Cottage and moved in.",
                                     "I met my first skitter.", "I saw a gloomling coming, but I kept safe."])

    def test_danger_is_told_by_what_it_was(self):
        """m3: never "some danger, but I kept safe" after a fall that hurt, starving or freezing."""
        self.assertEqual(day([("fall", "Pip fell 4 blocks and got hurt.")]), ["I fell and got hurt."])
        self.assertEqual(day([("starving", "Pip is starving.")]), ["I got very hungry."])
        self.assertEqual(day([("freezing", "Pip is freezing.")]), ["I got very cold."])
        self.assertEqual(day([("trapped", "Pip is stuck in a pit and starts digging out.")]),
                         ["I got stuck in a pit and had to dig my way out."])
        self.assertEqual(day([("hurt", "Pip was hit by a gloomling."), ("hurt", "Pip was hit by a gloomling."),
                              ("fall", "Pip fell 4 blocks and got hurt.")]),
                         ["A gloomling hit me twice, but I made it through."])

    def test_meals_are_told_by_food_and_never_claim_a_count_the_list_does_not_show(self):
        """I1 (live finding 1): "1 raw rabbit it had no room to carry" is raw rabbit, and five meals list five."""
        self.assertEqual(day([("ate", "Pip ate 1 raw rabbit it had no room to carry.")]), ["I ate raw rabbit."])
        self.assertEqual(day([("ate", "Pip ate bread."), ("ate", "Pip ate cooked fish."), ("ate", "Pip ate bread."),
                              ("ate", "Pip ate 1 raw rabbit it had no room to carry."), ("ate", "Pip ate bread.")]),
                         ["I ate five meals: bread three times, cooked fish and raw rabbit."])
        self.assertEqual(day([("ate", "Pip ate bread."), ("ate", "Pip ate cooked fish."), ("ate", "Pip ate bread."),
                              ("ate", "Pip ate apple."), ("ate", "Pip ate berries.")]),
                         ["I ate five meals, among them bread, cooked fish and apple."])


class ClosingTests(unittest.TestCase):
    def test_a_present_owner_never_reads_missed_you_or_visit_tomorrow(self):
        """I4: at any bond, the story for an owner who was there thanks them for the company."""
        for level in (0.0, 30.0, 55.0, 100.0):
            text = rules_story(3, ["I ate bread."], "", "Sam", level, present=True)
            self.assertNotIn("missed you", text)
            self.assertNotIn("visit tomorrow", text)
            self.assertTrue(text.endswith("Thanks for keeping me company, Sam!"), text)

    def test_the_words_turn_warm_where_the_hud_says_close(self):
        """m2: one table of bond levels for the HUD, the replies and the story."""
        self.assertEqual((SHY, CLOSE), (dict((words, floor) for floor, words in FEELINGS)["friendly"],
                                        dict((words, floor) for floor, words in FEELINGS)["close"]))
        self.assertEqual(rules_story(3, [], "", "Sam", 50.0), "Day 3 was a quiet one. I stayed close to home and kept "
                                                               "safe. Come back soon, Sam, I missed you!")


class StoryWorldTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]

    def tearDown(self):
        self.directory.cleanup()

    def visit(self, at):
        with self.world.transaction() as db:
            state = read_state(db)
            visit(state, at)
            write_state(db, state)

    def stories(self):
        with self.world.connect() as db:
            return [item for item in reversed(inbox_items(db, 1000)) if item["kind"] == "story"]

    def test_a_long_absence_is_told_from_its_first_day(self):
        """m16: an owner away 50 game days hears of the goal on day 3 (the old bound told only the last 30)."""
        self.visit(BORN + 10)
        with self.world.transaction() as db:
            log_event(db, BORN + 60 * 2 + 5, "goal", f"{self.name} reached a goal: iron tools.")  # day 3
            log_event(db, BORN + 60 * 44 + 5, "found", f"{self.name} met its first skitter.")  # day 45
        Talker(env={}, http=None, executor_factory=InlineExecutor, scale=SCALE).poll(self.registry, BORN + 60 * 50 + 1)
        [story] = self.stories()
        self.assertEqual(story["data"], {"day": 1, "last": 50, "writer": "rules"})
        self.assertIn("On day 3, I reached a goal: iron tools.", story["text"])
        self.assertIn("On day 45, I met my first skitter.", story["text"])

    def test_a_watching_owners_story_thanks_them_and_luna_hears_they_were_there(self):
        """I4: the owner was seen during the day the story tells: the rules thank them, Luna is told so."""
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN)
        self.visit(BORN + 10)
        self.visit(BORN + 50)
        job = story_job(SurvivalWorld(self.world.path, read_only=True), BORN + 61, SCALE, {})
        answer = job.decide({}, None)
        self.assertTrue(answer.text.endswith("Thanks for keeping me company, Sam!"), answer.text)
        with self.world.transaction() as db:
            state = read_state(db)
            state["bond"].pop("story_luna_day", None)
            write_state(db, state)
        luna = story_job(SurvivalWorld(self.world.path, read_only=True), BORN + 61, SCALE, LUNA)
        self.assertIs(luna_payload(luna)["present"], True)

    def test_an_owner_away_for_days_is_missed(self):
        self.visit(BORN + 10)
        job = story_job(SurvivalWorld(self.world.path, read_only=True), BORN + 60 * 3 + 1, SCALE, {})
        self.assertNotIn("keeping me company", job.decide({}, None).text)

    def test_a_promise_kept_is_in_the_story(self):
        """m15: the inbox's kept promise is the story's first highlight."""
        with self.world.transaction() as db:
            state = read_state(db)
            state.setdefault("bond", {})["request"] = {"goal": "cave", "at": BORN, "until": BORN + 500,
                                                       "status": "open"}
            write_state(db, state)
        run_chores(self.world, BORN + 1, SCALE)  # the inbox starts
        self.visit(BORN + 10)
        with self.world.transaction() as db:
            log_event(db, BORN + 20, "goal", f"{self.name} reached a goal: look into a cave.")
            log_event(db, BORN + 25, "found", f"{self.name} met its first skitter.")
        run_chores(self.world, BORN + 30, SCALE)
        Talker(env={}, http=None, executor_factory=InlineExecutor, scale=SCALE).poll(self.registry, BORN + 61)
        [story] = self.stories()
        self.assertIn("Day 1 was a good one. You asked me to look into a cave, and I did it! I met my first skitter.",
                      story["text"])


class InboxVoiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(registry.world_path(self.life))
        self.name = self.life["name"]
        run_chores(self.world, BORN + 1, 1.0)  # the inbox starts

    def tearDown(self):
        self.directory.cleanup()

    def test_the_computer_is_reported_once_and_a_home_without_the_pets_name(self):
        """I1: "I built Clover's computer." and the computer's own news were two reports of one moment."""
        with self.world.transaction() as db:
            log_event(db, BORN + 2, "built", f"{self.name} finished building {self.name}'s Round Cottage and moved in.")
            log_event(db, BORN + 3, "built", f"{self.name} built {title_of(MACHINES['computer'], self.name)}.")
            log_event(db, BORN + 4, "computer",
                      f"{self.name} built a machine that remembers how long it has been alive!")
        run_chores(self.world, BORN + 10, 1.0)
        with self.world.connect() as db:
            reports = [item["text"] for item in reversed(inbox_items(db, 100)) if item["kind"] == "report"]
        self.assertEqual(reports, ["I finished building my Round Cottage and moved in.",
                                   "I built a machine that remembers how long I have been alive!"])

    def test_asked_about_the_day_mimo_tells_the_days_news(self):
        """I1 with replies.news: "Tell me about your day." after a goal hours ago is not "Not much to tell yet"."""
        with self.world.transaction() as db:
            log_event(db, BORN + 10, "goal", f"{self.name} reached a goal: a home of its own.")
            state = read_state(db)
            s = from_db(db, state, BORN + 10 + 10 * 3600 / SCALE, SCALE)  # ten game hours later
            self.assertEqual(news(s, Heard("Tell me about your day.")), "Lately, I reached a goal: a home of my own.")
            self.assertIsNone(news(s, Heard("hello")))  # unasked, only the last game hour's news is shared


def luna_payload(job):
    """What Luna would be told by a story job (the model call, captured)."""
    bodies = []

    def http(url, headers, body, timeout):
        bodies.append(body)
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"story": "A. B."})}}]}
    job.decide(LUNA, http)
    return json.loads(bodies[0]["messages"][1]["content"])


if __name__ == "__main__":
    unittest.main()

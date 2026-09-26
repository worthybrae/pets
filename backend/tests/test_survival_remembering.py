import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose, goal and creature registered)
from backend.survival import minding  # noqa: F401  (the memory reply and its keeper registered)
from backend.survival.clock import DAY_SECONDS
from backend.survival.hatch import hatch
from backend.survival.mind import add_memory
from backend.survival.once import forget_logged
from backend.survival.owner_facts import remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.remembering import hear_memories, recalled_line
from backend.survival.replies import TOLD, Heard
from backend.survival.situation import from_db
from backend.survival.talk import owner_says
from backend.survival.talker import Talker, run_chores
from backend.survival.world import SurvivalWorld, log_event, read_state
from backend.tests.test_survival_talk_golden import LiveLikeJev
from backend.tests.test_survival_talker import FakeJev

BORN = 1_000_000.0
JEV = {"TYPESAFE_API_KEY": "k"}


class RememberingTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def remember(self, day, kind, text, importance=6):
        with self.world.transaction() as db:
            return add_memory(db, BORN + (day - 1) * DAY_SECONDS + 100, day, kind, text, (), importance, 1, "test")

    def say(self, text, at=BORN + 5, env=None, http=None):
        owner_says(self.world, text, at, 1.0)
        talker = Talker(env=env or {}, http=http or FakeJev(), scale=1.0)
        talker.poll(self.registry, at + 1)
        talker.close()
        with self.world.connect() as db:
            return db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]

    def strength(self, memory):
        with self.world.connect() as db:
            return tuple(db.execute("SELECT strength, last_recalled FROM mind_memories WHERE id=?",
                                    (memory,)).fetchone())

    def test_a_memory_the_words_name_comes_back_first_and_grows_stronger(self):
        skitter = self.remember(1, "episode", "I met my first skitter.")
        self.remember(1, "episode", "I hunted a cow.", 2)
        self.assertEqual(self.say("Do you remember the skitter?"), "I remember when I met my first skitter.")
        self.assertEqual(self.strength(skitter), (2.0, BORN + 6))

    def test_words_that_name_nothing_mimo_remembers_get_their_usual_answer(self):
        self.remember(1, "thought", "I love fishing by the lake.", 7)
        self.assertEqual(self.say("I love you"), "Aw, thank you! You're the best.")
        self.assertEqual(self.say("do you remember fishing at the lake?", at=BORN + 20),
                         "I keep thinking: I love fishing by the lake.")

    def test_a_memory_weighs_one_or_more_only_when_the_words_cue_it_and_less_than_what_was_just_told(self):
        # B1 re-review: recall shares one scale with the topics' keyword counts and TOLD (10).
        self.remember(1, "episode", "I met my first skitter.")
        self.remember(1, "thought", "I love fishing by the lake.", 7)
        self.remember(1, "episode", "I slept through a dark night.", 3)
        with self.world.transaction() as db:
            remember_fact(db, "about", "I work nights", BORN + 2)  # Bond's to say back, never Mind's
        with self.world.connect() as db:
            s = from_db(db, read_state(db), BORN + 5, 1.0)
            weights = {words: round((hear_memories(db, s, Heard(words)) or {}).get("weight") or 0, 2)
                       for words in ("I love you", "how was your day?", "hi!", "is it night yet?",
                                     "what did you do last night?", "skitters are scary",
                                     "do you remember the skitter?")}
        self.assertEqual(weights, {"I love you": 0, "how was your day?": 0, "hi!": 0, "is it night yet?": 0,
                                   "what did you do last night?": 0,  # 0: no memory line at all
                                   "skitters are scary": 1.67, "do you remember the skitter?": 3.0})
        self.assertLess(max(weights.values()), min(TOLD.values()))

    def test_yesterday_brings_back_yesterdays_gist(self):
        self.remember(1, "gist", "Day 1: hatched into a brand-new world and met my first cow.", 6)
        now = BORN + DAY_SECONDS + 50
        self.assertEqual(self.say("what did you do yesterday?", at=now),
                         "I remember day 1: hatched into a brand-new world and met my first cow.")

    def test_a_line_jev_did_not_choose_strengthens_nothing(self):
        skitter = self.remember(1, "episode", "I met my first skitter.")
        jev = FakeJev(lambda name, criteria: "mood" if name == "reply" else sorted(criteria)[0])
        self.say("Do you remember the skitter?", env=JEV, http=jev)
        self.assertIn("memory", jev.bodies[0]["questions"]["reply"]["criteria"])
        self.assertEqual(self.strength(skitter), (1.0, None))

    def homecoming(self, rough=False):
        name, day3 = self.life["name"], BORN + 2 * DAY_SECONDS
        events = [(BORN + 100, "expedition", f"{name} set out on an expedition to the east.")]
        if rough:
            events.append((BORN + DAY_SECONDS + 100, "hurt", f"{name} was hit by a skitter."))
        events.append((day3 + 100, "expedition", f"{name} came home from its expedition: 249 blocks out, "
                                                 "2 nights camped, 2 new things learned."))
        with self.world.transaction() as db:
            for when, kind, text in events:
                log_event(db, when, kind, text)
        run_chores(self.world, day3 + 101, 1.0)
        return day3 + 200

    def test_golden_welcome_home_is_answered_from_the_homecoming(self):
        """The live finding (Pebble, 2026-09-26): just home from an expedition, "Welcome home! How was your
        trip?" got "I feel great! Thanks for asking.". The rules and a live-like Jev answer from the
        homecoming now, and saying it strengthens that memory."""
        now = self.homecoming()
        trip = "It was wonderful! I went 249 blocks east, camped two nights and learned two new things."
        self.assertEqual(self.say("Welcome home! How was your trip?", at=now), trip)
        self.assertEqual(self.say("Welcome home! How was your trip?", at=now + 10, env=JEV,
                                  http=LiveLikeJev("Welcome home! How was your trip?")), trip)
        with self.world.connect() as db:
            home = db.execute("SELECT strength FROM mind_memories WHERE text LIKE 'I came home%'").fetchone()[0]
        self.assertEqual(home, 3.0)

    def test_a_rough_trip_is_told_as_one_and_an_old_trip_is_not_the_news(self):
        now = self.homecoming(rough=True)
        self.assertEqual(self.say("how was the trip?", at=now),
                         "It was a wild one! I went 249 blocks east, camped two nights and learned two new things.")
        self.assertNotIn("It was", self.say("how was the trip?", at=now + 3 * DAY_SECONDS))

    def test_a_verb_in_another_form_brings_its_moment_back(self):
        # Final fix wave (M9): recall reduces only plurals, so "hunting" never met "hunted".
        self.remember(1, "episode", "I hunted a cow.", 2)
        self.remember(1, "episode", "I fought off a gloomling.", 6)
        self.assertEqual(self.say("do you remember hunting?"), "I remember when I hunted a cow.")
        self.assertEqual(self.say("remember fighting?", at=BORN + 20), "I remember when I fought off a gloomling.")

    def test_a_goal_or_a_trip_is_said_back_as_its_gist_says_it(self):
        # Final fix wave (I3): the event log's colons stay out of what Mimo says too.
        memory = type("M", (), {})
        memory.kind = "episode"
        for text, line in (("I reached a goal: look into a cave.", "I remember when I managed to look into a cave."),
                           ("I set a goal aside for now: a herd of my own.",
                            "I remember when I put a herd of my own aside for now."),
                           ('I set a new goal: armor up. "Next time a gloomling swings at me, I\'ll be ready."',
                            "I remember when I decided to armor up."),
                           ("I nearly died: a gloomling almost got me.",
                            "I remember when I was nearly killed by a gloomling."),
                           ("I met my first skitter.", "I remember when I met my first skitter.")):
            memory.text = text
            self.assertEqual(recalled_line(memory), line)

    def test_how_each_kind_of_memory_is_said_back(self):
        memory = type("M", (), {})
        for kind, text, line in (("episode", "You gave me a snack.", "I remember when you gave me a snack."),
                                 ("told", "You taught me that sheep give wool.",
                                  "I remember when you taught me that sheep give wool."),
                                 ("gist", "Day 3: a quiet day.", "I remember day 3: a quiet day."),
                                 ("thought", "You visit me in the evenings.",
                                  "I keep thinking: You visit me in the evenings.")):
            memory.kind, memory.text = kind, text
            self.assertEqual(recalled_line(memory), line)


if __name__ == "__main__":
    unittest.main()

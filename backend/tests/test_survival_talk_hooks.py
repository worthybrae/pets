import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival.choosing import InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.memory import know, known
from backend.survival.once import forget_logged
from backend.survival.owner_facts import FACT_MIRRORS, owner_facts, remember_fact
from backend.survival.pickers import Option
from backend.survival.registry import LifeRegistry
from backend.survival.replies import REPLIES, TOLD, Reply
from backend.survival.talk import HEARING, KEEPERS, QUESTIONS, REPLY_KEEPERS, Question, owner_says
from backend.survival.talker import Talker
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0
JEV = {"TYPESAFE_API_KEY": "k"}


class FakeJev:
    def __init__(self, pick):
        self.pick, self.bodies = pick, []

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        return {"answers": {name: {"choice": self.pick(name, question["criteria"])}
                            for name, question in body["questions"].items()}}


def recall(s, heard):
    """A stand-in for Mind's recall writer: two lines, each quoting a memory."""
    return [Reply("recall", "I remember the night the skitter chased me.", note={"memory": 7}, weight=5.0),
            Reply("recall", "I remember my first campfire.", note={"memory": 9}, weight=4.0)]


def option(name):
    return Option(name, name, f"Answer {name}.", "a test answer", 0.0)


class ChatHookTests(unittest.TestCase):
    """The hooks Mind (memory and teaching) builds on: R1 to R6 in the chat, and the owner facts' mirror."""

    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.world = SurvivalWorld(self.registry.world_path(hatch(self.registry, random.Random(8), timestamp=BORN)))

    def tearDown(self):
        self.directory.cleanup()

    def say(self, text, jev=None, at=BORN + 5):
        owner_says(self.world, text, at, 1.0)
        Talker(env=JEV if jev else {}, http=jev, executor_factory=InlineExecutor, scale=1.0).poll(self.registry, at + 1)
        with self.world.connect() as db:
            return db.execute("SELECT text, picker FROM mimo_chat WHERE who='mimo' ORDER BY id DESC").fetchone()

    def test_r1_r6_a_writer_offers_several_lines_with_notes_and_the_chosen_ones_note_reaches_its_keeper(self):
        kept = []
        jev = FakeJev(lambda name, criteria: "recall:2" if name == "reply" else "none" if "none" in criteria
                      else sorted(criteria)[0])
        with patch.dict(REPLIES, {"recall": recall}), \
                patch.dict(REPLY_KEEPERS, {"recall": lambda db, state, heard, note, now: kept.append(note)}):
            said = self.say("do you remember the old days?", jev)
        self.assertEqual(tuple(said), ("I remember my first campfire.", "jev"))
        self.assertEqual(kept, [{"memory": 9}])
        criteria = jev.bodies[0]["questions"]["reply"]["criteria"]
        self.assertIn("recall", criteria)
        self.assertIn("recall:2", criteria)

    def test_r2_a_writers_weight_and_what_was_just_told_rank_first(self):
        with patch.dict(REPLIES, {"recall": recall}):
            self.assertEqual(self.say("hi!")[0], "I remember the night the skitter chased me.")  # 5 beats a greeting
        with patch.dict(REPLIES, {"teach_ack": lambda s, heard: "Oh! Cows give leather?"}), \
                patch.dict(TOLD, {"teach_ack": 10.0}):
            self.assertEqual(self.say("hi! cows give leather", at=BORN + 10)[0], "Oh! Cows give leather?")

    def test_r3_hearing_hooks_run_once_a_job_and_their_findings_reach_questions_and_writers(self):
        calls, asked = [], []

        def shortlist(db, s, heard):
            calls.append(heard.text)
            return ("leather",) if "leather" in heard.text else ()

        def broken(db, s, heard):
            raise RuntimeError("boom")

        def teach(s, heard):
            asked.append(dict(heard.context))
            return None
        with patch.dict(HEARING, {"broken": broken, "teach": shortlist}), \
                patch.dict(REPLIES, {"teach_ack": lambda s, heard: Reply("teach_ack", "Leather? Tell me more!", weight=9.0)
                                     if heard.context.get("teach") else None}):
            QUESTIONS.insert(0, teach)
            try:
                with self.assertLogs("backend.survival.talk", level="ERROR") as logs:
                    said = self.say("cows give leather")
            finally:
                QUESTIONS.remove(teach)
        self.assertEqual(calls, ["cows give leather"])
        self.assertEqual(asked, [{"teach": ("leather",)}])  # the crashing hook is left out
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(said[0], "Leather? Tell me more!")

    def test_r4_a_request_line_beats_a_teaching_line_which_beats_the_replys_own(self):
        def question(name):
            return lambda s, heard: Question(name, "Choose.", (option("a"), option("b")), "a")
        extra = [question("teach"), question("request")]
        keepers = {"teach": lambda *args: "I'll remember that cows give leather.",
                   "request": lambda *args: "Okay! I'll raise a herd next."}
        QUESTIONS.extend(extra)
        try:
            with patch.dict(KEEPERS, keepers):
                self.assertEqual(self.say("could you raise a herd?")[0], "Okay! I'll raise a herd next.")
                with patch.dict(KEEPERS, {"request": lambda *args: None}):
                    self.assertEqual(self.say("cows give leather", at=BORN + 10)[0], "I'll remember that cows give leather.")
        finally:
            for asked in extra:
                QUESTIONS.remove(asked)

    def test_r5_an_unoffered_pick_falls_back_for_that_question_alone(self):
        jev = FakeJev(lambda name, criteria: "like_ack" if name == "reply" else "a_secret" if name == "fact"
                      else "none" if "none" in criteria else sorted(criteria)[0])
        with self.assertLogs("backend.survival.talk", level="ERROR") as logs:
            said = self.say("I love the lake. I work nights.", jev)
        self.assertEqual(tuple(said), ("Ooh, the lake? I'll remember that you like it.", "jev"))
        self.assertIn("jev fact", logs.output[0])
        with self.world.connect() as db:
            self.assertEqual(owner_facts(db), [("likes", "the lake")])  # the rules' fact, and the reply's promise

    def test_the_owner_facts_mirror_hears_every_fact_kept_and_a_crash_is_rolled_back(self):
        told = []

        def write(db, kind, words, at, new):
            told.append((kind, words, new))

        def broken(db, kind, words, at, new):
            know(db, "half written", "test", at)
            raise RuntimeError("boom")
        saved = list(FACT_MIRRORS)
        FACT_MIRRORS.extend([broken, write])
        try:
            with self.assertLogs("backend.survival.owner_facts", level="ERROR") as logs:
                with self.world.transaction() as db:
                    remember_fact(db, "likes", "the lake", BORN + 1)
                    remember_fact(db, "likes", "the lake", BORN + 2)
        finally:
            FACT_MIRRORS[:] = saved
        self.assertEqual(told, [("likes", "the lake", True), ("likes", "the lake", False)])
        self.assertEqual(len(logs.records), 1)
        with self.world.connect() as db:
            self.assertEqual(owner_facts(db), [("likes", "the lake")])
            self.assertEqual(known(db, "test"), [])


if __name__ == "__main__":
    unittest.main()

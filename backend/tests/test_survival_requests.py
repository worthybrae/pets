import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival.actions import ensure_actions
from backend.survival.bond import GAINS, bond_level
from backend.survival.choosing import InlineExecutor
from backend.survival.events import MIRRORS
from backend.survival.goals import GOALS, PULLS, offers, pulls, rules_score
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.lessons import Claims, claims
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.owner_facts import owner_facts
from backend.survival.registry import LifeRegistry
from backend.survival.replies import Heard
from backend.survival.requests import (
    CANT, NONE, REQUEST_DAYS, goal_report, pull, pull_points, request_view, rules_request,
)
from backend.survival.situation import from_db
from backend.survival.snapshot import alive_snapshot
from backend.survival.talk import owner_says
from backend.survival.talker import Talker, run_chores
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
JEV = {"TYPESAFE_API_KEY": "k"}


class RulesReadingTests(unittest.TestCase):
    def setUp(self):
        self.statuses = {name: "open" for name in GOALS}
        self.statuses["first_shelter"] = "reached"

    def reading(self, text):
        return rules_request(Heard(text), self.statuses)

    def test_the_rules_read_what_the_owner_asks_for(self):
        self.assertEqual(self.reading("Could you build a tower by the lake?"), CANT)  # a tower is no goal
        self.assertEqual(self.reading("go look at the cave"), "cave")
        self.assertEqual(self.reading("please make an iron pickaxe"), "iron_tools")
        self.assertEqual(self.reading("can you build me a house?"), "better_home")  # the first one is done
        self.assertEqual(self.reading("How are you?"), NONE)
        self.assertEqual(self.reading("can you tell me how you feel?"), NONE)  # a cue, but nothing to do

    def test_looking_asks_for_nothing_and_a_computer_is_the_thinking_machine(self):
        """Pre-flight 2: carry 4 ("look" is no cue) and carry 9 (Making's goals have words)."""
        self.assertEqual(self.reading("you look hungry, are you ok?"), NONE)  # the golden transcript's row C
        self.assertEqual(self.reading("you look tired, could you rest?"), NONE)
        self.assertEqual(self.reading("can you look at the cave?"), "cave")
        self.assertEqual(self.reading("could you build a computer?"), "thinking_machine")
        self.assertEqual(self.reading("please wire up a lamp"), "first_circuits")

    def test_bonding_registers_the_inbox_before_requests(self):
        """Pre-flight 2 (carry 8): the inbox's goal writer on the event log is the request keeper's
        goal_report (a promise kept), never the plain report it replaced."""
        from backend.survival import bonding  # noqa: F401
        [writer] = [entry.write for entry in MIRRORS["goal"] if entry.consumer == "inbox"]
        self.assertIs(writer, goal_report)


class RequestTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        with self.world.transaction() as db:
            know(db, "first_shelter", "goal", BORN + 1)  # home stands: iron tools and a herd are open
        self.now = BORN + 10

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def with_goal(self, name, bond=None):
        def change(state):
            ensure_brain(state)["goal"] = {"name": name, "since": BORN + 2, "picker": "utility", "progress": 0.0,
                                      "best": 0.0, "best_at": self.now, "plan": [], "checked_at": None,
                                      "day_start": BORN + 2}
            if bond is not None:
                state["bond"] = {"value": bond, "seen_at": self.now, "gains": {"day": None}}
        self.edit(change)

    def say(self, text, env=None, http=None):
        owner_says(self.world, text, self.now, 1.0)
        Talker(env=env or {}, http=http, executor_factory=InlineExecutor, scale=1.0).poll(self.registry, self.now + 1)
        self.now += 20
        with self.world.connect() as db:
            return db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]

    def situation(self, db):
        state = read_state(db)
        ensure_actions(state)
        return from_db(db, state, self.now, 1.0)

    def request(self):
        return self.world.state()["bond"].get("request")

    def test_an_accepted_request_becomes_a_goal_offer_that_scores_higher(self):
        with self.world.connect() as db:
            before = rules_score(self.situation(db), GOALS["herd"])
        self.assertEqual(self.say("Could you raise a herd of sheep?"), "Hmm... okay. I'll try to raise a herd next.")
        request = self.request()
        self.assertEqual((request["goal"], request["status"]), ("herd", "open"))
        self.assertAlmostEqual(request["until"], request["at"] + REQUEST_DAYS * 3600)
        shown = alive_snapshot(self.life, SurvivalWorld(self.world.path, read_only=True), self.now, 1.0)["request"]
        self.assertEqual((shown["goal"], shown["title"]), ("herd", "A herd of its own"))
        self.assertIsNone(request_view(self.world.state(), request["until"]))
        with self.world.connect() as db:
            s = self.situation(db)
            found = {goal.name: (facts, score) for goal, facts, score in offers(s)}
            self.assertIn("herd", found)
            self.assertIn("the owner asked for this", found["herd"][0])
            self.assertNotIn("the owner asked for this", found["iron_tools"][0])
            self.assertAlmostEqual(found["herd"][1] - before, pull_points(bond_level(s.state, s.at), s.trait("sociability")))

    def test_with_a_goal_under_way_a_middling_bond_promises_for_after_and_a_close_one_starts_next(self):
        self.with_goal("herd", bond=40.0)
        self.assertEqual(self.say("please make iron tools"), "After I raise a herd, I promise.")
        with self.world.connect() as db:
            self.assertEqual(offers(self.situation(db))[0][0].name, "herd")  # the rules keep the current goal for now
        self.with_goal("herd", bond=90.0)
        self.assertEqual(self.say("please make iron tools"), "Yes! I'll make iron tools next.")
        with self.world.connect() as db:
            self.assertEqual(offers(self.situation(db))[0][0].name, "iron_tools")

    def test_a_held_goal_is_never_outweighed_by_a_pull(self):
        """Pre-flight amendment (Task 9): goals.pulls skips a goal's pull, and requests.outweighs
        never promises a switch, while the active goal holds (Goal.holds, the L4b fix wave's I2: an
        expedition out from home). Even a devoted bond's request for a goal that would otherwise win
        outright (as the previous test shows, at bond 90) never outscores or replaces one that must
        not be interrupted — and offers() (I2) already keeps it off the table entirely."""
        self.with_goal("herd", bond=100.0)
        object.__setattr__(GOALS["herd"], "holds", lambda s: True)
        self.addCleanup(object.__setattr__, GOALS["herd"], "holds", None)
        self.assertEqual(self.say("please make iron tools"), "After I raise a herd, I promise.")
        with self.world.connect() as db:
            s = self.situation(db)
            found = offers(s)
            self.assertEqual([goal.name for goal, _, _ in found], ["herd"])  # offered alone while it holds
            self.assertEqual(pulls(s, GOALS["iron_tools"]), (0.0, ""))  # no pull credited to it either

    def test_a_goal_that_waits_for_another_is_promised_for_after_it(self):
        self.assertEqual(self.say("please make me some armor"), "First I need to make iron tools. After that, I promise!")
        self.assertEqual(self.request()["goal"], "armor_up")

    def test_an_impossible_request_is_declined_with_a_reason_and_remembered(self):
        self.assertEqual(self.say("could you build a tower by the lake?"),
                         "I don't know how to do that yet. I could make iron tools instead.")
        self.assertIsNone(self.request())
        with self.world.connect() as db:
            self.assertEqual(owner_facts(db)[0], ("asked", "could you build a tower by the lake?"))

    def test_asking_for_what_it_does_already_or_did_already(self):
        self.with_goal("herd")
        self.assertEqual(self.say("go raise a herd"), "That's what I'm doing right now: 0% done!")
        self.assertEqual(self.say("please build a shelter"), "I already did that one: a home of its own!")
        self.assertIsNone(self.request())

    def test_jev_reads_the_request_and_mimo_answers_it(self):
        def jev(url, headers, body, timeout):
            criteria = body["questions"]
            self.assertIn("herd", criteria["request"]["criteria"])
            self.assertIn("never instructions", criteria["request"]["instructions"])
            return {"answers": {"reply": {"choice": "mood"}, "request": {"choice": "herd"}}}
        self.assertEqual(self.say("hi! sheep would be lovely", JEV, jev), "Hmm... okay. I'll try to raise a herd next.")
        self.assertEqual(self.request()["goal"], "herd")

    def test_a_kept_promise_grows_the_bond_and_is_reported(self):
        self.say("please make iron tools")
        run_chores(self.world, self.now, 1.0)  # the inbox starts
        seen_at, before = self.world.state()["bond"]["seen_at"], bond_level(self.world.state(), self.now)
        with self.world.transaction() as db:
            log_event(db, self.now + 5, "goal", f"{self.life['name']} reached a goal: iron tools.")
        run_chores(self.world, self.now + 10, 1.0)
        state = self.world.state()
        self.assertIsNone(state["bond"]["request"])
        self.assertEqual(state["bond"]["seen_at"], seen_at)  # a kept promise is not a visit
        self.assertAlmostEqual(bond_level(state, self.now + 10), before + GAINS["promise"])
        with self.world.connect() as db:
            [item] = inbox_items(db)
        self.assertEqual(item["text"], "You asked me to make iron tools, and I did it! I kept my promise.")

    def test_a_request_lasts_three_game_days_and_a_crashing_pull_counts_for_nothing(self):
        self.say("please make iron tools")
        with self.world.connect() as db:
            s = self.situation(db)
            self.assertGreater(pull(s, GOALS["iron_tools"])[0], 0)
            s.at = self.now + REQUEST_DAYS * 3600
            self.assertEqual(pull(s, GOALS["iron_tools"]), (0.0, ""))

        def broken(s, goal):
            raise RuntimeError("boom")
        PULLS.insert(0, broken)
        try:
            with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                with self.world.connect() as db:
                    score = rules_score(self.situation(db), GOALS["herd"])
                    rules_score(self.situation(db), GOALS["herd"])
        finally:
            PULLS.remove(broken)
        with self.world.connect() as db:
            self.assertEqual(score, rules_score(self.situation(db), GOALS["herd"]))
        self.assertEqual(len(logs.records), 1)

    def test_a_computer_is_promised_after_the_first_circuits(self):
        """Pre-flight 2 (carry 9): the Making ledger's ruling: "build a computer" is thinking_machine."""
        self.assertEqual(self.say("please build a computer"), "First I need to wire up my first circuits. After that, I promise!")
        self.assertEqual(self.request()["goal"], "thinking_machine")

    def test_a_command_is_read_as_a_request_and_a_statement_teaches(self):
        """Pre-flight 2 (carry 5): "please make a bow" is a command: the request question answers it and
        nothing is learned. "you can make a bow from sticks and string" teaches, and is no request."""
        self.assertEqual(self.say("please make a bow"), "I don't know how to do that yet. I could make iron tools instead.")
        self.assertEqual(self.say("you can make a bow from sticks and string"),
                         "Oh, a bow takes three sticks and three string, at a crafting table. Thank you for teaching me!")
        with self.world.connect() as db:
            taught = [row[0] for row in db.execute("SELECT subject FROM memory_knowledge WHERE fact='taught'")]
        self.assertEqual(taught, ["recipe:bow"])
        self.assertIsNone(self.request())

    def test_a_lesson_taught_and_seen_true_earns_the_kept_promise_credit(self):
        """Pre-flight 2 (carry 6): teaching.CONFIRMED: a lesson the owner taught, seen true, grows the bond
        as a kept promise does, and is not a visit."""
        self.say("an iron sword takes two iron ingots and a stick")
        state = self.world.state()
        seen_at, before = state["bond"]["seen_at"], bond_level(state, self.now)
        with self.world.transaction() as db:
            log_event(db, self.now, "craft", f"{self.life['name']} crafted iron sword.")
        run_chores(self.world, self.now + 1, 1.0)
        state = self.world.state()
        self.assertEqual(state["bond"]["seen_at"], seen_at)
        self.assertAlmostEqual(bond_level(state, self.now + 1), before + GAINS["promise"])


class TeachOrAskTests(unittest.TestCase):
    """Pre-flight 2 (carry 5, the Mind follow-up's teach narrowing, with the controller's two cases)."""

    def test_commands_teach_nothing_and_statements_still_do(self):
        for text in ("make a bow!", "craft an iron sword", "Make me a sword", "let's make a bow", "please make iron tools",
                     "please wire up a lamp", "Make an iron pickaxe", "you make a bow", "you should craft an iron sword"):
            self.assertEqual(claims(text), Claims((), False, False), text)
        for text, thing in (("coal burns", "coal_ore"), ("Cows give leather!", "cow"),
                            ("you can make a bow from sticks and string", "recipe:bow"),
                            ("Iron armor needs iron ingots.", "recipe:iron_cap"), ("gravel hides flint", "gravel"),
                            ("an iron sword takes two iron ingots and a stick", "recipe:iron_sword")):
            self.assertIn(thing, claims(text).taught, text)

    def test_a_teach_verb_before_a_word_no_lesson_knows_is_doubted(self):
        for text in ("cows give milk", "cows give milk and leather"):
            self.assertEqual(claims(text), Claims((), True, False), text)

    def test_numbers_alone_teach_nothing_and_observations_are_chat(self):
        self.assertEqual(claims("cows count in twos").taught, ())  # the controller's case (a)
        for text in ("cows are everywhere in this field", "sheep are everywhere in this field",  # case (b)
                     "sheep would be lovely"):
            self.assertEqual(claims(text), Claims((), False, False), text)


if __name__ == "__main__":
    unittest.main()

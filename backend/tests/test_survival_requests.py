import random
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival.actions import ensure_actions
from backend.survival.bond import GAINS, bond_level
from backend.survival.choosing import InlineExecutor
from backend.survival.events import MIRRORS
from backend.survival.goals import GOALS, PULLS, REPEAT_REST, SET_ASIDE, offers, pulls, rules_score
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.lessons import Claims, claims
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.owner_facts import owner_facts
from backend.survival.registry import LifeRegistry
from backend.survival.replies import Heard
from backend.survival.requests import (
    CANT, NONE, REQUEST_DAYS, goal_report, note_for, pull, pull_points, request_view, rules_request,
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
        goal_report (a promise kept), never the plain report it replaced. (Fix round 1, Minor 6: this
        pins which writer is registered, not the import order that decides it.)"""
        from backend.survival import bonding  # noqa: F401
        [writer] = [entry.write for entry in MIRRORS["goal"] if entry.consumer == "inbox"]
        self.assertIs(writer, goal_report)


    def test_everyday_lines_ask_for_nothing(self):
        """Fix round 1 (Important 2): a cue counts only as a sentence's first word or in an asking
        phrase, and to make "me", "you" or "us" is no thing to make."""
        for text in EVERYDAY:
            self.assertEqual(self.reading(text), NONE, text)

    def test_real_requests_still_read_and_explore_is_a_goal_word(self):
        """Fix round 1 (Important 2, Minor 4)."""
        for text, goal in REAL_REQUESTS:
            self.assertEqual(self.reading(text), goal, text)


    def test_a_goal_verb_alone_asks_for_nothing(self):
        """Fix round 2 (B): a verb that is also a goal's word ("follow", "meet", "explore", "store", "map",
        "wire", "farm") asks for its goal only bare ("explore!", "go explore") or with a word of the goal
        after it; "follow your dreams" or "wire me some money" asks for nothing."""
        for text in VERB_ALONE:
            self.assertEqual(self.reading(text), NONE, text)
        for text, goal in VERB_WITH_ITS_GOAL:
            self.assertEqual(self.reading(text), goal, text)

    def test_you_could_and_you_can_ask(self):
        """Fix round 2 (C): the readings round 1 lost."""
        self.assertEqual(self.reading("you could build a workshop"), "workshop")
        self.assertEqual(self.reading("you can build a computer now"), "thinking_machine")


# Fix round 2 (B): a goal's verb with no word of a goal after it ...
VERB_ALONE = ("follow your dreams", "follow your heart", "follow the rules", "meet my friend Bob",
              "meet the neighbours", "explore your options", "explore your feelings", "store that in your memory",
              "store it for later", "map out your day", "map it out", "farm some xp", "wire me some money")
# ... and with one, or bare.
VERB_WITH_ITS_GOAL = (("go camping", "expedition"), ("set up camp", "expedition"), ("follow the river", "water"),
                      ("store food in the chest", "full_larder"), ("go meet new creatures", "new_creature"),
                      ("explore the world!", "new_land"), ("can you go explore?", "new_land"),
                      ("please build a workshop", "workshop"), ("build a computer!", "thinking_machine"),
                      ("could you raise a herd?", "herd"), ("go look at the cave", "cave"),
                      ("can you go explore with me?", "new_land"))
# Fix round 1 (Important 2): everyday lines the old rules read as refused requests ...
EVERYDAY = ("you make me happy", "you make me smile", "I'll make you a snack", "let me make you dinner",
            "I'm going to build a sandcastle", "cows make me happy", "sticks make torches",
            "it takes two sticks to make a torch", "I'll be back soon, try to stay safe",
            # ... and a few more of the same kind (the fix round's probe)
            "please stay safe", "please don't go into the cave", "go to bed, it's late", "get home safe",
            "make sure you eat something", "follow me", "can you tell me what you're thinking?",
            "look at the lake, it's so pretty", "would you like a snack?", "keep the torch lit")
# ... while real requests still read, in everyday words too.
REAL_REQUESTS = (("please build a workshop", "workshop"), ("build a computer!", "thinking_machine"),
                 ("could you raise a herd?", "herd"), ("go look at the cave", "cave"),
                 ("please wire up a lamp", "first_circuits"), ("can you go explore?", "new_land"),
                 ("Pebble, build a workshop", "workshop"), ("a workshop, please!", "workshop"),
                 ("let's go to the lake", "water"), ("would you mind building a workshop?", "workshop"),
                 ("go look at the cave near the lake", "cave"), ("please make me a sandwich", CANT))


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
        """Pre-flight 2 (carry 9): the Making ledger's ruling: "build a computer" is thinking_machine.
        Fix round 1 (Minor 2): every goal still before it is named, first first, not only the first
        circuits it waits on directly."""
        self.assertEqual(self.say("please build a computer"), "First I need to make iron tools, then build my "
                         "workshop and wire up my first circuits. After that, I promise!")
        self.assertEqual(self.request()["goal"], "thinking_machine")

    def test_with_no_home_a_computer_waits_for_the_home_first(self):
        """Fix round 1 (Minor 2): the wait is walked down `after` to the first goal not settled."""
        with self.world.transaction() as db:
            db.execute("DELETE FROM memory_knowledge WHERE subject='first_shelter' AND fact='goal'")
        self.assertEqual(self.say("build a computer!"), "First I need to build my home, then make iron tools, build "
                         "my workshop and wire up my first circuits. After that, I promise!")

    def test_a_goal_waiting_on_one_that_is_not_registered_still_gets_an_answer(self):
        """Fix round 1 (Minor 2): no StopIteration drops the request question."""
        dream = replace(GOALS["herd"], name="dream", after=("no_such_goal",))
        with self.world.connect() as db:
            note = note_for(self.situation(db), dream, "after", 30.0, self.now + 10)
        self.assertEqual(note["answer"], "First I need to finish another goal. After that, I promise!")

    def test_with_no_goal_a_request_that_would_lose_the_next_choice_is_promised_for_after(self):
        """Fix round 1 (Minor 1): with no goal under way, the request is compared with the best other open
        goal, as the next goal choice will: a shy pet's pull (bond 0) leaves a cozy home behind iron
        tools, so Mimo promises it for after them instead of saying it comes next."""
        self.edit(lambda state: state.update(bond={"value": 0.0, "seen_at": self.now, "gains": {"day": None}}))
        self.assertEqual(self.say("please decorate your home"), "Maybe. After I make iron tools.")
        self.assertEqual(self.request()["goal"], "cozy_home")
        with self.world.connect() as db:
            self.assertEqual(offers(self.situation(db))[0][0].name, "iron_tools")

    def test_a_repeating_goal_resting_after_it_was_reached_is_answered_honestly(self):
        """Fix round 1 (Minor 5): a repeating goal rests (goals.REPEAT_REST) after it is reached: "I just
        did that", not "I gave up"; one given up is still "I gave up on that for now"."""
        with self.world.transaction() as db:
            know(db, "cave", "goal", self.now - 5)
            log_event(db, self.now - 5, "goal", f"{self.life['name']} reached a goal: look into a cave.")
        self.edit(lambda state: ensure_brain(state).setdefault("goal_penalties", {}).update(
            cave=self.now + REPEAT_REST))
        self.assertEqual(self.say("go look at the cave"), "I just did that! I'll do it again later.")
        with self.world.transaction() as db:
            log_event(db, self.now, "plan", f"{self.life['name']} set a goal aside for now: look into a cave (stuck).")
        self.edit(lambda state: ensure_brain(state)["goal_penalties"].update(cave=self.now + REPEAT_REST / 2))
        self.assertEqual(self.say("go look at the cave"), "I gave up on that for now. Ask me again tomorrow?")
        self.edit(lambda state: ensure_brain(state)["goal_penalties"].update(cave=self.now + SET_ASIDE))
        self.assertEqual(self.say("go look at the cave"), "I gave up on that for now. Ask me again tomorrow?")

    def test_a_promise_kept_too_late_or_a_goal_reached_before_the_request_is_a_plain_report(self):
        """Fix round 1 (Minor 3): the promise is kept only by a goal reached while the request lasts,
        from when it was made (goal_report's `request["at"] <= event["at"] < until`); a lapsed request
        is cleared."""
        self.say("please make iron tools")
        run_chores(self.world, self.now, 1.0)  # the inbox starts
        request, before = self.request(), bond_level(self.world.state(), self.now)
        reached_text = f"{self.life['name']} reached a goal: iron tools."
        with self.world.transaction() as db:
            log_event(db, request["at"] - 1, "goal", reached_text)  # before the request
        run_chores(self.world, self.now + 1, 1.0)
        self.assertEqual(self.request(), request)  # still asked for
        later = request["until"] + 5
        with self.world.transaction() as db:
            log_event(db, later, "goal", reached_text)  # after it lapsed
        run_chores(self.world, later + 1, 1.0)
        state = self.world.state()
        self.assertIsNone(state["bond"]["request"])
        self.assertAlmostEqual(bond_level(state, request["at"] + 20), before)  # no promise credit
        with self.world.connect() as db:
            texts = [item["text"] for item in inbox_items(db)]
        self.assertEqual(texts, ["I reached a goal: iron tools.", "I reached a goal: iron tools."])

    def test_everyday_lines_keep_the_reply_and_leave_no_asked_fact(self):
        """Fix round 1 (Important 2): through the rules (no key), no everyday line is answered as a
        request, and none is kept as an "asked" owner fact that could push the owner's name out."""
        answers = ("I don't know how", "I can't", "I promise", "I'll", "I already did", "right now:", "gave up")
        for text in EVERYDAY:
            reply = self.say(text)
            self.assertFalse(any(words in reply for words in answers), (text, reply))
        self.assertIsNone(self.request())
        with self.world.connect() as db:
            self.assertEqual([fact for fact in owner_facts(db) if fact[0] == "asked"], [])

    def test_a_jev_pick_the_rules_see_no_request_in_is_not_kept_as_asked(self):
        """Fix round 1 (Important 2): Jev's pick is still said, but an "asked" fact is kept only for words
        the rules read as a request too."""
        def jev(url, headers, body, timeout):
            return {"answers": {"reply": {"choice": "mood"}, "request": {"choice": "cant"}}}
        self.assertTrue(self.say("you make me happy", JEV, jev).startswith("I don't know how to do that yet."))
        with self.world.connect() as db:
            self.assertEqual(owner_facts(db), [])

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

    def test_a_goal_verb_alone_takes_no_request(self):
        """Fix round 2 (B): "wire me some money" was taken, a request pulling the first circuits."""
        reply = self.say("wire me some money")
        self.assertNotIn("I promise", reply)
        self.assertIsNone(self.request())

    def test_you_could_or_you_can_with_a_recipe_still_teaches_and_asks_nothing(self):
        """Fix round 2 (C): "you could" and "you can" are cues now, and a line that teaches is still a
        lesson, not a request (request_question's teach return)."""
        self.assertEqual(self.say("you could make a bow from sticks and string"), "Oh, a bow takes three sticks and "
                         "three string, at a crafting table. Thank you for teaching me!")
        self.assertEqual(self.say("you can make a bow from sticks and string"),
                         "I know that one! A bow takes three sticks and three string, at a crafting table.")
        self.assertIsNone(self.request())
        self.assertEqual(self.say("you could build a workshop"),
                         "First I need to make iron tools. After that, I promise!")
        self.assertEqual(self.request()["goal"], "workshop")

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


# Fix round 1 (Important 1): true lessons said with a describing word or an adverb after the verb.
TRUE_WITH_A_MODIFIER = (
    ("cows give good leather", "cow:drops"), ("cows give tasty beef", "cow:drops"),
    ("cows give great beef", "cow:drops"), ("sheep give soft wool", "sheep:drops"), ("sheep give fluffy wool", "sheep:drops"),
    ("sheep give nice wool", "sheep:drops"), ("chickens drop white feathers", "chicken:drops"),
    ("chickens drop soft feathers", "chicken:drops"), ("a bow needs strong string", "recipe:bow"),
    ("an iron sword needs shiny iron ingots", "recipe:iron_sword"), ("coal burns well", "coal_ore"),
    ("coal burns brightly", "coal_ore"), ("coal burns hot", "coal_ore"), ("moss grows thick in forests", "moss"),
    ("sugar cane grows near water", "sugar_cane"), ("sugar cane grows next to water", "sugar_cane"),
    ("lava burns things", "lava"), ("coal burns", "coal_ore"),
    ("you can make a bow from sticks and string", "recipe:bow"))


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

    def test_a_describing_word_or_adverb_after_the_verb_no_longer_doubts_a_true_lesson(self):
        """Fix round 1 (Important 1): the verb's clause is read to its end, describing words and a few
        adverbs are passed over, and one lesson word in it is enough."""
        for text, thing in TRUE_WITH_A_MODIFIER:
            found = claims(text)
            self.assertIn(thing, found.taught, text)
            self.assertFalse(found.doubtful, text)
        for text in ("cows give milk", "cows give milk and leather", "cows give tasty milk", "cows give wings"):
            self.assertEqual(claims(text), Claims((), True, False), text)  # the first clause holds no lesson word
        self.assertEqual(claims("cows count in twos").taught, ())

    def test_a_word_the_lesson_does_not_know_before_its_lesson_word_is_doubted(self):
        """Fix round 2 (A): one lesson word in the clause is enough only when no word the lesson does not
        know comes before it (a material, a distance or a state is no describing word), so a wrong
        qualifier is never thanked for; the true lines with a describing word still teach."""
        for text in ("sugar cane grows far from water", "sugar cane grows away from water",
                     "moss grows away from forests", "an iron sword needs golden ingots",
                     "diamonds need a golden pickaxe", "cows give rotten beef", "cows drop cooked beef"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)
        for text, thing in TRUE_WITH_A_MODIFIER:
            self.assertIn(thing, claims(text).taught, text)

    def test_numbers_alone_teach_nothing_and_observations_are_chat(self):
        self.assertEqual(claims("cows count in twos").taught, ())  # the controller's case (a)
        for text in ("cows are everywhere in this field", "sheep are everywhere in this field",  # case (b)
                     "sheep would be lovely"):
            self.assertEqual(claims(text), Claims((), False, False), text)


if __name__ == "__main__":
    unittest.main()

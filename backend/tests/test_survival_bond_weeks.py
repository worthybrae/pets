"""Bond's final fix wave, group 2 and T4: honesty over weeks.

I3 (the owner's name outlives any number of facts), I5 (a promise's clock starts when its goal can be
taken up, a lapse is told once, the HUD shows a waiting promise), I6 (no "I don't know how" about a recipe
Mimo knows), I7 (repeating goals and naming asks don't flood the inbox; an unanswered ask is never pruned;
opening the inbox marks only what it listed), m6 (a shy "maybe"), m7 (two places the same words), m8 (a
named place remembered), m13 (a promise kept at a faded bond pays), m14 (a care ask answered), and Task 9's
parked (3) ("you can make bread from wheat" asks for nothing) and (6) (the owner's name in answers).
"""

import json
import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.api.bond import ReadUpTo
from backend.survival import bonding, minding  # noqa: F401  (every Bond and Mind writer registers)
from backend.survival.actions import ensure_actions
from backend.survival.bond import GAINS, bond_level, grow_bond
from backend.survival.care import give_care
from backend.survival.choosing import InlineExecutor
from backend.survival.goals import GOALS
from backend.survival.hatch import hatch
from backend.survival.inbox import ITEMS_KEPT, ITEMS_SHOWN, inbox_items, mark_ids, post_item, unread
from backend.survival.memory import know, learn, remember
from backend.survival.once import forget_logged
from backend.survival.owner_facts import FACTS_KEPT, NAMED_KEPT, owner_facts, owner_name, remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.replies import Heard
from backend.survival.requests import REQUEST_DAYS, pull, request_view, rules_request
from backend.survival.situation import from_db
from backend.survival.talk import owner_says
from backend.survival.talker import Talker, run_chores
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
DAY = 3600.0  # a game day, in real seconds at the production scale (1)


class World(unittest.TestCase):
    """A pet at the production scale (1): a game day is a real hour."""

    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]
        with self.world.transaction() as db:
            know(db, "first_shelter", "goal", BORN + 1)  # home stands: iron tools and a herd are open
        self.now = BORN + 10
        run_chores(self.world, BORN + 2, 1.0)  # the inbox starts

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

    def say(self, text):
        owner_says(self.world, text, self.now, 1.0)
        Talker(env={}, http=None, executor_factory=InlineExecutor, scale=1.0).poll(self.registry, self.now + 1)
        self.now += 20
        with self.world.connect() as db:
            return db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]

    def request(self):
        return self.world.state()["bond"].get("request")

    def items(self, kind=None):
        with self.world.connect() as db:
            return [item for item in reversed(inbox_items(db, 10_000)) if kind is None or item["kind"] == kind]

    def reached(self, at, goal):
        with self.world.transaction() as db:
            know(db, goal, "goal", at)
            title = GOALS[goal].title
            log_event(db, at, "goal", f"{self.name} reached a goal: {title[:1].lower()}{title[1:]}.")


class OwnerNameTests(World):
    def test_the_owners_name_outlives_sixty_later_facts(self):
        """I3: the name never counts toward the 40; places named are capped at 10 on their own."""
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN)
            for number in range(60):
                kind = ("likes", "named", "asked")[number % 3]
                remember_fact(db, kind, f"thing number {number}", BORN + 1 + number)
            facts = owner_facts(db)
        self.assertEqual(owner_name(facts), "Sam")
        self.assertLessEqual(sum(1 for kind, _ in facts if kind not in ("name", "named")), FACTS_KEPT)
        self.assertEqual(sum(1 for kind, _ in facts if kind == "named"), NAMED_KEPT)

    def test_naming_places_never_pushes_out_what_the_owner_said(self):
        with self.world.transaction() as db:
            remember_fact(db, "likes", "the lake", BORN)
            for number in range(50):
                remember_fact(db, "named", f"a cave north of home, called Hollow {number}", BORN + 1 + number)
            facts = owner_facts(db)
        self.assertIn(("likes", "the lake"), facts)


class PromiseTests(World):
    def test_an_after_promise_waits_for_its_blocker_then_pulls_and_is_kept(self):
        """I5: "First I need to make iron tools" waits five game days for them (the old clock ran out after
        three), its clock starts once iron tools are made, and reaching the goal keeps the promise."""
        self.assertEqual(self.say("please make me some armor"),
                         "First I need to make iron tools. After that, I promise!")
        self.assertEqual((self.request()["goal"], self.request()["until"]), ("armor_up", None))
        view = request_view(self.world.state(), self.now)
        self.assertEqual((view["title"], view["after"], view["until"]), ("Armor up", "Iron tools", None))
        for hour in range(1, 6):  # five game days go by: the promise waits
            run_chores(self.world, self.now + hour * DAY, 1.0)
        self.assertIsNotNone(request_view(self.world.state(), self.now + 5 * DAY))
        self.assertEqual([item["text"] for item in self.items() if "couldn't" in item["text"]], [])
        self.reached(self.now + 5 * DAY + 10, "iron_tools")
        run_chores(self.world, self.now + 5 * DAY + 20, 1.0)
        request = self.request()
        self.assertAlmostEqual(request["until"], self.now + 5 * DAY + 10 + REQUEST_DAYS * DAY)
        with self.world.connect() as db:
            state = read_state(db)
            ensure_actions(state)
            self.assertGreater(pull(from_db(db, state, self.now + 6 * DAY, 1.0), GOALS["armor_up"])[0], 0)
        self.reached(self.now + 7 * DAY, "armor_up")
        run_chores(self.world, self.now + 7 * DAY + 10, 1.0)
        self.assertIsNone(self.request())
        self.assertEqual(self.items("report")[-1]["text"],
                         "You asked me to make my armor, and I did it! I kept my promise.")

    def test_a_promise_for_after_the_current_goal_starts_its_clock_when_that_goal_is_reached(self):
        self.with_goal("herd", bond=40.0)
        self.assertEqual(self.say("please make iron tools"), "After I raise a herd, I promise.")
        self.assertIsNone(self.request()["until"])
        self.assertEqual(request_view(self.world.state(), self.now)["after"], "A herd of its own")
        self.reached(self.now + 4 * DAY, "herd")
        run_chores(self.world, self.now + 4 * DAY + 5, 1.0)
        self.assertAlmostEqual(self.request()["until"], self.now + 4 * DAY + REQUEST_DAYS * DAY)

    def test_a_lapsed_promise_posts_exactly_one_inbox_item(self):
        """I5: never a silent broken promise, and never told twice."""
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN)
        self.with_goal("herd", bond=90.0)
        self.assertEqual(self.say("please make iron tools"), "Yes, Sam! I'll make iron tools next.")
        until = self.request()["until"]
        for at in (until - 5, until + 5, until + 50, until + DAY):
            run_chores(self.world, at, 1.0)
        lapsed = [item["text"] for item in self.items() if "in time" in item["text"]]
        self.assertEqual(lapsed, ["Sam, I couldn't make iron tools in time. Ask me again?"])
        self.assertIsNone(self.request())
        self.assertIsNone(request_view(self.world.state(), until + DAY))

    def test_a_promise_whose_goal_never_opens_is_told_after_waiting_its_longest(self):
        """I5: a promise for after the first circuits waits WAIT_DAYS at most, then is told once."""
        from backend.survival.requests import WAIT_DAYS
        self.assertTrue(self.say("please build a computer").startswith("First I need to make iron tools"))
        for day in (1, WAIT_DAYS - 1, WAIT_DAYS + 1, WAIT_DAYS + 2):
            run_chores(self.world, self.now + day * DAY, 1.0)
        self.assertEqual([item["text"] for item in self.items() if "in time" in item["text"]],
                         ["I couldn't build a computer in time. Ask me again?"])
        self.assertIsNone(self.request())

    def test_a_shy_maybe_is_no_promise_on_the_hud(self):
        """m6: "Maybe. After I ..." shows softly, and lapses softly."""
        self.with_goal("herd", bond=10.0)
        self.assertEqual(self.say("please make iron tools"), "Maybe. After I raise a herd.")
        self.assertTrue(request_view(self.world.state(), self.now)["maybe"])

    def test_a_recipe_mimo_knows_is_never_one_it_does_not_know_how_to_make(self):
        """I6: "could you make a furnace?" with the furnace known."""
        with self.world.transaction() as db:
            learn(db, "furnace", BORN + 3)
        self.with_goal("herd")
        said = self.say("could you make a furnace?")
        self.assertNotIn("know how to do that", said)
        self.assertEqual(said, "I know how to make a furnace, but I'm busy trying to raise a herd right now.")
        self.assertEqual(self.say("could you build a tower by the lake?"),
                         "That's not one of my goals yet. I'm busy trying to raise a herd anyway.")

    def test_you_can_make_bread_from_wheat_is_no_request(self):
        """Task 9's parked (3): how a thing is made is said, not asked."""
        statuses = {name: "open" for name in GOALS}
        self.assertEqual(rules_request(Heard("you can make bread from wheat"), statuses), "none")
        self.assertEqual(rules_request(Heard("you can make planks out of logs"), statuses), "none")
        self.assertEqual(rules_request(Heard("could you make bread from wheat?"), statuses), "cant")
        self.assertEqual(rules_request(Heard("you could build a workshop"), statuses), "workshop")

    def test_a_promise_kept_at_a_faded_full_bond_still_counts(self):
        """m13: the gain is capped by the bond's level, not the stored value."""
        state = {"bond": {"value": 100.0, "seen_at": BORN, "gains": {"day": None}}}
        faded = bond_level(state, BORN + 5 * 86_400)
        grown = grow_bond(state, "promise", BORN + 5 * 86_400, present=False)
        self.assertAlmostEqual(grown, min(100.0, faded + GAINS["promise"]))
        self.assertEqual(state["bond"]["seen_at"], BORN)  # still no visit


class InboxFloodTests(World):
    def test_a_repeating_goal_is_reported_once_then_at_most_once_a_real_day(self):
        """I7: an expedition reached five times in a UTC day is one report; the next day, one more."""
        for number in range(5):
            self.reached(BORN + 100 + number * DAY, "expedition")
        run_chores(self.world, BORN + 100 + 5 * DAY, 1.0)
        self.assertEqual([item["text"] for item in self.items("report")], ["I reached a goal: an expedition."])
        tomorrow = BORN + 86_400 * 2
        self.reached(tomorrow, "expedition")
        run_chores(self.world, tomorrow + 5, 1.0)
        self.assertEqual(len(self.items("report")), 2)

    def found_caves(self, count, start):
        with self.world.transaction() as db:
            for number in range(count):
                remember(db, "cave", (40 * number + 30, 60, 5), start + number)

    def test_one_naming_ask_waits_at_a_time_and_a_newer_one_replaces_a_stale_one(self):
        """I7: no hourly naming ask; an owner away a real day finds one, about the newest place."""
        self.found_caves(5, BORN + 50)
        for hour in range(1, 12):
            run_chores(self.world, BORN + 60 + hour * DAY, 1.0)
        asks = [item for item in self.items("ask") if item["data"].get("ask") == "name"]
        self.assertEqual(len(asks), 1)
        run_chores(self.world, BORN + 60 + 86_400 + DAY, 1.0)  # a real day later: stale, replaced
        asks = [item for item in self.items("ask") if item["data"].get("ask") == "name"]
        self.assertEqual(len(asks), 1)
        self.assertNotEqual(asks[0]["data"]["place"], {"kind": "cave", "x": 30, "y": 60, "z": 5})

    def test_an_unanswered_ask_survives_three_hundred_later_items(self):
        with self.world.transaction() as db:
            ask = post_item(db, BORN + 5, "ask", "I found a cave. What should we call it?",
                            {"ask": "name", "place": {"kind": "cave", "x": 1, "y": 2, "z": 3}, "words": "a cave"})
            for number in range(300):
                post_item(db, BORN + 6 + number, "report", f"News {number}.")
        items = {item["id"] for item in self.items()}
        self.assertIn(ask, items)
        self.assertLessEqual(len(items), ITEMS_KEPT + 1)

    def test_read_items_are_pruned_before_unread_ones(self):
        with self.world.transaction() as db:
            first = post_item(db, BORN + 5, "report", "Unread and old.")
            for number in range(ITEMS_KEPT - 1):
                post_item(db, BORN + 6 + number, "report", f"News {number}.")
            db.execute("UPDATE mimo_inbox SET read_at=? WHERE id > ?", (BORN + 900, first))
            post_item(db, BORN + 999, "report", "One more.")
            post_item(db, BORN + 999, "report", "And another.")
        self.assertIn(first, {item["id"] for item in self.items()})

    def test_opening_the_inbox_marks_only_what_it_listed(self):
        """I7: 50 unread, the panel lists 30 and marks those: 20 stay unread."""
        with self.world.transaction() as db:
            for number in range(50):
                post_item(db, BORN + 5 + number, "report", f"News {number}.")
            listed = [item["id"] for item in inbox_items(db, ITEMS_SHOWN)]
        self.assertEqual(mark_ids(self.world, listed, BORN + 100), 20)
        self.assertEqual(ReadUpTo(ids=listed).ids, listed)

    def test_two_days_of_a_busy_explorer_are_under_thirty_items(self):
        """I7: 48 game days at the production scale (two real days) of repeating goals and new places."""
        for day in range(48):
            at = BORN + 100 + day * DAY
            self.reached(at, "expedition")
            self.reached(at + 600, "cave")
            self.found_caves(1, at + 900) if day % 2 == 0 else None
            with self.world.transaction() as db:
                remember(db, "water", (day * 50, 60, 700), at + 1000)
            run_chores(self.world, at + 1200, 1.0)
        self.assertLess(len(self.items()), 30, [item["text"] for item in self.items()])


class PlaceTests(World):
    def test_two_places_with_the_same_words_are_told_apart(self):
        """m7: "another lake south of home", and "far" when it is."""
        with self.world.transaction() as db:
            remember(db, "home", (0, 60, 0), BORN + 3)
        for number, (x, z) in enumerate(((0, 20), (10, 50), (0, 200))):
            with self.world.transaction() as db:
                remember(db, "water", (x, 60, z), BORN + 50 + number)
            run_chores(self.world, BORN + 60 + number * 2 * 86_400, 1.0)
            asks = [item for item in self.items("ask") if item["data"].get("ask") == "name"]
            self.world_answer(asks[-1]["id"], f"Pond {number}", BORN + 61 + number * 2 * 86_400)
        words = [item["data"]["words"] for item in self.items("ask") if item["data"].get("ask") == "name"]
        self.assertEqual(words, ["a lake south of home", "another lake south of home", "a lake far south of home"])

    def world_answer(self, item, name, at):
        from backend.survival.inbox import name_place
        return name_place(self.world, item, name, at)

    def test_a_named_place_is_remembered_and_its_fact_reads_well(self):
        """m8: a told memory, and the fact "a lake south of home, called Echo Hollow"."""
        with self.world.transaction() as db:
            ask = post_item(db, BORN + 5, "ask", "I found a lake. What should we call it?",
                            {"ask": "name", "place": {"kind": "water", "x": 1, "y": 2, "z": 3},
                             "words": "a lake south of home"})
        self.world_answer(ask, "Echo Hollow", BORN + 6)
        with self.world.connect() as db:
            self.assertIn(("named", "a lake south of home, called Echo Hollow"), owner_facts(db))
            told = [row[0] for row in db.execute("SELECT text FROM mind_memories WHERE kind='told'")]
            said = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertIn("You helped me name a lake south of home, called Echo Hollow.", told)
        self.assertEqual(said, "Echo Hollow! I love it. I'll remember that.")


class CareAskTests(World):
    def test_a_care_ask_is_answered_when_that_days_care_is_given(self):
        """m14: "Could you spare a snack?" is marked done (and read) once today's snack is given."""
        self.edit(lambda state: (state["vitals"].update(hunger=10.0), state.update(last_tick_at=self.now)))
        run_chores(self.world, self.now, 1.0)
        [ask] = [item for item in self.items("ask") if item["data"].get("care") == "snack"]
        self.assertFalse(ask["data"].get("done"))
        give_care(self.world, "snack", self.now + 5)
        run_chores(self.world, self.now + 10, 1.0)
        [ask] = [item for item in self.items("ask") if item["data"].get("care") == "snack"]
        self.assertTrue(ask["data"]["done"])
        self.assertTrue(ask["read"])
        with self.world.connect() as db:
            self.assertEqual(unread(db), sum(1 for item in self.items() if not item["read"]))
        self.assertEqual(json.loads(json.dumps(ask["data"]))["care"], "snack")


if __name__ == "__main__":
    unittest.main()

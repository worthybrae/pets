"""Bond follow-up (the final fix wave's re-review): N1, N2 and N3's backend side.

N1: opening the inbox can always clear it (every unread item is listed first).
N2: a promise never lapses while Mimo works on its goal, a finish past its time is still credited, and a
goal tried and set aside is told as tried.
N3: a story written for an owner who was there says so in its data ("present"), so the viewer never pops it
up, while a story about an absence pops up whenever it arrives.
"""

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.api.bond import ReadUpTo, get_inbox, read_inbox
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.survival import bonding  # noqa: F401  (every Bond writer registers)
from backend.survival.bond import visit
from backend.survival.choosing import InlineExecutor
from backend.survival.diary import diary_entries
from backend.survival.goals import GOALS, lower
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items, post_item
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.requests import request_view
from backend.survival.talk import owner_says
from backend.survival.talker import Talker, run_chores
from backend.survival.triggers import ensure_brain
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
DAY = 3600.0  # a game day in real seconds at the production scale (1)


class InboxClearsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "no-legacy.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_opening_the_inbox_over_fifty_unread_items_clears_it(self):
        """N1: the re-review's week run left 18 unread for good; every unread item is listed now, first."""
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        with world.transaction() as db:
            for number in range(40):
                post_item(db, 1.0 + number, "report", f"Old news {number}.")
            db.execute("UPDATE mimo_inbox SET read_at=2.0")
            for number in range(50):
                post_item(db, 100.0 + number, "found", f"New thing {number}.")
            post_item(db, 200.0, "story", "Day 3 was a good one.", {"day": 3, "writer": "rules"})
        listed = get_inbox()
        self.assertEqual(listed["unread"], 51)
        unread = [item["id"] for item in listed["items"] if not item["read"]]
        self.assertEqual(len(unread), 51)
        self.assertEqual(listed["items"][:51], [item for item in listed["items"] if not item["read"]])  # unread first
        self.assertTrue(any(item["read"] for item in listed["items"]))  # then the newest read ones
        self.assertEqual(read_inbox(ReadUpTo(ids=unread)), {"unread": 0})
        self.assertEqual(get_mimo()["inbox"]["unread"], 0)


class PromiseWorkTests(unittest.TestCase):
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

    def goal(self, name, at):
        def change(state):
            ensure_brain(state)["goal"] = {"name": name, "since": at, "picker": "utility", "progress": 0.0,
                                           "best": 0.0, "best_at": at, "plan": [], "checked_at": None, "day_start": at}
        self.edit(change)

    def log(self, at, kind, text):
        with self.world.transaction() as db:
            log_event(db, at, kind, text)

    def ask(self, text):
        """The owner asks, at a devoted bond and with no goal under way: "Yes! I'll ... next." (a promise
        whose clock starts at once)."""
        self.edit(lambda state: state.setdefault("bond", {}).update(value=100.0, seen_at=self.now))
        owner_says(self.world, text, self.now, 1.0)
        Talker(env={}, http=None, executor_factory=InlineExecutor, scale=1.0).poll(self.registry, self.now + 1)
        with self.world.connect() as db:
            return db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]

    def notices(self):
        with self.world.connect() as db:
            return [item["text"] for item in reversed(inbox_items(db, 1000)) if item["data"].get("lapsed")
                    or item["data"].get("promise")]

    def take_up(self, at):
        """Mimo takes up the herd, the goal the owner asked for: its goal event and its brain."""
        self.log(at, "plan", f'{self.name} set a new goal: {lower(GOALS["herd"].title)}. "Sheep!"')
        self.goal("herd", at)

    def test_a_promise_never_lapses_while_mimo_works_on_its_goal_and_a_late_finish_is_kept(self):
        """N2: the models run's armor lapsed three minutes after it became the goal."""
        self.assertEqual(self.ask("please raise a herd"), "Yes! I'll raise a herd next.")
        until = read_state_request(self.world)["until"]
        self.take_up(until - 60)
        for at in (until - 30, until + 5, until + DAY, until + 2 * DAY):
            run_chores(self.world, at, 1.0)
        self.assertEqual(self.notices(), [])
        self.assertIsNotNone(read_state_request(self.world))
        self.assertIsNotNone(request_view(self.world.state(), until + 2 * DAY))  # the HUD still shows it
        self.log(until + 2 * DAY + 10, "goal", f"{self.name} reached a goal: {lower(GOALS['herd'].title)}.")
        self.edit(lambda state: ensure_brain(state).update(goal=None))
        run_chores(self.world, until + 2 * DAY + 20, 1.0)
        self.assertEqual(self.notices(), ["You asked me to raise a herd, and I did it! I kept my promise."])
        self.assertIsNone(read_state_request(self.world))

    def test_a_promised_goal_tried_and_set_aside_is_told_as_tried(self):
        """N2: "I tried to raise a herd, but it didn't work out this time.", never "I never got to"."""
        self.ask("please raise a herd")
        self.take_up(self.now + 60)
        run_chores(self.world, self.now + 90, 1.0)
        self.log(self.now + 120, "plan", f"{self.name} set a goal aside for now: {lower(GOALS['herd'].title)} "
                                         "(no progress for a day).")
        self.edit(lambda state: ensure_brain(state).update(goal=None))
        run_chores(self.world, self.now + 130, 1.0)
        run_chores(self.world, self.now + 5 * DAY, 1.0)
        self.assertEqual(self.notices(), ["I tried to raise a herd, but it didn't work out this time. Ask me again?"])
        self.assertIsNone(read_state_request(self.world))

    def test_a_goal_taken_up_between_chores_still_counts_as_worked_on(self):
        """N2: the goal event alone (Mimo took it up and switched away before a chore looked) marks it tried."""
        self.ask("please raise a herd")
        self.log(self.now + 60, "plan", f'{self.name} set a new goal: {lower(GOALS["herd"].title)}. "Sheep!"')
        until = read_state_request(self.world)["until"]
        run_chores(self.world, until + 5, 1.0)
        self.assertEqual(self.notices(), ["I tried to raise a herd, but it didn't work out this time. Ask me again?"])

    def test_a_promise_never_taken_up_still_runs_out_as_before(self):
        self.ask("please raise a herd")
        until = read_state_request(self.world)["until"]
        run_chores(self.world, until + 5, 1.0)
        self.assertEqual(self.notices(), ["I couldn't raise a herd in time. Ask me again?"])


class PresentStoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.world = SurvivalWorld(self.registry.world_path(hatch(self.registry, random.Random(8), timestamp=BORN)))

    def tearDown(self):
        self.directory.cleanup()

    def visit(self, at):
        with self.world.transaction() as db:
            state = read_state(db)
            visit(state, at)
            write_state(db, state)

    def stories(self):
        with self.world.connect() as db:
            return list(reversed(diary_entries(db)))

    def test_a_story_for_an_owner_who_was_there_says_so_and_one_about_an_absence_does_not(self):
        """N3: the story's data keeps story_job's `present`, and the diary shows it."""
        talker = Talker(env={}, http=None, executor_factory=InlineExecutor, scale=60.0)
        self.visit(BORN + 10)
        self.visit(BORN + 50)
        talker.poll(self.registry, BORN + 61)
        [watched] = self.stories()
        self.assertIs(watched["present"], True)
        with self.world.connect() as db:
            self.assertIs(inbox_items(db, 1)[0]["data"]["present"], True)
        with self.world.transaction() as db:
            db.execute("UPDATE mimo_inbox SET read_at=? WHERE kind='story'", (BORN + 70,))
        self.visit(BORN + 75)  # day 2, then away for days
        talker.poll(self.registry, BORN + 60 * 5 + 1)
        away = self.stories()[-1]
        self.assertEqual((away["day"], away["last"], away["present"]), (2, 5, False))


def read_state_request(world):
    return world.state()["bond"].get("request")


if __name__ == "__main__":
    unittest.main()

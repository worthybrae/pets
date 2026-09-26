import hashlib
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.bond import PlaceName, ReadUpTo, answer_inbox, get_inbox, read_inbox
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.survival.care import give_care
from backend.survival.choosing import InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.inbox import ITEMS_KEPT, STORY, inbox_items, mark_read, name_place, post_item, unread
from backend.survival.memory import places, remember
from backend.survival.once import forget_logged
from backend.survival.owner_facts import owner_facts, remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.talker import CHORE_EVERY, CHORES, Talker, run_chores
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0


class InboxTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]
        self.chores(BORN + 1)  # the inbox starts: old news and old places are passed over

    def tearDown(self):
        self.directory.cleanup()

    def chores(self, now, scale=1.0):
        run_chores(self.world, now, scale)

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state, db)
            write_state(db, state)

    def items(self):
        with self.world.connect() as db:
            return list(reversed(inbox_items(db, 1000)))

    def test_items_count_as_unread_until_marked_read(self):
        with self.world.transaction() as db:
            first = post_item(db, BORN + 2, "report", "One.")
            post_item(db, BORN + 3, "report", "Two.")
            post_item(db, BORN + 4, "report", "Three.")
        with self.world.connect() as db:
            self.assertEqual(unread(db), 3)
            self.assertEqual([item["text"] for item in inbox_items(db, 2)], ["Three.", "Two."])
        self.assertEqual(mark_read(self.world, first + 1, BORN + 5), 1)
        self.assertEqual([item["read"] for item in self.items()], [True, True, False])

    def test_the_inbox_keeps_its_newest_items_and_every_story(self):
        with self.world.transaction() as db:
            post_item(db, BORN, STORY, "Day 1 was quiet.")
            for number in range(ITEMS_KEPT + 5):
                post_item(db, BORN + number, "report", f"Report {number}.")
        items = self.items()
        self.assertEqual(len(items), ITEMS_KEPT + 1)
        self.assertEqual(items[0]["kind"], STORY)
        self.assertEqual(items[1]["text"], "Report 5.")

    def test_milestones_are_reported_in_mimos_own_words_and_old_news_is_not(self):
        with self.world.transaction() as db:
            log_event(db, BORN + 2, "goal", f"{self.name} reached a goal: a home of its own.")
            log_event(db, BORN + 3, "built", f"{self.name} finished building a hut and moved in.")
            log_event(db, BORN + 4, "purpose", f'{self.name} decided to rest. "Ahh."')  # no mirror takes it
        self.chores(BORN + 10)
        self.assertEqual([(item["kind"], item["text"]) for item in self.items()],
                         [("report", "I reached a goal: a home of my own."),
                          ("report", "I finished building a hut and moved in.")])
        self.chores(BORN + 20)
        self.assertEqual(len(self.items()), 2)  # each event once

    def test_mimo_asks_for_a_snack_or_a_bandage_once_a_day_while_there_is_one_to_give(self):
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN)
        self.edit(lambda state, db: state["vitals"].update(hunger=10.0, health=20.0))
        self.chores(BORN + 10)
        self.chores(BORN + 20)
        asks = [(item["text"], item["data"]) for item in self.items() if item["kind"] == "ask"]
        self.assertEqual(asks, [("Sam, I'm really hungry. Could you spare a snack?", {"care": "snack"}),
                                ("Sam, I got badly hurt. Could you bandage me?", {"care": "bandage"})])

    def test_no_ask_for_care_already_given_today(self):
        self.edit(lambda state, db: state.update(last_tick_at=BORN + 9))
        give_care(self.world, "snack", BORN + 10)
        self.edit(lambda state, db: state["vitals"].update(hunger=10.0))
        self.chores(BORN + 11)
        self.assertEqual(self.items(), [])

    def test_mimo_asks_the_owner_to_name_a_place_it_found_and_keeps_the_name(self):
        with self.world.transaction() as db:
            home = places(db, ("home",))
            remember(db, "cave", (40, 60, -80), BORN + 5, "cave mouth")
            remember(db, "water", (0, 50, 30), BORN + 6)
        self.chores(BORN + 10)
        [ask] = self.items()
        self.assertEqual(ask["kind"], "ask")
        self.assertEqual(ask["data"]["ask"], "name")
        self.assertTrue(ask["text"].startswith("I found a cave"), ask["text"])
        self.assertTrue(ask["text"].endswith("What should we call it?"))
        if home:
            self.assertIn("of home", ask["text"])
        self.chores(BORN + 20)
        self.assertEqual(len(self.items()), 1)  # one a game day
        with self.assertRaises(ValueError):
            name_place(self.world, ask["id"], "<script>", BORN + 30)
        answered = name_place(self.world, ask["id"], "  Echo   Hollow ", BORN + 30)
        self.assertEqual((answered["data"]["answer"], answered["read"]), ("Echo Hollow", True))
        with self.world.connect() as db:
            [cave] = places(db, ("cave",))
            self.assertEqual(cave["data"]["name"], "Echo Hollow")
            self.assertEqual(owner_facts(db)[0], ("named", f"{ask['data']['words']} Echo Hollow"))
            thanks = db.execute("SELECT who, text FROM mimo_chat ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(tuple(thanks), ("mimo", "Echo Hollow! I love it. That's what I'll call it."))
        with self.assertRaises(ValueError):
            name_place(self.world, ask["id"], "Another", BORN + 31)
        with self.assertRaises(LookupError):
            name_place(self.world, 999, "Nowhere", BORN + 31)
        self.chores(BORN + 10 + 3600)  # a game day later: the lake
        self.assertTrue(self.items()[-1]["text"].startswith("I found a lake"))

    def test_the_talker_runs_the_chores_every_few_seconds(self):
        talker = Talker(env={}, executor_factory=InlineExecutor, scale=1.0)
        with self.world.transaction() as db:
            log_event(db, BORN + 2, "goal", f"{self.name} reached a goal: iron tools.")
        talker.poll(self.registry, BORN + 10)
        self.assertEqual(len(self.items()), 1)
        with self.world.transaction() as db:
            log_event(db, BORN + 11, "goal", f"{self.name} reached a goal: armor up.")
        talker.poll(self.registry, BORN + 10 + CHORE_EVERY / 2)
        self.assertEqual(len(self.items()), 1)
        talker.poll(self.registry, BORN + 10 + CHORE_EVERY)
        self.assertEqual(len(self.items()), 2)

    def test_a_chore_that_crashes_is_rolled_back_alone_and_logged_once(self):
        def broken(db, state, now, scale):
            post_item(db, now, "report", "Half done.")
            state["broken"] = True
            raise RuntimeError("boom")
        with self.world.transaction() as db:
            log_event(db, BORN + 2, "goal", f"{self.name} reached a goal: iron tools.")
        CHORES.insert(0, broken)
        try:
            with self.assertLogs("backend.survival.talker", level="ERROR") as logs:
                self.chores(BORN + 10)
                self.chores(BORN + 20)
        finally:
            CHORES.remove(broken)
        self.assertEqual([item["text"] for item in self.items()], ["I reached a goal: iron tools."])
        self.assertNotIn("broken", self.world.state())
        self.assertEqual(len(logs.records), 1)


class InboxApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "no-legacy.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_owner_reads_the_inbox_marks_it_read_and_answers_a_question(self):
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        with world.transaction() as db:
            post_item(db, 1.0, "report", "I reached a goal: iron tools.")
            ask = post_item(db, 2.0, "ask", "I found a cave. What should we call it?",
                            {"ask": "name", "place": {"kind": "cave", "x": 1, "y": 2, "z": 3}, "words": "a cave"})
        path = Path(world.path)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        listed = get_inbox()
        self.assertEqual(get_mimo()["inbox"]["unread"], 2)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)  # reading never writes
        self.assertEqual(([item["id"] for item in listed["items"]], listed["unread"]), ([ask, ask - 1], 2))
        self.assertEqual([item["id"] for item in get_mimo()["inbox"]["newest"]], [ask, ask - 1])
        self.assertEqual(read_inbox(ReadUpTo(up_to=ask - 1)), {"unread": 1})
        self.assertEqual(answer_inbox(ask, PlaceName(text="Echo Hollow"))["item"]["data"]["answer"], "Echo Hollow")
        for item_id, text, status in ((ask, "Again", 400), (ask + 5, "Nowhere", 404), (ask, "!!", 400)):
            with self.assertRaises(HTTPException) as caught:
                answer_inbox(item_id, PlaceName(text=text))
            self.assertEqual(caught.exception.status_code, status)


if __name__ == "__main__":
    unittest.main()

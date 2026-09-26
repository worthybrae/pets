import hashlib
import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.bond import ChatLine, talk_to_mimo
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.survival.choosing import InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import alive_snapshot
from backend.survival.talk import (
    DAY_LIMIT, HOUR_LIMIT, LINES_KEPT, LINES_SHOWN, TEXT_LIMIT, WAITING, ChatLimited, chat_view, clean, day_start,
    owner_says,
)
from backend.survival.talker import Talker
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state

BORN = 1_000_000.0  # 13:46:40 UTC on 12 January 1970: ten hours of the UTC day are left


class OwnerLinesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def rows(self):
        with self.world.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM mimo_chat ORDER BY id")]

    def test_a_line_is_cleaned_and_queued_as_a_waiting_owner_row(self):
        said = owner_says(self.world, "  Hello\n\tthere,\x07 Mimo!  ", BORN + 10, 60.0)
        self.assertEqual(said["text"], "Hello there, Mimo!")
        self.assertEqual(said["left"], {"hour": HOUR_LIMIT - 1, "day": DAY_LIMIT - 1})
        [row] = self.rows()
        self.assertEqual((row["id"], row["who"], row["text"], row["status"]), (said["id"], "owner", "Hello there, Mimo!", WAITING))
        self.assertEqual((row["at"], row["game_at"]), (BORN + 10, 600.0))

    def test_an_empty_or_too_long_line_is_refused_and_nothing_is_written(self):
        for text in ("", "   \n ", "\x00\x01"):
            with self.assertRaises(ValueError):
                owner_says(self.world, text, BORN + 1, 1.0)
        with self.assertRaises(ValueError):
            owner_says(self.world, "a" * (TEXT_LIMIT + 1), BORN + 1, 1.0)
        owner_says(self.world, "a" * TEXT_LIMIT, BORN + 1, 1.0)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(clean("one\ntwo  three"), "one two three")

    def test_twenty_lines_a_game_hour_then_a_breather(self):
        for line in range(HOUR_LIMIT):
            owner_says(self.world, f"line {line}", BORN + line, 1.0)
        with self.assertRaises(ChatLimited):
            owner_says(self.world, "one more", BORN + 100, 1.0)
        self.assertEqual(len(self.rows()), HOUR_LIMIT)
        owner_says(self.world, "an hour later", BORN + 3600.5, 1.0)  # the first line fell out of the game hour
        self.assertEqual(len(self.rows()), HOUR_LIMIT + 1)

    def test_two_hundred_lines_a_utc_day_then_tomorrow(self):
        # At 60x a game hour is a real minute: a line every 3 real seconds stays within 20 a game hour.
        for line in range(DAY_LIMIT):
            owner_says(self.world, f"line {line}", BORN + 3 * line, 60.0)
        with self.assertRaises(ChatLimited):
            owner_says(self.world, "one more", BORN + 3 * DAY_LIMIT, 60.0)
        tomorrow = day_start(BORN) + 86_400 + 1
        self.assertEqual(owner_says(self.world, "good morning", tomorrow, 60.0)["left"]["day"], DAY_LIMIT - 1)

    def test_the_daily_limit_holds_when_every_line_is_answered_and_tomorrow_prunes_back(self):
        talker = Talker(env={}, executor_factory=InlineExecutor, scale=60.0)
        for line in range(DAY_LIMIT):
            owner_says(self.world, f"line {line}", BORN + 3 * line, 60.0)
            talker.poll(self.registry, BORN + 3 * line + 1)
        self.assertEqual(len(self.rows()), 2 * DAY_LIMIT)  # every line of the UTC day is kept, with its answer
        with self.assertRaises(ChatLimited):
            owner_says(self.world, "one more", BORN + 3 * DAY_LIMIT, 60.0)
        tomorrow = day_start(BORN) + 86_400 + 1
        owner_says(self.world, "good morning", tomorrow, 60.0)
        talker.poll(self.registry, tomorrow + 1)
        rows = self.rows()
        self.assertEqual(len(rows), LINES_KEPT)  # the first store of the day prunes back to the newest lines
        self.assertEqual([row["who"] for row in rows[-2:]], ["owner", "mimo"])
        self.assertEqual(rows[-2]["text"], "good morning")

    def test_a_dead_pet_takes_no_lines(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["died_at"] = BORN + 5
            write_state(db, state)
        with self.assertRaises(LifeOver):
            owner_says(self.world, "hello?", BORN + 10, 1.0)
        self.assertEqual(self.rows(), [])

    def test_the_stream_shows_the_newest_lines_oldest_first_and_whether_a_reply_is_coming(self):
        for line in range(LINES_SHOWN + 3):
            owner_says(self.world, f"line {line}", BORN + line, 1.0)
        view = alive_snapshot(self.life, SurvivalWorld(self.world.path, read_only=True), BORN + 20, 1.0)["chat"]
        self.assertEqual([line["text"] for line in view["lines"]], [f"line {n}" for n in range(3, LINES_SHOWN + 3)])
        self.assertEqual(view["lines"][0]["who"], "owner")
        self.assertTrue(view["waiting"])
        self.assertEqual(view["left"], {"hour": HOUR_LIMIT - LINES_SHOWN - 3, "day": DAY_LIMIT - LINES_SHOWN - 3})

    def test_a_world_from_before_bond_shows_an_empty_chat(self):
        raw = sqlite3.connect(self.world.path)
        raw.execute("DROP TABLE mimo_chat")
        raw.commit()
        raw.close()
        archive = SurvivalWorld(self.world.path, read_only=True)
        with archive.connect() as db:
            view = chat_view(db, read_state(db), BORN + 5, 1.0)
        self.assertEqual(view, {"lines": [], "waiting": False, "left": {"hour": HOUR_LIMIT, "day": DAY_LIMIT}})


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "no-legacy.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def status_of(self, call, *args):
        with self.assertRaises(HTTPException) as caught:
            call(*args)
        return caught.exception.status_code

    def test_the_owner_writes_through_the_api_and_sees_the_line_in_the_stream(self):
        self.assertEqual(self.status_of(talk_to_mimo, ChatLine(text="hi")), 409)  # no pet yet
        hatch_egg()
        said = talk_to_mimo(ChatLine(text="Hi Mimo!"))
        self.assertEqual(said["text"], "Hi Mimo!")
        chat = get_mimo()["chat"]
        self.assertEqual(([line["text"] for line in chat["lines"]], chat["waiting"]), (["Hi Mimo!"], True))
        self.assertEqual(self.status_of(talk_to_mimo, ChatLine(text=" ")), 400)
        self.assertEqual(self.status_of(talk_to_mimo, ChatLine(text="x" * 281)), 400)

    def test_past_the_hourly_limit_the_api_answers_429(self):
        hatch_egg()
        for line in range(HOUR_LIMIT):
            talk_to_mimo(ChatLine(text=f"line {line}"))
        self.assertEqual(self.status_of(talk_to_mimo, ChatLine(text="too many")), 429)

    def test_reading_the_stream_never_writes_the_world(self):
        hatch_egg()
        talk_to_mimo(ChatLine(text="hello"))
        registry = LifeRegistry()
        path = registry.world_path(registry.active_life())
        before = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        get_mimo()
        self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()

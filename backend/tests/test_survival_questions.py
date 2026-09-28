"""W1: Mimo asks its owner about what it does not understand, waits, and hears the answers."""

import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.survival import bonding, minding  # noqa: F401  (the chat, the inbox and teaching)
from backend.api.bond import PlaceName, answer_inbox
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.hatch import hatch
from backend.survival.inbox import inbox_items
from backend.survival.memory import know
from backend.survival.meals import wild_meal
from backend.survival.questions import answer_question, ask_wonders, questions_view
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.wild import thing
from backend.survival.wonders import WONDERS, hesitates, met
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state
from backend.tests.no_model import no_model

BORN = 1_000_000.0
SCALE = 60.0


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def meet(self, *wonders, at=BORN):
        with self.world.transaction() as db:
            state = read_state(db)
            for number, wonder_id in enumerate(wonders):
                met(state, wonder_id, at + number, " north of home" if wonder_id == "red_berries" else "")
            write_state(db, state)

    def chore(self, now):
        with self.world.transaction() as db:
            state = read_state(db)
            changed = ask_wonders(db, state, now, SCALE)
            write_state(db, state)
        return changed

    def questions(self):
        with self.world.connect() as db:
            return questions_view(db)

    def say(self, text, at):
        owner_says(self.world, text, at, SCALE)
        talker = Talker(env={}, http=no_model(self), scale=SCALE)
        talker.poll(self.registry, at + 0.1)
        talker.close()

    def knows(self, name):
        with self.world.connect() as db:
            return db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='lesson'",
                              (thing(name),)).fetchone() is not None

    def test_the_oldest_wonder_met_is_asked_in_the_inbox_and_the_chat(self):
        self.meet("red_berries", "cold_night")
        self.assertTrue(self.chore(BORN + 10))
        [question] = self.questions()
        self.assertEqual(question["text"], "I found red berries north of home. Are they safe to eat?")
        self.assertEqual(sorted(question["chips"]), sorted(chip.words for chip in WONDERS["red_berries"].chips))
        self.assertTrue(question["yes_no"])
        with self.world.connect() as db:
            chat = db.execute("SELECT text FROM mimo_chat WHERE who='mimo'").fetchall()
        self.assertEqual([row[0] for row in chat], [question["text"]])
        self.assertIn(("asked", f"{self.life['name']} asked you whether red berries are safe to eat."),
                      [(event["kind"], event["text"]) for event in self.world.events(20)])
        self.assertEqual(self.world.state()["last_thought"], "I asked about the berries. I'll wait a bit before I try one.")

    def test_a_new_question_waits_five_game_minutes_and_three_at_most_are_open(self):
        self.meet("red_berries", "red_mushroom", "sunleaf", "cold_night", "hard_floor")
        self.chore(BORN + 10)
        self.assertFalse(self.chore(BORN + 10 + 290 / SCALE))
        for step in (1, 2, 3, 4):
            self.chore(BORN + 10 + step * 300 / SCALE)
        self.assertEqual(len(self.questions()), 3)
        with self.world.connect() as db:
            asked = [row[0] for row in db.execute("SELECT json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask'")]
        self.assertEqual(asked, ["red_berries", "red_mushroom", "sunleaf"])

    def test_each_wonder_once_a_life_and_never_one_whose_lessons_mimo_knows(self):
        self.meet("sunleaf", "red_mushroom")
        with self.world.transaction() as db:
            know(db, thing("sunleaf"), "lesson", BORN)
        self.chore(BORN + 10)
        self.chore(BORN + 20)
        with self.world.connect() as db:
            asked = [row[0] for row in db.execute("SELECT json_extract(data, '$.wonder') FROM mimo_inbox WHERE kind='ask'")]
        self.assertEqual(asked, ["red_mushroom"])

    def test_a_gentle_pet_never_asks(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["difficulty"] = "gentle"
            met(state, "red_berries", BORN)
            self.assertFalse(ask_wonders(db, state, BORN + 10, SCALE))

    def test_hesitation_holds_a_taste_eight_game_minutes_unless_starving(self):
        self.meet("red_berries")
        self.chore(BORN + 10)
        with self.world.transaction() as db:
            state = read_state(db)
            state["inventory"] = {"berries": 4}
            state["vitals"]["hunger"] = 40.0
            write_state(db, state)
        with self.world.connect() as db:
            state = read_state(db)
            self.assertTrue(hesitates(from_db(db, state, BORN + 10 + 470 / SCALE, SCALE), "berries"))
            self.assertEqual(wild_meal(from_db(db, state, BORN + 10 + 470 / SCALE, SCALE)), [])
            self.assertEqual(len(wild_meal(from_db(db, state, BORN + 10 + 490 / SCALE, SCALE))), 1)
            state["vitals"]["hunger"] = 10.0
            self.assertEqual(len(wild_meal(from_db(db, state, BORN + 11, SCALE))), 1)

    def test_a_chip_teaches_doubts_or_is_noted(self):
        self.meet("red_berries", "red_mushroom", "hard_floor")
        for step in range(3):
            self.chore(BORN + 10 + step * 300 / SCALE)
        items = {question["text"].split(" ")[2]: question for question in self.questions()}
        berries = self.questions()[0]
        true = berries["chips"].index("Yes, bright red berries are safe.")
        self.assertEqual(answer_question(self.world, berries["id"], true, BORN + 100, SCALE)["data"]["closed"], "taught")
        self.assertTrue(self.knows("berries"))
        mushroom = next(question for question in self.questions() if "mushrooms" in question["text"])
        lie = mushroom["chips"].index("Sure, they're tasty.")
        self.assertEqual(answer_question(self.world, mushroom["id"], lie, BORN + 101, SCALE)["data"]["closed"], "doubted")
        self.assertFalse(self.knows("red_mushroom"))
        floor = self.questions()[0]
        shrug = floor["chips"].index("You'll get used to it.")
        self.assertEqual(answer_question(self.world, floor["id"], shrug, BORN + 102, SCALE)["data"]["closed"], "noted")
        with self.world.connect() as db:
            said = [row[0] for row in db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id")][-3:]
            taught = db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact='taught'", (thing("berries"),)).fetchone()
        self.assertEqual(said, ["Oh, bright red berries are safe to eat. Thank you for teaching me!",
                                "Hmm, I'm not sure that's right. I'll be careful.", "Okay. Thanks for telling me."])
        self.assertIsNotNone(taught)
        self.assertTrue(items)

    def test_an_answer_that_cannot_be_taken_is_refused(self):
        self.meet("red_mushroom")
        self.chore(BORN + 10)
        [question] = self.questions()
        with self.assertRaises(LookupError):
            answer_question(self.world, question["id"] + 99, 0, BORN + 20, SCALE)
        with self.assertRaises(ValueError):
            answer_question(self.world, question["id"], 5, BORN + 20, SCALE)
        answer_question(self.world, question["id"], 0, BORN + 20, SCALE)
        with self.assertRaises(ValueError):
            answer_question(self.world, question["id"], 0, BORN + 21, SCALE)
        with self.world.transaction() as db:
            state = read_state(db)
            state["died_at"] = BORN + 22
            write_state(db, state)
        with self.assertRaises(LifeOver):
            answer_question(self.world, question["id"], 0, BORN + 23, SCALE)

    def test_a_bare_yes_or_no_answers_the_newest_open_yes_or_no_question(self):
        self.meet("red_mushroom")
        self.chore(BORN + 10)
        self.say("No!", BORN + 20)
        self.assertTrue(self.knows("red_mushroom"))
        self.assertEqual(self.questions(), [])
        self.meet("raw_meat", at=BORN + 30)
        self.chore(BORN + 40)
        self.say("yes, go ahead", BORN + 50)
        self.assertFalse(self.knows("cooking"))
        with self.world.connect() as db:
            reply = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
            closed = [row[0] for row in db.execute("SELECT json_extract(data, '$.closed') FROM mimo_inbox WHERE kind='ask'")]
        self.assertEqual(reply, "Hmm, I'm not sure that's right. I'll be careful.")
        self.assertEqual(closed, ["taught", "doubted"])
        self.say("yes", BORN + 60)  # no yes-or-no question open: nothing
        self.assertFalse(self.knows("cooking"))

    def test_a_lesson_taught_or_worked_out_another_way_closes_the_question(self):
        self.meet("red_berries", "cold_night", "spoiled")
        for step in range(3):
            self.chore(BORN + 10 + step * 300 / SCALE)
        self.say("Food keeps twice as long in a chest.", BORN + 100)
        with self.world.transaction() as db:
            know(db, thing("fire"), "lesson", BORN + 101)
            know(db, thing("shelter"), "lesson", BORN + 101)
        self.chore(BORN + 200)
        with self.world.connect() as db:
            closed = {row[0]: row[1] for row in db.execute(
                "SELECT json_extract(data, '$.wonder'), json_extract(data, '$.closed') FROM mimo_inbox WHERE kind='ask'")}
        self.assertEqual(closed, {"red_berries": None, "cold_night": "figured", "spoiled": "taught"})
        with self.world.connect() as db:
            self.assertEqual(len(inbox_items(db)), 3)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def status(self, item_id, request):
        with self.assertRaises(HTTPException) as caught:
            answer_inbox(item_id, request)
        return caught.exception.status_code

    def test_the_answer_endpoint_takes_a_chip_and_api_mimo_shows_the_open_questions(self):
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        with world.transaction() as db:
            state = read_state(db)
            met(state, "hard_floor", 1.0)
            ask_wonders(db, state, 10.0, 1.0)
            write_state(db, state)
        [question] = get_mimo()["inbox"]["questions"]
        self.assertEqual(question["text"], "The floor is so hard to sleep on.")
        self.assertEqual(self.status(question["id"], PlaceName(choice=9)), 400)
        self.assertEqual(self.status(question["id"] + 9, PlaceName(choice=0)), 404)
        self.assertEqual(self.status(question["id"], PlaceName()), 400)
        item = answer_inbox(question["id"], PlaceName(choice=question["chips"].index("Six planks make a bed.")))["item"]
        self.assertEqual(item["data"]["closed"], "taught")
        self.assertEqual(get_mimo()["inbox"]["questions"], [])


if __name__ == "__main__":
    unittest.main()

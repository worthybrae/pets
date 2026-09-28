"""W1: Mimo asks its owner about what it does not understand, waits, and hears the answers."""

import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.survival.brain  # noqa: F401  (every hook registered)
from backend.survival import bonding, minding  # noqa: F401  (the chat, the inbox and teaching)
from backend.api import bond
from backend.api.bond import PlaceName, answer_inbox
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.ailments import open_wound
from backend.survival.brain import notice_step, observe_step
from backend.survival.hatch import hatch
from backend.survival.inbox import ITEMS_KEPT, inbox_items, item_of, post_item
from backend.survival.memory import know
from backend.survival.meals import sick_from, wild_meal
from backend.survival.once import forget_logged
from backend.survival.questions import answer_question, ask_wonders, open_items, opener, questions_view, words_of
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.spoilage import went_bad
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.teaching import TAUGHT_HOOKS
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import Surroundings
from backend.survival.wild import thing, wild_state
from backend.survival.wonders import COLD_NIGHT, FLOORS, WONDERS, hesitates, met, open_questions
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state
from backend.tests.no_model import no_model
from backend.tests.test_survival_brain import brainy, flat, pet

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
        self.assertEqual(self.world.state()["last_thought"],
                         "I asked about the red berries. I'll wait a bit before I try one.")

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

    # Fix round 1 (Tasks 10 and 11 review) -----------------------------------------------------------

    def test_an_open_question_outlives_the_inbox_pruning_and_a_closed_one_does_not(self):
        # Important 1: a wild pet posts about 90 items its first game day; an open question stays until answered.
        self.meet("hard_floor")
        self.chore(BORN + 10)
        [question] = self.questions()
        with self.world.transaction() as db:
            for number in range(ITEMS_KEPT + 5):
                post_item(db, BORN + 20 + number, "report", f"Report {number}.")
        self.assertEqual([found["id"] for found in self.questions()], [question["id"]])
        shrug = question["chips"].index("You'll get used to it.")
        answer_question(self.world, question["id"], shrug, BORN + 300, SCALE)
        with self.world.transaction() as db:
            post_item(db, BORN + 400, "report", "One more.")
            self.assertIsNone(db.execute("SELECT 1 FROM mimo_inbox WHERE id=?", (question["id"],)).fetchone())

    def test_a_crashing_taught_hook_is_logged_and_teaching_goes_on(self):
        # Important 2: TAUGHT_HOOKS is guarded like every other W1 registry.
        def crash(db, state, lesson_thing, now):
            raise RuntimeError("a taught hook broke")

        forget_logged()
        TAUGHT_HOOKS.insert(0, crash)
        self.addCleanup(TAUGHT_HOOKS.remove, crash)
        self.meet("hard_floor", "red_mushroom")
        self.chore(BORN + 10)
        self.chore(BORN + 10 + 300 / SCALE)
        with self.assertLogs("backend.survival.teaching", "ERROR"):
            self.say("Six planks make a bed.", BORN + 20)
        self.assertTrue(self.knows("bed"))
        [mushroom] = self.questions()  # the floor's question closed: the hooks after the crash still ran
        answer_question(self.world, mushroom["id"], mushroom["chips"].index("Red mushrooms are poison."), BORN + 30,
                        SCALE)
        self.assertTrue(self.knows("red_mushroom"))
        self.assertEqual(self.questions(), [])

    def test_a_bare_no_answers_the_newest_of_two_open_yes_or_no_questions(self):
        self.meet("red_mushroom", "raw_meat")
        self.chore(BORN + 10)
        self.chore(BORN + 10 + 300 / SCALE)
        self.assertEqual(len(self.questions()), 2)
        self.say("No", BORN + 20)
        self.assertTrue(self.knows("cooking"))
        self.assertFalse(self.knows("red_mushroom"))
        self.assertEqual([question["text"] for question in self.questions()],
                         ["There are red mushrooms here. Can I eat them?"])

    def test_the_chips_are_shuffled_and_each_still_maps_back_to_its_own(self):
        orders = set()
        for now in range(5):
            with self.world.transaction() as db:
                state = read_state(db)  # never written: the wonder stays unasked for the next round
                met(state, "red_berries", BORN)
                ask_wonders(db, state, BORN + 10 + now, SCALE)
                item = item_of(db.execute("SELECT * FROM mimo_inbox WHERE kind='ask'").fetchone())
                db.execute("DELETE FROM mimo_inbox")
            chips, order = item["data"]["chips"], item["data"]["order"]
            self.assertEqual(chips, [WONDERS["red_berries"].chips[index].words for index in order])
            orders.add(tuple(chips))
        self.assertGreater(len(orders), 1)

    def test_an_acknowledgement_or_an_idiom_never_answers_a_question(self):
        # The controller's ruling: "ok", "okay" and "fine" are no answers, and "No idea" and its kind never bind.
        self.meet("red_berries")
        self.chore(BORN + 10)
        self.say("Ok, I'm back!", BORN + 20)
        self.say("No idea", BORN + 30)
        self.assertFalse(self.knows("berries"))
        self.assertEqual(len(self.questions()), 1)
        self.say("Yes!", BORN + 40)
        self.assertTrue(self.knows("berries"))
        self.assertEqual(self.questions(), [])
        for said in ("ok", "Okay, thanks", "Fine.", "no idea!", "No clue, sorry", "No problem", "no worries",
                     "Not sure", "Don't know", "dont know", "Never mind", "Nevermind.", "Don’t know"):
            self.assertIsNone(opener(said), said)
        self.assertEqual([opener(said) for said in ("Yes!", "yep", "Of course", "No.", "Nope", "Never!")],
                         ["yes", "yes", "yes", "no", "no", "no"])

    def test_a_chip_says_what_mimo_learned_or_that_it_knew(self):
        # Minor 5: the thanks name the first lesson actually learned, and a chip that teaches nothing new is known.
        self.meet("red_berries", "raw_meat")
        with self.world.transaction() as db:
            know(db, thing("berries"), "lesson", BORN)
            know(db, thing("fire"), "lesson", BORN)
        self.chore(BORN + 10)
        self.chore(BORN + 10 + 300 / SCALE)
        berries, meat = self.questions()
        answer_question(self.world, berries["id"], berries["chips"].index("Yes, bright red berries are safe."),
                        BORN + 20, SCALE)
        answer_question(self.world, meat["id"], meat["chips"].index("Cook it on a campfire first."), BORN + 21, SCALE)
        with self.world.connect() as db:
            said = [row[0] for row in db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id")][-2:]
        self.assertEqual(said, ["I know that one! Bright red berries are safe to eat.",
                                "Oh, meat and fish cooked on a fire are safe to eat and fill you up far more. "
                                "Thank you for teaching me!"])
        self.assertTrue(self.knows("cooking"))

    def test_a_world_without_an_inbox_has_no_open_questions_and_any_other_error_is_raised(self):
        # Minor 9: one helper reads the open questions, and only a missing table reads as none.
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        self.assertEqual((open_items(db), open_questions(db)), ([], 0))
        db.execute("CREATE TABLE mimo_inbox (id INTEGER PRIMARY KEY, kind TEXT)")  # no data column
        with self.assertRaises(sqlite3.OperationalError):
            open_items(db)
        with self.assertRaises(sqlite3.OperationalError):
            open_questions(db)


class WonderTriggerTests(unittest.TestCase):
    """Each wonder is met by its own trigger, through the brain's hooks: wonders.meet after a vitals step
    (brain.notice_step) and wonders.sighted among steps.OBSERVERS after a walk (brain.observe_step)."""

    def notice(self, state, at):
        ensure_brain(state)["pending"] = None
        notice_step(state, brainy(), dict(state["vitals"]), Surroundings(), at - 1.0, at)
        return wild_state(state)["wonders"]

    def test_the_body_and_the_nights_meet_their_wonders(self):
        triggers = {
            "tummy": lambda state: sick_from(state, "nightberries", 5.0),
            "raw_meat": lambda state: state["inventory"].update(raw_beef=1),
            "wound": lambda state: (state.update(hurt_by="skitter"), open_wound(state, 5.0)),
            "cold_night": lambda state: wild_state(state).update(night_cold=COLD_NIGHT),
            "hard_floor": lambda state: wild_state(state).update(floor_nights=FLOORS),
            "spoiled": lambda state: state["inventory"].update(spoiled_food=1),
            "dark_creature": lambda state: state.update(hurt_at=5.0),
        }
        fills = {"tummy": "those berries", "raw_meat": "raw beef", "wound": "A skitter", "spoiled": "food"}
        for wonder_id, trigger in triggers.items():
            with self.subTest(wonder_id):
                state = pet(difficulty="wild")
                self.assertEqual(self.notice(state, 4.0), {})
                trigger(state)
                found = self.notice(state, 6.0)
                self.assertEqual(list(found), [wonder_id])
                self.assertEqual(found[wonder_id]["fill"], fills.get(wonder_id, ""))
                gentle = pet()
                trigger(gentle)
                self.assertEqual(self.notice(gentle, 6.0), {})

    def test_a_walk_meets_the_red_berries_red_mushrooms_and_sunleaf_within_sight(self):
        walk = {"kind": "walk", "path": [], "target": {"x": 0, "y": 1, "z": 0}}
        for wonder_id, block in (("red_berries", "nightberry_bush_ripe"), ("red_berries", "berry_bush_ripe"),
                                 ("red_mushroom", "red_mushroom"), ("sunleaf", "sunleaf")):
            with self.subTest(block):
                near, far = flat(), flat()
                near.edits[(5, 1, 3)] = block
                far.edits[(12, 1, 0)] = block  # past SIGHT
                state = pet(difficulty="wild")
                observe_step(state, walk, brainy(far), 5.0)
                self.assertEqual(wild_state(state)["wonders"], {})
                observe_step(state, walk, brainy(near), 6.0)
                self.assertEqual(list(wild_state(state)["wonders"]), [wonder_id])
                gentle = pet()
                observe_step(gentle, walk, brainy(near), 6.0)
                self.assertEqual(wild_state(gentle)["wonders"], {})

    def test_mimo_calls_nightberries_what_they_look_like(self):
        # Minor 6: the pet cannot tell the lookalike apart, so its own words never name it.
        state = pet(difficulty="wild")
        sick_from(state, "nightberries", 5.0)
        state["inventory"]["spoiled_food"] = 3
        went_bad(state, SimpleNamespace(db=None, events=[]), {"nightberries": 3}, "arms", 5.5)
        self.assertEqual(state["last_thought"], "Yuck, my red berries went bad.")
        found = self.notice(state, 6.0)
        self.assertEqual(words_of("tummy", found["tummy"]["fill"]),
                         "My tummy hurts after eating those berries. What helps?")
        self.assertEqual(words_of("spoiled", found["spoiled"]["fill"]),
                         "My red berries went bad! How do I keep food fresh?")


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
        self.assertEqual((question["text"], question["at"]), ("The floor is so hard to sleep on.", 10.0))
        self.assertEqual(self.status(question["id"], PlaceName(choice=9)), 400)
        self.assertEqual(self.status(question["id"] + 9, PlaceName(choice=0)), 404)
        self.assertEqual(self.status(question["id"], PlaceName()), 400)
        self.assertEqual(self.status(question["id"], PlaceName(choice=0, text="Echo Hollow")), 400)
        item = answer_inbox(question["id"], PlaceName(choice=question["chips"].index("Six planks make a bed.")))["item"]
        self.assertEqual(item["data"]["closed"], "taught")
        self.assertEqual(get_mimo()["inbox"]["questions"], [])

    def test_a_choice_that_is_not_a_whole_number_is_refused(self):
        # Minor 4: pydantic no longer reads true, 1.0 or "1" as the chip 1.
        hatch_egg()
        app = FastAPI()
        app.include_router(bond.router)
        client = TestClient(app)
        for choice in (True, 1.0, "1"):
            self.assertEqual(client.post("/mimo/inbox/999999/answer", json={"choice": choice}).status_code, 422, choice)
        self.assertEqual(client.post("/mimo/inbox/999999/answer", json={"choice": 1}).status_code, 404)


if __name__ == "__main__":
    unittest.main()

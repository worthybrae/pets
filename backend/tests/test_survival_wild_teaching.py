import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every lesson registered)
from backend.survival import minding  # noqa: F401  (the chat's "teach" question)
from backend.survival.hatch import hatch
from backend.survival.journal import LESSONS, journal_view
from backend.survival.lessons import claims, named, wants
from backend.survival.memory import know
from backend.survival.registry import LifeRegistry
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.wild import SURVIVAL, thing
from backend.survival.world import SurvivalWorld
from backend.tests.no_model import no_model

BORN = 1_000_000.0
# The spec's teaching table: what each survival lesson's owner lines teach, and the lines doubted.
TEACHES = {
    "berries": ("Red berries are safe to eat.",),
    "nightberries": ("Nightberries are the dark purple ones, and they are poison.", "The purple berries are poison.",
                     "Don't eat the purple berries."),
    "red_mushroom": ("Red mushrooms are poison.", "Never eat red mushrooms."),
    "sunleaf": ("Sunleaf cures sickness and cleans wounds.",),
    "bandage": ("A wool bandage stops a wound festering.",),
    "fire": ("Two logs and three sticks make a campfire.", "A campfire keeps you warm at night."),
    "cooking": ("Cooked meat and fish are safe to eat.", "Cook your meat on a fire."),
    "keeping": ("Food keeps twice as long in a chest.",),
    "light": ("Torches keep the dark creatures away.",),
    "shelter": ("A shelter with a roof and a door keeps you safe at night.",),
    "bed": ("Six planks make a bed.",),
}
DOUBTED = {
    "berries": "Red berries are poison.", "nightberries": "Nightberries are safe to eat.",
    "red_mushroom": "Red mushrooms are safe to eat.", "sunleaf": "Sunleaf is poison.",
    "fire": "Five logs make a campfire.", "cooking": "Raw meat is safe to eat.",
    "light": "Torches bring the dark creatures.", "bed": "Two planks make a bed.",
}


class TeachingTableTests(unittest.TestCase):
    def test_every_line_of_the_teaching_table_teaches_its_lesson_first(self):
        for name, lines in TEACHES.items():
            for text in lines:
                found = claims(text)
                self.assertEqual((found.taught[:1], found.doubtful), ((thing(name),), False), text)

    def test_every_doubted_line_is_doubted_and_teaches_nothing(self):
        for text in DOUBTED.values():
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)

    def test_the_lessons_are_named_after_wild_and_each_fact_teaches_itself(self):
        for lesson in SURVIVAL:
            self.assertEqual(named(LESSONS[thing(lesson.name)]), lesson.name)
            self.assertIn(thing(lesson.name), claims(lesson.fact).taught, lesson.fact)

    def test_a_warning_teaches_and_a_survival_command_teaches_while_staying_a_request(self):
        self.assertEqual(claims("Avoid nightberries.").taught, (thing("nightberries"),))
        self.assertEqual(claims("Don't eat raw meat.").taught, (thing("cooking"),))
        self.assertTrue(claims("Don't eat red berries.").doubtful)  # bright red berries are safe
        self.assertTrue(wants("Cook your meat on a fire."))  # B2 still reads it as a request
        for text in ("Make a campfire.", "Please cook the fish.", "make a bow!"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), False), text)

    def test_everyday_lines_about_torches_shelters_and_food_stay_chat(self):
        for text in ("sticks make torches", "A shelter keeps you warm.", "I made you a bed", "let's go home"):
            self.assertFalse(claims(text).doubtful, text)


class ChatTeachingTests(unittest.TestCase):
    """A wild pet taught in the chat, through the rules (no model): learned from you."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        life = hatch(self.registry, random.Random(8), timestamp=BORN, difficulty="wild")
        self.world = SurvivalWorld(self.registry.world_path(life))

    def tearDown(self):
        self.directory.cleanup()

    def say(self, text, at):
        owner_says(self.world, text, at, 1.0)
        talker = Talker(env={}, http=no_model(self), scale=1.0)
        talker.poll(self.registry, at + 1)
        talker.close()

    def test_the_owner_teaches_every_survival_lesson_in_one_sentence_each(self):
        for number, (name, lines) in enumerate(TEACHES.items()):
            self.say(lines[0], BORN + 10 * (number + 1))
        with self.world.connect() as db:
            taught = {row[0] for row in db.execute("SELECT subject FROM memory_knowledge WHERE fact='taught'")}
            listed = journal_view(db, self.world.state().get("brain"))
        self.assertEqual(taught, {thing(name) for name in TEACHES})
        self.assertEqual(listed, [])  # listed apart, in the survival field

    def test_a_doubted_line_teaches_nothing_and_says_so(self):
        self.say(DOUBTED["cooking"], BORN + 10)
        with self.world.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_knowledge WHERE subject LIKE 'wild:%'").fetchone()[0], 0)
            reply = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertTrue(reply.startswith("Hmm, I'm not sure that's right."), reply)

    def test_a_gentle_pet_already_knows_them(self):
        with self.world.transaction() as db:
            know(db, thing("fire"), "lesson", BORN)
        self.say(TEACHES["fire"][0], BORN + 10)
        with self.world.connect() as db:
            reply = db.execute("SELECT text FROM mimo_chat WHERE who='mimo' ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertTrue(reply.startswith("I know that one!"), reply)


if __name__ == "__main__":
    unittest.main()

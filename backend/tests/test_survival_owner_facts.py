import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.hatch import hatch
from backend.survival.owner_facts import (
    FACT_WORDS, FACTS_KEPT, NONE, fact_options, name_in, notice, owner_facts, owner_name, remember_fact, rules_fact,
)
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0


class NoticingTests(unittest.TestCase):
    def test_names_the_owner_gives_themselves(self):
        self.assertEqual(name_in("Hi! My name is sam."), "Sam")
        self.assertEqual(name_in("you can call me Alex-Jo"), "Alex-Jo")
        self.assertEqual(name_in("Hello, I'm Priya"), "Priya")
        self.assertEqual(name_in("my name's Robin"), "Robin")
        self.assertEqual(notice("I\u2019m Kai").get("name"), "Kai")
        for text in ("I'm tired", "I'm so happy today", "I am Back!", "I'm Going home", "what's your name?"):
            self.assertEqual(name_in(text), "", text)

    def test_likes_dislikes_and_words_about_themselves(self):
        self.assertEqual(notice("I love the lake at sunset!").get("likes"), "the lake at sunset")
        self.assertEqual(notice("My favourite colour is blue.").get("likes"), "blue")
        self.assertEqual(notice("I really hate spiders, honestly").get("dislikes"), "spiders")
        self.assertEqual(notice("I love you").get("likes"), "")  # too vague to remember
        self.assertEqual(notice("I work nights at the bakery").get("about"), "I work nights at the bakery")
        self.assertEqual(notice("Do I look tired?").get("about"), "")  # a question tells nothing
        self.assertEqual(notice("How are you doing today?").found, {})

    def test_facts_on_offer_and_the_rules_pick(self):
        noticed = notice("I'm Sam and I love fishing")
        self.assertEqual([option.name for option in fact_options(noticed)], [NONE, "name", "likes", "about"])
        self.assertIn('"Sam"', fact_options(noticed)[1].description)
        self.assertEqual(rules_fact(noticed), "name")
        self.assertEqual(rules_fact(notice("I hate the rain")), "dislikes")
        self.assertEqual(rules_fact(notice("I had a long day")), NONE)  # only Jev keeps words about themselves
        self.assertEqual([option.name for option in fact_options(notice("hello!"))], [NONE])


class RememberingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))

    def tearDown(self):
        self.directory.cleanup()

    def test_facts_are_kept_newest_first_and_a_new_name_replaces_the_old(self):
        with self.world.transaction() as db:
            self.assertTrue(remember_fact(db, "name", "Sam", BORN + 1))
            self.assertTrue(remember_fact(db, "likes", "the lake", BORN + 2))
            self.assertTrue(remember_fact(db, "name", "Samantha", BORN + 3))
            self.assertFalse(remember_fact(db, "likes", "the lake", BORN + 4))  # heard again: fresh again
            self.assertFalse(remember_fact(db, "secret", "anything", BORN + 5))
            facts = owner_facts(db)
        self.assertEqual(facts, [("likes", "the lake"), ("name", "Samantha")])
        self.assertEqual(owner_name(facts), "Samantha")

    def test_at_most_forty_facts_the_oldest_forgotten_first(self):
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN)
            for number in range(FACTS_KEPT + 5):
                remember_fact(db, "likes", f"thing {number}", BORN + 1 + number)
            facts = owner_facts(db)
        self.assertEqual(len(facts), FACTS_KEPT)
        self.assertEqual(facts[0], ("likes", f"thing {FACTS_KEPT + 4}"))
        self.assertEqual(facts[-1], ("likes", "thing 5"))
        self.assertEqual(owner_name(facts), "")  # the name was the oldest

    def test_long_words_are_trimmed(self):
        with self.world.transaction() as db:
            remember_fact(db, "about", "word " * 40, BORN)
            [(kind, words)] = owner_facts(db)
        self.assertEqual(kind, "about")
        self.assertLessEqual(len(words), FACT_WORDS)
        self.assertTrue(words.endswith("..."))


if __name__ == "__main__":
    unittest.main()

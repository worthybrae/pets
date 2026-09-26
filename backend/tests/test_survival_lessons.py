import unittest
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every creature, recipe and goal registered)
from backend.services.crafting import RECIPES
from backend.survival.creatures.kinds import KINDS
from backend.survival.journal import LESSONS, PLANTS, SURFACE
from backend.survival.lessons import SHORTLIST, claims, gear_group, teach_recipe

GEAR = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "gold_pickaxe", "diamond_pickaxe", "wooden_axe", "stone_axe",
        "iron_axe", "wooden_sword", "stone_sword", "iron_sword", "gold_sword", "diamond_sword", "bow", "arrow",
        "leather_cap", "leather_tunic", "iron_cap", "iron_tunic")


class TeachableLessonsTests(unittest.TestCase):
    def test_every_armor_tool_and_weapon_recipe_has_a_lesson_written_from_the_recipe(self):
        self.assertEqual(sorted(name for name in RECIPES if gear_group(name)), sorted(GEAR))
        for name in GEAR:
            lesson = LESSONS[f"recipe:{name}"]
            self.assertEqual(lesson.kind, "recipe")
            self.assertEqual(lesson.unlocks, "")
        fact = {name: LESSONS[f"recipe:{name}"].fact for name in GEAR}
        self.assertEqual(fact["iron_sword"], "An iron sword takes two iron ingots and a stick, at a crafting table.")
        self.assertEqual(fact["bow"], "A bow takes three sticks and three string, at a crafting table.")
        self.assertEqual(fact["arrow"], "A flint, a stick and a feather make four arrows, at a crafting table.")
        self.assertEqual(fact["leather_tunic"], "A leather tunic takes three leather, at a crafting table.")
        self.assertEqual(fact["iron_cap"], "An iron cap takes five iron ingots, at a crafting table.")
        self.assertEqual(fact["diamond_pickaxe"],
                         "A diamond pickaxe takes three diamonds and two sticks, at a crafting table.")
        self.assertEqual((gear_group("iron_cap"), gear_group("stone_axe"), gear_group("bow"), gear_group("bread")),
                         ("armor", "tool", "weapon", ""))

    def test_every_kind_of_creature_has_a_lesson_on_its_habits_and_one_on_its_drops(self):
        for name, kind in KINDS.items():
            self.assertEqual(LESSONS[f"{name}:habits"].kind, "creature")
            self.assertEqual(f"{name}:drops" in LESSONS, bool(kind.drops), name)
        self.assertEqual(LESSONS["cow:drops"].fact, "A cow drops one to three raw beef and up to two leather.")
        self.assertEqual(LESSONS["rabbit:drops"].fact, "A rabbit drops a raw rabbit and sometimes a rabbit hide.")
        self.assertEqual(LESSONS["cow:habits"].fact,
                         "Cows graze in meadows, forests, birch forests and swamps, two to three together.")
        self.assertEqual(LESSONS["rabbit:habits"].fact, "Rabbits hop about in every land, one to three together.")
        self.assertEqual(LESSONS["fish:habits"].fact, "Fish swim in the water of every land, two to four together.")
        self.assertEqual(LESSONS["skitter:habits"].fact,
                         "Skitters live in the caves and dark places, and the sunlight makes them fade.")

    def test_the_new_lessons_are_never_things_to_go_and_study(self):
        added = [thing for thing in LESSONS if ":" in thing]
        self.assertEqual(len(added), len(GEAR) + 2 * len(KINDS) - sum(1 for kind in KINDS.values() if not kind.drops))
        self.assertEqual(len(LESSONS) - len(added), 32)  # L4b's
        self.assertFalse(set(added) & (set(SURFACE) | set(PLANTS) | set(KINDS)))

    def test_part_b_can_add_a_recipe_lesson(self):
        with patch.dict(RECIPES, {"copper_sword": {"ingredients": {"copper_ingot": 2, "sticks": 1},
                                                    "output": {"copper_sword": 1}, "station": "crafting_table"}}):
            lesson = teach_recipe("copper_sword")
            try:
                self.assertEqual(lesson.fact,
                                 "A copper sword takes two copper ingots and a stick, at a crafting table.")
                self.assertEqual(claims("copper swords need copper ingots").taught, ("recipe:copper_sword",))
            finally:
                del LESSONS["recipe:copper_sword"]


class ClaimsTests(unittest.TestCase):
    def test_the_owners_words_fit_real_lessons(self):
        self.assertEqual(claims("Cows give leather!").taught, ("cow", "cow:drops"))
        self.assertEqual(claims("iron armor needs iron ingots").taught, ("recipe:iron_cap", "recipe:iron_tunic"))
        self.assertEqual(claims("skitters hate light").taught, ("skitter:habits", "skitter"))
        self.assertEqual(claims("you can make a bow from sticks and string").taught, ("recipe:bow",))
        self.assertEqual(claims("gravel hides flint").taught, ("gravel",))
        self.assertEqual(claims("zombies come out at night").taught, ("gloomling", "gloomling:habits"))
        self.assertEqual(claims("a stone pickaxe needs three cobblestone and two sticks").taught,
                         ("recipe:stone_pickaxe",))
        self.assertLessEqual(len(claims("swords need sticks").taught), SHORTLIST)

    def test_every_lesson_can_be_taught_in_its_own_words(self):
        for thing, lesson in LESSONS.items():
            self.assertIn(thing, claims(lesson.fact).taught, lesson.fact)

    def test_a_falsehood_fits_no_lesson_and_is_doubted(self):
        for text in ("cows give diamonds", "iron swords need gold", "skitters drop feathers"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)

    def test_a_verb_no_lesson_says_at_all_is_doubted_too_but_a_question_or_small_talk_is_not(self):
        # Controller ruling (Task 5 review): "cows fly" names a known subject and makes a claim no
        # lesson supports, so it is doubtful even though "fly" is outside TEACH_VERBS; "do you like
        # cows?" is a question, not a claim, and stays chit-chat; "cows give leather" is still taught.
        self.assertEqual((claims("cows fly").taught, claims("cows fly").doubtful), ((), True))
        self.assertEqual((claims("do you like cows?").taught, claims("do you like cows?").doubtful), ((), False))
        self.assertEqual(claims("cows give leather").taught, ("cow", "cow:drops"))

    def test_questions_and_small_talk_teach_nothing(self):
        for text in ("do cows give leather?", "Can you make a bow?", "cows are cute", "I love you", "my name is Sam",
                     "hi Mimo, how are you?"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful, found.unknown), ((), False, False), text)

    def test_words_about_what_no_lesson_covers_are_not_understood_yet(self):
        found = claims("bread is made from wheat")
        self.assertEqual((found.taught, found.doubtful, found.unknown), ((), False, True))


if __name__ == "__main__":
    unittest.main()

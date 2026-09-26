import unittest
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every creature, recipe and goal registered)
from backend.services.crafting import RECIPES
from backend.survival.creatures.kinds import KINDS
from backend.survival.journal import LESSONS, PLANTS, SURFACE
from backend.survival.lessons import SHORTLIST, claims, contradicts, denied, gear_group, raw_words, teach_recipe

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
        # Final fix wave: a sometimes-drop counted by mass reads naturally ("and sometimes tallow").
        self.assertEqual(LESSONS["sheep:drops"].fact,
                         "A sheep drops one to two raw mutton, one to two wool and sometimes tallow.")
        self.assertEqual(LESSONS["cow:habits"].fact,
                         "Cows graze in meadows, forests, birch forests and swamps, two to three together.")
        self.assertEqual(LESSONS["rabbit:habits"].fact, "Rabbits hop about in every land, one to three together.")
        self.assertEqual(LESSONS["fish:habits"].fact, "Fish swim in the water of every land, two to four together.")
        self.assertEqual(LESSONS["skitter:habits"].fact,
                         "Skitters live in the caves and dark places, and the sunlight makes them fade.")

    def test_the_new_lessons_are_never_things_to_go_and_study(self):
        added = [thing for thing in LESSONS if ":" in thing]
        self.assertEqual(len(added), len(GEAR) + 2 * len(KINDS) - sum(1 for kind in KINDS.values() if not kind.drops))
        self.assertEqual(len(LESSONS) - len(added), 36)  # L4b's 32, plus Making T2's 4 (copper_spark, clock, latch, adder)
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
        # "hate" no longer widens to "fade" (fix round 1, Minor 10): "light" alone still fits both,
        # so the order between them shifts.
        self.assertEqual(claims("skitters hate light").taught, ("skitter", "skitter:habits"))
        self.assertEqual(claims("you can make a bow from sticks and string").taught, ("recipe:bow",))
        self.assertEqual(claims("gravel hides flint").taught, ("gravel",))
        self.assertEqual(claims("zombies come out at night").taught, ("gloomling", "gloomling:habits"))
        self.assertEqual(claims("a stone pickaxe needs three cobblestone and two sticks").taught,
                         ("recipe:stone_pickaxe",))
        self.assertLessEqual(len(claims("swords need sticks").taught), SHORTLIST)

    def test_makings_plain_name_parts_do_not_make_a_true_lesson_doubtful(self):
        """The Making final fix wave, I5: "thinking" (thinking_machine), "cozy" (cozy_home) and "lit" (lamp_lit
        and the other lit parts) joined Mind's vocabulary as things, so these lines were doubted ("Hmm, I'm
        not sure that's right.") though each teaches a real lesson."""
        lines = {"skitters hate light, stay lit": "skitter:habits",
                 "thinking about it, skitters hate light": "skitter:habits",
                 "keep thinking: gravel hides flint": "gravel",
                 "cows give leather, I was thinking": "cow:drops",
                 "I'm thinking cows give leather": "cow:drops"}
        for text, lesson in lines.items():
            found = claims(text)
            self.assertIn(lesson, found.taught, text)
            self.assertFalse(found.doubtful, text)
        self.assertTrue(claims("skitters hate light, like a lamp").doubtful)  # a lamp is a real thing: Mind's rule

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

    def test_fix_round_1_the_copula_guard_is_narrow_and_does_not_leak(self):
        # Important 1: greetings, compliments and lines about a place stay chit-chat even when they
        # name a known subject in passing, and talk of the owner is never a claim about it.
        for text in ("good morning cows", "look, a cow!", "nice sword!", "let's go to the lake",
                     "hello cows", "good cow", "Pip, the cows look happy"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful, found.unknown), ((), False, False), text)
        # The leak: a copula elsewhere in the line (not right after the subject), or more than a bare
        # description right after it, still doubts a false claim about a known subject.
        for text in ("cows fly, it is true", "skitters are friendly and sing"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)

    def test_fix_round_1_hate_no_longer_falsely_teaches_a_habits_lesson(self):
        # Minor 10: "hate" was a synonym of "fade" (skitter:habits' own fact), so "I hate skitters"
        # taught it; "skitters hate light" still teaches through "light" alone.
        self.assertEqual(claims("I hate skitters").taught, ())
        self.assertIn("skitter:habits", claims("skitters hate light").taught)

    def test_fix_round_1_each_sentence_is_judged_on_its_own(self):
        # Minor 10: a foreign word in one sentence ("lake") no longer spoils a lesson a later
        # sentence teaches cleanly.
        self.assertEqual(claims("I like the lake.").taught, ())
        self.assertIn("skitter:habits", claims("I like the lake. Skitters hate light.").taught)

    def test_fix_round_2_unknown_is_narrowed_the_way_doubt_is(self):
        # Important 2: "keep the torch lit" no longer answers "I don't understand that yet" ("keep"
        # is not a thing); "bread is made from wheat" still does ("bread" is).
        for text in ("keep the torch lit", "I made you a bed", "we need more wood", "I grow tomatoes at home"):
            self.assertEqual((claims(text).unknown, claims(text).doubtful, claims(text).taught),
                             (False, False, ()), text)
        self.assertTrue(claims("bread is made from wheat").unknown)

    def test_fix_round_2_subject_first_exclamations_and_observations_are_not_doubted(self):
        # Residual 6: a comma right after the subject (an exclamation or address), or a word that
        # only exclaims or observes right after it, is not a claim.
        for text in ("cows look happy today", "cows seem happy", "cows rule!", "iron swords rock",
                     "gloomlings everywhere, run!", "skitters, yikes", "chickens, chickens everywhere",
                     "cow spotted near the lake"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful, found.unknown), ((), False, False), text)

    def test_fix_round_2_a_copula_followed_by_two_describing_words_is_not_doubted(self):
        # Residual 7: "X are A and B", both describing words, is chat; a non-describing word after
        # the copula ("skitters are friendly and sing") is still doubted.
        for text in ("rabbits are cute and fluffy", "cows are cute and friendly", "sheep are so fluffy and soft"):
            self.assertFalse(claims(text).doubtful, text)
        self.assertTrue(claims("skitters are friendly and sing").doubtful)

    def test_fix_round_2_more_pronouns_are_never_a_claim(self):
        # Residual 5: me, us, our, mine, u, he, him, she, her, they and them, added to PERSON_WORDS.
        for text in ("skitters scare me", "cows follow us around", "that sword is mine", "cows love u",
                     "cows remind him of home"):
            self.assertFalse(claims(text).doubtful, text)

    def test_fix_round_2_fear_and_avoid_no_longer_teach_a_habits_lesson(self):
        # Residual 8: "fear" and "avoid" were synonyms of "fade" (skitter:habits' own fact); removed,
        # so "I fear skitters" and "I avoid skitters" teach nothing. "skitters fear light" still
        # teaches through "light" alone.
        self.assertEqual(claims("I fear skitters").taught, ())
        self.assertEqual(claims("I avoid skitters").taught, ())
        self.assertIn("skitter:habits", claims("skitters fear light").taught)

    def test_fix_round_2_a_known_subject_that_continues_into_a_longer_one_is_not_doubted(self):
        # "iron" (iron_ore's own subject) followed by "sword" continues into recipe:iron_sword's own
        # longer subject, not a claim about iron ore.
        self.assertFalse(claims("iron swords rock").doubtful)

    def test_questions_and_small_talk_teach_nothing(self):
        for text in ("do cows give leather?", "Can you make a bow?", "cows are cute", "I love you", "my name is Sam",
                     "hi Mimo, how are you?"):
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful, found.unknown), ((), False, False), text)

    def test_words_about_what_no_lesson_covers_are_not_understood_yet(self):
        found = claims("bread is made from wheat")
        self.assertEqual((found.taught, found.doubtful, found.unknown), ((), False, True))


# The final review's corpus (I2): 13 false lines that each fit a true lesson and were thanked for,
# 26 true lines, and two parked residuals.
FALSE_LINES = (
    "skitters love sunlight", "skitters come out at noon", "gloomlings love light",  # the opposite
    "cows don't give leather", "cows never give leather", "cows do not drop beef",  # a denial
    "a bow takes two sticks", "a leather cap takes five leather", "iron cap needs eight iron ingots",  # a number
    "gloomlings love the sun", "sheep don't give wool", "cows drop five leather", "an iron sword takes 3 iron ingots",
)
# The shortlist each true line keeps, best first: the lesson the rules teach is the same as before.
# Two lose a second lesson whose own words they contradict ("two" is not in the cow lesson's fact;
# "sun" is the opposite of the gloomling lesson's "dark").
TRUE_LINES = (
    ("skitters hate light", ("skitter", "skitter:habits")),
    ("Gloomlings hate light", ("gloomling", "gloomling:habits")),
    ("you can make a bow from sticks and string", ("recipe:bow",)),
    ("an iron cap needs five iron ingots", ("recipe:iron_cap",)),
    ("cows drop up to two leather", ("cow:drops",)),
    ("zombies burn in the sun", ("gloomling:habits",)),
    ("Iron armor needs iron ingots.", ("recipe:iron_cap", "recipe:iron_tunic")),
    ("Cows give leather!", ("cow", "cow:drops")),
    ("sheep give wool", ("sheep", "sheep:drops")),
    ("chickens drop feathers", ("chicken", "chicken:drops")),
    ("a bow takes three sticks and three string", ("recipe:bow",)),
    ("an iron sword takes two iron ingots and a stick", ("recipe:iron_sword",)),
    ("skitters come out of caves at night", ("skitter", "skitter:habits")),
    ("gloomlings come out at night", ("gloomling", "gloomling:habits")),
    ("gravel hides flint", ("gravel",)),
    ("sugar cane grows beside water", ("sugar_cane",)),
    ("cactus grows on sand", ("sand", "cactus")),
    ("diamonds need an iron pickaxe", ("diamond_ore",)),
    ("a leather cap takes two leather", ("recipe:leather_cap",)),
    ("skitters drop string", ("skitter:drops",)),
    ("gloomlings drop gloom dust", ("gloomling:drops",)),
    ("moss grows on the forest floor", ("moss",)),
    ("a stone pickaxe takes three cobblestone and two sticks", ("recipe:stone_pickaxe",)),
    ("an iron tunic takes eight iron ingots", ("recipe:iron_tunic",)),
    ("skitters fear light", ("skitter", "skitter:habits")),
    ("light keeps gloomlings away", ("gloomling", "gloomling:habits")),
)
# Parked: a fact that says both sides ("the caves and dark places, and the sunlight") is never
# contradicted by either; "light" is on both sides of TEACH_SYNONYMS. Each still teaches only a
# true lesson.
RESIDUALS = ("skitters come out in the day", "skitters like light")


class ContradictionTests(unittest.TestCase):
    def test_the_corpus_is_the_final_reviews_forty_one_lines(self):
        self.assertEqual((len(FALSE_LINES), len(TRUE_LINES), len(RESIDUALS)), (13, 26, 2))

    def test_a_denial_a_wrong_number_or_the_opposite_is_doubted_never_taught(self):
        for text in FALSE_LINES:
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful, found.unknown), ((), True, False), text)

    def test_the_true_lines_still_teach_what_they_taught(self):
        for text, taught in TRUE_LINES:
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), (taught, False), text)

    def test_the_parked_residuals_teach_only_real_lessons(self):
        for text in RESIDUALS:
            self.assertTrue(set(claims(text).taught) <= set(LESSONS), text)

    def test_contradicts_reads_denials_numbers_and_opposites_against_the_lessons_own_words(self):
        def against(thing, text):
            return contradicts(LESSONS[thing], text, raw_words(text))

        self.assertTrue(against("recipe:bow", "a bow takes 2 sticks"))
        self.assertFalse(against("recipe:bow", "a bow takes three sticks"))
        self.assertTrue(against("skitter:habits", "skitters love caves"))
        self.assertTrue(against("skitter", "skitters come out at noon"))
        self.assertFalse(against("skitter:habits", "skitters come out in the day"))  # its fact says both sides
        self.assertEqual(denied("cows don't give leather, and I can't lie"),
                         "cows do not give leather, and I cannot lie")

    def test_a_true_recipe_said_with_make_is_taught_and_a_false_one_stays_doubtful(self):
        # M10: every recipe lesson means make, made, craft, need and take, whatever its fact says.
        self.assertEqual(claims("leather armor is made from leather").taught,
                         ("recipe:leather_cap", "recipe:leather_tunic"))
        found = claims("iron armor is made from leather")
        self.assertEqual((found.taught, found.doubtful), ((), True))


if __name__ == "__main__":
    unittest.main()

import unittest

from backend.services.crafting import craft
from backend.survival import storage
from backend.survival.carrying import valuable
from backend.survival.creatures.gear import gear_orders
from backend.survival.creatures.harm import armor_cut, armor_iron, armor_wanted, covered
from backend.survival.purposes import PURPOSES
from backend.survival.toolmaking import LANTERNS_WANTED, tool_plan
from backend.survival.work import wanted_ores
from backend.tests import test_survival_lighting as lighting_tests
from backend.tests.test_survival_lighting import CORNERS, EVENING
from backend.tests.test_survival_storage import LOOSE, Home
from backend.tests.test_survival_toolmaking import flat, situation
from backend.tests.test_survival_work import ground, pet
from backend.tests.test_survival_work import situation as work_situation

IRON = {"iron_cap": 1, "iron_tunic": 1}
LEATHER = {"leather_cap": 1, "leather_tunic": 1}


def stations():
    grid = flat()
    grid.put(2, 1, 0, "crafting_table")
    grid.put(-2, 1, 0, "furnace")
    return grid


def hurt(s):
    s.state["hurt_at"] = 5.0
    return s


class ArmorTests(unittest.TestCase):
    def test_iron_armor_at_a_crafting_table_and_lanterns_from_iron_and_a_torch(self):
        self.assertEqual(craft({"iron_ingot": 5}, "iron_cap", {"crafting_table"}), {"iron_cap": 1})
        self.assertEqual(craft({"iron_ingot": 8}, "iron_tunic", {"crafting_table"}), {"iron_tunic": 1})
        self.assertEqual(craft({"iron_ingot": 1, "torch": 2}, "lantern", set()), {"torch": 1, "lantern": 1})
        for item in ("iron_cap", "iron_tunic", "lantern"):
            self.assertTrue(valuable(item))

    def test_iron_takes_45_percent_off_a_blow_and_only_the_best_piece_on_each_slot_counts(self):
        self.assertAlmostEqual(armor_cut(IRON), 0.45)
        self.assertAlmostEqual(armor_cut({**IRON, **LEATHER}), 0.45)
        self.assertAlmostEqual(armor_cut(LEATHER), 0.20)
        self.assertAlmostEqual(armor_cut({"iron_cap": 1, "leather_tunic": 1}), 0.30)
        self.assertTrue(covered({"iron_cap": 1}, "leather_cap"))
        self.assertFalse(covered({"iron_cap": 1}, "leather_tunic"))
        self.assertEqual((armor_iron({}), armor_iron({"iron_cap": 1}), armor_iron(IRON)), (13, 8, 0))

    def test_leather_is_only_made_for_a_bare_slot(self):
        self.assertNotIn(("leather_tunic", "leather_cap"), gear_orders(IRON))
        self.assertEqual(gear_orders({"iron_cap": 1, "bow": 1, "arrow": 8}), [("leather_tunic",)])


class IronArmorPlanTests(unittest.TestCase):
    def test_once_a_creature_has_hurt_it_mimo_makes_iron_armor(self):
        inventory = {"iron_pickaxe": 1, "iron_sword": 1, "iron_ingot": 13}
        self.assertFalse(armor_wanted({}))
        self.assertIsNone(tool_plan(situation(inventory, stations())))
        s = hurt(situation(inventory, stations()))
        self.assertEqual(tool_plan(s), [{"kind": "craft", "recipe": "iron_tunic"}, {"kind": "craft", "recipe": "iron_cap"}])
        self.assertEqual(PURPOSES["craft_tools"].facts(s), "can make an iron tunic and an iron cap now")

    def test_and_goes_after_the_iron_it_takes(self):
        s = work_situation(pet(inventory={"iron_pickaxe": 1, "coal": 8, "gold_ingot": 3, "diamond": 3}), ground())
        self.assertEqual(wanted_ores(s), ())
        self.assertEqual(wanted_ores(hurt(s)), ("iron_ore",))

    def test_spare_iron_makes_lanterns_once_mimo_wears_both_pieces(self):
        best = {"diamond_pickaxe": 1, "diamond_sword": 1, **IRON}
        s = hurt(situation({**best, "iron_ingot": 2, "torch": 2}, stations()))
        self.assertEqual(tool_plan(s), [{"kind": "craft", "recipe": "lantern"}])
        self.assertIsNone(tool_plan(hurt(situation({**best, "iron_ingot": 2, "torch": 2, "lantern": LANTERNS_WANTED},
                                                   stations()))))

    def test_iron_replaces_leather(self):
        junk = storage.junk(Home({**LOOSE, "iron_cap": 1, "leather_cap": 1, "leather_tunic": 1}).situation())
        self.assertIn(("leather_cap", 1), junk)
        self.assertNotIn(("leather_tunic", 1), junk)


class LanternTests(unittest.TestCase):
    setUp = lighting_tests.LightTests.setUp  # a finished shelter with four torch corners
    situation = lighting_tests.LightTests.situation
    plan = lighting_tests.LightTests.plan

    def test_lanterns_light_the_dark_corners_first_then_torches(self):
        steps = self.plan(self.situation({"lantern": 1, "torch": 4}))
        placed = sorted((step["target"], step["block"]) for step in steps if step["kind"] == "place")
        self.assertEqual(sorted(cell for cell, _ in placed), sorted(CORNERS))
        self.assertEqual(sorted(block for _, block in placed), ["lantern", "torch", "torch", "torch"])

    def test_a_carried_lantern_takes_a_torch_corner_and_a_lantern_corner_is_lit(self):
        for cell in CORNERS:
            self.grid.put(*cell, "torch")
        self.assertFalse(PURPOSES["light_up"].valid(self.situation({"torch": 4})))
        s = self.situation({"lantern": 1})
        self.assertTrue(PURPOSES["light_up"].valid(s))
        steps = self.plan(s)
        at = steps.index({"kind": "place", "target": CORNERS[0], "block": "lantern"})
        self.assertEqual(steps[at - 1], {"kind": "mine", "target": CORNERS[0]})
        self.grid.put(*CORNERS[0], "lantern")
        self.assertFalse(PURPOSES["light_up"].valid(self.situation({"torch": 4}, clock=EVENING)))


    def test_the_facts_tell_of_carried_lanterns_and_the_torch_corners_they_could_take(self):
        """L3 final fix wave: the facts spoke only of torches, so the chooser never heard that
        light_up was on offer to hang a carried lantern or swap one for a torch."""
        facts = PURPOSES["light_up"].facts
        self.assertEqual(facts(self.situation({"torch": 3})), "4 dark corners around home, carrying 3 torches")
        for cell in CORNERS[:2]:
            self.grid.put(*cell, "torch")
        self.assertEqual(facts(self.situation({"torch": 1, "lantern": 3})),
                         "2 dark corners around home, carrying 1 torches and 3 lanterns; "
                         "1 torch corner a spare lantern can take")
        for cell in CORNERS[2:]:
            self.grid.put(*cell, "torch")
        self.assertEqual(facts(self.situation({"lantern": 1})),
                         "0 dark corners around home, carrying 0 torches and 1 lantern; "
                         "1 torch corner a spare lantern can take")


if __name__ == "__main__":
    unittest.main()

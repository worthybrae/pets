import unittest

from backend.services.crafting import RECIPES, SMELTING, TOOL_RANK, can_harvest, craft, smelt
from backend.survival import storage
from backend.survival.carrying import valuable
from backend.survival.creatures.combat import SWORDS, weapon
from backend.survival.grid import Grid
from backend.survival.purposes import PURPOSES
from backend.survival.senses import ORES, ores_around
from backend.survival.steps import mine_seconds
from backend.survival.toolmaking import next_tool, tool_orders, tool_plan, upgrades
from backend.survival.work import pickaxe_rank, wanted_ores
from backend.tests.test_survival_storage import LOOSE, Home
from backend.tests.test_survival_toolmaking import flat, situation
from backend.tests.test_survival_work import ground, pet
from backend.tests.test_survival_work import situation as work_situation


def stations():
    grid = flat()
    grid.put(2, 1, 0, "crafting_table")
    grid.put(-2, 1, 0, "furnace")
    return grid


def craft_step(recipe):
    return {"kind": "craft", "recipe": recipe}


class TierTests(unittest.TestCase):
    def test_gold_and_diamond_pickaxes_and_swords_at_a_crafting_table(self):
        self.assertEqual(craft({"gold_ingot": 3, "sticks": 2}, "gold_pickaxe", {"crafting_table"}), {"gold_pickaxe": 1})
        self.assertEqual(craft({"diamond": 3, "sticks": 2}, "diamond_pickaxe", {"crafting_table"}), {"diamond_pickaxe": 1})
        self.assertEqual(craft({"gold_ingot": 2, "sticks": 1}, "gold_sword", {"crafting_table"}), {"gold_sword": 1})
        self.assertEqual(craft({"diamond": 2, "sticks": 1}, "diamond_sword", {"crafting_table"}), {"diamond_sword": 1})
        for item in ("gold_pickaxe", "diamond_pickaxe", "gold_sword", "diamond_sword"):
            self.assertEqual(RECIPES[item]["station"], "crafting_table")
            self.assertTrue(valuable(item))
        self.assertEqual(SMELTING["gold_ore"], "gold_ingot")
        self.assertEqual(smelt({"gold_ore": 1, "coal": 1}, "gold_ore", {"furnace"}), {"gold_ingot": 1})
        self.assertTrue(valuable("diamond") and valuable("gold_ingot") and valuable("gold_ore"))

    def test_each_tier_mines_faster_and_hits_harder(self):
        order = ("wooden_pickaxe", "stone_pickaxe", "iron_pickaxe", "gold_pickaxe", "diamond_pickaxe")
        self.assertEqual([TOOL_RANK[tool] for tool in order], [1, 2, 3, 4, 5])
        times = [mine_seconds("stone", {tool: 1}) for tool in order]
        self.assertEqual(times, sorted(times, reverse=True))
        self.assertTrue(can_harvest("diamond_ore", {"gold_pickaxe": 1}))
        self.assertFalse(can_harvest("gold_ore", {"stone_pickaxe": 1}))
        self.assertEqual(list(SWORDS.values()), sorted(SWORDS.values()))
        self.assertEqual(weapon({"iron_sword": 1, "diamond_sword": 1, "gold_sword": 1}), "diamond_sword")


class LadderTests(unittest.TestCase):
    def test_over_an_iron_pickaxe_a_diamond_one_comes_before_gold(self):
        self.assertEqual(next_tool({"iron_pickaxe": 1}), "gold_pickaxe")
        self.assertEqual(upgrades({"iron_pickaxe": 1}), ["diamond_pickaxe", "gold_pickaxe"])
        self.assertEqual(upgrades({"stone_pickaxe": 1}), ["iron_pickaxe"])
        self.assertEqual(upgrades({"gold_pickaxe": 1}), ["diamond_pickaxe"])
        self.assertEqual(upgrades({"diamond_pickaxe": 1}), [])
        self.assertEqual(tool_orders({"iron_pickaxe": 1, "iron_sword": 1}),
                         [("diamond_pickaxe", "diamond_sword"), ("diamond_pickaxe", "gold_sword"), ("diamond_pickaxe",),
                          ("gold_pickaxe", "gold_sword"), ("gold_pickaxe",)])

    def test_gold_ore_is_smelted_into_a_gold_pickaxe_and_sword(self):
        s = situation({"iron_pickaxe": 1, "iron_sword": 1, "gold_ore": 5, "coal": 5, "sticks": 3}, stations())
        self.assertEqual(tool_plan(s), [{"kind": "smelt", "item": "gold_ore"}] * 3 + [craft_step("gold_pickaxe")]
                         + [{"kind": "smelt", "item": "gold_ore"}] * 2 + [craft_step("gold_sword")])
        self.assertEqual(PURPOSES["craft_tools"].facts(s), "can make a gold pickaxe and a gold sword now")

    def test_diamonds_skip_gold(self):
        s = situation({"iron_pickaxe": 1, "diamond": 5, "sticks": 3}, stations())
        self.assertEqual(tool_plan(s), [craft_step("diamond_pickaxe"), craft_step("diamond_sword")])

    def test_a_replaced_pickaxe_and_sword_are_dropped(self):
        junk = storage.junk(Home({**LOOSE, "gold_pickaxe": 1, "diamond_pickaxe": 1, "gold_sword": 1,
                                  "diamond_sword": 1}).situation())
        self.assertIn(("gold_pickaxe", 1), junk)
        self.assertIn(("gold_sword", 1), junk)
        self.assertNotIn(("diamond_pickaxe", 1), junk)


class OreTests(unittest.TestCase):
    def test_gold_and_diamond_are_noticed_and_wanted_once_mimo_has_an_iron_pickaxe(self):
        self.assertTrue({"gold_ore", "diamond_ore"} <= set(ORES))
        grid = Grid(lambda x, y, z: {(1, 0, 0): "gold_ore", (0, 1, 1): "diamond_ore"}.get((x, y, z), "stone"))
        self.assertEqual(sorted(ores_around(grid, (0, 0, 0))), [((0, 1, 1), "diamond_ore"), ((1, 0, 0), "gold_ore")])
        seen = lambda ore, count: [("ore", (9, -3, z), ore) for z in range(count)]
        both = seen("gold_ore", 3) + [("ore", (12, -3, z), "diamond_ore") for z in range(3)]
        want = lambda inventory, known=(): wanted_ores(work_situation(pet(inventory=inventory), ground(), known))
        self.assertEqual(want({"stone_pickaxe": 1, "coal": 8}, both), ("iron_ore",))
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}), ())  # none known: no trip worth making yet
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}, both), ("gold_ore", "diamond_ore"))
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8}, seen("gold_ore", 2)), ())  # not enough for a pickaxe
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8, "gold_ingot": 1}, seen("gold_ore", 2)), ("gold_ore",))
        self.assertEqual(want({"gold_pickaxe": 1, "coal": 8}, both), ("diamond_ore",))
        self.assertEqual(want({"iron_pickaxe": 1, "coal": 8, "gold_ingot": 3, "diamond": 3}, both), ())
        self.assertEqual(want({"diamond_pickaxe": 1, "coal": 8}, both), ())
        self.assertEqual(pickaxe_rank({"iron_pickaxe": 1, "wooden_pickaxe": 1}), 3)

    def test_mine_ore_goes_back_for_a_diamond(self):
        grid = ground({(3, -3, 0): "diamond_ore"})
        seen = [("ore", (3, -3, 0), "diamond_ore")]
        self.assertFalse(PURPOSES["mine_ore"].valid(work_situation(pet(inventory={"stone_pickaxe": 1, "coal": 8}), grid, seen)))
        s = work_situation(pet(inventory={"iron_pickaxe": 1, "coal": 8, "diamond": 2}), grid, seen)
        self.assertTrue(PURPOSES["mine_ore"].valid(s))
        self.assertEqual(PURPOSES["mine_ore"].plan(s, None),
                         [{"kind": "walk", "target": [3, -3, 0], "reach": 4.0}, {"kind": "mine", "target": [3, -3, 0]}])
        # fix round 1: ORE_REACH = steps.REACH (item 4)


if __name__ == "__main__":
    unittest.main()

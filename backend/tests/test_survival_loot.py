import unittest

from backend.survival import brain  # noqa: F401  (registers the loot hooks)
from backend.survival.carrying import valuable
from backend.survival.creatures.combat import finish_attack
from backend.survival.creatures.kinds import KINDS
from backend.survival.grid import Grid
from backend.survival.loot import extra_ore, ring_drops
from backend.survival.steps import finish_mine
from backend.survival.toolmaking import make
from backend.tests.test_survival_defense import meadow, pet

SEED = "5"


def hostile(number, kind="gloomling", **state):
    return {"id": number, "kind": kind, "state": dict(state)}


def share(kind, item, ring, count=600, **state):
    """How often a hostile of `kind` born in `ring` drops `item`, over `count` creatures."""
    return sum(item in ring_drops(SEED, hostile(number, kind, ring=ring, **state), KINDS[kind])
               for number in range(1, count + 1)) / count


class DropTests(unittest.TestCase):
    def test_at_home_and_from_animals_nothing_more(self):
        self.assertEqual(ring_drops(SEED, hostile(1), KINDS["gloomling"]), {})
        self.assertEqual(ring_drops(SEED, hostile(1, "cow", ring=3), KINDS["cow"]), {})

    def test_farther_out_the_drops_grow_richer(self):
        self.assertAlmostEqual(share("gloomling", "gloom_dust", 1), 0.4, delta=0.06)
        self.assertEqual(share("skitter", "gold_nugget", 1), 0.0)
        self.assertAlmostEqual(share("skitter", "gold_nugget", 2), 0.3, delta=0.06)
        self.assertAlmostEqual(share("skitter", "amber", 2), 0.12, delta=0.04)
        self.assertEqual(share("skitter", "diamond", 2), 0.0)
        self.assertAlmostEqual(share("skitter", "diamond", 3), 0.06, delta=0.03)
        self.assertAlmostEqual(share("thornback", "amber", 2), 0.27, delta=0.06)
        self.assertAlmostEqual(share("skitter", "amber", 3, elder=True), 0.48, delta=0.07)

    def test_the_same_kill_always_drops_the_same(self):
        creature = hostile(42, "skitter", ring=3)
        self.assertEqual(ring_drops(SEED, creature, KINDS["skitter"]), ring_drops(SEED, creature, KINDS["skitter"]))

    def test_a_kill_brings_them_into_mimo_s_arms(self):
        number = next(number for number in range(1, 400)
                      if "amber" in ring_drops("5", hostile(number, "skitter", ring=2), KINDS["skitter"]))
        grid = meadow()
        for _ in range(number):
            grid.herd.add("skitter", (1, 1, 0), 1.0, 0.0, 0.0, {"home": [1, 1, 0], "ring": 2})
        state = pet(inventory={"stone_sword": 1})
        finish_attack({"kind": "attack", "creature": number, "weapon": "stone_sword"}, state, grid, 1.0, [])
        self.assertEqual(state["inventory"].get("amber"), 1)
        self.assertIn("amber", grid.herd.get(number)["state"]["drops"])


class MiningTests(unittest.TestCase):
    def test_an_ore_mined_far_from_home_sometimes_gives_one_more(self):
        state = {"world_seed": SEED, "frontier": {"center": [0, 0]}, "position": {"x": 0.0, "y": 0.0, "z": 0.0}}
        cells = [(150 + x, -5, z) for x in range(20) for z in range(20)]
        lucky = [cell for cell in cells if extra_ore(state, cell, "iron_ore")]
        self.assertAlmostEqual(len(lucky) / len(cells), 0.10, delta=0.04)  # 5 % a level, in the far wilds
        self.assertEqual([cell for cell in cells if extra_ore(state, (cell[0] - 150, cell[1], cell[2]), "iron_ore")], [])
        self.assertEqual(extra_ore(state, lucky[0], "stone"), [])
        grid = Grid(lambda x, y, z: "iron_ore" if (x, y, z) == lucky[0] else "air")
        state["inventory"] = {}
        finish_mine({"kind": "mine", "target": {"x": lucky[0][0], "y": lucky[0][1], "z": lucky[0][2]},
                     "block": "iron_ore"}, state, grid, 1.0)
        self.assertEqual(state["inventory"], {"iron_ore": 2})


class ItemTests(unittest.TestCase):
    def test_four_gold_nuggets_make_an_ingot_when_there_is_no_ore_to_smelt(self):
        inventory, steps = {"gold_nugget": 12, "sticks": 2}, []
        make(inventory, "gold_pickaxe", 1, steps)
        self.assertEqual([step.get("recipe") for step in steps], ["gold_nuggets"] * 3 + ["gold_pickaxe"])
        self.assertEqual(inventory.get("gold_nugget", 0), 0)

    def test_amber_and_nuggets_are_worth_carrying(self):
        self.assertTrue(valuable("amber") and valuable("gold_nugget"))


if __name__ == "__main__":
    unittest.main()

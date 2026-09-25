import unittest

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.foraging import MORE_FOOD, food_need
from backend.survival.goals import GOALS, adopt_goal, complete
from backend.survival.housework import chest_key
from backend.survival.larder import chest_food, more_food
from backend.survival.purposes import PURPOSES
from backend.survival.storage import chest_spot
from backend.tests.test_survival_life_goals import built, shares


def larder(inventory=None):
    """A pet with its first shelter built whose goal is a full larder."""
    world = built(inventory)
    adopt_goal(world.state, "full_larder", "utility", "", 0.0)
    return world


class MoreFoodTests(unittest.TestCase):
    def test_a_fed_pet_filling_its_larder_wants_more_food_on_hand(self):
        self.assertIn(more_food, MORE_FOOD)
        world = built({"cooked_fish": 1})
        self.assertEqual((more_food(world.situation()), food_need(world.situation())), (0.0, 30.0))
        adopt_goal(world.state, "full_larder", "utility", "", 0.0)
        self.assertEqual((more_food(world.situation()), food_need(world.situation())), (40.0, 70.0))
        cell = chest_spot(world.situation())
        world.state["chests"] = {chest_key(cell): {"cooked_beef": 1}}  # 35 of the 60 in the chest already
        self.assertEqual(more_food(world.situation()), 25.0)
        world.state["vitals"]["hunger"] = 40.0  # hungry: food for now comes first
        self.assertEqual(more_food(world.situation()), 0.0)


class StockLarderTests(unittest.TestCase):
    def test_it_puts_a_chest_in_first_then_stores_the_food_beyond_a_days_worth(self):
        stock = PURPOSES["stock_larder"]
        world = built({"planks": 8, "cooked_fish": 4})
        self.assertFalse(stock.valid(world.situation()))  # only for the goal
        world = larder({"planks": 8, "cooked_fish": 4})
        s = world.situation()
        self.assertTrue(stock.valid(s))
        steps = stock.plan(s, world.context())
        cell = list(chest_spot(s))
        self.assertEqual([step["kind"] for step in steps], ["craft", "place", "store"])
        self.assertEqual(steps[1:], [{"kind": "place", "target": cell, "block": "chest"},
                                     {"kind": "store", "target": cell, "item": "cooked_fish", "amount": 2}])

    def test_the_larder_is_full_with_a_days_food_in_the_chest(self):
        world = larder({"planks": 8, "cooked_fish": 4})
        s = world.situation()
        self.assertEqual(shares(s, "full_larder"), [0.0, 0.0])
        world.grid.put(*chest_spot(s), "chest")
        world.state["chests"] = {chest_key(chest_spot(s)): {"cooked_fish": 1, "red_mushroom": 5}}
        s = world.situation()
        self.assertEqual((chest_food(s), shares(s, "full_larder")), (60.0, [1.0, 1.0]))
        self.assertTrue(complete(s, GOALS["full_larder"]))
        self.assertFalse(PURPOSES["stock_larder"].valid(s))


if __name__ == "__main__":
    unittest.main()

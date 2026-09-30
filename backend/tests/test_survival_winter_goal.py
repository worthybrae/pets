"""W2: "Ready for winter": when it is offered, how it wins the autumn's goal choice, the food that counts for it and
stock_larder serving it."""

import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.goals import GOALS, adopt_goal, is_open, rules_score
from backend.survival.home import home_cell
from backend.survival.housework import chest_key
from backend.survival.larder import more_food
from backend.survival.memory import know
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.storage import chest_spot
from backend.survival.trips import FENCES
from backend.survival.winter_prep import (
    GOAL, WINTER_EXTRA, WINTER_FOOD, far_goal, held, winter_fence, winter_food, winter_pull,
)
from backend.tests.test_survival_life_goals import built

WINTER = GOALS[GOAL]


def on_day(world, day, seconds=1000.0):
    """A Situation of the built world on game day `day` (born at 0, scale 1): day 21 is autumn day 1."""
    world.state.setdefault("born_at", 0.0)
    at = (day - 1) * DAY_SECONDS + seconds
    return Situation(world.state, world.grid, clock_at(0.0, at, 1.0), at, world.db)


def stocked(world, food):
    cell = chest_spot(on_day(world, 21))
    world.grid.put(*cell, "chest")
    world.state["chests"] = {chest_key(cell): food}
    return cell


class OfferTests(unittest.TestCase):
    def test_it_is_offered_in_autumn_to_a_pet_with_a_built_home_that_knows_winter(self):
        world = built()
        self.assertEqual([is_open(on_day(world, day), WINTER) for day in (11, 20, 21, 30, 31, 61, 71)],
                         [False, False, True, True, False, True, False])
        self.assertTrue(70 <= WINTER.score(on_day(world, 21)) <= 80)
        world.state["difficulty"] = "wild"
        self.assertFalse(is_open(on_day(world, 21), WINTER))
        know(world.db, "wild:winter", "lesson", 0.0)
        self.assertTrue(is_open(on_day(world, 21), WINTER))

    def test_the_autumn_pulls_it_past_a_goal_the_rules_would_keep(self):
        world = built({"wooden_pickaxe": 1})
        adopt_goal(world.state, "iron_tools", "utility", "", 0.0)
        s = on_day(world, 21)
        self.assertGreater(rules_score(s, WINTER), rules_score(s, GOALS["iron_tools"]))
        self.assertEqual(winter_pull(on_day(world, 15), WINTER), (0.0, ""))  # summer: no pull
        self.assertEqual(winter_pull(s, WINTER), (100.0, "winter comes in 10 days"))

    def test_in_winter_a_pet_that_knows_winter_keeps_near_the_home_it_built(self):
        world = built()
        winter, autumn = on_day(world, 31), on_day(world, 21)
        x, y, z = home_cell(winter)
        far, near = (x + 100, y, z), (x + 50, y, z)
        self.assertEqual([far_goal(s, GOALS[name]) for s in (winter, autumn) for name in ("expedition", "frontier", GOAL)],
                         [True, True, False, False, False, False])
        self.assertFalse(is_open(winter, GOALS["expedition"]))
        self.assertEqual([winter_fence(winter, far), winter_fence(winter, near), winter_fence(autumn, far)],
                         [True, False, False])
        heights = lambda cx, cz, seed: "alpine" if cx > x else "meadow"  # noqa: E731  (the mountains, east of home)
        with patch("backend.survival.winter_prep.biome_at", heights):
            self.assertTrue(winter_fence(winter, near))  # a winter day in the mountains freezes
        with patch("backend.survival.winter_prep.biome_at", return_value="alpine"):  # W2's final review: home up there
            self.assertEqual([winter_fence(winter, near), winter_fence(winter, far)], [False, True])
        self.assertIn(winter_fence, FENCES)
        world.state["difficulty"] = "wild"  # a wild pet that does not know winter roams as ever
        self.assertEqual((far_goal(on_day(world, 31), GOALS["expedition"]), winter_fence(on_day(world, 31), far)),
                         (False, False))

    def test_a_goal_whose_lesson_mimo_does_not_know_is_whole_for_it(self):
        world = built()
        world.state["difficulty"] = "wild"
        know(world.db, "wild:winter", "lesson", 0.0)
        s = on_day(world, 21)
        self.assertEqual([milestone.share(s) for milestone in WINTER.milestones[1:]], [1.0, 1.0, 1.0])


class FoodTests(unittest.TestCase):
    def test_a_gentle_pets_chest_food_all_counts(self):
        world = built()
        stocked(world, {"cooked_beef": 6, "bread": 4, "nightberries": 3})  # it knows nightberries from the start
        self.assertEqual(winter_food(on_day(world, 22)), 6 * 35 + 4 * 25)

    def test_a_wild_pets_counts_only_the_food_still_good_on_winter_day_one(self):
        world = built()
        world.state["difficulty"] = "wild"
        cell = stocked(world, {"cooked_beef": 4, "bread": 2})
        # cooked beef keeps 4 game days in arms, 8 in a chest; from autumn day 5 (6 days to winter) it ages
        # 6 x 0.5 = 3 game days of its 4 by winter day 1 (W2 plan, resolution 24): a lot under 0.25 worn keeps.
        world.state["chest_lots"] = {chest_key(cell): {"cooked_beef": [[1, 0.0], [3, 0.5]], "bread": [[2, 0.1]]}}
        self.assertEqual(winter_food(on_day(world, 25, 0.0)), 35 + 2 * 25)
        self.assertEqual(winter_food(on_day(world, 29, 0.0)), 4 * 35 + 2 * 25)
        # four winter days more (the goal's measure before resolution 24): 2 / 3 of a day more, under 0.08 worn
        self.assertEqual(winter_food(on_day(world, 25, 0.0), good_until=4), 35 + 2 * 25)

    def test_an_old_ruins_chest_counts_toward_no_milestone(self):
        """Carried from W2's seventh task: `held` counted a ruin chest's cloak and smoked meat toward the milestones,
        while `winter_food` leaves a ruin's chests out."""
        world = built()
        ruin = "500,20,500"
        world.state["chests"] = {ruin: {"wool_cloak": 1, "smoked_meat": 8, "bread": 10}}
        with patch("backend.survival.ruins.is_ruin_chest", lambda seed, cell: cell == (500, 20, 500)):
            s = on_day(world, 22)
            self.assertEqual((held(s, "wool_cloak"), held(s, "smoked_meat"), winter_food(s)), (0, 0, 0.0))
            self.assertEqual([milestone.share(s) for milestone in GOALS[GOAL].milestones], [0.0, 0.0, 0.0, 0.0])
            world.state["chests"]["1,1,1"] = {"smoked_meat": 2}  # one of its own
            self.assertEqual(held(on_day(world, 22), "smoked_meat"), 2)


class LarderTests(unittest.TestCase):
    def test_w2_a_wild_pet_readying_for_winter_stores_the_food_that_keeps_and_stays_with_the_goal(self):
        """W2 plan, resolution 24: on the W2 gate taught pets' chests held too little food good on winter day 1, 85 to
        126 of their foods spoiled a life, and they set the goal aside for expeditions."""
        from backend.survival.goals import holding
        from backend.survival.storage import spare_food
        world = built({"smoked_meat": 4, "bread": 4, "cooked_beef": 4, "berries": 5})
        world.state["difficulty"] = "wild"
        for lesson in ("winter", "keeping"):
            know(world.db, f"wild:{lesson}", "lesson", 0.0)
        before = dict(spare_food(on_day(world, 22)))
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        s = on_day(world, 22)
        spare = spare_food(s)
        # a day's worth stays on hand, the food that spoils soonest (the berries and a cooked beef); what keeps goes first
        self.assertEqual(spare, [("smoked_meat", 4), ("bread", 4), ("cooked_beef", 3)])
        self.assertNotEqual(dict(spare), before)
        self.assertTrue(holding(s, WINTER))  # its chests hold none of the winter's food yet
        self.assertEqual(winter_pull(s, WINTER)[0], 400.0)  # over a curious pet's discovery goal, kept (300)
        stocked(world, {"smoked_meat": 18})
        self.assertFalse(holding(on_day(world, 22), WINTER))  # 360 hunger points that keep: free to go
        self.assertEqual(winter_pull(on_day(world, 22), WINTER)[0], 100.0)
        world.state["chests"] = {}
        world.state["difficulty"] = "gentle"
        self.assertFalse(holding(on_day(world, 22), WINTER))  # a gentle pet: as before


    def test_stock_larder_fills_the_chests_to_the_winters_target(self):
        world = built({"cooked_fish": 5})
        adopt_goal(world.state, GOAL, "utility", "", 0.0)
        stocked(world, {"cooked_beef": 3})
        s = on_day(world, 22)
        self.assertEqual(more_food(s), WINTER_EXTRA)
        self.assertTrue(PURPOSES["stock_larder"].valid(s))
        self.assertIn(f"105 of {round(WINTER_FOOD)} hunger", PURPOSES["stock_larder"].facts(s))
        world.state["chests"] = {key: {"cooked_beef": 11} for key in world.state["chests"]}
        full = on_day(world, 22)
        self.assertFalse(PURPOSES["stock_larder"].valid(full))
        self.assertEqual(more_food(full), 0.0)

    def test_in_winter_a_pet_short_of_food_goes_to_its_chest_before_it_forages(self):
        world = built()
        stocked(world, {"cooked_beef": 11})
        world.state["vitals"]["hunger"] = 40.0
        autumn = on_day(world, 22)
        self.assertEqual(PURPOSES["build_storage"].score(autumn), 55.0)
        world.state["vitals"]["hunger"] = 20.0  # W2 plan, resolution 23: in any season once it is hungry
        self.assertGreater(PURPOSES["build_storage"].score(on_day(world, 22)), PURPOSES["forage"].score(on_day(world, 22)))
        world.state["vitals"]["hunger"] = 40.0
        world.state["sky"] = {"season": "winter"}
        s = on_day(world, 32)
        self.assertTrue(PURPOSES["build_storage"].valid(s))
        self.assertGreater(PURPOSES["build_storage"].score(s), PURPOSES["forage"].score(s))


if __name__ == "__main__":
    unittest.main()

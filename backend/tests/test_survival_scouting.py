import math
import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose and reason)
from backend.survival.goals import Goal, Milestone, advances
from backend.survival.grid import Grid
from backend.survival.memory import places
from backend.survival.trips import REASONS, best_trip, targets
from backend.survival.vitals import START_VITALS
from backend.tests.test_survival_purposes import context, pet, situation

TREES_EAST = lambda seed, x, z, radius: [(x, z, 0)] * 3 if x > 8 and abs(z) < 4 else []  # noqa: E731
BUSHES_EAST = lambda seed, x, z, radius, kinds: [(x, 1, z)] if x > 8 and abs(z) < 4 else []  # noqa: E731
FED = {"berries": 10}  # 80 hunger of food: no need to look for more


def with_cells(cells):
    """Stone at y <= 0 and air above, with `cells` overriding single cells."""
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


# Fix round 1: trees_value now checks the grid too, not worldgen alone (a chopped-out grove must
# not keep scoring as sure), so a test that wants a real, findable tree needs the grid and the
# worldgen mock to agree on where its trunks stand. A trunk cannot sit on the pet's own candidate
# column (Mimo could never stand there then), so this small forest stands a few blocks off the
# default pet's east candidate at (32, 0), still well within TREE_GROVE (12) of it.
TRUNKS = ((36, 0, 0), (38, 2, 0), (34, -2, 0))


def trees_nearby(seed, x, z, radius):
    return [trunk for trunk in TRUNKS if math.hypot(trunk[0] - x, trunk[1] - z) <= radius]


def with_forest(cells=None):
    """Stone at y <= 0 and air above, with a standing 4-tall oak trunk at each of TRUNKS; `cells`
    overrides single cells."""
    cells = cells or {}
    trunk_columns = {(tx, tz) for tx, tz, _ in TRUNKS}
    def natural(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if (x, z) in trunk_columns and 1 <= y <= 4:
            return "oak_log"
        return "stone" if y <= 0 else "air"
    return Grid(natural)


def shelter_goal(name):
    return Goal(name, name, "", (Milestone("Gather", lambda s: 0.0, ("explore",)),), score=lambda s: 50.0, thought="")


class TreesTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.exploring.terrain_height", lambda x, z, seed: 0),
                            ("backend.survival.scouting.trees_near", TREES_EAST)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_with_wood_wanted_and_no_tree_near_mimo_looks_for_trees_where_they_grow(self):
        with patch("backend.survival.scouting.trees_near", trees_nearby):
            s = situation(pet(inventory=dict(FED)), grid=with_forest())
            offer = best_trip(s)
            self.assertEqual((offer.reason, offer.why, offer.targets[0].direction),
                             ("trees", "I am out of wood and no tree stands near", "east"))
            self.assertEqual(offer.targets[0].what, "oak trees")
        self.assertIsNone(REASONS["trees"].wanted(situation(pet(inventory={**FED, "oak_log": 20}))))  # wood enough
        self.assertIsNone(REASONS["trees"].wanted(situation(pet(inventory={**FED, "oak_log": 5}))))  # not low
        tree = {(5, y, 0): "oak_log" for y in range(1, 5)}
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            self.assertIsNone(REASONS["trees"].wanted(situation(pet(inventory=dict(FED)), grid=with_cells(tree))))

    def test_a_candidate_whose_trees_are_already_gone_is_not_offered(self):
        # Fix round 1: worldgen never forgets a tree once it is cut down, so a chopped-out grove
        # must not keep scoring as a sure target -- otherwise the same empty spot keeps being
        # offered and the trip finds nothing there, again and again.
        s = situation(pet(inventory=dict(FED)))  # the default grid: TREES_EAST claims trees, none stand
        self.assertEqual(REASONS["trees"].value(s, 20, 0), (0.0, ""))
        self.assertEqual(targets(s, REASONS["trees"]), [])
        self.assertIsNone(best_trip(s))  # not offered at all: nowhere really holds a tree

    def test_trees_in_sight_after_a_walk_are_remembered_as_a_grove_and_end_the_trip(self):
        tree = {(5, y, 0): "oak_log" for y in range(1, 5)}
        with patch("backend.survival.senses.trees_near", lambda seed, x, z, radius: [(5, 0, 0)]):
            s = situation(pet(inventory=dict(FED)), grid=with_cells(tree))
            find = REASONS["trees"].look(s, context())
            self.assertEqual((find.words, find.done, find.new), ("oak trees", True, True))
            self.assertEqual([(place["x"], place["note"]) for place in places(s.db, ("grove",))], [(5, "oak")])
            self.assertFalse(REASONS["trees"].look(s, context()).new)  # the same wood: known already
        far = situation(pet(inventory=dict(FED)), places=[("grove", (-60, 1, 0))])
        self.assertEqual(REASONS["trees"].spots(far), [(-60, 0, "the oak trees it found")])

    def test_explore_for_trees_advances_the_goals_wood_is_for(self):
        with patch("backend.survival.scouting.trees_near", trees_nearby):
            s = situation(pet(inventory=dict(FED)), grid=with_forest())
            self.assertTrue(advances(s, "explore", shelter_goal("first_shelter")))
            self.assertFalse(advances(s, "explore", shelter_goal("herd")))
        self.assertTrue(advances(s, "gather_wood", shelter_goal("herd")))  # no check of its own


class FoodTests(unittest.TestCase):
    def setUp(self):
        for name, value in (("backend.survival.exploring.terrain_height", lambda x, z, seed: 0),
                            ("backend.survival.scouting.natural_plants", BUSHES_EAST)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_short_of_food_with_none_near_mimo_looks_for_it_where_it_grows(self):
        wood = {"oak_log": 20}  # no need for trees
        offer = best_trip(situation(pet(inventory=dict(wood))))
        self.assertEqual((offer.reason, offer.why, offer.targets[0].what), ("food", "I carry little food and none is near", "berries"))
        self.assertEqual(offer.score, 30.0 + 60.0 / 3 + (100.0 - START_VITALS["hunger"]) / 3)
        hungry = situation(pet(inventory=dict(wood), vitals={**START_VITALS, "hunger": 30.0}))
        self.assertEqual(REASONS["food"].wanted(hungry), "I am hungry and no food is near")
        self.assertIsNone(REASONS["food"].wanted(situation(pet(inventory={**wood, **FED}))))

    def test_ripe_food_in_sight_after_a_walk_is_remembered_and_ends_the_trip(self):
        bush = (6, 1, 0)
        with patch("backend.survival.senses.natural_plants", lambda seed, x, z, radius, kinds: [bush]):
            s = situation(pet(), grid=with_cells({bush: "berry_bush_ripe"}))
            find = REASONS["food"].look(s, context())
        self.assertEqual((find.words, find.done, find.new), ("berries", True, True))
        food = places(s.db, ("food",))
        self.assertEqual([(place["x"], place["data"]["ripe"]) for place in food], [(6, 1)])


if __name__ == "__main__":
    unittest.main()

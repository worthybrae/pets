import math
import sqlite3
import unittest
from unittest.mock import patch

from backend.services.worldgen import SEA_LEVEL
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import observe_step
from backend.survival.exploring import dry_target, explore_target
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, mark_explored, patch_of, places, remember
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
GROUND = 4
HOME = (0, GROUND + 1, 0)


def lake_world(lake=lambda x, z: False, cells=None):
    """Grass at height 4, except the `lake` columns: ground at 0 under water up to sea level.
    `cells` overrides single cells."""
    cells = cells or {}

    def height(x, z, seed=None):
        return 0 if lake(x, z) else GROUND

    def natural(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        top = height(x, z)
        if y < top:
            return "stone"
        if y == top:
            return "grass"
        return "water" if lake(x, z) and y <= SEA_LEVEL else "air"

    return height, Grid(natural)


def pet(x=0, z=0, **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": float(x), "y": float(GROUND + 1), "z": float(z)},
             "inventory": {}, "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def memory(places=(), visited=(), at=0.0):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    for kind, cell in places:
        remember(db, kind, cell, 0.0)
    mark_explored(db, visited, at)
    return db


def context(grid):
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[])


def line(start, end):
    """The patches a straight walk from `start` to `end` crosses."""
    steps = max(1, round(math.dist((start[0], start[2]), (end[0], end[2]))))
    return [patch_of(round(start[0] + (end[0] - start[0]) * i / steps), round(start[2] + (end[2] - start[2]) * i / steps))
            for i in range(steps + 1)]


class ExploreTargetTests(unittest.TestCase):
    def world(self, lake=lambda x, z: False):
        height, grid = lake_world(lake)
        patcher = patch("backend.survival.exploring.terrain_height", height)
        patcher.start()
        self.addCleanup(patcher.stop)
        return grid

    def test_a_column_with_water_at_its_surface_is_never_a_target(self):
        grid = self.world(lambda x, z: x >= 10)
        self.assertIsNone(dry_target(grid, "1", 20, 0))
        self.assertEqual(dry_target(grid, "1", 0, 20), (0, GROUND + 1, 20))
        basin = Grid(lambda x, y, z: "stone" if y <= 0 else "air")  # dug below sea level, but dry
        with patch("backend.survival.exploring.terrain_height", lambda x, z, seed: 0):
            self.assertEqual(dry_target(basin, "1", 3, 3), (3, 1, 3))
            basin.put(3, 2, 3, "water")  # edits count: water above the ground
            self.assertIsNone(dry_target(basin, "1", 3, 3))

    def test_explore_walks_whole_to_dry_ground_and_never_into_the_lake(self):
        lake = lambda x, z: x >= 12  # noqa: E731
        grid = self.world(lake)
        state, visited, at = pet(), [], 0.0
        for trip in range(8):
            at += 100.0
            s = Situation(state, grid, DAY, at, memory(visited=visited))
            ensure_brain(state)["batches"] = 0
            steps = PURPOSES["explore"].plan(s, context(grid))
            self.assertEqual(len(steps), 1)
            step = steps[0]
            self.assertEqual((step["kind"], step["reach"], step["whole"]), ("walk", 3.0, True))
            x, y, z = step["target"]
            self.assertFalse(lake(x, z), step)
            self.assertEqual(y, GROUND + 1)
            visited += line(HOME, step["target"])
        self.assertEqual(state["brain"]["explored"], 8)

    def test_explore_prefers_patches_it_has_not_visited(self):
        grid = self.world()
        east = [(rx, rz) for rx in range(0, 12) for rz in range(-12, 12)]
        s = Situation(pet(), grid, DAY, 100.0, memory(visited=east, at=90.0))
        target = explore_target(s)
        self.assertLess(target[0], 0)

    def test_the_next_trip_never_picks_the_ground_the_last_one_visited(self):
        grid = self.world()
        first = explore_target(Situation(pet(), grid, DAY, 100.0, memory()))
        walked = line(HOME, first)
        second = explore_target(Situation(pet(), grid, DAY, 200.0, memory(visited=walked, at=150.0)))
        self.assertNotIn(patch_of(second[0], second[2]), walked)

    def test_a_spot_mimo_walked_to_lately_is_not_picked_again(self):
        # A dry strip one patch wide between lakes, walked end to end just now: the lake either
        # side still looks new, but going back to either end would only pace up and down.
        grid = self.world(lambda x, z: not (0 <= x <= 7 and -64 <= z <= 7))
        db = memory(visited=[(0, rz) for rz in range(-8, 1)], at=50.0)
        state = pet(z=-24)
        self.assertIsNone(explore_target(Situation(state, grid, DAY, 100.0, db)))
        later = Situation(state, grid, DAY, 100.0 + 3600.0, db)  # a game day on, it may go back
        self.assertIn(explore_target(later), [(0, GROUND + 1, -56)])

    def test_a_lakeside_home_explores_somewhere_new_and_dry_on_every_trip(self):
        lake = lambda x, z: x >= 10 or z >= 30  # noqa: E731  (a lake east and south of home)
        grid = self.world(lake)
        visited, targets, at = [], [], 0.0
        for trip in range(6):
            at += 600.0
            s = Situation(pet(), grid, DAY, at, memory(places=[("home", HOME)], visited=visited, at=at - 300.0))
            target = explore_target(s)
            self.assertIsNotNone(target)
            self.assertFalse(lake(target[0], target[2]), target)
            self.assertNotIn(patch_of(target[0], target[2]), visited)
            targets.append(target)
            visited += line(HOME, target)
        self.assertEqual(len({patch_of(x, z) for x, _, z in targets}), 6)

    def test_with_no_dry_ground_in_reach_explore_is_not_offered(self):
        grid = self.world(lambda x, z: abs(x) > 6 or abs(z) > 6)
        s = Situation(pet(), grid, DAY, 100.0, memory())
        self.assertIsNone(explore_target(s))
        self.assertFalse(PURPOSES["explore"].valid(s))
        self.assertEqual(PURPOSES["explore"].plan(s, context(grid)), [])
        self.assertTrue(PURPOSES["explore"].valid(Situation(pet(), self.world(), DAY, 100.0, memory())))

    def test_ground_near_a_failed_step_is_left_alone(self):
        grid = self.world()
        # Everything is visited except around (32, 0), so that is where Mimo would go.
        seen = [(rx, rz) for rx in range(-12, 12) for rz in range(-12, 12) if abs(rx - 4) > 1 or abs(rz) > 1]
        s = Situation(pet(), grid, DAY, 100.0, memory(visited=seen, at=90.0))
        self.assertLess(math.dist(explore_target(s), (32, GROUND + 1, 0)), 12)
        failed = {"kind": "walk", "result": "failed", "target": {"x": 32, "y": GROUND + 1, "z": 0},
                  "started_at": 95.0, "ended_at": 95.0}
        s = Situation(pet(recent_actions=[failed]), grid, DAY, 100.0, memory(visited=seen, at=90.0))
        self.assertGreater(math.hypot(explore_target(s)[0] - 32, explore_target(s)[2]), 4)

    def test_farther_ground_is_tried_once_the_near_ground_is_well_explored(self):
        grid = self.world()
        near = explore_target(Situation(pet(), grid, DAY, 100.0, memory()))
        self.assertIn(round(math.hypot(near[0], near[2])), (32, 48))
        seen = [(rx, rz) for rx in range(-8, 8) for rz in range(-8, 8)]  # all within 56 blocks, lately
        far = explore_target(Situation(pet(), grid, DAY, 100.0, memory(visited=seen, at=90.0)))
        self.assertEqual(round(math.hypot(far[0], far[2])), 64)

    def test_with_a_home_targets_stay_within_reach_of_it(self):
        grid = self.world()
        for trip in range(6):
            state = pet(x=50)
            ensure_brain(state)["explored"] = trip
            s = Situation(state, grid, DAY, 100.0, memory(places=[("home", HOME)]))
            target = explore_target(s)
            self.assertLessEqual(math.hypot(target[0], target[2]), 60)


class NewGroundTests(unittest.TestCase):
    """The first visit to a patch more than 32 blocks from home that holds food or water nobody
    remembers yet is a discovery."""

    def setUp(self):
        self.bush, self.near_bush = (44, GROUND + 1, 3), (10, GROUND + 1, 20)
        height, self.grid = lake_world(lambda x, z: 60 <= x < 64 and 0 <= z < 8,
                                       {self.bush: "berry_bush_ripe", self.near_bush: "berry_bush_ripe"})
        plants = [self.bush, self.near_bush]
        for name, fake in (("backend.survival.exploring.terrain_height", height),
                           ("backend.survival.exploring.natural_plants",
                            lambda seed, x, z, radius, kinds: [cell for cell in plants
                                                               if math.hypot(cell[0] - x, cell[2] - z) <= radius])):
            patcher = patch(name, fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.state = pet()
        ensure_brain(self.state)["pending"] = None
        self.context = ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[],
                                     db=memory(places=[("home", HOME)]))

    def walk(self, cells, at, purpose="explore"):
        path = [{"x": x, "y": GROUND + 1, "z": z, "at": at} for x, z in cells]
        self.state["position"] = {"x": float(cells[-1][0]), "y": float(GROUND + 1), "z": float(cells[-1][1])}
        observe_step(self.state, {"kind": "walk", "path": path, "purpose": purpose}, self.context, at)

    def test_food_and_water_on_new_ground_far_from_home_are_discoveries(self):
        self.walk([(x, 3) for x in range(0, 56)], 10.0)  # past the bush, to the patch before the lake's
        self.assertEqual(self.context.events, [(10.0, "explore", "Pip found berries on new ground.")])
        self.assertEqual(self.state["brain"]["pending"]["reasons"], ["discovery"])
        food = places(self.context.db, ("food",))
        self.assertEqual([(place["x"], place["z"], place["data"]) for place in food],
                         [(44, 3, {"ripe": 1, "seen_at": 10.0})])
        self.state["brain"]["pending"] = None
        # On into the lake's patch, fetching wood: the first water is logged, but the wood trip
        # is not cut short for it.
        self.walk([(x, 3) for x in range(55, 60)], 20.0, purpose="gather_wood")
        self.assertEqual(self.context.events[-1], (20.0, "discovered", "Pip found water."))
        self.assertEqual([place["kind"] for place in places(self.context.db, ("water",))], ["water"])
        self.assertEqual(self.state["brain"]["found"], ["water"])
        self.assertIsNone(self.state["brain"]["pending"])
        self.walk([(x, 3) for x in range(59, -1, -1)], 30.0)  # home again: nothing new on the way
        self.assertEqual(len(self.context.events), 2)
        self.assertIsNone(self.state["brain"]["pending"])

    def test_new_ground_asks_for_a_new_choice_at_most_once_a_game_hour(self):
        second = (44, GROUND + 1, 60)  # another bush, far from the first
        self.grid.put(*second, "berry_bush_ripe")
        plants = [self.bush, second]
        with patch("backend.survival.exploring.natural_plants",
                   lambda seed, x, z, radius, kinds: [cell for cell in plants
                                                      if math.hypot(cell[0] - x, cell[2] - z) <= radius]):
            self.walk([(x, 3) for x in range(0, 50)], 10.0)
            self.state["brain"]["pending"] = None
            self.walk([(44, z) for z in range(4, 64)], 20.0)  # the second bush, soon after
            self.assertEqual(self.context.events[-1], (20.0, "explore", "Pip found berries on new ground."))
            self.assertIsNone(self.state["brain"]["pending"])  # logged, but no new choice so soon
        self.assertEqual(len(places(self.context.db, ("food",))), 2)

    def test_ground_near_home_holds_no_discoveries(self):
        self.walk([(10, z) for z in range(0, 24)], 10.0)
        self.assertEqual((self.context.events, places(self.context.db, ("food",))), ([], []))
        self.assertIsNone(self.state["brain"]["pending"])


class ExploreScoreTests(unittest.TestCase):
    def setUp(self):
        height, self.grid = lake_world()
        for name in ("backend.survival.exploring.terrain_height",):
            patcher = patch(name, height)
            patcher.start()
            self.addCleanup(patcher.stop)
        trees = patch("backend.survival.purposes.trees_near", lambda seed, x, z, radius: [(5, 0, 0)])
        trees.start()
        self.addCleanup(trees.stop)

    def test_explore_scores_lower_with_little_new_land_near_and_higher_for_curious_pets(self):
        explore = PURPOSES["explore"]
        fresh = explore.score(Situation(pet(), self.grid, DAY, 100.0, memory()))
        seen = [(rx, rz) for rx in range(-9, 9) for rz in range(-9, 9)]
        explored = explore.score(Situation(pet(), self.grid, DAY, 100.0, memory(visited=seen, at=90.0)))
        self.assertEqual(fresh, 30.0)
        self.assertEqual(fresh - explored, 20.0)
        curious = explore.score(Situation(pet(traits={"curiosity": 100}), self.grid, DAY, 100.0, memory()))
        self.assertGreater(curious, fresh)

    def test_the_facts_say_which_way_is_unexplored_and_how_much_was_seen(self):
        # West and south of Mimo are known; north, east and the far corners are not.
        seen = [(rx, rz) for rx in range(-9, 1) for rz in range(-9, 9)] + \
               [(rx, rz) for rx in range(-9, 9) for rz in range(0, 9)]
        facts = PURPOSES["explore"].facts(Situation(pet(), self.grid, DAY, 100.0, memory(visited=seen, at=90.0)))
        self.assertRegex(facts, r"; northeast, (east and north|north and east) are unexplored; ")
        self.assertRegex(facts, r"; \d+% of the land within 64 blocks seen$")
        fresh = PURPOSES["explore"].facts(Situation(pet(), self.grid, DAY, 100.0, memory()))
        self.assertTrue(fresh.endswith("; land lies unexplored every way; 0% of the land within 64 blocks seen"),
                        fresh)


if __name__ == "__main__":
    unittest.main()

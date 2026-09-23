import unittest

from backend.survival.grid import Grid
from backend.survival.pathing import MAX_NODES, MAX_RANGE, find_path, moves, route, timed_path


def world(rule):
    """A grid from a function of (x, y, z) that returns a material name."""
    return Grid(rule)


def flat(x, y, z):
    return "stone" if y <= 0 else "air"


class MoveTests(unittest.TestCase):
    def test_flat_ground_offers_the_four_neighbors(self):
        self.assertEqual(sorted(moves(world(flat), (0, 1, 0))), [(-1, 1, 0), (0, 1, -1), (0, 1, 1), (1, 1, 0)])

    def test_stepping_up_one_needs_headroom(self):
        step = {(1, 1, 0): "stone"}
        grid = world(lambda x, y, z: step.get((x, y, z)) or flat(x, y, z))
        self.assertIn((1, 2, 0), list(moves(grid, (0, 1, 0))))
        step[(0, 2, 0)] = "stone"
        grid = world(lambda x, y, z: step.get((x, y, z)) or flat(x, y, z))
        self.assertNotIn((1, 2, 0), list(moves(grid, (0, 1, 0))))

    def test_two_blocks_up_is_too_high(self):
        wall = world(lambda x, y, z: "stone" if y <= 0 or (x == 1 and y <= 2) else "air")
        self.assertNotIn(1, [cell[0] for cell in moves(wall, (0, 1, 0))])

    def test_drops_of_up_to_three(self):
        def ledge(height):
            return world(lambda x, y, z: "stone" if y <= 0 or (x <= 0 and y <= height) else "air")
        self.assertIn((1, 1, 0), list(moves(ledge(3), (0, 4, 0))))
        self.assertNotIn(1, [cell[0] for cell in moves(ledge(4), (0, 5, 0))])

    def test_mimo_swims_on_the_surface_but_never_under_it(self):
        pond = world(lambda x, y, z: "water" if x >= 1 and y <= 0 else flat(x, y, z))
        self.assertIn((1, 1, 0), list(moves(pond, (0, 1, 0))))
        self.assertTrue(pond.swimming((1, 1, 0)))
        high = world(lambda x, y, z: "water" if x >= 1 and y <= 1 else flat(x, y, z))
        reachable = list(moves(high, (0, 1, 0)))
        self.assertNotIn((1, 1, 0), reachable)
        self.assertIn((1, 2, 0), reachable)


class RouteTests(unittest.TestCase):
    def assert_connected(self, start, cells):
        previous = start
        for cell in cells:
            self.assertEqual(abs(cell[0] - previous[0]) + abs(cell[2] - previous[2]), 1, (previous, cell))
            previous = cell

    def test_walks_on_flat_ground_one_side_step_at_a_time(self):
        cells, reached = route(world(flat), (0, 1, 0), (5, 1, 5))
        self.assertTrue(reached)
        self.assertEqual(len(cells), 10)
        self.assertEqual(cells[-1], (5, 1, 5))
        self.assert_connected((0, 1, 0), cells)

    def test_climbs_a_step_and_drops_off_the_far_side(self):
        rule = lambda x, y, z: "stone" if y <= 0 or (x == 3 and y <= 1) else "air"
        cells, reached = route(world(rule), (0, 1, 0), (6, 1, 0))
        self.assertTrue(reached)
        self.assertIn((3, 2, 0), cells)
        self.assertEqual(len(cells), 6)

    def test_a_wall_two_high_blocks_the_way(self):
        rule = lambda x, y, z: "stone" if y <= 0 or (x == 3 and y <= 2) else "air"
        cells, reached = find_path(world(rule), (0, 1, 0), lambda cell: cell == (6, 1, 0), (6, 1, 0), max_range=8)
        self.assertFalse(reached)
        self.assertEqual(cells[-1], (2, 1, 0))

    def test_a_drop_deeper_than_three_is_never_taken(self):
        cliff = world(lambda x, y, z: "stone" if y <= 0 or (x <= 0 and y <= 4) else "air")
        _, reached = find_path(cliff, (0, 5, 0), lambda cell: cell == (3, 1, 0), (3, 1, 0), max_range=6)
        self.assertFalse(reached)
        step = world(lambda x, y, z: "stone" if y <= 0 or (x <= 0 and y <= 3) else "air")
        cells, reached = route(step, (0, 4, 0), (3, 1, 0))
        self.assertTrue(reached)
        self.assertEqual(cells, [(1, 1, 0), (2, 1, 0), (3, 1, 0)])

    def test_swimming_costs_three_times_as_much(self):
        def pool(half_width):
            def rule(x, y, z):
                if 1 <= x <= 3 and abs(z) <= half_width and y == 0:
                    return "water"
                return flat(x, y, z)
            return world(rule)

        narrow = pool(1)
        detour, reached = route(narrow, (0, 1, 0), (4, 1, 0))
        self.assertTrue(reached)
        self.assertEqual(len(detour), 8)
        self.assertFalse(any(narrow.swimming(cell) for cell in detour))
        wide = pool(5)
        across, _ = route(wide, (0, 1, 0), (4, 1, 0))
        self.assertEqual(across, [(1, 1, 0), (2, 1, 0), (3, 1, 0), (4, 1, 0)])
        timed = timed_path(wide, (0, 1, 0), across, 10.0)
        self.assertEqual([entry["at"] for entry in timed], [10.0, 10.9, 11.8, 12.7, 13.0])
        self.assertEqual([entry.get("swim", False) for entry in timed], [False, True, True, True, False])

    def test_reach_stops_beside_the_target(self):
        trunk = world(lambda x, y, z: "oak_log" if (x, z) == (5, 0) and 1 <= y <= 4 else flat(x, y, z))
        cells, reached = route(trunk, (0, 1, 0), (5, 1, 0), reach=1.5)
        self.assertTrue(reached)
        self.assertEqual(cells[-1], (4, 1, 0))

    def test_far_targets_are_reached_in_segments(self):
        grid = world(flat)
        position, segments = (0, 1, 0), 0
        while True:
            cells, reached = route(grid, position, (300, 1, 40))
            self.assertTrue(cells)
            for cell in cells:
                self.assertLessEqual(abs(cell[0] - position[0]), MAX_RANGE)
                self.assertLessEqual(abs(cell[2] - position[2]), MAX_RANGE)
            position, segments = cells[-1], segments + 1
            if reached:
                break
        self.assertEqual(position, (300, 1, 40))
        self.assertEqual(segments, 4)

    def test_the_search_stops_at_its_node_budget(self):
        self.assertEqual((MAX_NODES, MAX_RANGE), (20_000, 96))
        walled = world(lambda x, y, z: "stone" if y <= 0 or (x == 30 and y <= 2) else "air")
        cells, reached = find_path(walled, (0, 1, 0), lambda cell: cell == (40, 1, 0), (40, 1, 0), max_nodes=500)
        self.assertFalse(reached)
        self.assertEqual(cells[-1], (29, 1, 0))


if __name__ == "__main__":
    unittest.main()

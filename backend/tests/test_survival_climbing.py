import sqlite3
import unittest

from backend.services.blocks import is_tall
from backend.services.crafting import craft
from backend.survival.creatures.moves import steps as creature_steps
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.pathing import find_path, moves, route


def meadow(blocks=None):
    """Grass at y 0, dirt below, air above; `blocks` placed on top."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


def ring(size=4):
    """A fence ring around (0, 0): the cells of a size x size square's edge, at y 1."""
    return {(x, 1, z): "fence" for x in range(-1, size - 1) for z in range(-1, size - 1)
            if x in (-1, size - 2) or z in (-1, size - 2)}


class RecipeTests(unittest.TestCase):
    def test_ladders_from_sticks_and_fences_from_planks_and_sticks(self):
        self.assertEqual(craft({"sticks": 7}, "ladder", set()), {"ladder": 3})
        self.assertEqual(craft({"birch_planks": 4, "sticks": 2}, "fence", set()), {"fence": 3})
        self.assertTrue(is_tall("fence"))
        self.assertFalse(is_tall("stone") or is_tall("ladder") or is_tall("not_a_block"))


class FenceTests(unittest.TestCase):
    def test_nothing_stands_on_a_fence_or_steps_over_it(self):
        grid = meadow({(1, 1, 0): "fence"})
        self.assertFalse(grid.standable((1, 2, 0)))
        self.assertNotIn((1, 2, 0), list(moves(grid, (0, 1, 0))))
        self.assertTrue(grid.standable((2, 1, 0)))

    def test_mimo_walks_round_a_fence_and_an_animal_in_a_pen_stays_there(self):
        grid = meadow(ring())
        cells, reached = route(grid, (0, 1, 0), (4, 1, 0))
        self.assertFalse(reached)  # the pen has no way out
        grid.herd = Herd(sqlite3.connect(":memory:"))
        create_creature_tables(grid.herd.db)
        self.assertEqual(sorted(creature_steps(grid, (0, 1, 0), False)), [(0, 1, 1), (1, 1, 0)])
        outside, reached = route(meadow({(1, 1, 0): "fence", (1, 1, 1): "fence", (1, 1, -1): "fence"}), (0, 1, 0), (2, 1, 0))
        self.assertTrue(reached)
        self.assertTrue(all(cell[1] == 1 for cell in outside))  # round the end of the fence, never over it


class LadderTests(unittest.TestCase):
    def shaft(self):
        """A shaft dug 4 deep at (0, 0), a ladder from its floor to the surface."""
        grid = meadow()
        for y in range(-3, 1):
            grid.put(0, y, 0, "ladder")
        return grid

    def test_mimo_climbs_up_and_down_a_ladder(self):
        grid = self.shaft()
        self.assertTrue(grid.standable((0, -3, 0)) and grid.standable((0, 1, 0)))
        self.assertIn((0, -2, 0), list(moves(grid, (0, -3, 0))))
        self.assertIn((0, 0, 0), list(moves(grid, (0, 1, 0))))
        up, reached = find_path(grid, (0, -3, 0), lambda cell: cell == (3, 1, 0), (3, 1, 0))
        self.assertTrue(reached)
        self.assertEqual(up[:4], [(0, -2, 0), (0, -1, 0), (0, 0, 0), (1, 1, 0)])
        down, reached = find_path(grid, (3, 1, 0), lambda cell: cell == (0, -3, 0), (0, -3, 0))
        self.assertTrue(reached)

    def test_without_the_ladder_the_shaft_is_a_trap(self):
        grid = meadow({(0, y, 0): "air" for y in range(-3, 1)})
        _, reached = find_path(grid, (0, -3, 0), lambda cell: cell == (3, 1, 0), (3, 1, 0))
        self.assertFalse(reached)


if __name__ == "__main__":
    unittest.main()

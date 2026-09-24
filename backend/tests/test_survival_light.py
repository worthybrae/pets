import unittest
from unittest.mock import patch

from backend.survival.grid import Grid
from backend.survival.light import DARK, SKY_DAY, SKY_NIGHT, Lights, dark, light_at, sky_open


def hillside(blocks=None):
    """Grass at y 0, stone below with a cave at y -3..-2 under x 5..8, and `blocks` placed."""
    def natural(x, y, z):
        if y == 0:
            return "grass"
        if y < 0:
            return "air" if 5 <= x <= 8 and -3 <= y <= -2 else "stone"
        return "air"

    grid = Grid(natural)
    for cell, block in (blocks or {}).items():
        grid.put(*cell, block)
    return grid


class LightTests(unittest.TestCase):
    def setUp(self):
        patcher = patch("backend.survival.light.terrain_height", lambda x, z, seed: 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_sky_lights_open_ground_by_day_and_dimly_at_night(self):
        grid = hillside({(3, 5, 0): "leaves"})
        self.assertEqual((light_at(grid, "1", (0, 1, 0), False), light_at(grid, "1", (0, 1, 0), True)),
                         (SKY_DAY, SKY_NIGHT))
        self.assertTrue(sky_open(grid, "1", (3, 1, 0)))  # leaves let the sky through
        self.assertFalse(dark(grid, "1", (0, 1, 0), False))
        self.assertTrue(dark(grid, "1", (0, 1, 0), True))
        self.assertLessEqual(SKY_NIGHT, DARK)

    def test_caves_roofs_and_tunnels_are_dark_by_day_but_an_open_pit_is_not(self):
        grid = hillside({(0, 3, 0): "planks", (2, 0, 0): "air", (2, -1, 0): "air"})
        self.assertEqual(light_at(grid, "1", (6, -3, 0), False), 0)  # in the cave
        self.assertEqual(light_at(grid, "1", (0, 1, 0), False), 0)  # under a roof
        self.assertEqual(light_at(grid, "1", (2, -1, 0), False), SKY_DAY)  # at the bottom of a pit
        self.assertTrue(dark(grid, "1", (6, -3, 0), False))

    def test_torches_lanterns_and_fires_light_what_is_near_one_level_less_a_block(self):
        grid = hillside({(0, 1, 0): "torch", (20, 1, 0): "lantern", (40, 1, 0): "campfire", (60, 1, 0): "furnace"})
        lights = Lights(grid, (30, 1, 0), 40)
        self.assertEqual([lights.at(cell) for cell in ((0, 1, 0), (3, 1, 0), (0, 3, 2), (20, 1, 1), (40, 1, 0), (60, 2, 0))],
                         [14, 11, 10, 14, 13, 12])
        self.assertEqual(lights.at((0, 1, 100)), 0)
        self.assertEqual(light_at(grid, "1", (6, -3, 0), False, lights), 4)  # through the rock, 10 blocks off
        self.assertEqual(light_at(grid, "1", (6, 1, 0), True), 8)  # a torch keeps 6 blocks around it safe
        self.assertTrue(dark(grid, "1", (7, 1, 0), True))


if __name__ == "__main__":
    unittest.main()

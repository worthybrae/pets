import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.creatures.fishing import BITE_MOST, bite_bonus, fish_near, show_catch
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.steps import finish_step
from backend.survival.vitals import START_VITALS

HOOK = (3, 0, 0)


def lake():
    """Water at y 0 for x >= 2, grass elsewhere."""
    grid = Grid(lambda x, y, z: ("water" if x >= 2 else "grass") if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_creature_tables(db)
    grid.herd = Herd(db)
    return grid


def fish(grid, cell):
    return grid.herd.add("fish", cell, 2.0, 0.0, 50.0, {"home": list(cell), "pose": "swimming", "turn": 0})


def pet():
    return {"name": "Pip", "world_seed": "1", "position": {"x": 1.0, "y": 1.0, "z": 0.0}, "inventory": {},
            "vitals": dict(START_VITALS)}


class FishTests(unittest.TestCase):
    def test_each_fish_near_the_hook_adds_a_little_to_the_chance_up_to_a_tenth(self):
        grid = lake()
        self.assertEqual(bite_bonus(grid, HOOK, 0.0), 0.0)
        near = [fish(grid, (4 + n, 0, 0)) for n in range(3)]
        fish(grid, (30, 0, 0))
        grid.herd.add("cow", (1, 1, 0), 10.0, 0.0, 0.0, {})
        self.assertEqual([found["id"] for found in fish_near(grid, HOOK, 0.0)], [creature["id"] for creature in near])
        self.assertAlmostEqual(bite_bonus(grid, HOOK, 0.0), 0.06)
        for n in range(6):
            fish(grid, (3, 0, 1 + n))
        self.assertEqual(bite_bonus(grid, HOOK, 0.0), BITE_MOST)
        self.assertEqual(bite_bonus(Grid(lambda x, y, z: "water"), HOOK, 0.0), 0.0)

    def test_the_bonus_helps_only_while_the_water_has_stock(self):
        with patch("backend.survival.nature.roll", lambda *args: 0.05):
            self.assertFalse(nature.catches("1", HOOK, 0.0, 0))
            self.assertFalse(nature.catches("1", HOOK, 0.0, 0, 0.1))
            self.assertTrue(nature.catches("1", HOOK, 0.0, 1, 0.0))
        with patch("backend.survival.nature.roll", lambda *args: 0.2):
            self.assertFalse(nature.catches("1", HOOK, 0.0, 1))  # 0.9 / 12 = 0.075
            self.assertTrue(nature.catches("1", HOOK, 0.0, 1, 0.14))

    def test_a_catch_shows_at_the_nearest_fish_which_leaps_at_the_hook_and_swims_on(self):
        grid = lake()
        nearest, other = fish(grid, (5, 0, 0)), fish(grid, (8, 0, 2))
        show_catch(grid, HOOK, 40.0)
        leapt = grid.herd.get(nearest["id"])
        self.assertEqual((cell_of(leapt), leapt["state"]["caught_at"], leapt["state"]["path"][-1]["at"]),
                         (HOOK, 40.0, 40.3))
        self.assertEqual(leapt["next_at"], 50.0)
        self.assertNotIn("caught_at", grid.herd.get(other["id"])["state"])
        show_catch(lake(), HOOK, 40.0)  # no fish near: nothing happens

    def test_a_fishing_step_that_lands_a_fish_shows_the_catch(self):
        grid = lake()
        swimmer = fish(grid, (5, 0, 0))
        state = pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            step = {"kind": "fish", "started_at": 10.0, "ends_at": 30.0, "target": {"x": 3, "y": 0, "z": 0}}
            event = finish_step(step, state, grid, 30.0)
        self.assertEqual(event, ("fish", "Pip caught a fish."))
        self.assertEqual(state["inventory"], {"raw_fish": 1})
        self.assertEqual(grid.herd.get(swimmer["id"])["state"]["caught_at"], 30.0)


if __name__ == "__main__":
    unittest.main()

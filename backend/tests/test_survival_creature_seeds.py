import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.actions import ActionContext
from backend.survival.creatures.hunting import prey
from backend.survival.creatures.seeds import MARKER, SPROUT, local_kind
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.renewal import GROWERS, create_growth_table, renew, scheduled
from backend.survival.situation import Situation
from backend.survival.steps import finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = 3600.0


def field():
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    db = sqlite3.connect(":memory:")
    create_growth_table(db)
    create_memory_tables(db)
    create_creature_tables(db)
    grid.herd = Herd(db)
    return ActionContext(grid=grid, clock_at=lambda at: {"time_scale": 1.0}, planner=lambda *args: [], events=[], db=db)


def pet(inventory=None):
    return {"name": "Pip", "world_seed": "7", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
            "inventory": dict(inventory or {}), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}


def plant(ctx, state, cell=(2, 1, 0)):
    running = start_step({"kind": "plant", "target": list(cell), "item": "creature_seed"}, state, ctx.grid, 0.0)
    finish_step(running, state, ctx.grid, running["ends_at"])


class SeedTests(unittest.TestCase):
    def test_one_in_sixty_tall_grass_or_leaves_gives_a_creature_seed(self):
        for block in ("tall_grass", "leaves", "birch_leaves", "spruce_leaves"):
            found = sum("creature_seed" in nature.chance_drops("5", (x, 1, z), block) for x in range(60) for z in range(60))
            self.assertTrue(30 <= found <= 90, (block, found))  # 60 expected

    def test_it_is_planted_on_grass_only(self):
        ctx, state = field(), pet({"creature_seed": 2})
        plant(ctx, state)
        self.assertEqual((ctx.grid.material(2, 1, 0), state["inventory"]), (SPROUT, {"creature_seed": 1}))
        ctx.grid.put(0, 0, 2, "farmland")
        with self.assertRaisesRegex(ValueError, "needs grass"):
            start_step({"kind": "plant", "target": [0, 1, 2], "item": "creature_seed"}, state, ctx.grid, 0.0)


class GrowthTests(unittest.TestCase):
    def test_a_game_day_later_the_sprout_is_a_tame_local_animal(self):
        ctx, state = field(), pet({"creature_seed": 1})
        plant(ctx, state)
        renew(state, ctx, 10.0)
        self.assertEqual(scheduled(ctx.db), [((2, 1, 0), MARKER, 10.0 + DAY)])
        renew(state, ctx, 10.0 + DAY)
        self.assertEqual(ctx.grid.material(2, 1, 0), "air")
        (animal,) = ctx.grid.herd.near(2, 0, 4)
        kind = local_kind("7", (2, 1, 0))
        self.assertIn(kind.name, ("rabbit", "chicken", "sheep", "cow"))  # a meadow's animals
        self.assertEqual((animal["kind"], animal["health"], (animal["x"], animal["y"], animal["z"])),
                         (kind.name, kind.health, (2.0, 1.0, 0.0)))
        self.assertTrue(animal["state"]["tame"])
        self.assertEqual(animal["state"]["home"], [2, 1, 0])
        self.assertEqual(ctx.events[-1][1:], ("grow", f"A creature seed grew into a {kind.name}."))
        self.assertEqual(scheduled(ctx.db), [])
        self.assertIn(SPROUT, GROWERS)

    def test_it_waits_while_the_land_is_full_and_a_mined_sprout_grows_nothing(self):
        ctx, state = field(), pet({"creature_seed": 2})
        for number in range(24):
            ctx.grid.herd.add("rabbit", (10 + number % 6, 1, 10 + number // 6), 3.0, 0.0, 1e9, {})
        plant(ctx, state)
        renew(state, ctx, 0.0)
        renew(state, ctx, DAY)
        self.assertEqual(ctx.grid.material(2, 1, 0), SPROUT)
        self.assertEqual(scheduled(ctx.db), [((2, 1, 0), MARKER, DAY + 600.0)])
        other = field()
        plant(other, state, (3, 1, 0))
        renew(state, other, 0.0)
        other.grid.put(3, 1, 0, "air")  # mined: its seed back in Mimo's arms, nothing to grow
        renew(state, other, DAY)
        self.assertEqual(other.grid.herd.near(3, 0, 4), [])

    def test_mimo_never_hunts_an_animal_it_grew(self):
        ctx = field()
        tame = ctx.grid.herd.add("cow", (3, 1, 0), 10.0, 0.0, 1e9, {"tame": True})
        wild = ctx.grid.herd.add("cow", (6, 1, 0), 10.0, 0.0, 1e9, {})
        s = Situation(pet(), ctx.grid, {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1},
                      0.0, ctx.db)
        with patch("backend.survival.creatures.hunting.near_failure", lambda state, cell: False):
            self.assertEqual([creature["id"] for creature in prey(s)], [wild["id"]])
        self.assertNotEqual(tame["id"], wild["id"])


if __name__ == "__main__":
    unittest.main()

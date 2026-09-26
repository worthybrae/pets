"""The Making final fix wave's route check (MIMO_SLOW_TESTS=1): a pet whose home lies out of sight of any clay
gets its workshop's kiln on its own.

The final review ran six fresh worlds for 100 game days and no pet ever finished "A workshop": clay was looked
for only within sight, so a home out of sight of a shore never got its kiln, and what little clay turned up was
thrown away, built into walls or put in the chest for good. This starts from a hatched world (random.Random(55):
Hazel's, whose nearest dry clay is a shore about 62 blocks from its spawn, none within 30), a home built at the
spawn by hand, iron tools and the workshop for its goal, and lets the real brain and the rules picker (no Jev,
no model) run the tick for up to ten game days: the kiln is in its place in the workshop by then (about half a
game day, measured).
"""

import math
import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.services.worldgen import SEA_LEVEL, surface_material, swamp_pool, terrain_height
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.goals import adopt_goal
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import finish_structure, know, set_home, structures
from backend.survival.registry import LifeRegistry
from backend.survival.structures import blueprint_of, start
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.no_model import no_model

BORN = 1_000_000.0
SCALE = 60.0  # a game day is 60 ticks, a game minute each
SEED = 55
DAYS = 10
KIT = {"iron_pickaxe": 1, "iron_axe": 1, "iron_sword": 1, "cobblestone": 64, "planks": 32, "oak_log": 12, "sticks": 8,
       "coal": 16, "iron_ingot": 6, "bread": 12, "cooked_beef": 8}


def dry_clay(seed: str, x0: int, z0: int, reach: int) -> list[float]:
    """How far each dry clay column (not a lake bed or a swamp pool) within `reach` lies from (x0, z0)."""
    found = []
    for x in range(x0 - reach, x0 + reach + 1):
        for z in range(z0 - reach, z0 + reach + 1):
            distance = math.hypot(x - x0, z - z0)
            if distance <= reach and surface_material(x, z, seed) == "clay" and \
                    terrain_height(x, z, seed) >= SEA_LEVEL and not swamp_pool(x, z, seed):
                found.append(distance)
    return sorted(found)


@unittest.skipUnless(os.environ.get("MIMO_SLOW_TESTS"), "a slow run: set MIMO_SLOW_TESTS=1")
class RouteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(SEED), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def settle_in(self):
        """A home built at the spawn, iron tools and the workshop for its goal; the home's anchor."""
        with self.world.transaction() as db:
            state = read_state(db)
            grid = world_grid(db, state["world_seed"])
            x, z = self.life["spawn_x"], self.life["spawn_z"]
            center = (x, terrain_height(x, z, state["world_seed"]) + 1, z)
            site = find_site(grid, center, (3, 3), ("north", "east", "south", "west"), "flat")
            home = shelter(site, Style("flat", "cobblestone", "planks", "none", (site.side,)), "a home")
            for planned in home.parts("floor", "wall", "roof"):
                grid.put(*planned.cell, "cobblestone")
            grid.put(*home.one("door"), "door")
            finish_structure(db, start(db, grid, home, BORN), BORN)
            set_home(db, home.anchor, BORN)
            for goal in ("first_shelter", "iron_tools"):
                know(db, goal, "goal", BORN)
            state["position"] = dict(zip("xyz", map(float, home.anchor)))
            state["inventory"] = dict(KIT)
            adopt_goal(state, "workshop", "rules", "A workshop, with a kiln!", BORN)
            write_state(db, state)
        return home.anchor

    def kiln_in(self) -> bool:
        with self.world.connect() as db:
            workshops = [row for row in structures(db) if row["kind"] == "workshop"]
            if not workshops:
                return False
            kiln = next(planned.cell for planned in blueprint_of(workshops[-1]).cells if planned.block == "kiln")
            return world_grid(db, read_state(db)["world_seed"]).material(*kiln) == "kiln"

    def test_a_home_with_clay_sixty_blocks_away_gets_its_workshops_kiln_within_ten_game_days(self):
        home = self.settle_in()
        clay = dry_clay(self.life["seed"], home[0], home[2], 80)
        self.assertTrue(clay and clay[0] > 30, clay[:3])  # no clay in sight of home...
        self.assertLess(clay[0], 70)  # ...but a shore of it about 60 blocks off
        chooser = Chooser(env={}, http=no_model(self), executor=InlineExecutor(), rng=random.Random(SEED), scale=SCALE)
        day = None
        for second in range(1, DAYS * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
            if second % 5 == 0 and self.kiln_in():
                day = second / 60
                break
        self.assertIsNotNone(day, f"no kiln in {DAYS} game days")
        dug = [event for event in self.world.events(5000) if event["kind"] == "purpose"
               and "gather materials, toward a workshop" in event["text"]]
        self.assertTrue(dug)  # it went for the clay itself


if __name__ == "__main__":
    unittest.main()

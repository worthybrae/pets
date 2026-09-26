import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.services.blocks import is_solid
from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.goals import ask_for_goal
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import known, places
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0  # a game day is 60 real seconds, as in the days tests
DAY = 60  # ticks in a game day at that pace


class ExpeditionRunTests(unittest.TestCase):
    """L4b, headless: the days tests' pet goes on an expedition and comes home, in the real world."""

    def run_life(self, hatch_seed, chooser_seed, days, nudge_at=None):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(hatch_seed), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(chooser_seed), scale=SCALE)
            for second in range(1, days * DAY + 1):
                state = tick_life(registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
                self.assertIsNone(state["died_at"], state["cause"])
                if second == nudge_at:
                    self.nudge(world, BORN + second)
                chooser.poll(registry, BORN + second)
            with world.connect() as db:
                state = read_state(db)
                grid = world_grid(db, state["world_seed"])
                outposts = places(db, ("outpost",))
                roofs = [grid.material(place["x"], place["y"] + 1, place["z"]) for place in outposts]
                lessons = known(db, "lesson")
            return world.events(5000), outposts, roofs, lessons

    def nudge(self, world, at):
        """Early on day 2, with home built: restless, fed, rested and packed; a goal choice is asked for."""
        with world.transaction() as db:
            state = read_state(db)
            state["brain"]["curiosity"]["value"] = 90.0
            state["vitals"].update(hunger=100.0, energy=100.0, warmth=100.0, health=100.0)
            for item, count in (("bread", 4), ("torch", 4), ("campfire", 1)):
                state["inventory"][item] = state["inventory"].get(item, 0) + count
            ask_for_goal(state, "test", at)
            write_state(db, state)

    def test_a_restless_pet_packs_sets_out_camps_and_comes_home(self):
        events, outposts, roofs, lessons = self.run_life(8, 8, 3, nudge_at=DAY + 5)
        texts = [event["text"] for event in reversed(events)]  # oldest first
        name = "Clover"
        steps = [f"{name} set out on an expedition", f"{name} dug in for the night and made a camp.",
                 f"{name} came home from its expedition", f"{name} reached a goal: an expedition."]
        found = [next((index for index, text in enumerate(texts) if text.startswith(step)), None) for step in steps]
        self.assertNotIn(None, found, [text for text in texts if "expedition" in text or "camp" in text])
        self.assertEqual(found, sorted(found))  # in that order
        self.assertGreaterEqual(len(outposts), 1)
        self.assertFalse(any(is_solid(roof) for roof in roofs))  # it took the roof off and climbed out
        self.assertIn("1 night camped", next(text for text in texts if text.startswith(steps[2])))
        self.assertTrue(lessons)

    @unittest.skipUnless(os.environ.get("MIMO_SLOW_TESTS"), "a slow run: set MIMO_SLOW_TESTS=1")
    def test_left_alone_a_curious_pet_goes_on_an_expedition_of_its_own(self):
        """Left alone, the days tests' pet sets out on an expedition of its own and comes home. The
        spec gives no day count; the plan picked 7 game days, when it set out on day 4.4. The L4b final
        fix wave's I5 (a sight out of reach gives way to a new one of its kind, so it studies more near
        home and its curiosity climbs later) moved its set-out to about day 6.4 and its homecoming past
        day 7, so it runs 8 game days now (the controller's ruling): it must still set out and come home
        on its own."""
        events, outposts, _, _ = self.run_life(8, 8, 8)  # 8 game days (was 7): see the docstring
        texts = [event["text"] for event in events]
        self.assertTrue(any("set out on an expedition" in text for text in texts))
        self.assertTrue(any("came home from its expedition" in text for text in texts))
        self.assertGreaterEqual(len(outposts), 1)


if __name__ == "__main__":
    unittest.main()

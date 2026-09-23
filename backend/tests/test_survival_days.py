import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import places, structures
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import notable
from backend.survival.structures import blueprint_of
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld

BORN = 1_000_000.0
SCALE = 60.0  # a game day is 60 real seconds, as in the manual check
FOODS = ("berries", "brown_mushroom", "red_mushroom", "carrot", "bread", "raw_fish", "cooked_fish", "apple")


class LivingDaysTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def test_left_alone_mimo_finds_real_food_and_lives_through_three_game_days(self):
        chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
        lowest = 100.0
        for second in range(1, 3 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
            lowest = min(lowest, state["vitals"]["hunger"])
        events = self.world.events(2000)
        eaten = [event["text"] for event in events if event["kind"] == "ate"]
        self.assertTrue(eaten, "Mimo never ate")
        self.assertGreater(lowest, 15.0)
        self.assertTrue(any(state["inventory"].get(food) for food in FOODS) or len(eaten) >= 3)
        self.assertNotIn("ate", [event["kind"] for event in notable(events)])

    def test_left_alone_mimo_builds_a_home_before_its_second_night_and_lives_in_it(self):
        chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
        in_bed, lit = set(), set()
        for second in range(1, 4 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
            if second % 60 == 50:  # deep in the night
                night = second // 60 + 1
                action = state["action"] or {}
                if action.get("kind") == "sleep" and action.get("bed"):
                    in_bed.add(night)
                with self.world.connect() as db:
                    grid = world_grid(db, state["world_seed"])
                    for shelter in structures(db, ("shelter",)):
                        if any(grid.material(*cell.cell) == "torch" for cell in blueprint_of(shelter).parts("torch")):
                            lit.add(night)
        built = [event for event in self.world.events(5000) if event["kind"] == "built" and "moved in" in event["text"]]
        self.assertEqual(len(built), 1)
        self.assertLess(built[0]["at"], BORN + 60 + 40)  # before the second night falls
        self.assertIn("built", [event["kind"] for event in notable(self.world.events(5000))])
        with self.world.connect() as db:
            home = places(db, ("home",))[0]
            shelter = blueprint_of(structures(db, ("shelter",))[0])
        self.assertEqual((home["note"], (home["x"], home["y"], home["z"])), ("built", shelter.anchor))
        self.assertGreaterEqual(len(in_bed), 2)
        self.assertTrue(lit)
        self.assertTrue(any(state.get("chests", {}).values()))


if __name__ == "__main__":
    unittest.main()

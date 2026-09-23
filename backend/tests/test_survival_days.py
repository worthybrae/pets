import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import notable
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


if __name__ == "__main__":
    unittest.main()

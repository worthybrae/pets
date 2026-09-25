import os
import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.brain import BRAIN
from backend.survival.choosing import Chooser, InlineExecutor
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
        in_bed = set()
        for second in range(1, 4 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
            if second % 60 == 50:  # deep in the night
                night = second // 60 + 1
                action = state["action"] or {}
                if action.get("kind") == "sleep" and action.get("bed"):
                    in_bed.add(night)
        built = [event for event in self.world.events(5000) if event["kind"] == "built" and "moved in" in event["text"]]
        self.assertEqual(len(built), 1)
        self.assertLess(built[0]["at"], BORN + 60 + 40)  # before the second night falls
        # L4: reached goals are notable too, so "built" may be older than the newest few notable
        # events in snapshot.notable()'s NOTABLE_LIMIT-trimmed highlight window. The world's own
        # notable_events query has no such small trim (it is bounded only by the limit we pass, far
        # more than this short life ever logs), so "built" is found among every notable event.
        self.assertIn("built", [event["kind"] for event in self.world.notable_events(5000)])
        with self.world.connect() as db:
            home = places(db, ("home",))[0]
            shelter = blueprint_of(structures(db, ("shelter",))[0])
        self.assertEqual((home["note"], (home["x"], home["y"], home["z"])), ("built", shelter.anchor))
        self.assertGreaterEqual(len(in_bed), 2)
        # light_up only fires once coal turns up to make torches from (or iron for a lantern), and
        # this pinned seed (8) never finds coal in these four days (confirmed by instrumenting this
        # loop), so there is no honest way to exercise light_up's corner-lighting from here. That
        # deterministic path -- a finished shelter, coal and sticks at dusk, light_up crafts torches
        # and hangs one on each dark corner -- is already covered by test_survival_lighting.py's
        # test_it_makes_torches_puts_one_on_each_dark_corner_and_goes_back_inside. This test only
        # checks what this seed really exercises: a home built early and slept in.
        self.assertTrue(any(state.get("chests", {}).values()))

    def test_left_alone_mimo_hunts_an_animal_and_cooks_its_meat(self):
        chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(8), scale=SCALE)
        for second in range(1, 4 * 60 + 1):
            state = tick_life(self.registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            self.assertIsNone(state["died_at"], state["cause"])
            chooser.poll(self.registry, BORN + second)
        events = self.world.events(5000)
        hunts = [event["text"] for event in events if event["kind"] == "hunt"]
        cooked = [event["text"] for event in events if event["kind"] == "cook"]
        self.assertTrue(hunts, "Mimo never hunted")
        self.assertTrue(any(f"raw {meat}" in text for text in cooked for meat in ("beef", "mutton", "chicken", "rabbit")),
                        cooked)
        self.assertNotIn("hunt", [event["kind"] for event in notable(events)])
        if os.environ.get("MIMO_SLOW_TESTS"):
            # L3 fix round 1, item 1: a spare torch filling Mimo's arms made gather_stone and
            # build_storage beat hunt far more often (30/40 across Chooser seeds 0-39, down from
            # 38/40 before Task 6). Chooser seeds 5-9 alone went from 5/5 hunting and cooking to
            # 2/5; the fix should put it back near 5/5, so at least 4 of 5 is the floor here.
            successes = 0
            for seed in range(5, 10):
                with tempfile.TemporaryDirectory() as root:
                    registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
                    life = hatch(registry, random.Random(8), timestamp=BORN)
                    world = SurvivalWorld(registry.world_path(life))
                    chooser = Chooser(env={}, executor=InlineExecutor(), rng=random.Random(seed), scale=SCALE)
                    for second in range(1, 4 * 60 + 1):
                        seed_state = tick_life(registry, BORN + second, scale=SCALE, mind=BRAIN, action_scale=SCALE)
                        self.assertIsNone(seed_state["died_at"], seed_state["cause"])
                        chooser.poll(registry, BORN + second)
                    seed_events = world.events(5000)
                    seed_hunts = [event["text"] for event in seed_events if event["kind"] == "hunt"]
                    seed_cooked = [event["text"] for event in seed_events if event["kind"] == "cook"]
                    if seed_hunts and any(f"raw {meat}" in text for text in seed_cooked
                                          for meat in ("beef", "mutton", "chicken", "rabbit")):
                        successes += 1
            self.assertGreaterEqual(successes, 4, f"only {successes}/5 Chooser seeds 5-9 hunted and cooked")


if __name__ == "__main__":
    unittest.main()

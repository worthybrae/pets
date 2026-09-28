"""W2: the gate script's W2 parts: the scripted owner's day 2, the upgraded world, the summary's winters and the
W2 criteria read from the lives' summaries."""

import json
import random
import tempfile
import unittest
from pathlib import Path

from backend.scripts.wild_gate import (
    BORN, SCALE, TEACHES_W2, before_w2, check_w2, sample_sky, upgrade, winter_of,
)
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.lessons import claims
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.wild import thing
from backend.survival.world import SurvivalWorld

W2 = ("winter", "cloak", "hearth", "smoking", "rain", "storm", "fog")


def life(condition, seed, **changes):
    found = {"condition": condition, "seed": seed, "died_day": None, "cause": None, "difficulty": "gentle",
             "machines": {"lamp_lever": 40.0}, "model_calls": 0, "errors": [], "ever": {"sick": False},
             "winters": {str(n): {"health_mean": 95.0, "ticks": 600, "freezing": 2, "starving": 0, "cold": 2, "hungry": 10}
                         for n in (1, 2, 3)},
             "winter_food": {"1": 400.0, "2": 380.0, "3": 365.0}, "struck": 0, "strike_home": 30.0,
             "fire_claimed": 0, "clearing_edits": 0, "sky_offset": 0}
    found.update(changes)
    return found


class OwnerTests(unittest.TestCase):
    def test_the_scripted_owners_day_two_teaches_each_w2_lesson(self):
        self.assertEqual([claims(line).taught for line in TEACHES_W2], [(thing(name),) for name in W2])


class UpgradeTests(unittest.TestCase):
    def test_a_world_that_lived_without_w2_gets_spring_on_its_upgrade_day(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))
            with before_w2(True):
                tick_life(registry, BORN + 90, scale=SCALE, mind=BRAIN, action_scale=SCALE)  # to day 2
            self.assertNotIn("sky", world.state())
            upgrade(world)
            tick_life(registry, BORN + 91, scale=SCALE, mind=BRAIN, action_scale=SCALE)
            state = world.state()
            self.assertEqual((state["sky"]["offset"], state["sky"]["season"], state["sky"]["season_day"]), (39, "spring", 0))
            found = {}
            sample_sky(found, state, 91, world)
            self.assertEqual(found.get("winters", {}), {})  # spring: no winter yet
            self.assertIsNone(winter_of({}, state, 91))
            self.assertEqual(winter_of({}, state, (1 + 30) * 60 + 5), 1)  # its first winter: 30 days on


class CheckTests(unittest.TestCase):
    def write(self, lives):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for number, found in enumerate(lives):
            (Path(directory.name) / f"{number}.json").write_text(json.dumps(found))
        return {name: passed for name, passed, _ in check_w2(Path(directory.name), cost=False)}

    def lives(self, **changes):
        gentle = [life("gentle", seed) for seed in range(6)]
        taught = [life("taught", seed, difficulty="wild") for seed in range(6)]
        untaught = [life("untaught", seed, difficulty="wild",
                         winters={str(n): {"health_mean": 70.0, "ticks": 600, "freezing": 30, "starving": 5, "cold": 30,
                                           "hungry": 40} for n in (1, 2, 3)})
                    for seed in range(6)]
        upgraded = [life("upgrade", seed, sky_offset=21, winters={"1": {"health_mean": 90.0, "ticks": 600, "freezing": 0,
                                                                          "starving": 0}}) for seed in range(2)]
        found = gentle + taught + untaught + upgraded
        for index, entry in changes.items():
            condition, seed, key = index.split("__")
            for one in found:
                if one["condition"] == condition and one["seed"] == int(seed):
                    one.update(entry)
        return found

    def test_every_w2_criterion_passes_on_good_lives(self):
        results = self.write(self.lives())
        self.assertTrue(all(results.values()), results)

    def test_each_criterion_can_fail(self):
        winter = {"health_mean": 50.0, "ticks": 600, "freezing": 0, "starving": 0}
        results = self.write(self.lives(gentle__0__cold={"winters": {"1": winter}},
                                        taught__1__near={"strike_home": 12.0, "struck": 2},
                                        taught__2__empty={"winter_food": {"1": 100.0, "2": 100.0, "3": 100.0}},
                                        taught__3__empty={"winter_food": {"1": 100.0, "2": 400.0, "3": 400.0}}))
        failed = {name.split()[0] for name, passed in results.items() if not passed}
        self.assertEqual(failed, {"2", "3", "4", "8"})

    def test_criterion_six_counts_the_cold_minutes_of_the_winters_each_pet_lived(self):
        """Restated by the controller's ruling on the W2 interim report: the cold minutes (warmth under CHILL_BELOW) of
        the winters each pet lived through (alive at the winter's start), untaught at least twice taught's, and some."""
        def six(**changes):
            results = self.write(self.lives(**changes))
            return results[next(name for name in results if name.startswith("6 "))]

        def winters(cold, count=3):
            return {str(n): {"health_mean": 95.0, "ticks": 600, "freezing": 0, "starving": 0, "cold": cold, "hungry": 10}
                    for n in range(1, count + 1)}
        self.assertTrue(six())  # 540 cold minutes against 36
        self.assertFalse(six(**{f"untaught__{seed}__mild": {"winters": winters(3)} for seed in range(6)}))  # 54 < 72
        self.assertTrue(six(**{f"untaught__{seed}__mild": {"winters": winters(4)} for seed in range(6)}))  # 72
        dead = {f"untaught__{seed}__dead": {"died_day": 25.0, "cause": "sickness", "winters": {}} for seed in range(4)}
        self.assertFalse(six(**dead, **{f"untaught__{seed}__one": {"winters": winters(10, 1)} for seed in (4, 5)}))
        self.assertFalse(six(**{f"{condition}__{seed}__warm": {"winters": winters(0)} for condition in ("untaught", "taught")
                                for seed in range(6)}))  # none at all


if __name__ == "__main__":
    unittest.main()

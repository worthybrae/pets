import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from backend.survival.care import CareRefused, care_remaining, give_care
from backend.survival.world import LifeOver, SurvivalWorld, WorldBehind, new_survival_state, read_state, write_state

NOON = datetime(2026, 9, 23, 12, tzinfo=timezone.utc).timestamp()
DAY = 86400.0


class CareTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.world = SurvivalWorld.create(Path(self.directory.name) / "2.sqlite3", new_survival_state(
            name="Pip", seed="1", spawn={"x": 3000, "y": 5, "z": 0}, born_at=NOON - 3600, traits={}))
        self.set_vitals(hunger=40.0, health=90.0)
        self.set_state(last_tick_at=NOON)

    def tearDown(self):
        self.directory.cleanup()

    def set_vitals(self, **vitals):
        with self.world.transaction() as db:
            state = read_state(db)
            state["vitals"].update(vitals)
            write_state(db, state)

    def set_state(self, **changes):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(changes)
            write_state(db, state)

    def test_a_fresh_pet_has_one_snack_and_one_bandage_today(self):
        self.assertEqual(care_remaining(self.world.state(), NOON), {"snack": 1, "bandage": 1})

    def test_a_snack_adds_thirty_hunger_once_per_day(self):
        result = give_care(self.world, "snack", NOON)
        self.assertEqual(result["vitals"]["hunger"], 70.0)
        self.assertEqual(result["remaining"], {"snack": 0, "bandage": 1})
        self.assertEqual(self.world.events()[0]["text"], "You gave Pip a snack.")
        self.assertEqual(self.world.state()["last_thought"], "Yum! Thank you.")
        self.set_state(last_tick_at=NOON + 3600)
        with self.assertRaises(CareRefused):
            give_care(self.world, "snack", NOON + 3600)

    def test_a_bandage_adds_twenty_five_health_capped_at_100(self):
        result = give_care(self.world, "bandage", NOON)
        self.assertEqual(result["vitals"]["health"], 100.0)
        self.assertEqual(result["remaining"], {"snack": 1, "bandage": 0})

    def test_the_allowance_resets_at_the_next_utc_day(self):
        give_care(self.world, "snack", NOON)
        self.assertEqual(care_remaining(self.world.state(), NOON + DAY)["snack"], 1)
        self.set_state(last_tick_at=NOON + DAY)
        result = give_care(self.world, "snack", NOON + DAY)
        self.assertEqual(result["vitals"]["hunger"], 100.0)

    def test_a_dead_pet_cannot_receive_care(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(died_at=NOON - 60, cause="starvation", status="dead")
            write_state(db, state)
        with self.assertRaises(LifeOver):
            give_care(self.world, "snack", NOON)

    def test_unknown_care_is_rejected(self):
        with self.assertRaises(ValueError):
            give_care(self.world, "massage", NOON)

    def test_care_is_refused_while_the_world_is_behind(self):
        self.set_state(last_tick_at=NOON - 20)
        with self.assertRaises(WorldBehind):
            give_care(self.world, "snack", NOON)


if __name__ == "__main__":
    unittest.main()

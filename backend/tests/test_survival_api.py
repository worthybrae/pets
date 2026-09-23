import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.lives import get_life, get_life_blocks, hatch_egg, list_lives
from backend.api.mimo import (
    CareRequest, OwnerAction, act_with_mimo, care_for_mimo, get_mimo, get_mimo_blocks, greet_mimo,
)
from backend.services.live_mimo import MimoStore
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state


class SurvivalApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        legacy = MimoStore(root / "mimo.sqlite3")
        legacy.put_block(80, 20, 0, "stone")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def status_of(self, call, *args, **kwargs):
        with self.assertRaises(HTTPException) as caught:
            call(*args, **kwargs)
        return caught.exception.status_code

    def active_world(self):
        registry = LifeRegistry()
        return SurvivalWorld(registry.world_path(registry.active_life()))

    def test_before_the_first_hatch_the_egg_waits_and_mimo_is_retired(self):
        first = get_mimo()
        self.assertEqual(first["phase"], "egg")
        self.assertEqual(len(first["egg"]["attributes"]), 5)
        self.assertEqual(get_mimo()["egg"], first["egg"])
        last = first["last_life"]
        self.assertEqual((last["id"], last["kind"], last["cause"]), (1, "legacy", "retired"))
        self.assertNotIn("db_path", last)
        self.assertEqual(last["days"], 1)
        self.assertEqual(last["notable_events"][0]["kind"], "birth")

    def test_hatching_starts_a_life_that_mimo_reports(self):
        egg = get_mimo()["egg"]
        hatched = hatch_egg()
        self.assertEqual(hatched["life"]["id"], 2)
        self.assertEqual(hatched["life"]["egg"], egg)
        state = get_mimo()
        self.assertEqual(state["phase"], "alive")
        for field in ("life", "clock", "vitals", "position", "status", "last_thought", "events", "inventory",
                      "recipes", "blocks_seq", "care", "server_time"):
            self.assertIn(field, state)
        self.assertEqual(state["clock"]["day_number"], 1)
        self.assertEqual(state["care"], {"snack": 1, "bandage": 1})
        self.assertNotIn("plans", state)
        self.assertEqual(self.status_of(hatch_egg), 409)

    def test_care_hello_and_crafting_help_reach_the_active_life(self):
        hatch_egg()
        self.assertEqual(care_for_mimo(CareRequest(kind="snack"))["remaining"]["snack"], 0)
        self.assertEqual(self.status_of(care_for_mimo, CareRequest(kind="snack")), 409)
        self.assertIn("mood", greet_mimo())
        self.assertEqual(self.status_of(act_with_mimo, OwnerAction(action="craft", item="planks")), 400)
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            state["inventory"] = {"oak_log": 1}
            write_state(db, state)
        self.assertEqual(act_with_mimo(OwnerAction(action="craft", item="planks"))["inventory"], {"planks": 4})

    def test_without_a_live_pet_care_hello_and_blocks_are_refused(self):
        self.assertEqual(self.status_of(care_for_mimo, CareRequest(kind="bandage")), 409)
        self.assertEqual(self.status_of(greet_mimo), 409)
        self.assertEqual(self.status_of(get_mimo_blocks, since=0, limit=5000), 409)

    def test_block_changes_for_the_active_life_and_the_archives(self):
        hatch_egg()
        position = get_mimo()["position"]
        self.active_world().put_block(round(position["x"]) + 1, round(position["y"]), round(position["z"]), "lantern")
        active = get_mimo_blocks(since=0, limit=5000)
        self.assertEqual([change["material"] for change in active["changes"]], ["lantern"])
        self.assertEqual(get_life_blocks(2, since=0, limit=5000), active)
        self.assertEqual(get_life_blocks(1, since=0, limit=5000)["changes"],
                         [{"x": 80, "y": 20, "z": 0, "material": "stone"}])
        self.assertEqual(self.status_of(get_life_blocks, 99, since=0, limit=5000), 404)

    def test_lives_list_newest_first_with_both_state_shapes(self):
        hatch_egg()
        self.assertEqual([life["id"] for life in list_lives()], [2, 1])
        legacy = get_life(1)
        self.assertEqual(legacy["life"]["kind"], "legacy")
        for field in ("plans", "currentIndex", "progress", "world_seed", "blocks_seq"):
            self.assertIn(field, legacy["state"])
        survival = get_life(2)
        self.assertEqual(survival["life"]["kind"], "survival")
        self.assertIn("vitals", survival["state"])
        self.assertEqual(self.status_of(get_life, 99), 404)

    def test_after_death_the_memorial_data_comes_with_a_new_egg(self):
        born = hatch_egg()["life"]["born_at"]
        tick_life(LifeRegistry(), born + 20_000, scale=1)
        memorial = get_mimo()
        self.assertEqual(memorial["phase"], "egg")
        last = memorial["last_life"]
        self.assertEqual((last["id"], last["cause"], last["days"]), (2, "starvation", 3))
        self.assertEqual(last["notable_events"][0]["kind"], "death")
        self.assertEqual(get_life(2)["state"]["clock"]["day_number"], 3)
        self.assertEqual(self.status_of(care_for_mimo, CareRequest(kind="snack")), 409)

    def test_a_missing_world_file_answers_503(self):
        hatch_egg()
        registry = LifeRegistry()
        registry.world_path(registry.active_life()).unlink()
        self.assertEqual(self.status_of(get_mimo), 503)
        self.assertEqual(self.status_of(get_life, 2), 503)

    def test_an_unwritable_data_dir_answers_503(self):
        blocker = Path(self.directory.name) / "not-a-dir"
        blocker.write_text("x")
        with patch.dict(os.environ, {"MIMO_DATA_DIR": str(blocker / "data")}):
            self.assertEqual(self.status_of(get_mimo), 503)


if __name__ == "__main__":
    unittest.main()

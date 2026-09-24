import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.lives import get_life, get_life_blocks, hatch_egg, list_lives
from backend.api.mimo import (
    CareRequest, OwnerAction, act_with_mimo, care_for_mimo, get_mimo, get_mimo_blocks, greet_mimo,
)
from backend.services.live_mimo import MimoStore
from backend.survival.memory import add_structure, mark_explored, patch_of, remember
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import built_view, notable, recent_decays, replayable, survival_view
from backend.survival.tick import tick_life
from backend.survival.triggers import new_brain
from backend.survival.world import SurvivalWorld, log_event, new_survival_state, read_state, write_state


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
        self.assertEqual(state["decays"], [])
        self.assertEqual((state["structures"], state["chests"]), ([], {}))
        self.assertEqual((state["explored"], state["landmarks"]), ([], []))
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

    def test_get_mimo_returns_quickly_while_another_connection_holds_the_world_lock(self):
        hatch_egg()
        world_path = self.active_world().path
        holding = threading.Event()
        released = threading.Event()

        def hold_write_lock():
            connection = sqlite3.connect(world_path, timeout=10)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("BEGIN IMMEDIATE")
            holding.set()
            released.wait(2)
            connection.rollback()
            connection.close()

        thread = threading.Thread(target=hold_write_lock)
        thread.start()
        try:
            self.assertTrue(holding.wait(2))
            start = time.monotonic()
            state = get_mimo()
            elapsed = time.monotonic() - start
        finally:
            released.set()
            thread.join()
        self.assertEqual(state["phase"], "alive")
        self.assertLess(elapsed, 0.5)

    def test_get_routes_never_modify_the_world_file(self):
        hatch_egg()
        world_path = self.active_world().path
        before = hashlib.sha256(world_path.read_bytes()).hexdigest()
        get_mimo()
        get_mimo_blocks(since=0, limit=5000)
        get_mimo()
        after = hashlib.sha256(world_path.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_the_egg_screen_still_loads_when_the_last_lifes_world_cannot_be_read(self):
        born = hatch_egg()["life"]["born_at"]
        tick_life(LifeRegistry(), born + 20_000, scale=1)
        registry = LifeRegistry()
        registry.world_path(registry.get(2)).unlink()
        result = get_mimo()
        self.assertEqual(result["phase"], "egg")
        self.assertEqual(result["last_life"]["id"], 2)
        self.assertNotIn("notable_events", result["last_life"])

    def test_get_mimo_asks_the_registry_for_the_active_life_only_once(self):
        hatch_egg()
        registry = LifeRegistry()
        with patch("backend.api.mimo.open_registry", return_value=registry), \
             patch.object(LifeRegistry, "active_life", wraps=registry.active_life) as spy:
            get_mimo()
        self.assertEqual(spy.call_count, 1)

    def test_a_missing_worlds_503_detail_has_no_filesystem_path(self):
        hatch_egg()
        registry = LifeRegistry()
        registry.world_path(registry.active_life()).unlink()
        with self.assertRaises(HTTPException) as caught:
            get_mimo()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("/", caught.exception.detail)
        with self.assertRaises(HTTPException) as caught:
            get_life(2)
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("/", caught.exception.detail)

    def test_hatch_error_detail_has_no_filesystem_path(self):
        registry = LifeRegistry()
        with patch("backend.api.lives.SurvivalWorld") as mock_world:
            mock_world.side_effect = OSError("/absolute/path/to/world/data.sqlite3: permission denied")
            with self.assertRaises(HTTPException) as caught:
                hatch_egg()
            self.assertEqual(caught.exception.status_code, 503)
            self.assertNotIn("/", caught.exception.detail)
            self.assertEqual(caught.exception.detail, "The new world could not be created.")

    def test_the_current_step_and_recent_steps_are_streamed(self):
        hatch_egg()
        fresh = get_mimo()
        self.assertEqual((fresh["action"], fresh["recent_actions"]), (None, []))
        path = [{"x": 1, "y": 9, "z": 2, "at": 10.0}, {"x": 2, "y": 9, "z": 2, "at": 10.9, "swim": True}]
        finished = {"kind": "mine", "started_at": 5.0, "target": {"x": 3, "y": 9, "z": 2}, "block": "oak_log",
                    "ended_at": 7.0, "result": "done"}
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            state.update(action={"kind": "walk", "started_at": 10.0, "ends_at": 10.9, "path": path,
                                 "target": {"x": 2, "y": 9, "z": 2}, "reach": 0.0, "reached": True, "segments": 0},
                         recent_actions=[finished])
            write_state(db, state)
        mimo = get_mimo()
        self.assertEqual(mimo["action"], {"kind": "walk", "started_at": 10.0, "ends_at": 10.9, "path": path,
                                          "target": {"x": 2, "y": 9, "z": 2}})
        self.assertEqual(mimo["recent_actions"], [finished])
        self.assertIn("server_time", mimo)

    def test_the_brain_is_streamed(self):
        hatch_egg()
        fresh = get_mimo()
        self.assertEqual((fresh["purpose"], fresh["reflex"], fresh["picker"], fresh["choosing"]), (None, None, None, True))
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            state["brain"] = {**new_brain(state["born_at"]), "purpose": "gather_wood", "picker": "jev",
                              "reflex": "head_home", "pending": None}
            write_state(db, state)
        mimo = get_mimo()
        self.assertEqual((mimo["purpose"], mimo["reflex"], mimo["picker"], mimo["choosing"]),
                         ("gather_wood", "head_home", "jev", False))

    def test_only_replayable_paths_are_streamed(self):
        path = [{"x": 1, "y": 9, "z": 2, "at": 10.0}, {"x": 2, "y": 9, "z": 2, "at": 10.9}]
        old = {"kind": "walk", "started_at": 10.0, "ended_at": 10.9, "result": "done", "path": path}
        new = {**old, "started_at": 30.0, "ended_at": 30.9}
        self.assertEqual(replayable([old, new], 35.0), [{k: v for k, v in old.items() if k != "path"}, new])
        self.assertIn("path", old)

    def test_what_mimo_built_and_its_chests_are_streamed(self):
        hatch_egg()
        world = self.active_world()
        with world.transaction() as db:
            add_structure(db, "shelter", "Pip's Snug Cottage", (5, 6, 7), 10.0, {}, [((5, 6, 7), "passage", "air")])
            state = read_state(db)
            state["chests"] = {"6,6,8": {"dirt": 9}}
            write_state(db, state)
        state = get_mimo()
        self.assertEqual(state["structures"], [{"id": 1, "kind": "shelter", "name": "Pip's Snug Cottage",
                                                "status": "building", "x": 5, "y": 6, "z": 7}])
        self.assertEqual(state["chests"], {"6,6,8": {"dirt": 9}})

    def explore_around_mimo(self, reach, visits=1, at=None):
        """Mark every patch within `reach` patches of Mimo explored `visits` times, after moving
        Mimo to `at` ((x, z)) when given."""
        world = self.active_world()
        with world.transaction() as db:
            state = read_state(db)
            if at is not None:
                state["position"] = {**state["position"], "x": float(at[0]), "z": float(at[1])}
                write_state(db, state)
            position = state["position"]
            rx, rz = patch_of(round(position["x"]), round(position["z"]))
            patches = [(rx + dx, rz + dz) for dx in range(-reach, reach + 1) for dz in range(-reach, reach + 1)]
            mark_explored(db, patches, 10.0)
            db.execute("UPDATE memory_explored SET visits = ?", (visits,))
        return world, rx, rz

    def test_the_ground_mimo_explored_around_it_and_its_landmarks_are_streamed(self):
        hatch_egg()
        world, rx, rz = self.explore_around_mimo(1)
        with world.transaction() as db:
            mark_explored(db, [(rx, rz), (rx + 12, rz - 12), (rx + 13, rz)], 20.0)  # the last is too far
            position = read_state(db)["position"]
            x, y, z = round(position["x"]), round(position["y"]), round(position["z"])
            remember(db, "home", (x + 3, y, z), 5.0)
            remember(db, "farm", (x - 20, y, z + 4), 6.0)
            remember(db, "farm", (x + 90, y, z), 7.0)  # a farther farm is left out
            remember(db, "ore", (x, y - 5, z), 8.0, "coal_ore")
        state = get_mimo()
        self.assertEqual(state["explored"], sorted([[rx + dx, rz + dz, 2 if (dx, dz) == (0, 0) else 1]
                                                    for dx in (-1, 0, 1) for dz in (-1, 0, 1)] + [[rx + 12, rz - 12, 1]]))
        self.assertEqual(state["landmarks"], [{"kind": "home", "x": x + 3, "y": y, "z": z},
                                              {"kind": "farm", "x": x - 20, "y": y, "z": z + 4}])

    def test_the_explored_ground_stays_small_and_is_read_without_writing(self):
        hatch_egg()
        # The worst case for size: a life as far out as spawns go (6,000 blocks, so every patch
        # coordinate has four characters with its sign) that saw all 625 patches many times.
        world, _, _ = self.explore_around_mimo(20, visits=4321, at=(-5999, -5999))
        before = {suffix: hashlib.sha256(Path(f"{world.path}{suffix}").read_bytes()).hexdigest()
                  for suffix in ("", "-wal") if Path(f"{world.path}{suffix}").exists()}
        explored = get_mimo()["explored"]
        after = {suffix: hashlib.sha256(Path(f"{world.path}{suffix}").read_bytes()).hexdigest()
                 for suffix in ("", "-wal") if Path(f"{world.path}{suffix}").exists()}
        self.assertEqual(before, after)
        self.assertEqual(len(explored), 625)  # 12 patches (96 blocks) each way
        self.assertEqual({visits for _, _, visits in explored}, {9})  # the viewer only needs "seen"
        largest = 625 * len("[-762,-762,9]") + 624 + 2  # entries, commas, brackets
        self.assertLessEqual(len(json.dumps(explored, separators=(",", ":"))), largest)  # as the API sends it
        self.assertLess(largest, 9_000)

    def test_an_archived_world_from_before_m5_built_nothing(self):
        """Fix wave fold-in: a pre-M5 world opened read-only (an archive) has no structures table,
        and built_view falls back to an empty list instead of failing the whole view."""
        path = Path(self.directory.name) / "before-m5.sqlite3"
        state = new_survival_state(name="Pip", seed="1", spawn={"x": 0, "y": 1, "z": 0}, born_at=10.0, traits={})
        SurvivalWorld.create(path, state)
        db = sqlite3.connect(path)
        with db:
            db.execute("DROP TABLE structure_cells")
            db.execute("DROP TABLE structures")
        db.close()
        archive = SurvivalWorld(path, read_only=True)
        self.assertEqual(built_view(archive), [])
        view = survival_view(archive, 20.0, 1.0)
        self.assertEqual((view["structures"], view["chests"]), ([], {}))
        self.assertEqual(view["explored"], [])
        with archive.connect() as db:  # the read-only view did not add the tables
            self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='structures'").fetchone())

    def test_only_leaves_that_decayed_in_the_last_ten_seconds_are_streamed(self):
        decays = [{"x": 1, "y": 6, "z": 1, "at": 20.0}, {"x": 2, "y": 6, "z": 1, "at": 25.0},
                  {"x": 3, "y": 6, "z": 1, "at": 34.5}]
        self.assertEqual(recent_decays(decays, 35.0), decays[1:])
        self.assertEqual(recent_decays(decays, 100.0), [])

    def test_a_memorial_keeps_its_notable_events_under_a_flood_of_routine_ones(self):
        hatch_egg()
        world = self.active_world()
        with world.transaction() as db:
            log_event(db, time.time(), "found", "Pip spotted iron ore.")
            for index in range(50):
                log_event(db, time.time(), "purpose", f"Pip decided to rest ({index}).")
            state = read_state(db)
            state.update(died_at=time.time(), cause="cold", status="dead")
            write_state(db, state)
        LifeRegistry().mark_dead(LifeRegistry().active_life()["id"], time.time(), "cold")
        detail = get_life(LifeRegistry().list_lives()[0]["id"])
        self.assertEqual([event["kind"] for event in detail["notable_events"]], ["found", "birth"])

    def test_memorials_skip_choices_and_reflexes(self):
        events = [{"kind": kind, "text": kind} for kind in ("purpose", "reflex", "found", "discovered", "trapped")]
        self.assertEqual([event["kind"] for event in notable(events)], ["found", "discovered", "trapped"])



if __name__ == "__main__":
    unittest.main()

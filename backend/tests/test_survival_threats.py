import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.choosing import route_for
from backend.survival.creatures.moves import timed
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.pickers import context_payload
from backend.survival.registry import LifeRegistry
from backend.survival.situation import Situation
from backend.survival.triggers import new_brain
from backend.survival.vitals import START_VITALS
from backend.survival.world import SurvivalWorld, read_state, write_state

NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}


class ModelPayloadTests(unittest.TestCase):
    def test_the_model_is_told_what_threatens_mimo_and_what_it_can_meet_them_with(self):
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        create_creature_tables(db)
        grid.herd = Herd(db)
        grid.herd.add("gloomling", (5, 1, 0), 20.0, 0.0, 0.0, {"chasing": True})
        grid.herd.add("skitter", (0, 1, 10), 12.0, 0.0, 0.0, {})
        grid.herd.add("cow", (2, 1, 0), 10.0, 0.0, 0.0, {})
        state = {"name": "Pip", "world_seed": "5", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                 "inventory": {"stone_sword": 1, "bow": 1, "arrow": 5, "leather_cap": 1}, "vitals": dict(START_VITALS),
                 "traits": {}, "brain": new_brain(0.0), "hurt_by": "skitter"}
        payload = context_payload(Situation(state, grid, NIGHT, 10.0, db), [])
        self.assertEqual(payload["threats"], [{"kind": "gloomling", "distance": 5, "after_mimo": True},
                                              {"kind": "skitter", "distance": 10, "after_mimo": False}])
        self.assertEqual(payload["defense"], {"indoors": False, "sword": "stone_sword", "arrows": 5,
                                              "armor": ["leather_cap"], "last_hurt_by": "skitter"})

    def test_the_alarm_reaches_jev_at_once_even_right_after_another_call(self):
        brain = new_brain(0.0)
        brain["last_call_at"] = 995.0
        brain["pending"] = {"id": 3, "reasons": ["threat"], "since": 990.0, "urgent": True}
        self.assertEqual(route_for(brain, 1000.0, {"TYPESAFE_API_KEY": "k"}, 600.0), "jev")
        brain["pending"]["urgent"] = False
        self.assertEqual(route_for(brain, 1000.0, {"TYPESAFE_API_KEY": "k"}, 600.0), "utility")


class ViewerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()
        hatch_egg()
        registry = LifeRegistry()
        self.world = SurvivalWorld(registry.world_path(registry.active_life()))

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def add(self, *creatures):
        """Add (kind, dx, dz, health, state) creatures around Mimo; returns Mimo's cell."""
        state = self.world.state()
        x, y, z = (round(state["position"][axis]) for axis in "xyz")
        with self.world.transaction() as db:
            herd = Herd(db)
            for kind, dx, dz, health, extra in creatures:
                herd.add(kind, (x + dx, y, z + dz), health, 0.0, 0.0, {"turn": 0, **extra})
        return x, y, z

    def test_the_viewer_learns_which_creatures_are_hostile_what_they_do_and_when_mimo_was_hurt(self):
        now = time.time()
        self.add(("gloomling", 3, 0, 20.0, {"pose": "attacking", "struck_at": now - 1.0}),
                 ("skitter", 0, 6, 12.0, {"pose": "idle"}),
                 ("gloomling", -4, 0, 20.0, {"pose": "burning", "burning_at": now - 0.5}),
                 ("cow", 5, 5, 10.0, {"pose": "idle"}))
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(hurt_at=now - 1.0, hurt_by="gloomling")
            write_state(db, state)
        view = get_mimo()
        by_state = {creature["state"]: creature for creature in view["creatures"]}
        self.assertAlmostEqual(by_state["attacking"]["struck_at"], now - 1.0, places=1)
        self.assertAlmostEqual(by_state["burning"]["burning_at"], now - 0.5, places=1)
        self.assertEqual({creature["kind"]: creature.get("hostile", False) for creature in view["creatures"]},
                         {"gloomling": True, "skitter": True, "cow": False})
        self.assertEqual((view["hurt_at"], view["hurt_by"]), (now - 1.0, "gloomling"))

    def test_a_chase_reads_chasing_while_it_runs_and_the_stream_stays_small(self):
        now = time.time()
        x, y, z = (round(self.world.state()["position"][axis]) for axis in "xyz")
        run = timed((x + 9, y, z), [(x + 8, y, z), (x + 7, y, z)], now - 0.5, 0.9)
        self.add(*[("gloomling", 9, dz, 20.0, {"pose": "chasing", "chasing": True, "path": run}) for dz in range(8)],
                 *[("sheep", dx, dz, 8.0, {"pose": "fleeing", "path": run}) for dx in range(-3, 3) for dz in range(-2, 2)])
        view = get_mimo()
        chasers = [creature for creature in view["creatures"] if creature["kind"] == "gloomling"]
        self.assertEqual({creature["state"] for creature in chasers}, {"chasing"})
        size = len(json.dumps({"creatures": view["creatures"], "creature_moves": view["creature_moves"]}))
        self.assertLess(size, 16_000)  # 8 hostiles and 24 animals, all on the move


if __name__ == "__main__":
    unittest.main()

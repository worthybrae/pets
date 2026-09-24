import hashlib
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
from backend.survival.creatures.moves import timed
from backend.survival.creatures.table import Herd
from backend.survival.creatures.view import creatures_view, MOST_SHOWN
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, new_survival_state


class CreatureApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def active_world(self):
        registry = LifeRegistry()
        return SurvivalWorld(registry.world_path(registry.active_life()))

    def around_mimo(self, world, *creatures):
        """Add (kind, dx, dz, health, state) creatures around Mimo; returns Mimo's cell."""
        state = world.state()
        x, y, z = (round(state["position"][axis]) for axis in "xyz")
        with world.transaction() as db:
            herd = Herd(db)
            for kind, dx, dz, health, extra in creatures:
                herd.add(kind, (x + dx, y, z + dz), health, 0.0, 0.0, {"turn": 0, **extra})
        return x, y, z

    def test_creatures_near_mimo_and_their_recent_moves_are_streamed(self):
        hatch_egg()
        world = self.active_world()
        now = time.time()
        x, y, z = world.state()["position"]["x"], world.state()["position"]["y"], world.state()["position"]["z"]
        start = (round(x) + 3, round(y), round(z))
        walk = timed(start, [(start[0] + 1, start[1], start[2])], now - 0.5, 0.7)
        old = timed(start, [(start[0], start[1], start[2] + 1)], now - 60.0, 0.7)
        self.around_mimo(world,
                         ("cow", 4, 0, 5.0, {"pose": "walking", "path": walk}),
                         ("sheep", 0, 5, 8.0, {"pose": "walking", "path": old}),
                         ("rabbit", 2, 2, 0.0, {"pose": "dead", "dead_at": now - 2.0, "drops": ["raw_rabbit"],
                                                "hurt_at": now - 2.0}),
                         ("chicken", 3, 3, 0.0, {"pose": "dead", "dead_at": now - 60.0}),
                         ("cow", 200, 0, 10.0, {"pose": "idle"}))
        state = get_mimo()
        by_kind = {creature["kind"]: creature for creature in state["creatures"]}
        self.assertEqual(set(by_kind), {"cow", "sheep", "rabbit"})
        self.assertEqual(by_kind["cow"], {"id": 1, "kind": "cow", "x": x + 4, "y": y, "z": z, "heading": 0.0,
                                          "health": 0.5, "state": "walking"})
        self.assertEqual(by_kind["sheep"]["state"], "idle")  # its walk ended long ago
        rabbit_times = {key: by_kind["rabbit"][key] for key in ("state", "health", "dead_at", "hurt_at", "drops")}
        self.assertEqual(rabbit_times["state"], "dead")
        self.assertEqual(rabbit_times["health"], 0.0)
        self.assertEqual(rabbit_times["drops"], ["raw_rabbit"])
        self.assertAlmostEqual(rabbit_times["dead_at"], now - 2.0, places=1)
        self.assertAlmostEqual(rabbit_times["hurt_at"], now - 2.0, places=1)
        moves = state["creature_moves"]
        self.assertEqual(len(moves), 1)
        move = moves[0]
        self.assertEqual(move["id"], 1)
        self.assertEqual(move["from"], {"x": start[0], "y": start[1], "z": start[2]})
        self.assertEqual(move["to"], {"x": start[0] + 1, "y": start[1], "z": start[2]})
        self.assertAlmostEqual(move["started"], walk[0]["at"], places=1)
        self.assertAlmostEqual(move["ends"], walk[-1]["at"], places=1)

    def test_the_stream_stays_small_with_every_animal_moving(self):
        hatch_egg()
        world = self.active_world()
        now = time.time()
        x, y, z = (round(world.state()["position"][axis]) for axis in "xyz")
        flee = timed((x, y, z), [(x + step, y, z) for step in range(1, 9)], now - 1.0, 0.2)
        creatures = []
        for i in range(MOST_SHOWN):
            dx = i % 8
            dz = i // 8
            creatures.append(("sheep", dx, dz, 8.0, {"pose": "fleeing", "path": flee, "hurt_at": now - 0.5}))
        self.around_mimo(world, *creatures)
        state = get_mimo()
        self.assertEqual(len(state["creatures"]), MOST_SHOWN)
        flight = next(move for move in state["creature_moves"] if len(move.get("cells", [])) == 9)
        self.assertEqual((flight["cells"][0], flight["cells"][-1]), ([x, y, z], [x + 8, y, z]))
        size = len(json.dumps({"creatures": state["creatures"], "creature_moves": state["creature_moves"]}))
        self.assertLess(size, 14_400)  # the worst case: all MOST_SHOWN on the move at once with hurt_at

    def test_reading_creatures_never_writes(self):
        hatch_egg()
        world = self.active_world()
        self.around_mimo(world, ("cow", 2, 0, 10.0, {"pose": "idle"}))
        before = hashlib.sha256(world.path.read_bytes()).hexdigest()
        get_mimo()
        get_mimo()
        self.assertEqual(hashlib.sha256(world.path.read_bytes()).hexdigest(), before)

    def test_an_archived_world_from_before_l1_has_no_creatures(self):
        path = Path(self.directory.name) / "before-l1.sqlite3"
        state = new_survival_state(name="Pip", seed="1", spawn={"x": 0, "y": 1, "z": 0}, born_at=10.0, traits={})
        SurvivalWorld.create(path, state)
        db = sqlite3.connect(path)
        with db:
            db.execute("DROP TABLE creatures")
        db.close()
        archive = SurvivalWorld(path, read_only=True)
        with archive.connect() as db:
            self.assertEqual(creatures_view(db, {"x": 0.0, "y": 1.0, "z": 0.0}, 20.0),
                             {"creatures": [], "creature_moves": []})

    def test_only_nearest_most_shown_are_returned_when_more_nearby(self):
        hatch_egg()
        world = self.active_world()
        now = time.time()
        x, y, z = (round(world.state()["position"][axis]) for axis in "xyz")
        self.around_mimo(world, *[("sheep", dx, dz, 8.0, {"pose": "idle"})
                                  for dx in range(-10, 11) for dz in range(-10, 11)])
        state = get_mimo()
        self.assertEqual(len(state["creatures"]), MOST_SHOWN)
        distances = [((c["x"] - x) ** 2 + (c["z"] - z) ** 2) ** 0.5 for c in state["creatures"]]
        self.assertTrue(all(distances[i] <= distances[i + 1] for i in range(len(distances) - 1)))


if __name__ == "__main__":
    unittest.main()

import random
import tempfile
import unittest
from pathlib import Path

from backend.services.worldgen import terrain_height
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.script import scripted_plan
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.workers import mimo_worker

BORN = 1_000_000.0


class TickActionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.registry = LifeRegistry(self.root / "data", self.root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def edit(self, **changes):
        with self.world.transaction() as db:
            state = read_state(db)
            state.update(changes)
            write_state(db, state)

    def spawn_column(self):
        position = self.world.state()["position"]
        return round(position["x"]), round(position["z"])

    def test_one_tick_can_walk_chop_and_craft(self):
        state = tick_life(self.registry, BORN + 120, scale=1, planner=scripted_plan)
        self.assertIsNone(state["died_at"])
        self.assertGreaterEqual(state["inventory"].get("planks", 0), 4)
        self.assertIn("air", [change["material"] for change in self.world.blocks_since(0)["changes"]])
        self.assertIn("craft", [event["kind"] for event in self.world.events(50)])

    def test_a_restarted_worker_resumes_a_stored_walk(self):
        x, z = self.spawn_column()
        path = [{"x": x + step, "y": 100, "z": z, "at": BORN + 0.3 * step} for step in range(4)]
        self.edit(position={"x": float(x), "y": 100.0, "z": float(z)}, queue=[], recent_actions=[], actions_at=BORN,
                  action={"kind": "walk", "started_at": BORN, "ends_at": path[-1]["at"], "path": path,
                          "target": {"x": x + 3, "y": 100, "z": z}, "reach": 0.0, "reached": True, "segments": 0})
        restarted = LifeRegistry(self.root / "data", self.root / "no-legacy.sqlite3")
        state = tick_life(restarted, BORN + 0.5, scale=1)
        self.assertEqual(state["action"]["started_at"], BORN)
        self.assertEqual(state["position"], {"x": float(x + 1), "y": 100.0, "z": float(z)})
        self.assertEqual(state["status"], "walking")

    def test_a_long_fall_kills_and_archives_the_life(self):
        x, z = self.spawn_column()
        self.edit(position={"x": float(x), "y": float(terrain_height(x, z, self.world.seed) + 40), "z": float(z)})
        state = tick_life(self.registry, BORN + 5, scale=1)
        self.assertEqual((state["status"], state["cause"]), ("dead", "fall"))
        self.assertLess(state["died_at"], BORN + 3)
        self.assertIsNone(state["action"])
        self.assertEqual(self.registry.get(self.life["id"])["cause"], "fall")
        self.assertIn("died of a fall on day 1", self.world.events()[0]["text"])

    def test_night_sleep_is_a_step_without_an_end(self):
        state = tick_life(self.registry, BORN + 2450, scale=1)
        self.assertEqual((state["action"]["kind"], state["action"]["ends_at"]), ("sleep", None))

    def test_the_worker_runs_the_interim_script(self):
        self.assertIs(mimo_worker.WORKER_PLANNER, scripted_plan)


if __name__ == "__main__":
    unittest.main()

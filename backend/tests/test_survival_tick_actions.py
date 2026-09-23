import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.worldgen import terrain_height
from backend.survival import steps as steps_module
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

    def test_a_long_catch_up_shares_one_search_budget_for_the_whole_tick(self):
        """Controller ruling (Task 6 fix round 1): advance_world creates one ActionContext per
        tick_life call and every catch-up step's advance_actions call shares it, so a gap spanning
        several 60-game-second steps still spends at most MAX_SEARCHES_PER_TICK (2) route()
        searches for the whole tick, not that many per catch-up step. The deferred walks stay
        queued and the next tick call can pick them up with a fresh budget."""
        x, z = self.spawn_column()
        y = terrain_height(x, z, self.world.seed) + 1
        for step in range(6):
            self.world.put_block(x + step, y - 1, z, "stone")
            self.world.put_block(x + step, y, z, "air")
        self.edit(position={"x": float(x), "y": float(y), "z": float(z)}, action=None, recent_actions=[],
                  actions_at=BORN, queue=[{"kind": "walk", "target": [x + step, y, z]} for step in range(1, 6)])
        with patch("backend.survival.steps.route", wraps=steps_module.route) as spy:
            state = tick_life(self.registry, BORN + 300, scale=1)  # 5 catch-up steps + 1 final call
        self.assertIsNone(state["died_at"])
        self.assertLessEqual(spy.call_count, 2)
        self.assertTrue(state["queue"] or (state["action"] and state["action"]["kind"] == "walk"))
        with patch("backend.survival.steps.route", wraps=steps_module.route) as spy_next:
            tick_life(self.registry, BORN + 301, scale=1)
        self.assertGreaterEqual(spy_next.call_count, 1)

    def test_the_worker_runs_the_interim_script(self):
        self.assertIs(mimo_worker.WORKER_PLANNER, scripted_plan)

    def test_a_crashing_planner_never_freezes_the_life(self):
        """Reviewer-reported bug (Task 7 final review): an exception escaping advance_actions
        rolled back the whole tick's write transaction, so last_tick_at never advanced and every
        later tick replayed the same state and raised again. A broken planner (M3 will plug new
        ones in) must not be able to do that."""
        def broken(state, grid, at, clock):
            raise RuntimeError("boom")

        state = tick_life(self.registry, BORN + 5, scale=1, planner=broken)
        self.assertIsNone(state["died_at"])
        self.assertEqual(state["last_tick_at"], BORN + 5)
        again = tick_life(self.registry, BORN + 10, scale=1, planner=broken)
        self.assertEqual(again["last_tick_at"], BORN + 10)

    def test_a_malformed_queued_step_never_freezes_the_life(self):
        self.edit(action=None, queue=[{"kind": "mine", "target": None}], recent_actions=[])
        state = tick_life(self.registry, BORN + 5, scale=1)
        self.assertEqual(state["last_tick_at"], BORN + 5)
        self.assertEqual(state["recent_actions"][-1]["reason"], "bad step: target")


if __name__ == "__main__":
    unittest.main()

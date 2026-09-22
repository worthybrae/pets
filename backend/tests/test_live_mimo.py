import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.services.live_mimo import MimoStore, _model_decision, observe_world, run_tick, validate_decision


class LiveMimoTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "mimo.sqlite3"
        self.store = MimoStore(self.path)

    def tearDown(self):
        self.directory.cleanup()

    def test_luna_request_uses_supported_chat_parameters(self):
        requests = []

        def fake_urlopen(request, timeout):
            self.assertEqual(timeout, 45)
            requests.append(json.loads(request.data))
            return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"action\\":\\"rest\\",\\"thought\\":\\"I will rest.\\"}"}}]}')

        with patch.dict("os.environ", {"MIMO_MODEL": "gpt-6-luna", "OPENAI_API_KEY": "test-only-key",
                                     "MIMO_MODEL_URL": "https://api.openai.com/v1/chat/completions"}), \
             patch("backend.services.live_mimo.urlopen", fake_urlopen):
            state = self.store.snapshot()
            result = _model_decision(state, observe_world(state), [])

        self.assertEqual(result["action"], "rest")
        self.assertEqual(requests[0]["model"], "gpt-6-luna")
        self.assertEqual(requests[0]["reasoning_effort"], "none")
        self.assertEqual(requests[0]["max_completion_tokens"], 256)
        self.assertEqual(requests[0]["response_format"], {"type": "json_object"})
        self.assertNotIn("temperature", requests[0])
        self.assertNotIn("max_tokens", requests[0])

    def test_luna_stays_paused_without_api_key(self):
        state = self.store.snapshot()
        with patch.dict("os.environ", {"MIMO_MODEL": "gpt-6-luna", "OPENAI_API_KEY": "",
                                     "MIMO_MODEL_API_KEY": "", "MIMO_MODEL_URL": "https://api.openai.com/v1/chat/completions"}), \
             patch("backend.services.live_mimo.urlopen") as urlopen_mock:
            run_tick(self.store, timestamp=state["next_tick_at"] + 1)
        self.assertEqual(self.store.snapshot()["status"], "waiting_for_model")
        urlopen_mock.assert_not_called()

    def test_model_chosen_build_keeps_progressing_without_a_browser(self):
        first = self.store.snapshot()

        def decide(_state, observation, _events):
            self.assertTrue(observation["candidate_sites"])
            return {"action": "build", "kind": "greenhouse", "candidate_id": 0,
                    "thought": "A greenhouse would make this clearing feel alive."}

        self.assertTrue(run_tick(self.store, decide, first["next_tick_at"] + 1))
        planned = self.store.snapshot()
        self.assertEqual(planned["plans"][-1]["kind"], "greenhouse")
        self.assertEqual(planned["currentIndex"], 1)
        self.assertEqual(planned["progress"], 0)

        for _ in range(30):
            state = self.store.snapshot()
            if state["progress"] == 100:
                break
            run_tick(self.store, decide, state["next_tick_at"] + 1)

        reloaded = MimoStore(self.path).snapshot()
        self.assertEqual(reloaded["progress"], 100)
        self.assertEqual(reloaded["plans"][-1]["kind"], "greenhouse")
        self.assertTrue(any(event["kind"] == "completed" for event in reloaded["events"]))

    def test_missing_model_pauses_instead_of_faking_actions(self):
        state = self.store.snapshot()

        def missing_model(_state, _observation, _events):
            raise RuntimeError("No model configured")

        run_tick(self.store, missing_model, state["next_tick_at"] + 1)
        updated = self.store.snapshot()
        self.assertEqual(updated["status"], "waiting_for_model")
        self.assertEqual(len(updated["plans"]), 1)
        self.assertIn("No model configured", updated["last_error"])

    def test_digging_and_loose_block_gravity_are_persistent(self):
        self.store.put_block(73, 0, 0, "air")
        self.store.put_block(73, -1, 0, "air")
        self.store.put_block(73, 2, 0, "sand")
        self.assertEqual(self.store.step_loose_blocks(), 1)
        self.assertEqual(self.store.material_at(73, 1, 0), "sand")
        self.assertEqual(self.store.step_loose_blocks(), 1)
        self.assertEqual(self.store.material_at(73, 0, 0), "sand")
        self.assertEqual(self.store.step_loose_blocks(), 1)
        self.assertEqual(self.store.material_at(73, -1, 0), "sand")
        self.assertEqual(self.store.step_loose_blocks(), 0)
        self.assertEqual(MimoStore(self.path).material_at(73, -1, 0), "sand")

    def test_spatial_decision_rejects_unobserved_site(self):
        observation = observe_world(self.store.snapshot())
        with self.assertRaises(ValueError):
            validate_decision({"action": "build", "kind": "plaza", "candidate_id": 999,
                               "thought": "Too far."}, observation)
        with self.assertRaises(ValueError):
            validate_decision({"action": "dig", "x": 1000, "y": -1, "z": 0,
                               "thought": "Too far."}, observation)

    def test_crafting_table_furnace_smelting_and_tool_chain_persists(self):
        actions = [
            {"action": "craft", "recipe": "planks"},
            {"action": "craft", "recipe": "crafting_table"},
            {"action": "place", "x": 73, "y": 1, "z": 0, "material": "crafting_table"},
            {"action": "craft", "recipe": "furnace"},
            {"action": "place", "x": 74, "y": 1, "z": 0, "material": "furnace"},
            {"action": "smelt", "input_item": "iron_ore"},
            {"action": "smelt", "input_item": "iron_ore"},
            {"action": "smelt", "input_item": "iron_ore"},
            {"action": "craft", "recipe": "planks"},
            {"action": "craft", "recipe": "sticks"},
            {"action": "craft", "recipe": "iron_pickaxe"},
        ]

        def decide(_state, _observation, _events):
            return {**actions.pop(0), "thought": "I am making a tool from the resources I have."}

        while actions:
            state = self.store.snapshot()
            run_tick(self.store, decide, state["next_tick_at"] + 1)
            self.assertIsNone(self.store.snapshot()["last_error"])

        reloaded = MimoStore(self.path).snapshot()
        self.assertEqual(reloaded["inventory"]["iron_pickaxe"], 1)
        self.assertEqual(self.store.material_at(73, 1, 0), "crafting_table")
        self.assertEqual(self.store.material_at(74, 1, 0), "furnace")
        self.assertTrue(any(event["kind"] == "craft" for event in reloaded["events"]))

    def test_daily_model_limit_stops_additional_calls(self):
        calls = []

        def decide(_state, _observation, _events):
            calls.append(True)
            return {"action": "rest", "thought": "I will rest."}

        with patch.dict("os.environ", {"MIMO_MAX_DECISIONS_PER_DAY": "1"}):
            first = self.store.snapshot()
            run_tick(self.store, decide, first["next_tick_at"] + 1)
            second = self.store.snapshot()
            run_tick(self.store, decide, second["next_tick_at"] + 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.snapshot()["status"], "sleeping")

    def test_exploration_walks_in_steps_around_existing_world(self):
        first = self.store.snapshot()

        def decide(_state, observation, _events):
            self.assertTrue(observation["candidate_sites"])
            return {"action": "explore", "candidate_id": 0, "thought": "I want to inspect that clearing."}

        run_tick(self.store, decide, first["next_tick_at"] + 1)
        planned = self.store.snapshot()
        self.assertEqual(planned["position"]["x"], 73)
        self.assertIsNotNone(planned["explore_target"])
        run_tick(self.store, decide, planned["next_tick_at"] + 1)
        moved = self.store.snapshot()
        self.assertLessEqual(abs(moved["position"]["x"] - 73) + abs(moved["position"]["z"]), 8)
        self.assertGreaterEqual(moved["position"]["y"], 1)
        self.assertEqual(moved["status"], "travelling")

    def test_owner_can_craft_and_place_real_machines(self):
        self.store.owner_action("craft", "planks")
        self.store.owner_action("craft", "crafting_table")
        self.store.owner_action("place_machine", "crafting_table")
        self.store.owner_action("craft", "furnace")
        self.store.owner_action("place_machine", "furnace")
        self.store.owner_action("smelt", "iron_ore")
        saved = MimoStore(self.path).snapshot()
        self.assertEqual(saved["inventory"]["iron_ingot"], 1)
        self.assertEqual(len([block for block in saved["block_edits"] if block["material"] in ("crafting_table", "furnace")]), 2)
        self.assertEqual(saved["events"][0]["kind"], "owner")


if __name__ == "__main__":
    unittest.main()

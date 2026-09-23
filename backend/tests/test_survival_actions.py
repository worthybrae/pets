import math
import unittest
from unittest.mock import patch

from backend.survival import steps as steps_module
from backend.survival.actions import ActionContext, activity_of, advance_actions, ensure_actions
from backend.survival.grid import Grid
from backend.survival.steps import start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}


def small_world(cells=None, floor="stone"):
    """`floor` at y <= 0 and air above, with `cells` overriding single cells."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or (floor if y <= 0 else "air"))


def pet(position=(0, 1, 0), **changes):
    state = {"name": "Pip", "position": {"x": float(position[0]), "y": float(position[1]), "z": float(position[2])},
             "inventory": {}, "vitals": dict(START_VITALS), "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


class Plans:
    """A planner that hands out prepared plans in order and counts how often it was asked."""

    def __init__(self, *plans):
        self.plans = list(plans)
        self.calls = 0

    def __call__(self, state, grid, at, clock):
        self.calls += 1
        return self.plans.pop(0) if self.plans else []


def context(grid, planner=None, clock=None):
    return ActionContext(grid=grid, clock_at=clock or (lambda at: DAY), planner=planner or Plans(), events=[])


class ActionEngineTests(unittest.TestCase):
    def test_several_steps_can_finish_in_one_advance(self):
        grid, state = small_world(), pet(inventory={"planks": 2})
        state["queue"] = [{"kind": "place", "target": [1, 1, 0], "block": "planks"},
                          {"kind": "place", "target": [0, 1, 1], "block": "planks"},
                          {"kind": "wait", "seconds": 5}]
        advance_actions(state, context(grid), 1.0)
        self.assertEqual([(entry["kind"], entry["ended_at"]) for entry in state["recent_actions"]],
                         [("place", 0.3), ("place", 0.6)])
        self.assertEqual((grid.material(1, 1, 0), grid.material(0, 1, 1)), ("planks", "planks"))
        self.assertEqual(state["inventory"], {})
        self.assertEqual((state["action"]["kind"], state["action"]["ends_at"]), ("wait", 5.6))
        self.assertEqual(state["status"], "idle")

    def test_a_walk_moves_mimo_cell_by_cell(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [5, 1, 0]}]
        ctx = context(grid)
        advance_actions(state, ctx, 0.7)
        self.assertEqual(state["position"]["x"], 2.0)
        self.assertEqual((state["status"], activity_of(state)), ("walking", "working"))
        advance_actions(state, ctx, 2.0)
        self.assertEqual(state["position"], {"x": 5.0, "y": 1.0, "z": 0.0})
        self.assertEqual(state["recent_actions"][-1]["kind"], "walk")
        self.assertEqual((state["status"], activity_of(state)), ("idle", "idle"))

    def test_the_planner_fills_an_empty_queue(self):
        planner = Plans([{"kind": "wait", "seconds": 2}], [{"kind": "wait", "seconds": 2}],
                        [{"kind": "wait", "seconds": 2}])
        state = pet()
        advance_actions(state, context(small_world(), planner), 5.0)
        self.assertEqual(planner.calls, 3)
        self.assertEqual(state["action"]["ends_at"], 6.0)
        self.assertEqual(state["recent_actions"], [])

    def test_a_failed_step_is_recorded_and_clears_the_plan(self):
        state = pet()
        state["queue"] = [{"kind": "mine", "target": [9, 1, 0]}, {"kind": "wait", "seconds": 1}]
        advance_actions(state, context(small_world({(9, 1, 0): "dirt"})), 1.0)
        failed = state["recent_actions"][-1]
        self.assertEqual((failed["kind"], failed["result"], failed["reason"]), ("mine", "failed", "out of reach"))
        self.assertEqual(failed["target"], {"x": 9, "y": 1, "z": 0})
        self.assertEqual((state["action"], state["queue"]), (None, []))

    def test_digging_out_the_floor_drops_mimo_and_long_falls_hurt(self):
        grid, state = small_world({(0, 8, 0): "dirt"}), pet(position=(0, 9, 0))
        state["queue"] = [{"kind": "mine", "target": [0, 8, 0]}]
        ctx = context(grid)
        self.assertIsNone(advance_actions(state, ctx, 3.0))
        self.assertEqual(state["position"], {"x": 0.0, "y": 1.0, "z": 0.0})
        self.assertEqual(state["vitals"]["health"], 50.0)
        fall = state["recent_actions"][-1]
        self.assertEqual((fall["kind"], fall["ended_at"]), ("fall", round(0.6 + math.sqrt(16 / 32), 3)))
        self.assertEqual(ctx.events[-1][1:], ("fall", "Pip fell 8 blocks and got hurt."))

    def test_a_hazard_records_the_interrupted_plan_once(self):
        grid, state = small_world(), pet(position=(0, 9, 0))
        state["queue"] = [{"kind": "mine", "target": [5, 1, 0]}, {"kind": "wait", "seconds": 1}]
        ctx = context(grid)
        advance_actions(state, ctx, 1.0)
        kinds = [(entry["kind"], entry["result"], entry.get("reason")) for entry in state["recent_actions"]]
        self.assertEqual(kinds, [("mine", "failed", "interrupted: fall"), ("fall", "done", None)])
        self.assertEqual(state["recent_actions"][0]["target"], {"x": 5, "y": 1, "z": 0})
        self.assertEqual(state["queue"], [])

    def test_a_hazard_does_not_record_an_interrupted_wait(self):
        grid, state = small_world(), pet(position=(0, 9, 0))
        state["queue"] = [{"kind": "wait", "seconds": 5}]
        advance_actions(state, context(grid), 1.0)
        self.assertEqual([entry["kind"] for entry in state["recent_actions"]], ["fall"])

    def test_falls_of_three_or_into_water_do_not_hurt(self):
        state = pet(position=(0, 4, 0))
        advance_actions(state, context(small_world()), 2.0)
        self.assertEqual((state["position"]["y"], state["vitals"]["health"]), (1.0, 100.0))
        state = pet(position=(0, 20, 0))
        advance_actions(state, context(small_world(floor="water")), 3.0)
        self.assertEqual((state["position"]["y"], state["vitals"]["health"]), (1.0, 100.0))

    def test_a_long_fall_can_kill(self):
        state = pet(position=(0, 12, 0))
        state["vitals"]["health"] = 30.0
        died_at = advance_actions(state, context(small_world()), 5.0)
        self.assertEqual(died_at, round(math.sqrt(2 * 11 / 32), 3))
        self.assertEqual(state["vitals"]["health"], 0.0)

    def test_mimo_swims_up_when_its_cell_is_water(self):
        column = {(0, 1, 0): "water", (0, 2, 0): "water", (0, 3, 0): "water"}
        state = pet()
        ctx = context(small_world(column))
        advance_actions(state, ctx, 1.0)
        self.assertEqual(state["action"]["kind"], "swim")
        self.assertEqual([entry["y"] for entry in state["action"]["path"]], [1, 2, 3, 4])
        self.assertEqual(state["action"]["ends_at"], 2.7)
        self.assertEqual((state["position"]["y"], state["status"], activity_of(state)), (2.0, "swimming", "working"))
        advance_actions(state, ctx, 3.0)
        self.assertEqual((state["position"]["y"], state["status"]), (4.0, "idle"))

    def test_sleep_lasts_until_rested_and_daylight(self):
        planner = Plans([{"kind": "sleep", "thought": "Sleepy."}])
        state = pet()
        state["vitals"]["energy"] = 50.0
        ctx = context(small_world(), planner, clock=lambda at: NIGHT if at < 100 else DAY)
        advance_actions(state, ctx, 10.0)
        self.assertEqual((state["status"], activity_of(state), state["last_thought"]), ("sleeping", "sleeping", "Sleepy."))
        state["vitals"]["energy"] = 99.0
        advance_actions(state, ctx, 60.0)
        self.assertEqual(state["status"], "sleeping")
        advance_actions(state, ctx, 120.0)
        self.assertEqual(state["status"], "idle")
        self.assertEqual([event[1] for event in ctx.events], ["sleep", "wake"])
        self.assertEqual(state["recent_actions"][-1]["ended_at"], 120.0)

    def test_far_walks_continue_segment_by_segment(self):
        """Each call below simulates a separate tick_life call, which in production always builds
        a fresh ActionContext (Task 6 fix round 1), so each gets its own search budget here too;
        only a single advance_actions call sharing one context is limited to 2 searches total."""
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [200, 1, 0]}]
        advance_actions(state, context(grid), 0.0)
        first = state["action"]
        self.assertFalse(first["reached"])
        advance_actions(state, context(grid), first["ends_at"])
        self.assertEqual((state["action"]["kind"], state["action"]["started_at"]), ("walk", first["ends_at"]))
        advance_actions(state, context(grid), 100.0)
        self.assertEqual(state["position"], {"x": 200.0, "y": 1.0, "z": 0.0})

    def test_a_walk_stops_where_its_path_became_blocked(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [5, 1, 0]}]
        ctx = context(grid)
        advance_actions(state, ctx, 0.4)
        grid.put(3, 1, 0, "planks")
        advance_actions(state, ctx, 2.0)
        self.assertEqual(state["position"]["x"], 2.0)
        self.assertEqual(state["recent_actions"][-1]["reason"], "path blocked")
        self.assertIsNone(state["action"])

    def test_states_saved_before_actions_get_the_new_fields(self):
        state = {"last_tick_at": 42.0}
        ensure_actions(state)
        self.assertEqual(state, {"last_tick_at": 42.0, "action": None, "queue": [], "recent_actions": [],
                                 "actions_at": 42.0})

    def test_only_the_last_twenty_steps_are_kept_and_waits_are_left_out(self):
        state = pet(inventory={"berries": 25})
        state["queue"] = [{"kind": "eat", "item": "berries"} for _ in range(25)] + [{"kind": "wait", "seconds": 1}]
        ctx = context(small_world())
        advance_actions(state, ctx, 50.0)
        self.assertEqual(len(state["recent_actions"]), 20)
        self.assertEqual({entry["kind"] for entry in state["recent_actions"]}, {"eat"})
        self.assertEqual(len(ctx.events), 25)

    def test_a_malformed_queued_step_fails_clean_and_the_tick_keeps_going(self):
        """Reviewer-reported crashes (Task 7 final review): a bad field used to raise a raw
        TypeError/ValueError out of advance_actions, rolling back the whole tick transaction so
        last_tick_at never advanced and the pet froze. Each of these must instead fail the one
        step and let advance_actions finish normally."""
        cases = [{"kind": "mine", "target": None}, {"kind": "walk", "target": [1, 1, 0], "reach": None},
                 {"kind": "place", "target": [1, 1, 0], "block": ["x"]}, {"kind": "mine", "target": [1, 2]}]
        for spec in cases:
            grid, state = small_world(), pet()
            state["queue"] = [spec, {"kind": "wait", "seconds": 1}]
            advance_actions(state, context(grid), 1.0)  # must not raise
            failed = state["recent_actions"][-1]
            self.assertEqual(failed["result"], "failed", msg=spec)
            self.assertIn("bad step", failed["reason"], msg=spec)
            self.assertEqual(state["actions_at"], 1.0, msg=spec)
            self.assertEqual((state["action"], state["queue"]), (None, []), msg=spec)

    def test_a_crashing_planner_falls_back_to_rest_and_the_tick_keeps_going(self):
        def broken(state, grid, at, clock):
            raise RuntimeError("boom")

        state = pet()
        state["vitals"]["energy"] = 5.0  # below EXHAUSTED_BELOW, so rest_plan sleeps regardless of time of day
        with self.assertLogs("backend.survival.actions", level="ERROR"):
            advance_actions(state, context(small_world(), broken), 1.0)
        self.assertEqual(state["action"]["kind"], "sleep")
        self.assertEqual(state["actions_at"], 1.0)

    def test_a_non_list_of_dicts_plan_falls_back_to_rest_too(self):
        for bad_result in (None, "nope", {"kind": "wait"}, [1, 2, 3]):
            def bad_planner(state, grid, at, clock, result=bad_result):
                return result

            state = pet()
            state["vitals"]["energy"] = 5.0
            advance_actions(state, context(small_world(), bad_planner), 1.0)
            self.assertEqual(state["action"]["kind"], "sleep", msg=bad_result)
            self.assertEqual(state["actions_at"], 1.0, msg=bad_result)

    def test_an_unexpected_crash_starting_a_step_fails_clean_and_continues(self):
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "mine", "target": [1, 1, 0]}]
        with patch("backend.survival.actions.start_step", side_effect=RuntimeError("boom")):
            advance_actions(state, context(grid), 1.0)  # must not raise
        failed = state["recent_actions"][-1]
        self.assertEqual((failed["kind"], failed["result"], failed["reason"]), ("mine", "failed", "bad step"))
        self.assertEqual((state["action"], state["queue"], state["actions_at"]), (None, [], 1.0))

    def test_an_unexpected_crash_finishing_a_step_fails_clean_and_continues(self):
        grid, state = small_world(), pet(inventory={"berries": 1})
        state["action"] = start_step({"kind": "eat", "item": "berries"}, state, grid, 0.0)
        with patch("backend.survival.actions.finish_step", side_effect=RuntimeError("boom")):
            advance_actions(state, context(grid), 5.0)  # must not raise
        failed = state["recent_actions"][-1]
        self.assertEqual((failed["kind"], failed["result"], failed["reason"]), ("eat", "failed", "bad step"))
        self.assertIsNone(state["action"])
        self.assertEqual(state["actions_at"], 5.0)

    def test_the_engine_shares_its_search_budget_across_calls_on_one_context(self):
        """Controller ruling (Task 3 review, tightened in Task 6 fix round 1): at most
        MAX_SEARCHES_PER_TICK route()/start_step(walk) searches across every advance_actions call
        sharing one ActionContext (context.searches_left), not a fresh budget per call, so a long
        catch-up (which calls advance_actions many times inside one advance_world, all on the same
        context) cannot blow up the tick's write transaction. A queue of 5 short,
        independently-reachable walks with a huge elapsed time would finish all 5 (and search 5
        times) without the cap; with it, only 2 searches run, even split across two separate
        advance_actions calls that reuse the same context."""
        grid, state = small_world(), pet()
        state["queue"] = [{"kind": "walk", "target": [x, 1, 0]} for x in (1, 2, 3, 4, 5)]
        ctx = context(grid)
        with patch("backend.survival.steps.route", wraps=steps_module.route) as spy:
            advance_actions(state, ctx, 1000.0)
            self.assertEqual(spy.call_count, 2)
            self.assertLess(state["position"]["x"], 5.0)
            self.assertTrue(state["queue"] or (state["action"] and state["action"]["kind"] == "walk"))
            # The same context, asked again: the spent budget carries over, so no more searches run.
            advance_actions(state, ctx, 2000.0)
        self.assertEqual(spy.call_count, 2)


if __name__ == "__main__":
    unittest.main()

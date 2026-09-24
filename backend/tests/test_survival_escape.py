import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.escape import escape_plan, reachable_count
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def pit(wall="dirt", width=1):
    """Stone at y <= 0, `wall` from y 1 to 4 around an open pit (x 0 to width-1 at z 0), air from y 5."""
    def rule(x, y, z):
        if y <= 0:
            return "stone"
        if y >= 5:
            return "air"
        return "air" if z == 0 and 0 <= x < width else wall

    return Grid(rule)


def flat():
    return Grid(lambda x, y, z: "stone" if y <= 0 else "air")


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def brainy(grid):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=brain_plan, events=[], db=db)


def mine(x, y, z):
    return {"kind": "mine", "target": [x, y, z]}


def rubble(x, y, z):
    return {**mine(x, y, z), "rubble": True}


def walk(x, y, z):
    return {"kind": "walk", "target": [x, y, z], "reach": 0.0}


def place(x, y, z, block="dirt"):
    return {"kind": "place", "target": [x, y, z], "block": block}


def failed_walk(at, purpose="explore"):
    return {"kind": "walk", "started_at": at, "ended_at": at, "result": "failed", "reason": "no way there",
            "code": "no_path", "target": {"x": 40, "y": 5, "z": 0}, "purpose": purpose}


def stuck(**changes):
    """A pet exploring whose last two walks found no path, with the second failure not yet handled."""
    state = pet(**changes)
    state["recent_actions"] = [failed_walk(1.0), failed_walk(2.0)]
    state["last_failure"] = {"code": "no_path", "reason": "no way there", "kind": "walk",
                             "cell": {"x": 40, "y": 5, "z": 0}, "purpose": "explore", "at": 2.0}
    ensure_brain(state).update(purpose="explore", pending=None, chosen_at=0.0, replans=1, planned_at=1.0)
    return state


@patch("backend.survival.escape.terrain_height", lambda x, z, seed: 4)
class EscapeTests(unittest.TestCase):
    def test_a_pit_is_a_small_world(self):
        self.assertEqual(reachable_count(pit(), (0, 1, 0), 256), 1)
        self.assertEqual(reachable_count(pit(width=5), (0, 1, 0), 256), 5)
        self.assertEqual(reachable_count(flat(), (0, 1, 0), 256), 256)

    def test_digs_a_staircase_out_of_a_dirt_pit(self):
        self.assertEqual(escape_plan(pit(), (0, 1, 0), {}, "1"),
                         [mine(1, 2, 0), mine(1, 3, 0), rubble(1, 4, 0), rubble(1, 2, 1), rubble(1, 3, 1),
                          rubble(1, 4, 1), walk(1, 2, 0),
                          mine(2, 3, 0), mine(2, 4, 0), rubble(2, 3, 1), rubble(2, 4, 1), walk(2, 3, 0),
                          mine(3, 4, 0), rubble(3, 4, 1), walk(3, 4, 0), walk(4, 5, 0)])

    def test_stone_walls_need_a_pickaxe(self):
        self.assertEqual(escape_plan(pit("stone"), (0, 1, 0), {}, "1"), [])
        self.assertEqual(escape_plan(pit("stone"), (0, 1, 0), {"wooden_pickaxe": 1}, "1")[0], mine(1, 2, 0))

    def test_builds_stairs_from_carried_blocks_in_a_wide_pit(self):
        self.assertEqual(escape_plan(pit("stone", width=5), (0, 1, 0), {"dirt": 4}, "1"),
                         [place(1, 1, 0), walk(1, 2, 0), place(2, 2, 0), walk(2, 3, 0),
                          place(3, 3, 0), walk(3, 4, 0), place(4, 4, 0), walk(4, 5, 0)])
        self.assertEqual(escape_plan(pit("stone", width=5), (0, 1, 0), {"dirt": 3}, "1"), [])

    def test_the_brain_digs_out_after_two_failed_walks(self):
        state = stuck()
        ctx = brainy(pit())
        steps = brain_plan(state, ctx, 2.0)
        self.assertEqual(steps[0], {"kind": "mine", "target": [1, 2, 0], "purpose": "escape"})
        self.assertEqual(steps[-1], {"kind": "walk", "target": [4, 5, 0], "reach": 0.0, "purpose": "escape"})
        brain = state["brain"]
        self.assertEqual((brain["purpose"], brain["escaped_at"], brain["replans"], ctx.searches_left),
                         ("explore", 2.0, 0, 1))
        self.assertEqual(ctx.events[-1][1:], ("trapped", "Pip is stuck in a pit and starts digging out."))

    def test_any_second_no_path_failure_of_the_purpose_checks_for_a_trap(self):
        partial = {"kind": "walk", "started_at": 1.5, "ended_at": 1.8, "result": "done", "purpose": "explore",
                   "target": {"x": 40, "y": 5, "z": 0}}
        state = stuck()
        state["recent_actions"] = [failed_walk(1.0), partial, failed_walk(2.0)]
        self.assertEqual(brain_plan(state, brainy(pit()), 2.0)[0]["purpose"], "escape")
        fresh = stuck()
        fresh["brain"].update(replans=0, batches=2)  # the batch before the second failure went well
        self.assertEqual(brain_plan(fresh, brainy(pit()), 2.0)[0]["purpose"], "escape")

    def test_failures_from_before_the_purpose_was_chosen_or_of_another_purpose_do_not_count(self):
        earlier = stuck()
        earlier["recent_actions"] = [failed_walk(1.0), failed_walk(2.0, "go_home")]
        self.assertEqual(brain_plan(earlier, brainy(pit()), 2.0), [{"kind": "wait", "seconds": 1.0}])
        self.assertIsNone(earlier["brain"]["purpose"])
        rechosen = stuck()
        rechosen["brain"]["chosen_at"] = 1.5
        brain_plan(rechosen, brainy(pit()), 2.0)
        self.assertIsNone(rechosen["brain"]["purpose"])

    def test_with_no_search_left_the_check_waits_for_the_next_tick(self):
        state = stuck()
        ctx = brainy(pit())
        ctx.searches_left = 0
        self.assertEqual(brain_plan(state, ctx, 2.0), [{"kind": "wait", "seconds": 1.0}])
        self.assertIsNone(state["brain"]["handled_failure"])
        self.assertEqual(state["brain"]["purpose"], "explore")

    def test_a_pet_that_is_not_trapped_reports_the_failure(self):
        state = stuck()
        brain_plan(state, brainy(flat()), 2.0)
        self.assertIsNone(state["brain"]["purpose"])
        self.assertIn("explore", state["brain"]["penalties"])


if __name__ == "__main__":
    unittest.main()

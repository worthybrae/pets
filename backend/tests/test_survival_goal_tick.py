import random
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.survival.actions import ActionContext
from backend.survival.brain import BRAIN
from backend.survival.clock import DAY_SECONDS
from backend.survival.goals import (
    IDLE, IDLE_RETRY, Goal, Milestone, active, adopt_goal, as_goal, ask_for_goal, goal_state, tend_goal, workable,
)
from backend.survival.hatch import hatch
from backend.survival.memory import known
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES, Purpose
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_goals import LATER, STONE, WOOD, only_goals
from backend.tests.test_survival_pickers import DAY, NIGHT, forest, situation

BORN = 1_000_000.0
ONLY = Goal("only", "Only", "Its own work.", (Milestone("Do it", lambda s: 0.0, ("goal_only",)),),
            score=lambda s: 20.0, thought="Mine alone.")


@contextmanager
def goal_only_purpose():
    """A purpose offered only while ONLY is Mimo's goal, as improve_home is for a bigger home."""
    PURPOSES["goal_only"] = Purpose(
        "goal_only", "do it", "Only for its goal.", valid=lambda s: active(s) is not None and active(s).name == "only",
        facts=lambda s: "", score=lambda s: 50.0, plan=lambda s, context: [], thoughts=("Mine alone.",))
    try:
        yield
    finally:
        del PURPOSES["goal_only"]


class TendTests(unittest.TestCase):
    def setUp(self):
        self.s = situation()
        self.s.brain["pending"] = None
        self.state = self.s.state
        self.events = []
        self.context = ActionContext(grid=forest(), clock_at=lambda at: DAY, planner=lambda *args: [],
                                     events=self.events, db=self.s.db)

    def tend(self, at, phase=None):
        tend_goal(self.state, self.context, at, phase)
        return goal_state(self.state)

    def test_without_a_goal_one_is_asked_for_now_and_again_while_none_is_open(self):
        brain = self.tend(0.0)
        self.assertEqual(brain["goal_due"]["reasons"], ["no_goal"])
        adopt_goal(self.state, None, "utility", "", 5.0)  # nothing was open
        self.assertIsNone(self.tend(5.0 + IDLE_RETRY - 1)["goal_due"])
        self.assertEqual(self.tend(5.0 + IDLE_RETRY)["goal_due"]["reasons"], ["no_goal"])
        adopt_goal(self.state, None, "utility", "", 700.0)
        self.assertEqual(self.tend(701.0, "dawn")["goal_due"]["reasons"], ["dawn"])  # dawn asks at once

    def test_a_new_goal_gets_a_day_plan_and_its_progress_is_read_once_a_game_minute(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            brain = self.tend(1.0)
            self.assertEqual(brain["goal"]["plan"], [{"text": "Carry 4 logs", "done": False, "step": 0},
                                                     {"text": "Make a pickaxe", "done": False, "step": 1}])
            self.assertEqual(self.events[-1][1:], ("plan", "Pip's plan for today: carry 4 logs and make a pickaxe."))
            self.state["inventory"]["oak_log"] = 4
            self.assertEqual(self.tend(30.0)["goal"]["progress"], 0.0)  # read at most once a game minute
            brain = self.tend(61.0)
            self.assertEqual((brain["goal"]["progress"], brain["goal"]["plan"][0]["done"]), (0.5, True))
            self.assertEqual(len(self.events), 1)

    def test_the_day_plan_sets_time_aside_for_what_else_the_day_calls_for(self):
        extras = [lambda s, goal: {"text": "Take time to wander", "kind": "wander"}, lambda s, goal: None]
        with only_goals(WOOD), patch("backend.survival.goals.PLAN_EXTRAS", extras):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            plan = self.tend(1.0)["goal"]["plan"]
        self.assertEqual(plan[-1], {"text": "Take time to wander", "done": False, "step": None, "kind": "wander"})
        self.assertEqual(self.events[-1][2], "Pip's plan for today: carry 4 logs, make a pickaxe and take time to wander.")

    def test_a_complete_goal_is_reached_remembered_and_cheered(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            self.state["inventory"].update(oak_log=4, wooden_pickaxe=1)
            mood = self.state["vitals"]["mood"]
            brain = self.tend(100.0)
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][1:], ("goal", "Pip reached a goal: a woodpile."))
            self.assertEqual(self.state["vitals"]["mood"], min(100.0, mood + 15.0))
            self.assertEqual(known(self.s.db, "goal"), ["woodpile"])
            self.assertEqual(brain["goal_due"]["reasons"], ["reached"])
            self.assertIn("goal", brain["pending"]["reasons"])

    def test_at_dawn_the_plan_is_written_again_and_a_goal_choice_is_asked_for(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            self.state["inventory"]["oak_log"] = 4
            brain = self.tend(DAY_SECONDS - 10.0, "dawn")
            self.assertEqual(brain["goal"]["plan"], [{"text": "Make a pickaxe", "done": False, "step": 1}])
            self.assertEqual(brain["goal_due"]["reasons"], ["dawn"])

    def test_a_goal_without_progress_for_a_day_is_set_aside_at_dawn(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            brain = self.tend(DAY_SECONDS + 5.0, "dawn")
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][1:],
                             ("plan", "Pip set a goal aside for now: a woodpile (no progress for a day)."))
            self.assertEqual((brain["goal_penalties"], brain["goal_due"]["reasons"]),
                             ({"woodpile": 2 * DAY_SECONDS + 5.0}, ["given_up"]))

    def test_by_day_a_goal_with_nothing_to_do_for_it_is_set_aside_once_it_idles(self):
        with only_goals(WOOD, LATER):
            adopt_goal(self.state, "later", "jev", "Some day.", 0.0)  # no pickaxe: nothing digs stone
            self.tend(1.0)
            self.assertIsNotNone(self.tend(IDLE - 10.0)["goal"])
            brain = self.tend(IDLE + 70.0)
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][2], "Pip set a goal aside for now: later (nothing to do for it now).")

    def test_whether_a_goal_is_workable_is_judged_as_if_it_were_mimos_goal(self):
        with only_goals(WOOD, ONLY), goal_only_purpose():
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.assertTrue(workable(self.s, ONLY))
            self.assertEqual(as_goal(self.s, ONLY).brain["goal"]["name"], "only")
            self.assertEqual(self.s.brain["goal"]["name"], "woodpile")  # the real state is untouched

    def test_a_goal_that_can_no_longer_be_done_is_set_aside(self):
        with only_goals(WOOD, STONE):
            adopt_goal(self.state, "quarry", "jev", "Stone next.", 0.0)  # the woodpile is not settled
            self.assertIsNone(self.tend(1.0)["goal"])
            self.assertEqual(self.events[-1][2], "Pip set a goal aside for now: a quarry (it cannot be done now).")

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        with only_goals(WOOD), patch("backend.survival.goals.check_goal", side_effect=RuntimeError("boom")):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                self.tend(1.0)
                self.tend(2.0)
        self.assertEqual(len(logs.output), 1)

    def test_reaching_a_goal_gives_a_pending_ask_a_fresh_id(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            ask_for_goal(self.state, "dawn", 50.0)  # a choice already pending, as if Jev were still
                                                     # working out whether to keep the goal
            old_id = goal_state(self.state)["goal_due"]["id"]
            self.state["inventory"].update(oak_log=4, wooden_pickaxe=1)
            brain = self.tend(100.0)
            self.assertIsNone(brain["goal"])
            self.assertNotEqual(brain["goal_due"]["id"], old_id)
            self.assertEqual(brain["goal_due"]["reasons"], ["dawn", "reached"])

    def test_giving_up_a_goal_gives_a_pending_ask_a_fresh_id(self):
        with only_goals(WOOD, STONE):
            adopt_goal(self.state, "quarry", "jev", "Stone next.", 0.0)  # the woodpile is not settled
            ask_for_goal(self.state, "dawn", 0.0)
            old_id = goal_state(self.state)["goal_due"]["id"]
            brain = self.tend(1.0)
            self.assertIsNone(brain["goal"])
            self.assertNotEqual(brain["goal_due"]["id"], old_id)
            self.assertEqual(brain["goal_due"]["reasons"], ["dawn", "given_up"])

    def test_a_second_reach_of_the_same_goal_logs_nothing_more(self):
        with only_goals(WOOD):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            self.tend(1.0)
            self.state["inventory"].update(oak_log=4, wooden_pickaxe=1)
            mood = self.state["vitals"]["mood"]
            self.tend(100.0)  # reached once: the notable event and the mood reward
            self.assertEqual(self.events[-1][1:], ("goal", "Pip reached a goal: a woodpile."))
            self.assertEqual(self.state["vitals"]["mood"], min(100.0, mood + 15.0))
            # a stale answer re-adopts the completed goal (as store_goal's id check would normally
            # have prevented) and the next check finds it complete again: no second celebration.
            adopt_goal(self.state, "woodpile", "utility", "", 100.0)
            events_before, mood_after_first = len(self.events), self.state["vitals"]["mood"]
            brain = self.tend(200.0)
            self.assertIsNone(brain["goal"])
            self.assertEqual(len(self.events), events_before)
            self.assertEqual(self.state["vitals"]["mood"], mood_after_first)

    def test_a_goal_adopted_at_night_is_not_set_aside_before_1200_daylight_seconds_pass(self):
        with only_goals(LATER):
            adopt_goal(self.state, "later", "jev", "Some day.", 0.0)  # e.g. late at night
            self.tend(1.0)
            brain = self.tend(1300.0, "dawn")  # a long gap until dawn: not stalled (under STALL)
            self.assertIsNotNone(brain["goal"])
            # 1000 seconds pass, all of them daylight since this morning began at 1300.0: even
            # though best_at (1.0) is long past IDLE by raw elapsed time, only today's daylight counts
            self.assertIsNotNone(self.tend(2300.0)["goal"])
            # past 1200 daylight seconds since dawn, and nothing else is on offer for it: given up
            brain = self.tend(2550.0)
            self.assertIsNone(brain["goal"])
            self.assertEqual(self.events[-1][2], "Pip set a goal aside for now: later (nothing to do for it now).")

    def test_a_bad_plan_extra_is_left_out_logged_once_and_never_stalls_the_plan(self):
        forget_logged()
        extras = [lambda s, goal: "not a dict", lambda s, goal: {"kind": "wander"},  # no "text"
                  lambda s, goal: {"text": "Bring something odd", "value": object()},  # not JSON-safe
                  lambda s, goal: {"text": "Take time to wander", "kind": "wander"}]  # good
        with only_goals(WOOD), patch("backend.survival.goals.PLAN_EXTRAS", extras):
            adopt_goal(self.state, "woodpile", "jev", "Wood first.", 0.0)
            with self.assertLogs("backend.survival.goals", level="ERROR") as logs:
                plan = self.tend(1.0)["goal"]["plan"]
        self.assertEqual(plan[-1], {"text": "Take time to wander", "done": False, "step": None, "kind": "wander"})
        self.assertEqual(len(plan), 3)  # the 2 milestones plus the one good extra: the 3 bad ones left out
        self.assertEqual(len(logs.output), 3)  # each distinct bad entry logged once

    def test_a_goal_that_idles_past_idle_but_stays_workable_is_kept(self):
        with only_goals(ONLY), goal_only_purpose():
            adopt_goal(self.state, "only", "jev", "Mine alone.", 0.0)
            self.tend(1.0)
            brain = self.tend(IDLE + 70.0)  # never workable is False for ONLY: never idle
            self.assertIsNotNone(brain["goal"])

    def test_a_goal_that_idles_at_night_is_kept(self):
        night = ActionContext(grid=forest(), clock_at=lambda at: NIGHT, planner=lambda *args: [],
                              events=self.events, db=self.s.db)

        def tend_night(at):
            tend_goal(self.state, night, at, None)
            return goal_state(self.state)

        with only_goals(WOOD, LATER):
            adopt_goal(self.state, "later", "jev", "Some day.", 0.0)  # nothing digs stone: not workable
            tend_night(1.0)
            brain = tend_night(IDLE + 70.0)
            self.assertIsNotNone(brain["goal"])


class BrainTests(unittest.TestCase):
    def test_the_brain_asks_for_a_goal_after_its_first_vitals_step(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            hatch(registry, random.Random(8), timestamp=BORN)
            state = tick_life(registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertEqual(state["brain"]["goal_due"]["reasons"], ["no_goal"])

    def test_a_dawn_reached_through_catch_up_gives_exactly_one_plan(self):
        # STALL is patched huge so the goal (no real progress across the run) is not given up as
        # stalled at the very dawn this test crosses: that is a different path (goals ~454), tested
        # elsewhere (test_a_goal_without_progress_for_a_day_is_set_aside_at_dawn); this test is only
        # about the dawn plan *rewrite* firing exactly once through a catch-up run.
        with only_goals(WOOD), patch("backend.survival.goals.STALL", 10.0 * DAY_SECONDS), \
             tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            hatch(registry, random.Random(8), timestamp=BORN)
            path = registry.world_path(registry.active_life())
            world = SurvivalWorld(path)
            with world.transaction() as db:
                state = read_state(db)
                adopt_goal(state, "woodpile", "utility", "Wood first.", BORN)
                write_state(db, state)
            tick_life(registry, BORN + 1.0, scale=1.0, mind=BRAIN)  # the goal's first (non-dawn) plan
            plans = lambda: [event for event in world.events(500) if "'s plan for today" in event["text"]]
            self.assertEqual(len(plans()), 1)
            # a big catch-up jump, crossing one dawn boundary over many small vitals steps
            tick_life(registry, BORN + DAY_SECONDS + 50.0, scale=1.0, mind=BRAIN)
            self.assertEqual(len(plans()), 2)  # exactly one more: the dawn rewrite, not one per step


if __name__ == "__main__":
    unittest.main()

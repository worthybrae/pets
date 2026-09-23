import unittest
from unittest.mock import patch

from backend.survival.actions import ensure_actions
from backend.survival.grid import Grid
from backend.survival.script import rest_plan, scripted_plan
from backend.survival.vitals import START_VITALS

MORNING = {"phase": "day", "seconds_into_day": 1200.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}
TREE = (5, 0, 0)  # trunk x, trunk z, ground height: logs at y 1 to 4
NO_TREES_THOUGHT = "No trees here. I'll look further out."


def forest(cells=None):
    """Flat stone with one oak trunk at x=5, z=0 (logs at y 1 to 4), with `cells` overriding single cells."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if (x, z) == (5, 0) and 1 <= y <= 4:
            return "oak_log"
        return "stone" if y <= 0 else "air"

    return Grid(rule)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


class RestPlanTests(unittest.TestCase):
    def test_sleeps_at_night_or_when_exhausted(self):
        self.assertEqual(rest_plan(pet(), forest(), 0.0, NIGHT),
                         [{"kind": "sleep", "thought": "It's dark. Time to curl up and sleep."}])
        tired = pet(vitals={**START_VITALS, "energy": 5.0})
        self.assertEqual(rest_plan(tired, forest(), 0.0, MORNING)[0]["thought"], "I'm too tired to keep my eyes open.")

    def test_waits_for_nightfall_at_most_a_minute_at_a_time(self):
        self.assertEqual(rest_plan(pet(), forest(), 0.0, MORNING), [{"kind": "wait", "seconds": 60.0}])
        dusk = {**MORNING, "phase": "dusk", "seconds_into_day": 2390.0}
        self.assertEqual(rest_plan(pet(), forest(), 0.0, dusk)[0]["seconds"], 10.0)
        fast = {**MORNING, "seconds_into_day": 2399.5, "time_scale": 60.0}
        self.assertEqual(rest_plan(pet(), forest(), 0.0, fast)[0]["seconds"], 1.0)


@patch("backend.survival.script.trees_near", lambda seed, x, z, radius: [TREE])
class ScriptedPlanTests(unittest.TestCase):
    def test_walks_to_the_nearest_tree_and_chops_it_bottom_up(self):
        plan = scripted_plan(pet(), forest(), 0.0, MORNING)
        self.assertEqual(plan[0], {"kind": "walk", "target": [5, 1, 0], "reach": 2.0,
                                   "thought": "That tree has good wood."})
        self.assertEqual([step["target"] for step in plan[1:]], [[5, 1, 0], [5, 2, 0], [5, 3, 0], [5, 4, 0]])
        self.assertEqual({step["kind"] for step in plan[1:]}, {"mine"})

    def test_logs_become_planks_before_more_chopping(self):
        plan = scripted_plan(pet(inventory={"oak_log": 2}), forest(), 0.0, MORNING)
        self.assertEqual(plan, [{"kind": "craft", "recipe": "planks", "thought": "Logs make good planks."}])

    def test_skips_chopped_logs_and_trees_where_a_step_failed(self):
        chopped = forest({(5, 1, 0): "air", (5, 2, 0): "air"})
        self.assertEqual([step["target"] for step in scripted_plan(pet(), chopped, 0.0, MORNING)[1:]],
                         [[5, 3, 0], [5, 4, 0]])
        failed = pet()
        failed["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                     "target": {"x": 5, "y": 1, "z": 0}, "reason": "no way there"}]
        self.assertEqual(scripted_plan(failed, forest(), 0.0, MORNING)[0]["thought"], NO_TREES_THOUGHT)

    def test_sleep_comes_first_at_night(self):
        self.assertEqual(scripted_plan(pet(), forest(), 0.0, NIGHT)[0]["kind"], "sleep")

    def test_without_trees_it_walks_out_in_the_day_s_direction(self):
        with patch("backend.survival.script.trees_near", lambda seed, x, z, radius: []), \
                patch("backend.survival.script.terrain_height", lambda x, z, seed: 0):
            plan = scripted_plan(pet(), forest(), 0.0, {**MORNING, "day_number": 2})
        self.assertEqual(plan, [{"kind": "walk", "target": [-48, 1, 0], "reach": 3.0, "thought": NO_TREES_THOUGHT}])


if __name__ == "__main__":
    unittest.main()

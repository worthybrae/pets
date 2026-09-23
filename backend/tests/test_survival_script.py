import unittest

from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.script import rest_plan
from backend.survival.vitals import START_VITALS

MORNING = {"phase": "day", "seconds_into_day": 1200.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {"phase": "night", "seconds_into_day": 3000.0, "time_scale": 1.0, "day_number": 1}


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def ctx(clock):
    """An ActionContext frozen at `clock` over flat stone."""
    return ActionContext(grid=Grid(lambda x, y, z: "stone" if y <= 0 else "air"), clock_at=lambda at: clock,
                         planner=rest_plan, events=[])


class RestPlanTests(unittest.TestCase):
    def test_sleeps_at_night_or_when_exhausted(self):
        self.assertEqual(rest_plan(pet(), ctx(NIGHT), 0.0),
                         [{"kind": "sleep", "thought": "It's dark. Time to curl up and sleep."}])
        tired = pet(vitals={**START_VITALS, "energy": 5.0})
        self.assertEqual(rest_plan(tired, ctx(MORNING), 0.0)[0]["thought"], "I'm too tired to keep my eyes open.")

    def test_waits_for_nightfall_at_most_a_minute_at_a_time(self):
        self.assertEqual(rest_plan(pet(), ctx(MORNING), 0.0), [{"kind": "wait", "seconds": 60.0}])
        dusk = {**MORNING, "phase": "dusk", "seconds_into_day": 2390.0}
        self.assertEqual(rest_plan(pet(), ctx(dusk), 0.0)[0]["seconds"], 10.0)
        fast = {**MORNING, "seconds_into_day": 2399.5, "time_scale": 60.0}
        self.assertEqual(rest_plan(pet(), ctx(fast), 0.0)[0]["seconds"], 1.0)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every goal, purpose and reason)
from backend.survival.camp import leave_camp, observe_camp
from backend.survival.goals import meets_need
from backend.survival.memory import places, remember
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.tests.test_survival_expedition import DUSK, FLAT, MORNING, NIGHT, Expedition

LATE = {"phase": "day", "seconds_into_day": 2000.0, "time_scale": 1.0, "day_number": 2}


class CampTests(unittest.TestCase):
    def setUp(self):
        self.pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            self.pet.set_out()
        self.pet.go(101, 1)

    def test_far_out_late_in_the_day_making_camp_is_a_need(self):
        camp = PURPOSES["camp"]
        self.assertFalse(camp.valid(self.pet.situation()))  # midday: travel on
        s = self.pet.situation(LATE)
        self.assertTrue(camp.valid(s))
        self.assertEqual(camp.score(s), 85.0)
        self.assertTrue(meets_need(s, "camp", camp.score(s)))
        self.assertEqual(camp.score(self.pet.situation(DUSK)), 95.0)

    def test_at_dusk_it_digs_in_by_a_campfire_with_torches_and_roofs_itself_over(self):
        camp = PURPOSES["camp"]
        steps = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(steps, [{"kind": "place", "target": [102, 1, 1], "block": "campfire"},
                                 {"kind": "place", "target": [100, 1, 1], "block": "torch"},
                                 {"kind": "place", "target": [101, 1, 2], "block": "torch"},
                                 {"kind": "mine", "target": [101, 0, 1]}])
        self.pet.world.carry_out(steps)
        self.pet.state["position"]["y"] = 0.0  # it dropped into the hole
        roof = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(roof, [{"kind": "place", "target": [101, 1, 1], "block": "dirt"}])
        self.pet.world.carry_out(roof)
        context = self.pet.context(DUSK)
        observe_camp(self.pet.state, {**roof[0], "purpose": "camp"}, context, 10.0)
        self.assertEqual([(place["x"], place["y"], place["z"]) for place in places(self.pet.world.db, ("outpost",))],
                         [(101, 0, 1)])
        self.assertEqual(context.events, [(10.0, "camp", "Pip dug in for the night and made a camp.")])
        self.assertEqual(camp.plan(self.pet.situation(DUSK), context)[0]["kind"], "wait")  # for nightfall
        self.assertFalse(camp.valid(self.pet.situation(NIGHT)))  # dug in: sleep takes over
        self.assertTrue(PURPOSES["sleep"].valid(self.pet.situation(NIGHT)))
        walk = [{"kind": "walk", "target": [120, 1, 1], "reach": 3.0}]
        self.assertEqual(leave_camp(self.pet.situation(NIGHT), walk), walk)  # a flight at night: the roof stays
        self.pet.state["brain"]["purpose"] = "gather_stone"
        dig = [{"kind": "mine", "target": [101, -1, 1]}]  # a staircase down from the hole
        self.assertEqual(leave_camp(self.pet.situation(MORNING), dig), [{"kind": "mine", "target": [101, 1, 1]}, *dig])

    def test_it_goes_back_to_an_outpost_near_it(self):
        self.pet.world.grid.put(110, 0, 1, "air")  # an old camp's hole, its roof off
        remember(self.pet.world.db, "outpost", (110, 0, 1), 0.0, "camp")
        self.assertEqual(PURPOSES["camp"].plan(self.pet.situation(DUSK), self.pet.context(DUSK)),
                         [{"kind": "walk", "target": [110, 1, 1], "reach": 1.0, "whole": True},
                          {"kind": "walk", "target": [110, 0, 1], "reach": 0.0}])
        self.assertEqual(self.pet.state["brain"]["expedition"]["camp"], [110, 0, 1])

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        self.pet.state["brain"]["expedition"]["camp"] = "not a cell"
        with self.assertLogs("backend.survival.camp", level="ERROR") as logs:
            for at in (1.0, 2.0):
                observe_camp(self.pet.state, {"kind": "place", "purpose": "camp", "target": [1, 1, 1], "block": "dirt"},
                             self.pet.context(), at)
        self.assertEqual(len(logs.output), 1)


if __name__ == "__main__":
    unittest.main()

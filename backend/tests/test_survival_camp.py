import unittest
from unittest.mock import patch

from backend.survival import brain  # registers every goal, purpose and reason; also used directly below
from backend.survival.camp import camp_spot, leave_camp, new_camp, observe_camp, outpost_near, settled
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


class CampLoopFixTests(unittest.TestCase):
    """Fix round 1, Critical 1: a camp that kept failing looped about once a game second, choosing
    camp again and again (the review's probes: a berry bush or mushroom beside the spot, a torch
    or campfire already there, an unreachable spot, a reused outpost missing a wall, and a roof
    step planned onto a cell already taken)."""

    def setUp(self):
        self.pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            self.pet.set_out()
        self.pet.go(101, 1)

    def test_a_berry_bush_or_mushroom_beside_the_spot_is_left_alone_not_placed_over(self):
        self.pet.world.grid.put(102, 1, 1, "berry_bush_ripe")  # the nearest ground spot: not free to build on
        camp = PURPOSES["camp"]
        steps = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(steps, [{"kind": "place", "target": [100, 1, 1], "block": "campfire"},
                                 {"kind": "place", "target": [101, 1, 2], "block": "torch"},
                                 {"kind": "place", "target": [101, 1, 0], "block": "torch"},
                                 {"kind": "mine", "target": [101, 0, 1]}])
        self.pet.world.carry_out(steps)  # every placement lands on open ground; the bush stays put
        self.assertEqual(self.pet.world.grid.material(102, 1, 1), "berry_bush_ripe")

    def test_a_campfire_or_torch_already_standing_is_counted_not_placed_again(self):
        camp = PURPOSES["camp"]
        first = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.pet.world.carry_out(first[:1])  # only the campfire went down before the batch was cut short
        again = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(again, [{"kind": "place", "target": [100, 1, 1], "block": "torch"},
                                 {"kind": "place", "target": [101, 1, 2], "block": "torch"},
                                 {"kind": "mine", "target": [101, 0, 1]}])
        self.pet.world.carry_out(again)  # no "that cell is taken": the campfire is not placed twice
        self.assertEqual(self.pet.world.grid.material(102, 1, 1), "campfire")

    def test_a_spot_a_walk_just_failed_near_is_not_tried_again_at_once(self):
        # Only (105, 1, 1) is diggable; the rest is stone the pet has no pickaxe for.
        grid = self.pet.world.grid
        for dx in range(-6, 7):
            for dz in range(-6, 7):
                grid.put(101 + dx, 0, 1 + dz, "stone")
        grid.put(105, 0, 1, "grass")
        self.assertEqual(new_camp(self.pet.situation(DUSK)), (105, 1, 1))
        self.pet.state["recent_actions"] = [{"kind": "walk", "result": "failed", "code": "no_path",
                                             "target": {"x": 105.0, "y": 1.0, "z": 1.0}}]
        s = self.pet.situation(DUSK)
        self.assertIsNone(new_camp(s))  # not tried again at once
        self.assertFalse(PURPOSES["camp"].valid(s))  # nowhere left: camp is not on offer

    def test_an_outpost_with_a_wall_dug_away_is_not_reused(self):
        grid = self.pet.world.grid
        grid.put(120, 0, 1, "air")  # an old camp's hole, its roof off
        remember(self.pet.world.db, "outpost", (120, 0, 1), 0.0, "camp")
        self.assertEqual(outpost_near(self.pet.situation(DUSK)), (120, 0, 1))
        grid.put(119, 0, 1, "air")  # a wall dug away since
        self.assertIsNone(outpost_near(self.pet.situation(DUSK)))

    def test_a_roof_cell_already_solid_is_treated_as_settled_not_planned_again(self):
        camp = PURPOSES["camp"]
        steps = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.pet.world.carry_out(steps)
        self.pet.state["position"]["y"] = 0.0  # it dropped into the hole
        self.pet.world.grid.put(101, 1, 1, "dirt")  # the roof cell is already solid (a batch planned twice)
        self.pet.world.grid.put(102, 0, 1, "air")  # a wall gone: in_camp alone would not call this settled
        s = self.pet.situation(DUSK)
        self.assertTrue(settled(s))
        self.assertEqual(camp.plan(s, self.pet.context(DUSK)), [{"kind": "wait", "seconds": 60.0}])  # for nightfall
        self.assertFalse(camp.valid(self.pet.situation(NIGHT)))  # dug in: sleep takes over, not planned again


class CampWiringFixTests(unittest.TestCase):
    """Fix round 1, Minor 2 (leave_camp crash-guarded in brain_plan) and Minor 4 (coverage named in
    the brief: nowhere to dig, the water/lava/reserved exclusions, and the morning exemption for
    sleep and camp in leave_camp, through brain_plan, which also covers its wiring)."""

    def setUp(self):
        self.pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            self.pet.set_out()
        self.pet.go(101, 1)

    def dig_in_and_seal(self):
        """Dig in, roof over, and remember the outpost, as a full camp does by dusk."""
        camp = PURPOSES["camp"]
        steps = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.pet.world.carry_out(steps)
        self.pet.state["position"]["y"] = 0.0
        roof = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.pet.world.carry_out(roof)
        context = self.pet.context(DUSK)
        observe_camp(self.pet.state, {**roof[0], "purpose": "camp"}, context, 10.0)

    def plan_as(self, purpose, clock, at=20.0):
        brainy = self.pet.state["brain"]
        brainy.update(purpose=purpose, batches=0, replans=0, planned_at=None, reflex=None)
        self.pet.state["last_failure"] = None
        context = self.pet.context(clock)
        context.planner = brain.brain_plan
        return brain.brain_plan(self.pet.state, context, at)

    def test_camp_is_not_on_offer_with_nowhere_to_dig_in(self):
        grid = self.pet.world.grid
        for dx in range(-6, 7):
            for dz in range(-6, 7):
                grid.put(101 + dx, 0, 1 + dz, "stone")
        s = self.pet.situation(DUSK)
        self.assertFalse(PURPOSES["camp"].valid(s))
        self.assertEqual(PURPOSES["camp"].plan(s, self.pet.context(DUSK)), [])

    def test_camp_spot_excludes_water_lava_and_a_reserved_ground(self):
        s = self.pet.situation(DUSK)
        self.assertTrue(camp_spot(s, (101, 1, 1)))
        self.pet.world.grid.put(102, 1, 1, "water")  # beside the hole, not the wall under it
        self.assertFalse(camp_spot(self.pet.situation(DUSK), (101, 1, 1)))
        self.pet.world.grid.put(102, 1, 1, "lava")
        self.assertFalse(camp_spot(self.pet.situation(DUSK), (101, 1, 1)))
        self.pet.world.grid.put(102, 1, 1, "air")
        self.pet.world.grid.claims.add((101, 0, 1))  # something Mimo built or tends
        self.assertFalse(camp_spot(self.pet.situation(DUSK), (101, 1, 1)))

    def test_a_crashing_leave_camp_is_logged_once_and_planning_continues(self):
        self.dig_in_and_seal()
        forget_logged()
        with patch("backend.survival.brain.leave_camp", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.brain", level="ERROR") as logs:
            first = self.plan_as("explore", MORNING)
            second = self.plan_as("explore", MORNING)  # the same error again: no new log
        self.assertEqual(len(logs.output), 1)
        self.assertEqual(first, [{"kind": "walk", "target": [56, 1, -44], "reach": 3.0, "whole": True,
                                 "purpose": "explore"}])  # planned as if leave_camp weren't there
        self.assertTrue(second and all(step.get("purpose") == "explore" for step in second))

    def test_leave_camp_through_brain_plan_spares_sleep_and_camp_but_not_other_purposes(self):
        self.dig_in_and_seal()
        self.pet.state["vitals"]["energy"] = 10.0  # exhausted: sleep is valid even by day
        # Asleep inside its sealed camp by day: the roof stays (leave_camp's purpose exemption).
        self.assertEqual(self.plan_as("sleep", MORNING), [{"kind": "sleep", "purpose": "sleep"}])
        # Any other purpose planned inside the sealed camp takes the roof off first.
        self.assertEqual(self.plan_as("explore", MORNING),
                         [{"kind": "mine", "target": [101, 1, 1], "purpose": "explore"},
                          {"kind": "walk", "target": [56, 1, -44], "reach": 3.0, "whole": True,
                           "purpose": "explore"}])


if __name__ == "__main__":
    unittest.main()

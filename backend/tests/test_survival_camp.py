import unittest
from unittest.mock import patch

from backend.services.crafting import BLOCKS, add_item
from backend.survival import brain  # registers every goal, purpose and reason; also used directly below
from backend.survival.camp import (
    camp_spot, in_camp, leave_camp, new_camp, observe_camp, outpost_near, roof_block, settled,
)
from backend.survival.carrying import full, settle
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


FILLER = {f"item_{n}": 1 for n in range(13)}  # 13 stacks of nothing a camp uses or may drop


class FullArmsTests(unittest.TestCase):
    """L4b final fix wave, I1: with 16 stacks and no building block, the block Mimo dug out for its
    roof was left behind (carrying's overflow rule), and it slept in an open hole, which a gloomling
    on the rim hits through (seed 3: 100 to 35 health in a night). It makes room first now, by
    dropping a stack of what gives way to food, and with nothing it may drop it does not dig in."""

    def setUp(self):
        self.pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            self.pet.set_out()
        self.pet.go(101, 1)

    def carry(self, steps):
        """Do camp steps at once, the way they would end, with carrying's rules for what Mimo digs out."""
        inventory = self.pet.state["inventory"]
        for step in steps:
            if step["kind"] == "drop":
                inventory[step["item"]] -= step["amount"]
                if not inventory[step["item"]]:
                    del inventory[step["item"]]
            elif step["kind"] == "mine":
                before = dict(inventory)
                add_item(inventory, BLOCKS[self.pet.world.grid.material(*step["target"])]["drop"])
                settle(inventory, before)  # what does not fit is left behind
                self.pet.world.grid.put(*step["target"], "air")
            else:
                self.pet.world.carry_out([step])

    def test_with_full_arms_it_drops_a_stack_first_so_the_block_it_digs_out_roofs_it_over(self):
        self.pet.state["inventory"] = {**FILLER, "bread": 4, "torch": 4, "wool": 5}
        s = self.pet.situation(DUSK)
        self.assertTrue(full(s.inventory))
        self.assertIsNone(roof_block(s))
        camp = PURPOSES["camp"]
        self.assertTrue(camp.valid(s))
        steps = camp.plan(s, self.pet.context(DUSK))
        self.assertEqual(steps, [{"kind": "place", "target": [102, 1, 1], "block": "torch"},
                                 {"kind": "place", "target": [100, 1, 1], "block": "torch"},
                                 {"kind": "drop", "item": "wool", "amount": 5},
                                 {"kind": "mine", "target": [101, 0, 1]}])
        self.carry(steps)
        self.assertEqual(self.pet.state["inventory"]["dirt"], 1)  # it fits: the roof
        self.pet.state["position"]["y"] = 0.0  # it dropped into the hole
        roof = camp.plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual(roof, [{"kind": "place", "target": [101, 1, 1], "block": "dirt"}])
        self.carry(roof)
        self.assertTrue(in_camp(self.pet.situation(DUSK)))

    def test_with_room_made_by_its_torches_it_drops_nothing(self):
        self.pet.state["inventory"] = {**FILLER, "bread": 4, "torch": 2, "wool": 5}
        steps = PURPOSES["camp"].plan(self.pet.situation(DUSK), self.pet.context(DUSK))
        self.assertEqual([step["kind"] for step in steps], ["place", "place", "mine"])  # the torches free a stack

    def test_a_spot_is_offered_when_the_campfire_it_puts_down_frees_the_roofs_stack(self):
        # Follow-up 2 (F2): camp_spot judged room for the roof on its arms as they were, not as
        # plan_camp leaves them once the fire and torches are down; two trips spent a night out on
        # the surface for it (seed 13: a campfire stack, and 3 sticks the campfire would use).
        self.pet.state["inventory"] = {**FILLER, "bread": 4, "torch": 4, "campfire": 1}  # 16, nothing to drop
        s = self.pet.situation(DUSK)
        self.assertTrue(full(s.inventory))
        camp = PURPOSES["camp"]
        self.assertTrue(camp.valid(s))
        steps = camp.plan(s, self.pet.context(DUSK))
        self.assertEqual(steps, [{"kind": "place", "target": [102, 1, 1], "block": "campfire"},
                                 {"kind": "place", "target": [100, 1, 1], "block": "torch"},
                                 {"kind": "place", "target": [101, 1, 2], "block": "torch"},
                                 {"kind": "mine", "target": [101, 0, 1]}])  # no drop: the fire made room
        self.carry(steps)
        self.assertEqual(self.pet.state["inventory"]["dirt"], 1)  # its roof
        made = {**{f"item_{n}": 1 for n in range(12)}, "bread": 4, "torch": 4, "sticks": 3, "oak_log": 3}
        self.pet.state["inventory"] = made  # 16 stacks: the campfire it makes uses the sticks' stack up
        self.pet.world.grid.put(101, 0, 1, "grass")
        for cell in ((102, 1, 1), (100, 1, 1), (101, 1, 2)):
            self.pet.world.grid.put(*cell, "air")
        s = self.pet.situation(DUSK)
        self.assertTrue(camp.valid(s))
        self.assertEqual([step["kind"] for step in camp.plan(s, self.pet.context(DUSK))],
                         ["craft", "place", "place", "place", "mine"])

    def test_with_full_arms_and_nothing_it_may_drop_it_does_not_camp(self):
        for spare in ({"leather": 3},  # gear still wants it: no armor yet
                      {"gold_ingot": 2, "iron_pickaxe": 1}):  # the pickaxe ladder counts it
            arms = {**FILLER, "bread": 4, "torch": 4, **spare}
            while len(arms) > 16:
                arms.pop(next(item for item in arms if item.startswith("item_")))
            self.pet.state["inventory"] = arms
            s = self.pet.situation(DUSK)
            self.assertTrue(full(s.inventory))
            self.assertIsNone(new_camp(s))
            self.assertFalse(PURPOSES["camp"].valid(s))  # it sleeps where it stands
        del self.pet.state["inventory"]["gold_ingot"]  # a stack free: the block it digs out fits
        self.assertTrue(PURPOSES["camp"].valid(self.pet.situation(DUSK)))

    def test_an_outpost_is_gone_back_to_only_with_a_roof_block_in_hand(self):
        self.pet.world.grid.put(110, 0, 1, "air")  # an old camp's hole, its roof off
        remember(self.pet.world.db, "outpost", (110, 0, 1), 0.0, "camp")
        self.assertEqual(outpost_near(self.pet.situation(DUSK)), (110, 0, 1))  # PACKED has dirt
        del self.pet.state["inventory"]["dirt"]
        s = self.pet.situation(DUSK)
        self.assertIsNone(outpost_near(s))  # nothing to roof it with: it digs in, and the block dug out roofs it
        self.assertEqual(PURPOSES["camp"].plan(s, self.pet.context(DUSK))[-1], {"kind": "mine", "target": [101, 0, 1]})


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

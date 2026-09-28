import sqlite3
import unittest

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, know, places, remember
from backend.survival.reflexes import REFLEXES, fall_depth, reflex_hook
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
LATE = {**DAY, "seconds_into_day": 2100.0}  # within 3 game minutes of dusk


def flat(cells=None):
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("stone" if y <= 0 else "air"))


def holed(column, cells=None):
    """Flat stone with a hole 6 deep under the (x, z) column (air from y -6 to -1)."""
    cells = cells or {}

    def rule(x, y, z):
        if (x, y, z) in cells:
            return cells[(x, y, z)]
        if (x, z) == column and -6 <= y <= -1:
            return "air"
        return "stone" if y <= 0 else "air"

    return Grid(rule)


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def brainy(grid=None, clock=None):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return ActionContext(grid=grid or flat(), clock_at=clock or (lambda at: DAY), planner=brain_plan, events=[],
                         db=db, interrupt=reflex_hook)


def choose(state, purpose):
    ensure_brain(state).update(purpose=purpose, pending=None, chosen_at=0.0, batches=0, replans=0, planned_at=None)


def walk(x, y, z, purpose):
    return {"kind": "walk", "target": [x, y, z], "reach": 0.0, "purpose": purpose}


class ReflexTests(unittest.TestCase):
    def test_m3_reflexes_run_in_priority_order_with_l2s_flee_and_fight_among_them(self):
        # The L5 final fix wave (I4): L5's fence (a veto) and turn_back (backend.survival.frontier) sit after a
        # flight and a fight, which they never cut into.
        self.assertEqual([(reflex.name, reflex.priority) for reflex in REFLEXES],
                         [("surface", 10), ("avoid_drop", 20), ("flee_fire", 25), ("flee", 30), ("eat_now", 40),
                          ("fight", 40), ("fence", 45), ("take_herb", 45), ("warm_up", 50), ("turn_back", 55),
                          ("head_home", 60), ("collapse", 70)])  # W1: take_herb; W2: flee_fire (sky_reflexes)

    def test_collapse_sets_the_plan_aside_and_gives_it_back(self):
        state = pet(vitals={**START_VITALS, "energy": 5.0})
        choose(state, "explore")
        state["queue"] = [walk(9, 1, 0, "explore")]
        ctx = brainy()
        advance_actions(state, ctx, 1.0)
        brain = state["brain"]
        self.assertEqual((state["action"]["kind"], state["action"]["purpose"], brain["reflex"]),
                         ("sleep", "collapse", "collapse"))
        self.assertEqual(brain["set_aside"], [walk(9, 1, 0, "explore")])
        self.assertIn(("reflex", "Pip collapsed from exhaustion."), [event[1:] for event in ctx.events])
        state["vitals"]["energy"] = 96.0
        advance_actions(state, ctx, 2.0)
        self.assertEqual((state["action"]["kind"], state["action"]["purpose"]), ("walk", "explore"))
        self.assertIsNone(brain["reflex"])
        self.assertEqual(brain["reflex_ends"], {"collapse": 2.0})
        self.assertIn("reflex_ended", brain["pending"]["reasons"])

    def test_collapse_still_sleeps_where_it_is_when_the_walk_to_the_bed_fails(self):
        """Fix wave minor 3: the sleep after the walk to a bed is kept (`keep`), so a failed walk
        does not drop it with the rest of the plan."""
        boxed = {cell: "stone" for x, z in ((1, 0), (-1, 0), (0, 1), (0, -1)) for cell in ((x, 1, z), (x, 2, z))}
        grid = flat(boxed)
        grid.put(2, 1, 0, "bed")  # within 8 blocks, but Mimo is walled in
        state = pet(vitals={**START_VITALS, "energy": 5.0})
        choose(state, "explore")
        ctx = brainy(grid)
        advance_actions(state, ctx, 1.0)
        advance_actions(state, ctx, 2.0)
        failed = [(entry["kind"], entry["code"]) for entry in state["recent_actions"] if entry["result"] == "failed"]
        self.assertEqual(failed, [("walk", "no_path")])
        self.assertEqual((state["action"]["kind"], state["action"]["purpose"]), ("sleep", "collapse"))
        self.assertNotIn("bed", state["action"])  # where it stands, not in the bed

    def test_cleanup_steps_come_back_after_a_reflex_even_without_a_purpose(self):
        state = pet()
        mine_back = {"kind": "mine", "target": [1, 1, 0], "keep": True, "purpose": "craft_tools"}
        state["brain"] = {**ensure_brain(state), "purpose": None, "pending": None, "reflex": "collapse",
                          "set_aside": [walk(9, 1, 0, "explore"), mine_back]}
        self.assertEqual(brain_plan(state, brainy(), 1.0), [mine_back])
        self.assertIsNone(state["brain"]["reflex"])

    def test_the_more_urgent_reflex_goes_first(self):
        state = pet(inventory={"berries": 1}, vitals={**START_VITALS, "energy": 5.0, "hunger": 10.0})
        choose(state, "explore")
        state["queue"] = [walk(9, 1, 0, "explore")]
        ctx = brainy()
        advance_actions(state, ctx, 1.0)
        self.assertEqual((state["action"]["kind"], state["brain"]["reflex"]), ("eat", "eat_now"))
        advance_actions(state, ctx, 3.0)
        self.assertEqual((state["action"]["kind"], state["brain"]["reflex"]), ("sleep", "collapse"))
        self.assertEqual(state["brain"]["set_aside"], [walk(9, 1, 0, "explore")])

    def test_head_home_near_dusk_cuts_a_walk_and_sets_it_aside(self):
        state = pet()
        choose(state, "gather_wood")
        state["queue"] = [walk(0, 1, 9, "gather_wood")]
        ctx = brainy(clock=lambda at: DAY if at < 1.0 else LATE)
        remember(ctx.db, "home", (20, 1, 0), 0.0)
        advance_actions(state, ctx, 0.5)
        advance_actions(state, ctx, 1.0)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("walk", "interrupted", "head_home"))
        self.assertEqual(state["position"], {"x": 0.0, "y": 1.0, "z": 3.0})
        self.assertEqual((state["action"]["target"], state["action"]["purpose"]),
                         ({"x": 20, "y": 1, "z": 0}, "head_home"))
        self.assertEqual(state["brain"]["set_aside"], [walk(0, 1, 9, "gather_wood")])
        self.assertEqual(state["last_thought"], "It's getting dark. Home, quickly.")

    def test_avoid_drop_vetoes_mining_the_block_under_mimo_over_a_deep_hole(self):
        state = pet()
        choose(state, "mine_ore")
        state["queue"] = [{"kind": "mine", "target": [0, 0, 0], "purpose": "mine_ore"}]
        grid = holed((0, 0), {(0, 0, 0): "coal_ore"})
        ctx = brainy(grid)
        advance_actions(state, ctx, 1.0)
        self.assertEqual(grid.material(0, 0, 0), "coal_ore")
        self.assertEqual(state["position"]["y"], 1.0)
        self.assertEqual((state["last_failure"]["code"], state["last_failure"]["reason"]),
                         ("blocked", "that would be a long fall"))
        self.assertEqual([(place["kind"], place["note"]) for place in places(ctx.db)], [("danger", "drop")])

    def test_a_kept_mine_step_over_a_deep_drop_is_vetoed_once_and_never_runs(self):
        """A cleanup step (`keep`, a portable station's mine-back) that targets the block under
        Mimo over a deep drop must stay vetoed. Task 8 review: the vetoed spec was still at
        queue[0] when fail() ran, so kept_steps kept it (it has `keep`) and the reflex re-vetoed
        the very same step on the next pass instead of dropping it - up to MAX_TAKEOVERS times,
        after which the interrupt check is skipped and the dangerous mine runs anyway."""
        state = pet()
        mine_back = {"kind": "mine", "target": [0, 0, 0], "purpose": "gather_stone", "keep": True}
        state["queue"] = [dict(mine_back)]
        grid = holed((0, 0), {(0, 0, 0): "dirt"})
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        ctx = ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda state, context, at: [],
                            events=[], db=db, interrupt=reflex_hook)
        advance_actions(state, ctx, 1.0)
        self.assertEqual(grid.material(0, 0, 0), "dirt")
        self.assertEqual(state["position"]["y"], 1.0)
        self.assertEqual(state["inventory"], {})
        for until in (2.0, 3.0, 4.0):
            state["queue"] = [dict(mine_back)]
            advance_actions(state, ctx, until)
        self.assertEqual(grid.material(0, 0, 0), "dirt")
        self.assertEqual(state["position"]["y"], 1.0)

    def test_avoid_drop_cuts_a_walk_whose_next_cell_lost_its_floor(self):
        state = pet()
        choose(state, "explore")
        state["queue"] = [walk(5, 1, 0, "explore")]
        grid = holed((2, 0))
        ctx = brainy(grid)
        advance_actions(state, ctx, 0.4)
        grid.put(2, 0, 0, "air")
        advance_actions(state, ctx, 0.5)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("walk", "interrupted", "avoid_drop"))
        path = [(entry["x"], entry["y"], entry["z"]) for entry in state["action"]["path"]]
        self.assertNotIn((2, 1, 0), path)
        self.assertEqual((path[-1], state["action"]["purpose"]), ((5, 1, 0), "explore"))

    def test_warm_up_places_a_carried_furnace_or_walks_home(self):
        cold = pet(inventory={"furnace": 1}, vitals={**START_VITALS, "warmth": 20.0})
        self.assertEqual(reflex_hook(cold, brainy(), 0.0), "warm_up")
        self.assertEqual(cold["queue"], [{"kind": "place", "target": [1, 1, 0], "block": "furnace", "purpose": "warm_up"}])
        homeward = pet(vitals={**START_VITALS, "warmth": 20.0})
        ctx = brainy()
        remember(ctx.db, "home", (30, 1, 0), 0.0)
        self.assertEqual(reflex_hook(homeward, ctx, 0.0), "warm_up")
        self.assertEqual(homeward["queue"], [walk(30, 1, 0, "warm_up")])
        self.assertIsNone(reflex_hook(pet(vitals={**START_VITALS, "warmth": 20.0}), brainy(), 0.0))

    def test_surface_mines_a_ceiling_or_heads_for_the_shore(self):
        under = pet(vitals={**START_VITALS, "air": 30.0})
        self.assertEqual(reflex_hook(under, brainy(flat({(0, 1, 0): "water", (0, 2, 0): "dirt"})), 0.0), "surface")
        self.assertEqual(under["queue"], [{"kind": "mine", "target": [0, 2, 0], "purpose": "surface"}])
        lake = Grid(lambda x, y, z: ("water" if x <= 2 else "stone") if y <= 0 else "air")
        floating = pet(vitals={**START_VITALS, "air": 30.0})
        self.assertEqual(reflex_hook(floating, brainy(lake), 0.0), "surface")
        self.assertEqual(floating["queue"], [walk(3, 1, 0, "surface")])

    def test_eat_now_never_eats_food_known_to_be_poisonous(self):
        state = pet(inventory={"red_mushroom": 2, "apple": 1}, vitals={**START_VITALS, "hunger": 10.0})
        ctx = brainy()
        know(ctx.db, "red_mushroom", "poisonous", 0.0)
        self.assertEqual(reflex_hook(state, ctx, 0.0), "eat_now")
        self.assertEqual(state["queue"], [{"kind": "eat", "item": "apple", "purpose": "eat_now"}])
        sick = pet(inventory={"red_mushroom": 2}, vitals={**START_VITALS, "hunger": 10.0})
        self.assertIsNone(reflex_hook(sick, ctx, 0.0))

    def test_warm_up_lights_a_carried_campfire_or_walks_to_one(self):
        cold = pet(inventory={"campfire": 1, "furnace": 1}, vitals={**START_VITALS, "warmth": 20.0})
        self.assertEqual(reflex_hook(cold, brainy(), 0.0), "warm_up")
        self.assertEqual(cold["queue"], [{"kind": "place", "target": [1, 1, 0], "block": "campfire", "purpose": "warm_up"}])
        grid = flat()
        grid.put(12, 1, 0, "campfire")
        wandering = pet(vitals={**START_VITALS, "warmth": 20.0})
        self.assertEqual(reflex_hook(wandering, brainy(grid), 0.0), "warm_up")
        # All the way or not at all: part of the way to a fire can end in a pit.
        self.assertEqual(wandering["queue"],
                         [{"kind": "walk", "target": [12, 1, 0], "reach": 2.0, "whole": True, "purpose": "warm_up"}])
        stuck = pet(vitals={**START_VITALS, "warmth": 20.0})
        stuck["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                    "target": {"x": 12, "y": 1, "z": 0}, "reason": "no way there", "code": "no_path"}]
        self.assertIsNone(reflex_hook(stuck, brainy(grid), 0.0))

    def test_warm_up_keeps_a_running_whole_walk_whole_when_it_sets_it_aside(self):
        """A whole walk (all the way or not at all) that a reflex cuts must resume as a whole
        walk too, or the resumed leg can end in a pit. steps.start_walk must copy `whole` onto
        the running step, and reflexes.set_aside must copy it into the re-queued spec."""
        state = pet()
        choose(state, "gather_wood")
        state["queue"] = [{"kind": "walk", "target": [0, 1, 9], "reach": 0.0, "whole": True,
                           "purpose": "gather_wood"}]
        ctx = brainy()
        advance_actions(state, ctx, 0.5)
        self.assertEqual((state["action"]["kind"], state["action"].get("whole")), ("walk", True))
        state["vitals"]["warmth"] = 20.0
        remember(ctx.db, "home", (20, 1, 0), 0.0)
        advance_actions(state, ctx, 1.0)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("walk", "interrupted", "warm_up"))
        self.assertEqual(state["brain"]["set_aside"],
                         [{"kind": "walk", "target": [0, 1, 9], "reach": 0.0, "whole": True,
                           "purpose": "gather_wood"}])

    def test_avoid_drop_keeps_a_cut_whole_walk_whole_when_it_walks_around(self):
        """avoid_drop's re-walk (plan_avoid_drop's `again`) must also keep `whole`."""
        state = pet()
        choose(state, "explore")
        state["queue"] = [{"kind": "walk", "target": [5, 1, 0], "reach": 0.0, "whole": True, "purpose": "explore"}]
        grid = holed((2, 0))
        ctx = brainy(grid)
        advance_actions(state, ctx, 0.4)
        self.assertEqual((state["action"]["kind"], state["action"].get("whole")), ("walk", True))
        grid.put(2, 0, 0, "air")
        advance_actions(state, ctx, 0.5)
        cut = state["recent_actions"][-1]
        self.assertEqual((cut["kind"], cut["result"], cut["reason"]), ("walk", "interrupted", "avoid_drop"))
        path = [(entry["x"], entry["y"], entry["z"]) for entry in state["action"]["path"]]
        self.assertNotIn((2, 1, 0), path)
        self.assertEqual((path[-1], state["action"]["purpose"], state["action"].get("whole")),
                         ((5, 1, 0), "explore", True))


class FallDepthTests(unittest.TestCase):
    """L3 fix round 1: fall_depth re-implemented "what holds Mimo up" with is_solid alone, so it
    disagreed with Grid.supported once fences and ladders existed (Task 12 made build_pen place
    fences)."""

    def test_fall_depth_down_a_ladder_shaft_is_zero(self):
        grid = flat()
        for y in range(-2, 2):
            grid.put(0, y, 0, "ladder")
        self.assertEqual(fall_depth(grid, (0, 1, 0)), (0, False))

    def test_a_drop_onto_a_fence_top_counts_as_a_fall_past_it(self):
        """A fence is solid ground to the old is_solid check, so it used to be read as an instant,
        zero-depth landing the moment Mimo was even a little above it. It must count as a real fall
        that comes to rest just above the fence (never inside it) instead."""
        grid = flat()
        grid.put(0, 1, 0, "fence")
        self.assertFalse(grid.supported((0, 2, 0)))
        self.assertEqual(fall_depth(grid, (0, 5, 0)), (3, False))


if __name__ == "__main__":
    unittest.main()

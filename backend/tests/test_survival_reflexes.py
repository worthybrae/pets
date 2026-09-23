import sqlite3
import unittest

from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, places, remember
from backend.survival.reflexes import REFLEXES, reflex_hook
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
    def test_m3_reflexes_run_in_priority_order_with_room_for_flee(self):
        self.assertEqual([(reflex.name, reflex.priority) for reflex in REFLEXES][:6],
                         [("surface", 10), ("avoid_drop", 20), ("eat_now", 40), ("warm_up", 50),
                          ("head_home", 60), ("collapse", 70)])

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


if __name__ == "__main__":
    unittest.main()

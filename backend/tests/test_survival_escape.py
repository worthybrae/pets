import sqlite3
import unittest
from collections import deque
from unittest.mock import patch

from backend.services.worldgen import block_at, terrain_height
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.brain import brain_plan
from backend.survival.choosing import Choice, apply_choice
from backend.survival.creatures.hunting import in_a_cave
from backend.survival.escape import (
    POCKET, SURFACE_SEARCH, TRAP_WINDOW, escape_plan, on_surface, roomy, staircase, way_out,
)
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.pathing import moves
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT_60 = {"phase": "night", "seconds_into_day": 2700.0, "time_scale": 60.0, "day_number": 40}


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


def ground():
    """Open ground on the natural surface (y 5 and up is air, as EscapeTests patches it)."""
    return Grid(lambda x, y, z: "stone" if y <= 4 else "air")


def dune_pit(depth=2):
    """L4b final fix wave, C1: open ground at y 5 (the natural surface, as EscapeTests patches it)
    with a sand dune on it, 7 by 7 and `depth` high (y 5 up), and a 1x1 pit in its middle at (0, 0)
    whose floor, y 5, lies above the natural surface: the seed-21 life's trap."""
    def rule(x, y, z):
        if y <= 4:
            return "stone"
        if abs(x) <= 3 and abs(z) <= 3 and y < 5 + depth and (x, z) != (0, 0):
            return "sand"
        return "air"

    return Grid(rule)


def carry_out(grid, state, steps):
    """Do escape steps at once, the way they would end: mines open cells, places fill them, walks move Mimo."""
    for step in steps:
        if step["kind"] == "mine":
            grid.put(*step["target"], "air")
        elif step["kind"] == "place":
            grid.put(*step["target"], step["block"])
        elif step["kind"] == "walk":
            state["position"] = dict(zip("xyz", map(float, step["target"])))


def fenced_pit(width=5):
    """Like `pit("stone", width)`, but a fence already fills the first stair's support cell (1, 1,
    0): solid, but nothing stands on it (Grid.supported), and not open ground a placed support
    block could go in either."""
    def rule(x, y, z):
        if (x, y, z) == (1, 1, 0):
            return "fence"
        if y <= 0:
            return "stone"
        if y >= 5:
            return "air"
        return "air" if z == 0 and 0 <= x < width else "stone"

    return Grid(rule)


def overridden_pit(overrides, wall="dirt", width=1):
    """Like pit(), but specific cells are overridden: for narrowing (water, an unminable block, an
    ore or a surface log) and for what Mimo built (fix round 1, items 2 and 3, and the minors)."""
    def rule(x, y, z):
        if (x, y, z) in overrides:
            return overrides[(x, y, z)]
        if y <= 0:
            return "stone"
        if y >= 5:
            return "air"
        return "air" if z == 0 and 0 <= x < width else wall

    return Grid(rule)


def pocket(size=20):
    """A cave pocket: a room `size` by `size` and 3 high (y 1 to 3, from x 0 and z 0) under dirt that
    reaches y 4 (the natural surface, as the class patches it), with stone below and air from y 5.
    At 20 it holds 400 standable cells, more than the 256 the old trap check counted up to."""
    def rule(x, y, z):
        if y <= 0:
            return "stone"
        if y >= 5:
            return "air"
        return "air" if y <= 3 and 0 <= x < size and 0 <= z < size else "dirt"

    return Grid(rule)


def flood(grid, start, limit=5000):
    """How many cells Mimo can walk to from `start`, counting up to `limit`."""
    seen, frontier = {start}, deque([start])
    while frontier and len(seen) < limit:
        for step in moves(grid, frontier.popleft()):
            if step not in seen:
                seen.add(step)
                frontier.append(step)
    return len(seen)


def mined(steps):
    return {tuple(step["target"]) for step in steps if step["kind"] == "mine"}


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
    def test_a_pit_or_a_pocket_has_no_way_out_but_a_home_or_a_way_up_is_one(self):
        """L3 final fix wave: Mimo is trapped when no cell at or above the natural surface (y 5 here),
        and no home, is within SURFACE_SEARCH cells of it -- however big the pocket is."""
        self.assertFalse(way_out(pit(), (0, 1, 0), "1"))
        self.assertTrue(way_out(pit(), (0, 1, 0), "1", homes={(0, 1, 0)}))
        self.assertGreater(flood(pocket(), (0, 1, 0)), 256)  # the old check (< 256 cells) never fired here
        self.assertFalse(way_out(pocket(), (0, 1, 0), "1"))
        self.assertTrue(way_out(pocket(), (0, 1, 0), "1", homes={(19, 1, 19)}))
        ramp = overridden_pit({(1, 2, 0): "air", (1, 3, 0): "air", (2, 3, 0): "air", (2, 4, 0): "air", (3, 4, 0): "air"})
        self.assertTrue(way_out(ramp, (0, 1, 0), "1"))
        self.assertFalse(way_out(flat(), (0, 1, 0), "1"))  # a cave floor as wide as the search: no way up in reach
        # On the surface already. (L4b final fix wave, C1: this stood in flat()'s air at y 5, over a cave
        # floor at y 1, where Mimo can walk nowhere; a cell above the surface is free only when Mimo can
        # walk on from it, so the pet stands on real ground now.)
        self.assertTrue(way_out(ground(), (0, 5, 0), "1"))
        self.assertEqual(SURFACE_SEARCH, 2000)

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

    def test_with_full_arms_a_dug_block_that_would_be_left_behind_is_not_counted_on(self):
        """L4b final fix wave, follow-up 2: mined dirt went into the stock whether or not it fit, so
        with full arms a staircase planned to place dirt it had left behind; the step failed "no dirt
        to place" twice and a pet stayed in a cave for a game day, until a skitter caught it."""
        grid = overridden_pit({(1, 1, 0): "air"})  # the first stair has nothing under it
        self.assertIn(place(1, 1, 0), staircase(grid, (0, 1, 0), (1, 0), {}, "1"))  # the stair's own dirt props it up
        full = {f"item_{n}": 1 for n in range(16)}
        self.assertIsNone(staircase(grid, (0, 1, 0), (1, 0), full, "1"))  # that dirt stays behind: not this way
        room = {**{f"item_{n}": 1 for n in range(15)}, "dirt": 1}  # 16 stacks, but the dirt stack has room
        self.assertIn(place(1, 1, 0), staircase(grid, (0, 1, 0), (1, 0), room, "1"))
        self.assertEqual(escape_plan(grid, (0, 1, 0), full, "1")[0], mine(0, 2, 1))  # another way out, dug, not built

    def test_a_fence_already_filling_the_support_cell_blocks_this_heading(self):
        """L3 fix round 1: `support`'s old is_solid check treated a fence the same as real ground,
        so Mimo's plan would have walked onto a cell nothing actually held it up in
        (Grid.supported). Fixed, the fence is read as no support, but it already fills the cell a
        placed support block would go in, so this heading is abandoned instead of built on a lie."""
        self.assertIsNone(staircase(fenced_pit(), (0, 1, 0), (1, 0), {"dirt": 5}, "1"))

    def test_narrows_at_water_and_an_unminable_block(self):
        """Minor (fix round 1): the pit shape was the only one tested; water is never mined and
        bedrock cannot be, so both widening cells are skipped and the rest still opens."""
        grid = overridden_pit({(1, 2, 1): "water", (2, 4, 1): "bedrock"})
        self.assertEqual(staircase(grid, (0, 1, 0), (1, 0), {}, "1"),
                         [mine(1, 2, 0), mine(1, 3, 0), rubble(1, 4, 0), rubble(1, 3, 1), rubble(1, 4, 1),
                          walk(1, 2, 0), mine(2, 3, 0), mine(2, 4, 0), rubble(2, 3, 1), walk(2, 3, 0),
                          mine(3, 4, 0), rubble(3, 4, 1), walk(3, 4, 0), walk(4, 5, 0)])

    def test_never_mines_a_claimed_chest_or_wall_or_the_cell_below_a_claimed_cell(self):
        """L3 fix round 1, item 2: open_up never checked `reserved`, so a claimed chest or wall in
        the widening could be mined for rubble and lost. Each claimed cell's own floor is also
        left (the same rule as work.cut: never undermine a claimed cell), and Mimo still gets
        out."""
        grid = overridden_pit({(1, 3, 1): "chest"})
        grid.claims.update({(1, 3, 1), (2, 4, 1)})  # a claimed chest, and a claimed wall elsewhere
        self.assertEqual(staircase(grid, (0, 1, 0), (1, 0), {}, "1"),
                         [mine(1, 2, 0), mine(1, 3, 0), rubble(1, 4, 0), rubble(1, 4, 1), walk(1, 2, 0),
                          mine(2, 3, 0), mine(2, 4, 0), walk(2, 3, 0),
                          mine(3, 4, 0), rubble(3, 4, 1), walk(3, 4, 0), walk(4, 5, 0)])
        plan = staircase(grid, (0, 1, 0), (1, 0), {}, "1")
        self.assertFalse(mined(plan) & {(1, 3, 1), (2, 4, 1), (1, 2, 1), (2, 3, 1)})  # claimed, or under a claim

    def test_a_widening_cell_leaves_an_ore_or_a_surface_log_standing(self):
        """L3 fix round 1, item 3 and the minors: a rubble cell drops nothing, so an ore or a
        surface log in the widening was lost for good; both are left standing instead."""
        grid = overridden_pit({(1, 3, 1): "iron_ore", (2, 4, 1): "oak_log"})
        self.assertEqual(staircase(grid, (0, 1, 0), (1, 0), {"stone_pickaxe": 1}, "1"),
                         [mine(1, 2, 0), mine(1, 3, 0), rubble(1, 4, 0), rubble(1, 2, 1), rubble(1, 4, 1),
                          walk(1, 2, 0), mine(2, 3, 0), mine(2, 4, 0), rubble(2, 3, 1), walk(2, 3, 0),
                          mine(3, 4, 0), rubble(3, 4, 1), walk(3, 4, 0), walk(4, 5, 0)])
        self.assertFalse(mined(staircase(grid, (0, 1, 0), (1, 0), {"stone_pickaxe": 1}, "1")) & {(1, 3, 1), (2, 4, 1)})

    def test_the_brain_digs_out_after_two_failed_walks(self):
        state = stuck()
        ctx = brainy(pit())
        steps = brain_plan(state, ctx, 2.0)
        self.assertEqual(steps[0], {"kind": "mine", "target": [1, 2, 0], "purpose": "escape", "keep": "escape"})
        self.assertEqual(steps[-1],
                         {"kind": "walk", "target": [4, 5, 0], "reach": 0.0, "purpose": "escape", "keep": "escape"})
        brain = state["brain"]
        self.assertEqual((brain["purpose"], brain["escaped_at"], brain["replans"], ctx.searches_left),
                         ("explore", 2.0, 0, 1))
        self.assertEqual(ctx.events[-1][1:], ("trapped", "Pip is stuck in a pit and starts digging out."))

    def test_a_new_choice_mid_escape_keeps_the_escape_steps(self):
        """Follow-up fix, the minors: apply_choice keeps only `keep` steps (choosing.kept_steps), so
        a new choice landing mid-escape used to drop the rest of the staircase out along with the
        old plan (the seed-11 pocket replay lost a 41-step escape 9 game seconds in, and took 24
        more purpose changes and a second escape to get out). Escape steps now carry `keep: "escape"`
        too, so they ride out a purpose change the same way a portable station's mine-back does --
        but, unlike the mine-back's `keep: True`, only that: a failure of one of these steps still
        ends the escape (follow-up 2, item 3; test_survival_actions.py's
        test_a_failed_escape_step_ends_the_escape_and_is_charged_to_the_purpose)."""
        state = stuck()
        steps = brain_plan(state, brainy(pit()), 2.0)
        self.assertTrue(steps and all(step.get("keep") == "escape" for step in steps))
        state["queue"] = steps
        choice = Choice("craft_tools", "utility", "A table would help.", {"model": 0, "luna": 0, "reflections": 0})
        apply_choice(state, choice, 3.0)
        self.assertEqual(state["queue"], steps)
        self.assertEqual(state["brain"]["purpose"], "craft_tools")
        # the same steps, set aside during a reflex, ride out a choice there too (kept_steps is
        # shared by both apply_choice's queue and its reflex set_aside).
        reflexed = stuck()
        reflexed["brain"]["reflex"] = "warm_up"
        reflexed["brain"]["set_aside"] = steps
        apply_choice(reflexed, choice, 3.0)
        self.assertEqual(reflexed["brain"]["set_aside"], steps)

    def test_any_second_no_path_failure_of_the_purpose_checks_for_a_trap(self):
        partial = {"kind": "walk", "started_at": 1.5, "ended_at": 1.8, "result": "done", "purpose": "explore",
                   "target": {"x": 40, "y": 5, "z": 0}}
        state = stuck()
        state["recent_actions"] = [failed_walk(1.0), partial, failed_walk(2.0)]
        self.assertEqual(brain_plan(state, brainy(pit()), 2.0)[0]["purpose"], "escape")
        fresh = stuck()
        fresh["brain"].update(replans=0, batches=2)  # the batch before the second failure went well
        self.assertEqual(brain_plan(fresh, brainy(pit()), 2.0)[0]["purpose"], "escape")

    def test_two_failures_of_any_purposes_within_a_few_game_minutes_check_for_a_trap(self):
        """L3 final fix wave: in a pocket each purpose gave up after one walk with no path, so two of
        one purpose never came and the check never ran. Any two within TRAP_WINDOW now count."""
        mixed = stuck()
        mixed["recent_actions"] = [failed_walk(1.0, "hunt"), failed_walk(2.0, "go_home")]
        mixed["brain"].update(purpose="go_home", chosen_at=1.5, replans=0)
        self.assertEqual(brain_plan(mixed, brainy(pit()), 2.0)[0]["purpose"], "escape")
        rechosen = stuck()
        rechosen["brain"]["chosen_at"] = 1.5
        self.assertEqual(brain_plan(rechosen, brainy(pit()), 2.0)[0]["purpose"], "escape")

    def test_failures_of_another_purpose_or_before_the_choice_count_only_within_the_window(self):
        long_ago = 2.0 - TRAP_WINDOW - 1.0
        earlier = stuck()
        earlier["recent_actions"] = [failed_walk(long_ago), failed_walk(2.0, "go_home")]
        self.assertEqual(brain_plan(earlier, brainy(pit()), 2.0), [{"kind": "wait", "seconds": 1.0}])
        self.assertIsNone(earlier["brain"]["purpose"])
        rechosen = stuck()
        rechosen["recent_actions"] = [failed_walk(long_ago), failed_walk(2.0)]
        rechosen["brain"]["chosen_at"] = 1.5
        brain_plan(rechosen, brainy(pit()), 2.0)
        self.assertIsNone(rechosen["brain"]["purpose"])
        same = stuck()
        same["recent_actions"] = [failed_walk(long_ago), failed_walk(2.0)]
        same["brain"]["chosen_at"] = long_ago - 1.0  # both of the purpose since it was chosen: the old rule
        self.assertEqual(brain_plan(same, brainy(pit()), 2.0)[0]["purpose"], "escape")

    def test_a_pocket_bigger_than_256_cells_with_no_way_up_is_dug_out_of(self):
        """L3 final fix wave: the old check counted up to 256 cells, so a 393-cell cave pocket (the
        seed-11 life) never looked like a trap. A 400-cell pocket with no way up is one now, and
        Mimo digs a staircase out through the dirt over its side."""
        state = stuck()
        ctx = brainy(pocket())
        steps = brain_plan(state, ctx, 2.0)
        self.assertEqual({step["purpose"] for step in steps}, {"escape"})
        self.assertEqual(steps[-1],
                         {"kind": "walk", "target": [-4, 5, 0], "reach": 0.0, "purpose": "escape", "keep": "escape"})
        self.assertEqual(ctx.events[-1][1:], ("trapped", "Pip is stuck in a pit and starts digging out."))

    def test_a_home_within_reach_is_a_way_out(self):
        state = stuck()
        ctx = brainy(pocket())
        ctx.db.execute("INSERT INTO memory_places (kind, x, y, z, note, found_at, visited_at, data) "
                       "VALUES ('home', 19, 1, 19, '', 0, 0, '{}')")
        brain_plan(state, ctx, 2.0)
        self.assertIsNone(state["brain"]["purpose"])  # not trapped: the failure is reported as usual
        self.assertIn("explore", state["brain"]["penalties"])

    def test_a_claimed_open_room_or_passage_on_the_way_out_is_walked_through(self):
        """L3 final fix wave: `reserved` came before the open-cell check, so a claimed open cell --
        the shelter's room over Mimo's head, a passage stair -- failed every heading, and a pet
        trapped in its own room had no plan ([] where it had 16 steps). An open cell needs no mining,
        claimed or not; a claimed solid cell is still never mined."""
        room = pit()
        room.claims.update({(0, 1, 0), (0, 2, 0), (0, 3, 0), (0, 4, 0)})  # Mimo's cell and the room over it
        self.assertEqual(escape_plan(room, (0, 1, 0), {}, "1"), escape_plan(pit(), (0, 1, 0), {}, "1"))
        self.assertEqual(len(escape_plan(room, (0, 1, 0), {}, "1")), 16)
        passage = overridden_pit({(1, 2, 0): "air", (1, 3, 0): "air"})
        passage.claims.update({(1, 2, 0), (1, 3, 0)})  # an open passage stair on the way
        plan = staircase(passage, (0, 1, 0), (1, 0), {}, "1")
        self.assertEqual(plan[:2], [rubble(1, 4, 0), rubble(1, 2, 1)])
        self.assertEqual(plan[-1], walk(4, 5, 0))
        self.assertFalse(mined(plan) & {(1, 2, 0), (1, 3, 0)})

    def test_with_no_search_left_the_check_waits_for_the_next_tick(self):
        state = stuck()
        ctx = brainy(pit())
        ctx.searches_left = 0
        self.assertEqual(brain_plan(state, ctx, 2.0), [{"kind": "wait", "seconds": 1.0}])
        self.assertIsNone(state["brain"]["handled_failure"])
        self.assertEqual(state["brain"]["purpose"], "explore")

    def test_at_night_at_sixty_times_a_pet_in_its_own_staircase_digs_out_before_dawn(self):
        """W2 (the controller's ruling on the W2 dry run, 6): the escape tried again only ESCAPE_RETRY *server*
        seconds after the last, which at MIMO_TIME_SCALE 60 is a game day. On the W2 gate a gentle pet (seed 21)
        dug its staircase into a frozen swamp's bed at dusk, failed two walks home, slept the night in the pit
        with nothing to eat and dug out only after dawn. The wait is ESCAPE_RETRY game seconds now, the same at 1x."""
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        state = stuck()
        state["brain"]["escaped_at"] = 2.0 - 20.0  # an escape tried 20 server seconds ago: 20 game minutes at 60x
        ctx = ActionContext(grid=pit(), clock_at=lambda at: NIGHT_60, planner=brain_plan, events=[], db=db)
        steps = brain_plan(state, ctx, 2.0)
        self.assertEqual({step.get("purpose") for step in steps}, {"escape"})
        self.assertEqual(ctx.events[-1][1], "trapped")
        soon = stuck()
        soon["brain"]["escaped_at"] = 1.5  # half a server second ago: 30 game seconds at 60x, under ESCAPE_RETRY
        ctx = ActionContext(grid=pit(), clock_at=lambda at: NIGHT_60, planner=brain_plan, events=[], db=db)
        self.assertFalse(any(step.get("purpose") == "escape" for step in brain_plan(soon, ctx, 2.0)))

    def test_a_pet_that_is_not_trapped_reports_the_failure(self):
        state = stuck(position={"x": 0.0, "y": 5.0, "z": 0.0})  # on the natural surface (y 4 and up)
        ctx = brainy(Grid(lambda x, y, z: "stone" if y <= 4 else "air"))
        brain_plan(state, ctx, 2.0)
        self.assertIsNone(state["brain"]["purpose"])
        self.assertIn("explore", state["brain"]["penalties"])
        self.assertEqual(ctx.searches_left, 2)  # on the surface the check needs no search at all


@patch("backend.survival.escape.terrain_height", lambda x, z, seed: 4)
class PitAboveTheSurfaceTests(unittest.TestCase):
    """L4b final fix wave, C1: routes drop 3 blocks but climb 1, and a 1x1 pit a dune or a boulder
    leaves has its floor above the natural surface. Every cell above the surface counted as free, so
    a pet a walk dropped in never dug out (the seed-21 fake-Jev life starved there on day 9)."""

    def test_a_pit_above_the_surface_is_a_trap_and_the_brain_digs_out_of_it(self):
        grid = dune_pit()
        self.assertEqual(flood(grid, (0, 5, 0)), 1)  # nowhere to walk from the pit's floor
        self.assertTrue(on_surface((0, 5, 0), "1"))  # yet above the natural surface: once "free"
        self.assertFalse(roomy(grid, (0, 5, 0)))
        self.assertFalse(way_out(grid, (0, 5, 0), "1"))
        state = stuck(position={"x": 0.0, "y": 5.0, "z": 0.0})
        ctx = brainy(grid)
        steps = brain_plan(state, ctx, 2.0)
        self.assertEqual({step["purpose"] for step in steps}, {"escape"})
        self.assertEqual(ctx.events[-1][1:], ("trapped", "Pip is stuck in a pit and starts digging out."))
        carry_out(grid, state, steps)
        out = as_cell(state["position"])
        self.assertEqual(out, (1, 6, 0))  # one stair up and out: the dune top is a step from there
        self.assertGreater(flood(grid, out), POCKET)
        self.assertTrue(way_out(grid, out, "1"))

    def test_a_deeper_pit_climbs_on_until_a_stair_leads_somewhere(self):
        grid = dune_pit(depth=3)
        steps = escape_plan(grid, (0, 5, 0), {}, "1")
        self.assertEqual(steps[-1], walk(2, 7, 0))  # the first stair above the surface is still in a pit
        state = pet(position={"x": 0.0, "y": 5.0, "z": 0.0})
        carry_out(grid, state, steps)
        self.assertTrue(way_out(grid, as_cell(state["position"]), "1"))

    def test_one_surface_cell_over_a_hole_it_can_drop_into_is_a_trap(self):
        """W2 fix T: on the W2 gate an untaught pet stood on the one surface cell between its house wall and its pen's
        fence, where its two mining staircases met; they and their tunnels made 62 cells to walk, so it was not "in a
        pit", every walk out failed ("no way there") and it starved there over a game day. Now only cells above the
        natural surface count toward a way out."""
        def rule(x, y, z):
            if 0 <= x <= 5 and 1 <= z <= 6 and y in (3, 4):
                return "air"  # a dug room below the surface, 36 cells to walk, 2 down from the cell over its corner
            if (x, z) == (0, 1) and y == 5:
                return "air"
            if y <= 4:
                return "stone"
            if y <= 6 and (x in (-1, 1) or z == -1) and z <= 0:
                return "planks"  # walls 2 high on three sides of the one cell (0, 5, 0)
            return "air"
        grid = Grid(rule)
        here = (0, 5, 0)
        self.assertGreater(flood(grid, here), POCKET)  # the old check called this open ground
        self.assertFalse(roomy(grid, here, seed="1"))
        self.assertFalse(way_out(grid, here, "1"))
        state = stuck(position={"x": 0.0, "y": 5.0, "z": 0.0}, inventory={"dirt": 8})
        steps = brain_plan(state, brainy(grid), 2.0)
        self.assertEqual({step["purpose"] for step in steps}, {"escape"})
        carry_out(grid, state, steps)
        self.assertTrue(way_out(grid, as_cell(state["position"]), "1"))

    def test_open_ground_above_the_surface_is_free_with_no_search(self):
        state = stuck(position={"x": 2.0, "y": 7.0, "z": 2.0})  # on the dune top, beside the pit
        ctx = brainy(dune_pit())
        self.assertTrue(roomy(ctx.grid, (2, 7, 2)))
        brain_plan(state, ctx, 2.0)
        self.assertIsNone(state["brain"]["purpose"])  # not trapped: the failure is reported as usual
        self.assertIn("explore", state["brain"]["penalties"])
        self.assertEqual(ctx.searches_left, 2)  # the small flood takes no search from the tick's budget


# The seed-11 life of the L3 final review (fake Jev): at game day 2.349 a hunt took Mimo down its own
# staircase after a chicken, and off its side where it passes a natural cave opening, 3 blocks down
# into a 393-cell pocket with no way up. Every walk failed "no way there" for most of a game day.
# The world is the real one; these are the cells Mimo had dug (all air) around the pocket.
SEED_11 = "1672576148184018844"
DUG_11 = ((-5562, 2, -1341), (-5562, 2, -1340), (-5562, 3, -1341), (-5561, 1, -1341), (-5561, 1, -1340),
          (-5561, 2, -1341), (-5561, 2, -1340), (-5560, -3, -1341), (-5560, 1, -1341), (-5560, 1, -1340),
          (-5560, 2, -1341), (-5560, 2, -1340), (-5559, -1, -1341), (-5559, -1, -1340), (-5559, 0, -1341),
          (-5559, 0, -1340), (-5559, 1, -1341), (-5559, 1, -1340), (-5558, -2, -1341), (-5558, -2, -1340),
          (-5558, -1, -1341), (-5558, -1, -1340), (-5558, 0, -1341), (-5558, 0, -1340), (-5557, -4, -1342),
          (-5557, -3, -1341), (-5557, -3, -1340), (-5557, -2, -1341), (-5557, -2, -1340), (-5557, -1, -1341),
          (-5557, -1, -1340), (-5556, -3, -1341), (-5556, -3, -1340), (-5556, -2, -1341), (-5556, -2, -1340),
          (-5556, -1, -1341), (-5556, -1, -1340), (-5555, -3, -1341), (-5555, -3, -1340), (-5555, -2, -1341),
          (-5555, -2, -1340), (-5555, -1, -1341), (-5555, -1, -1340), (-5555, -3, -1342), (-5555, -3, -1343))
CARRIED_11 = {"birch_log": 8, "cobblestone": 12, "stone_sword": 1, "coal": 2, "oak_log": 1, "planks": 2,
              "sticks": 1, "iron_pickaxe": 1, "furnace": 1, "crafting_table": 1, "iron_ore": 1, "feather": 2,
              "campfire": 1, "raw_chicken": 1}


def seed_11():
    grid = Grid(lambda x, y, z: block_at(x, y, z, SEED_11))
    for cell in DUG_11:
        grid.put(*cell, "air")
    return grid


class Seed11PocketTests(unittest.TestCase):
    def test_the_pocket_is_a_trap_now_and_mimo_digs_out_of_it(self):
        grid = seed_11()
        here = (-5561, -4, -1342)
        self.assertGreater(flood(grid, here), 256)  # 393: the old check called it open ground
        self.assertFalse(way_out(grid, here, SEED_11))
        self.assertTrue(way_out(grid, (-5563, 3, -1341), SEED_11))  # where the hunt started, on the surface
        self.assertTrue(in_a_cave((-5562, -4, -1343), SEED_11))  # the chicken it chased is no prey now
        state = stuck(world_seed=SEED_11, position={"x": -5561.0, "y": -4.0, "z": -1342.0}, inventory=dict(CARRIED_11))
        state["recent_actions"] = [failed_walk(1.0, "hunt"), failed_walk(2.0, "go_home")]  # one each, as in the life
        state["brain"].update(purpose="go_home", chosen_at=1.5, replans=0)
        steps = brain_plan(state, brainy(grid), 2.0)
        self.assertEqual({step["purpose"] for step in steps}, {"escape"})
        end = steps[-1]["target"]
        self.assertGreater(end[1], terrain_height(end[0], end[2], SEED_11))  # it ends on the natural surface


# L4b final fix wave, C1: the seed-21 life of the L4b final review (fake Jev, sim pace). A wander walk
# ended at the bottom of a 1x1 pit in a desert's sandstone, 3 deep, whose floor lies above the natural
# surface. From day 4.28 every walk failed "no way there" (204 explores, 39 go-homes), and on day 9.07
# the pet starved. The pit is worldgen's own: Mimo dug nothing there.
SEED_21 = "58672336141078560"  # the world hatch(random.Random(21)) makes


class Seed21PitTests(unittest.TestCase):
    def test_the_pit_is_a_trap_now_and_mimo_digs_out_of_it(self):
        grid = Grid(lambda x, y, z: block_at(x, y, z, SEED_21))
        here = (5931, 10, 571)
        self.assertGreater(here[1], terrain_height(here[0], here[2], SEED_21))  # its floor: above the natural surface
        self.assertEqual(flood(grid, here), 1)
        self.assertFalse(way_out(grid, here, SEED_21))
        state = stuck(world_seed=SEED_21, position={"x": 5931.0, "y": 10.0, "z": 571.0})
        state["recent_actions"] = [failed_walk(1.0, "explore"), failed_walk(2.0, "go_home")]
        state["brain"].update(purpose="go_home", chosen_at=1.5, replans=0)
        steps = brain_plan(state, brainy(grid), 2.0)
        self.assertEqual({step["purpose"] for step in steps}, {"escape"})
        carry_out(grid, state, steps)
        out = as_cell(state["position"])
        self.assertGreater(flood(grid, out), POCKET)
        self.assertTrue(way_out(grid, out, SEED_21))


if __name__ == "__main__":
    unittest.main()

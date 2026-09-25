import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import foraging  # noqa: F401  (registers forage and fish)
from backend.survival.actions import ActionContext, advance_actions, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, know, remember, set_home, update_place
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
SHORE = ((2, 1, 0), (3, 0, 0))


def meadow(food=None):
    """Grass at y 0 and air above, with `food` placed as blocks that grew there (edits). Near the
    origin worldgen grows no wild food, so only these cells hold any."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (food or {}).items():
        grid.put(*cell, block)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state=None, grid=None, clock=DAY, at=0.0):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state or pet(), grid or meadow(), clock, at, db)


def context(s):
    return ActionContext(grid=s.grid, clock_at=lambda at: s.clock, planner=lambda *args: [], events=[], db=s.db)


def pick(x, y, z):
    return {"kind": "pick", "target": [x, y, z]}


def walk(x, y, z, reach=0.0):
    return {"kind": "walk", "target": [x, y, z], "reach": reach, "whole": True}


class ForageTests(unittest.TestCase):
    def test_picks_ripe_food_nearest_first_walking_only_when_out_of_reach(self):
        grid = meadow({(3, 1, 0): "berry_bush_ripe", (4, 1, 0): "berry_bush_ripe", (10, 1, 0): "brown_mushroom",
                       (0, 1, 2): "berry_bush"})
        s = situation(grid=grid)
        forage = PURPOSES["forage"]
        self.assertTrue(forage.valid(s))
        self.assertEqual(forage.plan(s, context(s)), [pick(3, 1, 0), pick(4, 1, 0), walk(10, 1, 0, 2.0), pick(10, 1, 0)])

    def test_enough_food_carried_night_or_nothing_ripe_means_no_foraging(self):
        grid = meadow({(3, 1, 0): "berry_bush_ripe"})
        forage = PURPOSES["forage"]
        self.assertFalse(forage.valid(situation(pet(inventory={"bread": 2, "berries": 2}), grid)))
        self.assertFalse(forage.valid(situation(grid=grid, clock=NIGHT)))
        self.assertFalse(forage.valid(situation(grid=meadow({(3, 1, 0): "berry_bush"}))))

    def test_red_mushrooms_are_left_once_mimo_knows(self):
        s = situation(grid=meadow({(2, 1, 0): "red_mushroom"}))
        self.assertEqual(PURPOSES["forage"].plan(s, context(s)), [pick(2, 1, 0)])
        wiser = situation(grid=meadow({(2, 1, 0): "red_mushroom"}))
        know(wiser.db, "red_mushroom", "poisonous", 0.0)
        self.assertFalse(PURPOSES["forage"].valid(wiser))

    def test_goes_back_to_a_patch_that_has_grown_again(self):
        s = situation(at=10_000.0)
        remember(s.db, "food", (60, 1, 0), 0.0)
        update_place(s.db, "food", (60, 1, 0), {"ripe": 0, "seen_at": 10_000.0 - 7200.0})
        self.assertEqual(PURPOSES["forage"].plan(s, context(s)), [walk(60, 1, 0, 3.0)])
        recent = situation(at=10_000.0)
        remember(recent.db, "food", (60, 1, 0), 0.0)
        update_place(recent.db, "food", (60, 1, 0), {"ripe": 0, "seen_at": 9_000.0})
        self.assertFalse(PURPOSES["forage"].valid(recent))

    def test_the_hungrier_and_emptier_handed_the_higher_it_scores(self):
        score = PURPOSES["forage"].score
        full = score(situation())
        hungry = score(situation(pet(vitals={**START_VITALS, "hunger": 40.0})))
        stocked = score(situation(pet(vitals={**START_VITALS, "hunger": 40.0}, inventory={"bread": 3})))
        self.assertEqual(round(full), 55)
        self.assertEqual(round(hungry), 75)
        self.assertEqual(round(stocked), 55)
        late = situation(clock={**DAY, "seconds_into_day": 2000.0})
        self.assertEqual(round(score(late)), 25)


# L4a final fix wave, C1: 16 stacks of things Mimo keeps, nothing of which gives way to food.
NO_ROOM = {"iron_pickaxe": 1, "iron_sword": 1, "crafting_table": 1, "furnace": 1, "iron_cap": 1, "iron_tunic": 1,
           "oak_log": 8, "sticks": 4, "coal": 8, "iron_ore": 4, "seeds": 5, "sapling": 3, "wheat": 2, "torch": 2,
           "campfire": 1, "bow": 1}
# The same, with a stack of feathers in place of the bow: food pushes them out.
FEATHERS = {**{item: count for item, count in NO_ROOM.items() if item != "bow"}, "feather": 3}


class RoomForFoodTests(unittest.TestCase):
    """L4a final fix wave, C1: food work is offered only while its food would be kept (a stack is
    free or one gives way to food) or eaten on the spot (Mimo is hungry), and food patches Mimo goes
    back to lie within FORAGE_REACH of home as well as of Mimo, so each forage no longer leads
    farther out than the last."""

    def test_forage_and_fish_wait_while_the_food_could_only_be_left_behind(self):
        grid = meadow({(3, 1, 0): "berry_bush_ripe"})
        forage, fish = PURPOSES["forage"], PURPOSES["fish"]
        with patch("backend.survival.foraging.shores_near", lambda grid, seed, here, radius: [SHORE]):
            for inventory, hunger, offered in ((NO_ROOM, 100.0, False), (FEATHERS, 100.0, True),
                                               (NO_ROOM, 50.0, True), ({}, 100.0, True)):
                state = pet(inventory=dict(inventory), vitals={**START_VITALS, "hunger": hunger})
                s = situation(state, grid)
                self.assertEqual((forage.valid(s), fish.valid(s)), (offered, offered), (sorted(inventory), hunger))
                self.assertEqual(bool(forage.plan(s, context(s))), offered)

    def test_with_16_kept_stacks_and_a_berry_bush_the_berries_are_kept_or_eaten_never_left(self):
        for inventory, hunger in ((FEATHERS, 100.0), (NO_ROOM, 40.0)):
            grid = meadow({(1, 1, 0): "berry_bush_ripe"})
            state = pet(inventory=dict(inventory), vitals={**START_VITALS, "hunger": hunger})
            s = situation(state, grid)
            steps = PURPOSES["forage"].plan(s, context(s))
            self.assertEqual(steps, [pick(1, 1, 0)])
            events = []
            state["queue"] = steps
            advance_actions(state, ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [],
                                                 events=events), 5.0)
            self.assertEqual(grid.material(1, 1, 0), "berry_bush")  # picked
            eaten = state["vitals"]["hunger"] - hunger  # (hunger falls only with time, and no time passed)
            self.assertEqual(state["inventory"].get("berries", 0) * 8.0 + eaten, 8.0 * 3, sorted(inventory))
            self.assertNotIn("feather", state["inventory"])  # what gave way to the berries, if anything

    def test_food_patches_stay_within_reach_of_home(self):
        s = situation(pet(position={"x": 60.0, "y": 1.0, "z": 0.0}), at=10_000.0)
        set_home(s.db, (0, 1, 0), 0.0)
        for cell in ((40, 1, 30), (110, 1, 0)):  # both within 64 of Mimo; the second 110 from home
            remember(s.db, "food", cell, 0.0)
            update_place(s.db, "food", cell, {"ripe": 3, "seen_at": 9_000.0})
        self.assertEqual([place["x"] for place in foraging.patches(s)], [40])
        away = situation(pet(position={"x": 100.0, "y": 1.0, "z": 0.0}), at=10_000.0)
        set_home(away.db, (0, 1, 0), 0.0)
        remember(away.db, "food", (110, 1, 0), 0.0)
        update_place(away.db, "food", (110, 1, 0), {"ripe": 3, "seen_at": 9_000.0})
        self.assertFalse(PURPOSES["forage"].valid(away))  # it does not lead Mimo on farther out


@patch("backend.survival.foraging.shores_near", lambda grid, seed, here, radius: [SHORE])
class FishTests(unittest.TestCase):
    def test_walks_to_the_shore_and_fishes_three_times_a_batch(self):
        s = situation()
        fish = PURPOSES["fish"]
        self.assertTrue(fish.valid(s))
        self.assertEqual(fish.plan(s, context(s)), [walk(2, 1, 0)] + [{"kind": "fish", "target": [3, 0, 0]}] * 3)
        there = situation(pet(position={"x": 2.0, "y": 1.0, "z": 0.0}, inventory={"raw_fish": 2}))
        self.assertEqual(fish.plan(there, context(there)), [{"kind": "fish", "target": [3, 0, 0]}] * 2)

    def test_no_fishing_in_empty_water_at_night_or_with_enough_fish(self):
        fish = PURPOSES["fish"]
        self.assertFalse(fish.valid(situation(pet(fish={"0,0": {"stock": 0, "since": 0.0}}))))
        self.assertFalse(fish.valid(situation(clock=NIGHT)))
        self.assertFalse(fish.valid(situation(pet(inventory={"raw_fish": 1, "cooked_fish": 3}))))


if __name__ == "__main__":
    unittest.main()

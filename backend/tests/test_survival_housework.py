import sqlite3
import unittest

from backend.survival.actions import activity_of, ensure_actions
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables
from backend.survival.purposes import PURPOSES
from backend.survival.reflexes import by_name
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
CHEST = (1, 1, 0)


def room(cells=None):
    """Stone at y <= 0 and air above, with `cells` placed as Mimo placed them."""
    grid = Grid(lambda x, y, z: "stone" if y <= 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


def pet(position=(0, 1, 0), **changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": float(position[0]), "y": float(position[1]),
             "z": float(position[2])}, "inventory": {}, "vitals": dict(START_VITALS), "traits": {},
             "status": "idle", "last_thought": "", "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def run(spec, state, grid):
    step = start_step(spec, state, grid, 0.0)
    finish_step(step, state, grid, step["ends_at"])
    return step


def store(item, amount):
    return {"kind": "store", "target": list(CHEST), "item": item, "amount": amount}


def take(item, amount):
    return {"kind": "take", "target": list(CHEST), "item": item, "amount": amount}


class ChestStepTests(unittest.TestCase):
    def test_storing_moves_items_into_the_chest_in_a_moment(self):
        grid, state = room({CHEST: "chest"}), pet(inventory={"dirt": 10, "planks": 2})
        step = run(store("dirt", 6), state, grid)
        self.assertEqual((step["ends_at"], step["target"], step["item"]), (0.3, {"x": 1, "y": 1, "z": 0}, "dirt"))
        self.assertEqual(state["inventory"], {"dirt": 4, "planks": 2})
        self.assertEqual(state["chests"], {"1,1,0": {"dirt": 6}})
        run(store("dirt", 9), state, grid)
        self.assertEqual(state["inventory"], {"planks": 2})
        self.assertEqual(state["chests"]["1,1,0"], {"dirt": 10})

    def test_taking_moves_them_back_as_far_as_mimo_can_carry(self):
        grid, state = room({CHEST: "chest"}), pet(chests={"1,1,0": {"bread": 3}})
        run(take("bread", 2), state, grid)
        self.assertEqual((state["inventory"], state["chests"]["1,1,0"]), ({"bread": 2}, {"bread": 1}))
        full = pet(inventory={f"item_{n}": 1 for n in range(CARRY_STACKS)}, chests={"1,1,0": {"bread": 3}})
        with self.assertRaisesRegex(StepFailed, "arms are full"):
            start_step(take("bread", 1), full, grid, 0.0)

    def test_a_full_chest_takes_nothing_more(self):
        packed = {f"item_{n}": 32 for n in range(CHEST_STACKS)}
        grid, state = room({CHEST: "chest"}), pet(inventory={"dirt": 3}, chests={"1,1,0": packed})
        with self.assertRaisesRegex(StepFailed, "chest is full"):
            start_step(store("dirt", 3), state, grid, 0.0)

    def test_chest_steps_need_a_chest_in_reach_and_the_item(self):
        grid = room({CHEST: "chest"})
        with self.assertRaisesRegex(StepFailed, "no dirt"):
            start_step(store("dirt", 1), pet(), grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "no bread in the chest"):
            start_step(take("bread", 1), pet(), grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "out of reach"):
            start_step(store("dirt", 1), pet(position=(9, 1, 0), inventory={"dirt": 1}), grid, 0.0)
        with self.assertRaisesRegex(StepFailed, "bad step: amount"):
            start_step(store("dirt", 0), pet(inventory={"dirt": 1}), grid, 0.0)

    def test_a_chest_that_is_gone_took_its_contents_along(self):
        grid, state = room(), pet(inventory={"dirt": 1}, chests={"1,1,0": {"bread": 3}})
        with self.assertRaises(StepFailed) as caught:
            start_step(store("dirt", 1), state, grid, 0.0)
        self.assertEqual(caught.exception.code, "gone")
        self.assertEqual(state["chests"], {})

    def test_dropping_leaves_items_behind_for_good(self):
        grid, state = room(), pet(inventory={"red_mushroom": 3, "dirt": 1})
        run({"kind": "drop", "item": "red_mushroom", "amount": 5}, state, grid)
        self.assertEqual(state["inventory"], {"dirt": 1})

    def test_mining_a_chest_clears_its_contents(self):
        grid, state = room({CHEST: "chest"}), pet(inventory={"stone_pickaxe": 1})
        state["chests"] = {"1,1,0": {"bread": 3}}
        step = start_step({"kind": "mine", "target": list(CHEST)}, state, grid, 0.0)
        finish_step(step, state, grid, step["ends_at"])
        self.assertEqual(state["chests"], {})


class BedTests(unittest.TestCase):
    def test_sleeping_on_a_bed_rests_at_the_bed_rate(self):
        grid = room({(0, 1, 0): "bed"})
        on_bed = pet(position=(0, 2, 0))
        on_bed["action"] = start_step({"kind": "sleep"}, on_bed, grid, 0.0)
        self.assertTrue(on_bed["action"]["bed"])
        self.assertEqual(activity_of(on_bed), "sleeping_in_bed")
        floor = pet()
        floor["action"] = start_step({"kind": "sleep"}, floor, grid, 0.0)
        self.assertEqual(activity_of(floor), "sleeping")

    def situation(self, grid, clock=NIGHT, position=(0, 1, 0), energy=100.0):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        state = pet(position=position)
        state["vitals"]["energy"] = energy
        return Situation(state, grid, clock, 0.0, db)

    def test_sleep_walks_onto_a_bed_within_eight_blocks_first(self):
        s = self.situation(room({(5, 1, 0): "bed"}))
        plan = PURPOSES["sleep"].plan(s, None)
        self.assertEqual(plan, [{"kind": "walk", "target": [5, 2, 0], "reach": 0.0}, {"kind": "sleep"}])
        on_it = self.situation(room({(5, 1, 0): "bed"}), position=(5, 2, 0))
        self.assertEqual(PURPOSES["sleep"].plan(on_it, None), [{"kind": "sleep"}])
        far = self.situation(room({(12, 1, 0): "bed"}))
        self.assertEqual(PURPOSES["sleep"].plan(far, None), [{"kind": "sleep"}])

    def test_collapsing_mimo_crawls_into_a_near_bed(self):
        collapse = by_name("collapse")
        s = self.situation(room({(3, 1, 0): "bed"}), clock=DAY, energy=5.0)
        self.assertTrue(collapse.trigger(s))
        self.assertEqual(collapse.plan(s, None), [{"kind": "walk", "target": [3, 2, 0], "reach": 0.0}, {"kind": "sleep"}])
        self.assertEqual(collapse.plan(self.situation(room(), clock=DAY, energy=5.0), None), [{"kind": "sleep"}])


if __name__ == "__main__":
    unittest.main()

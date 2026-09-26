import sqlite3
import time
import unittest
from unittest.mock import patch

from backend.survival import signals
from backend.survival.blueprints import Blueprint, Planned
from backend.survival.memory import finish_structure
from backend.survival.once import forget_logged
from backend.survival.signals import (
    BUTTON_STEPS, FULL, MATERIALS, MAX_CELLS, compile_circuit, drawn_on, fresh_state, machine_state, parse,
    run_signals, settle, step,
)
from backend.survival.structures import start
from backend.tests.test_survival_workshop import Yard


class Bench:
    """A circuit on the bench: a layout's parts, their state, and the levers and buttons to work it."""

    def __init__(self, rows, held=None):
        self.circuit = compile_circuit(tuple(((x, y, z), kind, facing, setting)
                                             for x, y, z, kind, facing, setting in parse(rows)))
        self.state = fresh_state(self.circuit)
        self.sources = {index: 0 for index, part in enumerate(self.circuit.parts)
                        if part[1] in ("lever", "button", "sensor", "plate")}
        self.pressing = {}
        settle(self.circuit, self.state, dict(self.sources), {self.at(cell): FULL for cell in (held or ())})
        self.costs = []

    def at(self, cell) -> int:
        x, z = cell
        return next(index for index, part in enumerate(self.circuit.parts) if part[0] == (x, 0, z))

    def set(self, cell, on=True):
        self.sources[self.at(cell)] = FULL if on else 0

    def press(self, cell):
        self.pressing[self.at(cell)] = BUTTON_STEPS

    def tick(self, steps=1):
        for _ in range(steps):
            readings = dict(self.sources)
            for button, left in list(self.pressing.items()):
                readings[button] = FULL if left > 0 else 0
                self.pressing[button] = left - 1
                if left <= 0:
                    del self.pressing[button]
            cost, _ = step(self.circuit, self.state, readings)
            self.costs.append(cost)
        return self

    def lit(self, cell) -> bool:
        return drawn_on(self.circuit, self.state, self.at(cell))

    def trace(self, cell, steps):
        found = []
        for _ in range(steps):
            self.tick()
            found.append(self.lit(cell))
        return found


class GateTests(unittest.TestCase):
    def test_a_lever_and_copper_wire_light_a_lamp(self):
        bench = Bench(("L w w * ",))
        self.assertFalse(bench.lit((3, 0)))
        bench.set((0, 0))
        bench.tick()
        self.assertTrue(bench.lit((3, 0)) and bench.lit((1, 0)) and bench.lit((2, 0)))
        bench.set((0, 0), False)
        bench.tick()
        self.assertFalse(bench.lit((3, 0)) or bench.lit((1, 0)))

    def test_wire_carries_a_spark_fifteen_blocks_weakening_one_a_block(self):
        far = Bench(("L " + "w " * 15 + "* ",))
        far.set((0, 0))
        far.tick()
        self.assertEqual([far.state["power"][far.at((x, 0))] for x in (1, 2, 15)], [15, 14, 1])
        self.assertTrue(far.lit((16, 0)))
        too_far = Bench(("L " + "w " * 16 + "* ",))
        too_far.set((0, 0))
        too_far.tick()
        self.assertFalse(too_far.lit((17, 0)))

    def test_an_inverter_is_not(self):
        bench = Bench(("L w n>* ",))
        truth = []
        for on in (False, True, False):
            bench.set((0, 0), on)
            bench.tick(2)
            truth.append((on, bench.lit((3, 0))))
        self.assertEqual(truth, [(False, True), (True, False), (False, True)])

    def test_a_repeater_passes_its_input_on_after_its_delay_and_only_forwards(self):
        bench = Bench(("L w 3>* ",))
        bench.set((0, 0))
        self.assertEqual(bench.trace((3, 0), 5), [False, False, False, True, True])  # 3 steps after the wire
        backwards = Bench(("L w 3<* ",))  # facing away from the lever: nothing reaches the lamp
        backwards.set((0, 0))
        self.assertEqual(backwards.trace((3, 0), 5), [False] * 5)

    def test_a_joiner_ands_or_ors_what_its_two_sides_carry(self):
        for key, table in (("a", [False, False, False, True]), ("o", [False, True, True, True])):
            bench = Bench((". L . ", f". {key}>* ", ". L . "))
            found = []
            for north, south in ((0, 0), (1, 0), (0, 1), (1, 1)):
                bench.set((1, 0), bool(north))
                bench.set((1, 2), bool(south))
                bench.tick(2)
                found.append(bench.lit((2, 1)))
            self.assertEqual(found, table, key)

    def test_power_goes_into_a_gate_only_from_behind_and_out_only_at_its_front(self):
        bench = Bench((". L . ", "w 1>* ", ". . * "))
        bench.set((1, 0))  # the lever beside the repeater's side
        bench.tick(3)
        self.assertFalse(bench.lit((2, 1)))
        self.assertFalse(bench.lit((2, 2)))  # a lamp beside the repeater's side, not its front


class MachineTests(unittest.TestCase):
    CLOCK = ("w n>2>w . ",
             "w . . w * ",
             "w 2<2<w . ")

    def test_a_loop_of_repeaters_through_an_inverter_ticks_like_a_clock(self):
        bench = Bench(self.CLOCK)
        seen = bench.trace((4, 1), 60)
        rises = [index for index in range(1, len(seen)) if seen[index] and not seen[index - 1]]
        self.assertGreaterEqual(len(rises), 3)
        self.assertEqual({later - earlier for earlier, later in zip(rises, rises[1:])}, {14})  # 2 x (1 + 2 + 2 + 2)
        self.assertEqual(sum(seen[rises[0]:rises[1]]), 7)  # on for half of it

    LATCH = (". . * . ",
             "w w w B ",
             "n^Nv. . ",
             "w w w B ")

    def test_two_inverters_feeding_each_other_remember_one_bit(self):
        bench = Bench(self.LATCH, held=[(1, 2)])
        self.assertFalse(bench.lit((2, 0)))
        bench.tick(10)
        self.assertFalse(bench.lit((2, 0)))
        bench.press((3, 1))  # set
        bench.tick(4)
        self.assertTrue(bench.lit((2, 0)))
        self.assertTrue(all(bench.trace((2, 0), 100)))  # it holds long after the press
        bench.press((3, 3))  # reset
        bench.tick(4)
        self.assertFalse(bench.lit((2, 0)))
        self.assertFalse(any(bench.trace((2, 0), 100)))
        self.assertEqual(bench.costs[-1], 0)  # nothing under way: a quiet circuit costs nothing

    def test_only_what_changed_is_worked_out(self):
        bench = Bench(("L w w * . . . . . . ", ". . . . w w w w w * "))
        bench.set((0, 0))
        bench.tick()
        self.assertEqual(bench.costs[-1], 3)  # the lever's two wires and its lamp, not the other net
        bench.tick()
        self.assertEqual(bench.costs[-1], 0)


def machine(yard, rows=None, origin=(20, 1, 20), name="test", parts=None):
    """A machine Mimo finished at `origin`, from a layout (or a list of parts), every part in place."""
    parts = parts or parse(rows, origin)
    for x, y, z, kind, _, _ in parts:
        if kind != "door":
            yard.grid.put(x, y, z, MATERIALS[kind][0])
    cells = tuple(Planned((x, y, z), "part", MATERIALS[kind][0]) for x, y, z, kind, _, _ in parts if kind != "door")
    blueprint = Blueprint("machine", f"Pip's {name}", origin, cells, style={"machine": name, "circuit": parts})
    number = start(yard.db, yard.grid, blueprint, 0.0)
    finish_structure(yard.db, number, 0.0)
    return number


def snake(origin_x=0, z=0):
    """A clock (MachineTests.CLOCK without its lamp) feeding one long net of wire: 167 parts."""
    parts = parse(("w n>2>w ", "w . . w ", "w 2<2<w "), (origin_x, 1, z))
    cells = [(x, 0) for x in range(4, 44)] + [(43, 1)] + [(x, 2) for x in range(6, 44)] + [(6, 3)]
    cells += [(x, 4) for x in range(6, 44)] + [(43, 5)] + [(x, 6) for x in range(6, 44)]
    return parts + [[origin_x + x, 1, z + dz, "wire", "", 0] for x, dz in cells]


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.yard = Yard()

    def run_at(self, at):
        run_signals(self.yard.state, self.yard.context(), at)

    def material(self, x, z):
        return self.yard.grid.material(x, 1, z)

    def test_a_finished_machine_runs_in_the_tick_and_draws_what_is_lit(self):
        number = machine(self.yard, ("L w w * ",))
        self.yard.grid.put(20, 1, 20, "lever_on")
        self.run_at(1.0)
        self.assertEqual([self.material(x, 20) for x in (21, 22, 23)],
                         ["copper_wire_lit", "copper_wire_lit", "lamp_lit"])
        self.yard.grid.put(20, 1, 20, "lever")
        self.run_at(3.0)
        self.assertEqual([self.material(x, 20) for x in (21, 22, 23)], ["copper_wire", "copper_wire", "lamp"])
        self.assertEqual(machine_state(self.yard.db, number)["at"], 3.0)

    def test_the_daylight_sensor_follows_the_clock(self):
        machine(self.yard, ("S n>* ",))
        self.run_at(1000.0)
        self.assertEqual(self.material(22, 20), "lamp")
        self.run_at(1100.0)
        self.run_at(2500.0)  # night
        self.assertEqual(self.material(22, 20), "lamp_lit")

    def test_a_bell_rings_once_as_it_becomes_powered(self):
        machine(self.yard, ("L b ",), name="bell")
        self.run_at(1.0)
        self.yard.grid.put(20, 1, 20, "lever_on")
        self.run_at(2.0)
        self.run_at(3.0)
        self.assertEqual([event for event in self.yard.events if event[1] == "bell"],
                         [(1.5, "bell", "The bell on Pip's bell rang.")])

    def test_a_pressure_plate_under_mimo_powers_the_door_beside_it_and_a_press_lasts_a_second(self):
        number = machine(self.yard, ("P D B * ",))
        self.yard.grid.put(21, 1, 20, "door")
        self.run_at(1.0)
        door, lamp = 1, 3
        self.assertEqual(machine_state(self.yard.db, number)["lit"][door], 0)
        self.yard.state["position"] = {"x": 20.0, "y": 1.0, "z": 20.0}
        self.run_at(2.0)
        self.assertEqual(machine_state(self.yard.db, number)["lit"][door], 1)
        self.yard.state["position"] = {"x": 12.0, "y": 1.0, "z": 1.0}
        self.run_at(4.0)
        self.assertEqual(machine_state(self.yard.db, number)["lit"][door], 0)
        self.yard.grid.put(22, 1, 20, "button_on")
        self.run_at(4.5)
        self.assertEqual(self.material(23, 20), "lamp_lit")
        self.run_at(6.0)
        self.assertEqual((self.material(22, 20), self.material(23, 20)), ("button", "lamp"))
        self.assertEqual(machine_state(self.yard.db, number)["lit"][lamp], 0)

    def test_a_part_taken_out_is_left_out(self):
        machine(self.yard, ("L w w * ",))
        self.yard.grid.put(20, 1, 20, "lever_on")
        self.run_at(1.0)
        self.yard.grid.put(21, 1, 20, "air")
        self.run_at(2.0)
        self.assertEqual((self.material(22, 20), self.material(23, 20)), ("copper_wire", "lamp"))

    def test_the_machines_cost_no_more_than_the_budget_a_tick(self):
        for z in (20, 40, 60):
            machine(self.yard, parts=snake(20, z), origin=(20, 1, z))
        costs = []
        original = signals.run_machine

        def counted(*args, **kwargs):
            cost = original(*args, **kwargs)
            costs.append(cost)
            return cost

        with patch.object(signals, "run_machine", counted):
            self.run_at(1.0)  # each starts
            for tick in range(2, 30):
                before = len(costs)
                began = time.perf_counter()
                self.run_at(tick * 60.0)
                self.assertLess(time.perf_counter() - began, 0.1)
                self.assertLessEqual(sum(costs[before:]), MAX_CELLS)
        self.assertGreater(sum(costs), 20 * MAX_CELLS // 2)  # the clocks keep them all busy

    def test_a_different_machine_goes_first_each_tick_so_a_busy_one_keeps_none_waiting(self):
        clock = machine(self.yard, MachineTests.CLOCK, origin=(20, 1, 20))  # it could use every cell a tick
        lamp = machine(self.yard, ("L w w * ",), origin=(20, 1, 40))
        order = []
        original = signals.run_machine

        def noted(db, grid, life, number, *args):
            order.append(number)
            return original(db, grid, life, number, *args)

        with patch.object(signals, "run_machine", noted):
            for at in (1.0, 301.0, 601.0):
                self.run_at(at)
        self.assertEqual(order, [clock, lamp, lamp, clock, clock, lamp])

    def test_a_world_without_the_table_reads_as_no_signals_and_a_crash_leaves_the_tick_alone(self):
        self.assertIsNone(machine_state(sqlite3.connect(":memory:"), 1))
        forget_logged()
        with patch.object(signals, "live_machines", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.signals", level="ERROR"):
            self.run_at(1.0)


if __name__ == "__main__":
    unittest.main()

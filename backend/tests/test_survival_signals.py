import random
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import signals
from backend.survival.blueprints import Blueprint, Planned
from backend.survival.grid import world_grid
from backend.survival.hatch import hatch
from backend.survival.memory import finish_structure
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.signals import (
    BUTTON_STEPS, FULL, MATERIALS, MAX_BEHIND, MAX_CELLS, PLATE_SECONDS, STEP, compile_circuit, drawn_on,
    fresh_state, live_machines, machine_state, parse, run_machine, run_signals, settle, step, stepped_on,
)
from backend.survival.structures import start
from backend.survival.tick import advance_world
from backend.survival.world import SurvivalWorld
from backend.tests.test_survival_workshop import Yard

BORN = 1_000_000.0


class Bench:
    """A circuit on the bench: a layout's parts, their state, and the levers and buttons to work it.
    `order` (fix round 1) lists the parts in another order, to show the result does not hang on it."""

    def __init__(self, rows, held=None, order=None):
        parts = [((x, y, z), kind, facing, setting) for x, y, z, kind, facing, setting in parse(rows)]
        self.circuit = compile_circuit(tuple(order(parts) if order else parts))
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
        # Fix round 1: the lamp at (1, 2) is beside the repeater's side, the one at (2, 1) at its front; the
        # lever at (1, 0) beside its other side, the one at (0, 0) behind it (it powers the wire at (0, 1)).
        bench = Bench(("L L . ", "w 1>* ", ". * . "))
        bench.set((1, 0))  # the side lever alone
        bench.tick(3)
        self.assertEqual((bench.lit((2, 1)), bench.lit((1, 2))), (False, False))
        bench.set((0, 0))  # the lever behind it
        bench.tick(3)
        self.assertEqual((bench.lit((2, 1)), bench.lit((1, 2))), (True, False))

    # A clock and its lamp; a lever whose wires reach a joiner both straight and through an inverter; a
    # button, a repeater and two inverters in a row.
    MIXED = ("w n>2>w . . L w w w ",
             "w . . w * . w n>avw ",
             "w 2<2<w . . . . * . ",
             ". B 1>n>n>* . . . . ")

    def test_every_gate_changes_together_whatever_order_the_parts_are_in(self):
        """Fix round 1: a step is synchronous. Every gate works from what was given out the step before, so
        the same circuit with its parts listed in any order runs the same. (When the lever is thrown the
        joiner reads its wire on at once and the inverter still on for one step: its lamp flickers on.)"""
        orders = (None, lambda parts: parts[::-1], lambda parts: parts[7:] + parts[:7],
                  lambda parts: parts[1::2] + parts[::2])
        lamps = ((4, 1), (8, 2), (5, 3))
        traces = []
        for order in orders:
            bench = Bench(self.MIXED, order=order)
            trace = []
            for tick in range(40):
                if tick in (5, 30):
                    bench.set((6, 0))
                if tick == 12:
                    bench.press((1, 3))
                if tick == 25:
                    bench.set((6, 0), False)
                bench.tick()
                trace.append((*(bench.lit(lamp) for lamp in lamps), bench.costs[-1]))
            traces.append(trace)
        self.assertEqual([lit[1] for lit in traces[0]].count(True), 2)  # the joiner's flicker, twice
        self.assertEqual(traces[1:], [traces[0]] * (len(orders) - 1))


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

    def test_an_inverter_set_to_start_on_starts_on_untold(self):
        bench = Bench(self.LATCH)  # fix round 1: nothing held; the "N" at (1, 2) holds itself on
        self.assertEqual(bench.state["out"][bench.at((1, 2))], FULL)
        self.assertEqual(bench.trace((2, 0), 10), [False] * 10)  # the latch is steady, its lamp dark

    def test_only_what_changed_is_worked_out(self):
        bench = Bench(("L w w * . . . . . . ", ". . . . w w w w w * "))
        bench.set((0, 0))
        bench.tick()
        self.assertEqual(bench.costs[-1], 3)  # the lever's two wires and its lamp, not the other net
        bench.tick()
        self.assertEqual(bench.costs[-1], 0)

    # Fix round 1 ---------------------------------------------------------------------------------

    def test_a_joiner_facing_into_a_repeater_locks_it_too(self):
        """Not only another repeater (LockTests, above): a joiner facing into a repeater's side locks it
        the same way."""
        bench = Bench(("L w 1>* ", "L 1>o^. "))  # the second row's repeater and joiner feed into the first's side
        bench.set((0, 0))
        bench.tick(3)
        self.assertTrue(bench.lit((3, 0)))
        bench.set((0, 1))  # powers the joiner's side, through a repeater, into the main one's side
        bench.tick(4)
        bench.set((0, 0), False)
        bench.tick(3)
        self.assertTrue(bench.lit((3, 0)))  # locked: it still gives out what it did
        bench.set((0, 1), False)
        bench.tick(4)
        self.assertFalse(bench.lit((3, 0)))  # let go: it follows its input again

    def test_a_locked_repeaters_register_is_flushed_so_letting_go_does_not_glitch(self):
        """A repeater's register (its pending, not-yet-given-out readings) must be flushed to the value it
        is holding while locked; otherwise a stale reading queued before the lock can slip out as a brief,
        wrong flicker once it lets go."""
        bench = Bench(("L w 4>* ", ". . 1^. ", ". L w . "))
        bench.set((0, 0))  # the main repeater's input rises
        bench.set((1, 2))  # locked at once, before it has given out anything
        bench.tick(1)  # the locker takes hold
        bench.set((0, 0), False)  # the input changes while it is locked
        bench.tick(1)
        bench.set((1, 2), False)  # let go
        self.assertFalse(any(bench.tick().lit((3, 0)) for _ in range(10)))  # no stale flicker once it lets go


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
                self.assertLess(time.perf_counter() - began, 2.0)  # fix round 1: generous, the cells are the bound
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

    # Fix round 1 ---------------------------------------------------------------------------------

    def test_a_machine_that_crashes_leaves_the_next_one_running_on_the_same_tick(self):
        broken = machine(self.yard, ("L w * ",), name="broken")
        lamp = machine(self.yard, ("L w * ",), origin=(20, 1, 40))
        self.yard.grid.put(20, 1, 40, "lever_on")

        def boom(*args):
            raise RuntimeError("boom")

        forget_logged()
        with patch.dict(signals.STARTS, {"broken": boom}), \
                self.assertLogs("backend.survival.signals", level="ERROR") as logged:
            self.run_at(1.0)  # the broken one goes first
        self.assertEqual(self.material(22, 40), "lamp_lit")
        self.assertEqual(machine_state(self.yard.db, lamp)["at"], 1.0)
        self.assertIn(f"signals {broken} crashed", logged.output[0])

    def test_a_part_put_back_as_another_goes_starts_the_machine_again(self):
        """One part taken out and a different one put back in the same tick leaves the count of parts
        the same but not which they are: the machine starts again (it once hit a KeyError every tick)."""
        number = machine(self.yard, ("L w * ", "L w * "))
        self.yard.grid.put(20, 1, 20, "lever_on")
        self.yard.grid.put(20, 1, 21, "lever_on")
        self.run_at(1.0)
        self.yard.grid.put(21, 1, 20, "air")  # a wire out
        self.run_at(2.0)
        self.assertEqual(self.material(22, 20), "lamp")
        self.yard.grid.put(21, 1, 20, "copper_wire")  # back in, and the other lamp out
        self.yard.grid.put(22, 1, 21, "air")
        forget_logged()
        with self.assertNoLogs("backend.survival.signals", level="ERROR"):
            self.run_at(3.0)
            self.run_at(4.0)
        self.assertEqual(machine_state(self.yard.db, number)["at"], 4.0)
        self.assertEqual((self.material(21, 20), self.material(22, 20)), ("copper_wire_lit", "lamp_lit"))

    def test_a_crossing_mimo_will_make_later_does_not_press_the_plate_now(self):
        number = machine(self.yard, ("P * ",))
        self.run_at(1.0)
        # A walk under way from (10, 1, 20) that reaches the plate at 60.0.
        path = [{"x": x, "y": 1, "z": 20, "at": 1.5 + (x - 10) * 5.85} for x in range(10, 21)]
        self.yard.state["position"] = {"x": 10.0, "y": 1.0, "z": 20.0}
        self.yard.state["action"] = {"kind": "walk", "started_at": 1.5, "ends_at": path[-1]["at"], "path": path}
        self.run_at(2.0)
        self.assertEqual((machine_state(self.yard.db, number)["lit"][1], self.material(21, 20)), (0, "lamp"))
        self.yard.state["position"] = {"x": 20.0, "y": 1.0, "z": 20.0}
        self.run_at(60.5)  # and once Mimo gets there, it is
        self.assertEqual((machine_state(self.yard.db, number)["lit"][1], self.material(21, 20)), (1, "lamp_lit"))
        # Nor does the rest of a walk cut short before it got there.
        cut_short = {"position": {"x": 10.0, "y": 1.0, "z": 20.0}, "action": None,
                     "recent_actions": [{"kind": "walk", "ended_at": 2.0, "result": "failed", "path": path}]}
        self.assertFalse(stepped_on(cut_short, (20, 1, 20), 59.5, 60.5))

    def test_a_crossing_inside_a_long_window_opens_the_door_for_the_steps_it_covers(self):
        """A 60-game-second transaction (a catch-up, or 60x) in which Mimo crossed the plate at 31.0 and walked
        on: the door opens at that step and closes a second after Mimo stepped off (at 31.25)."""
        number = machine(self.yard, ("P D ",))
        self.yard.grid.put(21, 1, 20, "door")
        self.run_at(1.0)
        path = [{"x": 20, "y": 1, "z": z, "at": 30.75 + (z - 19) * 0.25} for z in (19, 20, 21, 22)]
        self.yard.state["recent_actions"] = [{"kind": "walk", "started_at": 30.75, "ended_at": 31.5, "path": path,
                                              "result": "done"}]
        self.yard.state["position"] = {"x": 20.0, "y": 1.0, "z": 22.0}
        opened = []
        original = signals.step

        def noted(circuit, state, readings):
            result = original(circuit, state, readings)
            opened.append(state["lit"][1])  # the door
            return result

        with patch.object(signals, "step", noted):
            self.run_at(61.0)
        self.assertEqual(len(opened), 120)
        self.assertEqual([1.0 + STEP * (index + 1) for index, lit in enumerate(opened) if lit], [31.0, 31.5, 32.0])
        self.assertEqual(machine_state(self.yard.db, number)["lit"][1], 0)

    def test_a_plate_stays_down_a_second_after_mimo_steps_off_it(self):
        plate = (20, 1, 20)
        standing = {"position": {"x": 20.0, "y": 1.0, "z": 20.0}, "action": None, "recent_actions": []}
        self.assertTrue(stepped_on(standing, plate, 99.0, 100.0))
        # Mimo stood on the plate, set off at 10.0 and stepped off it at 10.25.
        path = [{"x": x, "y": 1, "z": 20, "at": 10.0 + (x - 20) * 0.25} for x in (20, 21, 22)]
        walked = {"position": {"x": 22.0, "y": 1.0, "z": 20.0}, "action": None,
                  "recent_actions": [{"kind": "walk", "ended_at": 10.5, "path": path}]}
        down = [at for at in (5.0, 10.0, 10.5, 11.0, 11.2, 11.3, 12.0)
                if stepped_on(walked, plate, at - PLATE_SECONDS, at)]
        self.assertEqual(down, [5.0, 10.0, 10.5, 11.0, 11.2])

    def test_a_machine_far_behind_skips_ahead_instead_of_running_every_step(self):
        number = machine(self.yard, MachineTests.CLOCK)
        self.run_at(1.0)
        self.run_at(1001.0)  # 2,000 steps behind
        self.assertGreaterEqual(machine_state(self.yard.db, number)["at"], 1001.0 - MAX_BEHIND * STEP)

    def test_a_machine_state_is_written_only_when_it_changed(self):
        number = machine(self.yard, MachineTests.CLOCK)
        self.run_at(1.0)
        self.run_at(2.0)  # the clock's next step works out 5 cells (its inverter's output reaches a net)
        ((_, _, name, parts),) = live_machines(self.yard.db)
        saved = []
        with patch.object(signals, "save_state", side_effect=lambda db, which, state: saved.append(state["at"])):
            args = (self.yard.db, self.yard.grid, self.yard.state, number, name, parts, 2.5, 1.0)
            self.assertEqual(run_machine(*args, 4, []), 0)  # it does not fit in 4 cells: nothing changed
            self.assertEqual(saved, [])
            self.assertEqual(run_machine(*args, MAX_CELLS, []), 5)
            self.assertEqual(saved, [2.5])


class TickTests(unittest.TestCase):
    def test_the_tick_runs_the_machines_in_its_transaction(self):
        """Fix round 1: through the tick itself (advance_world), on a world whose tables create_world_tables
        made."""
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))
            with world.transaction() as db:
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("machine_signals", tables)
                grid = world_grid(db, world.seed)
                parts = parse(("L w w * ",), (0, 200, 0))  # up in the air, out of Mimo's way
                for x, y, z, kind, _, _ in parts:
                    grid.put(x, y, z, MATERIALS[kind][0])
                cells = tuple(Planned((x, y, z), "part", MATERIALS[kind][0]) for x, y, z, kind, _, _ in parts)
                blueprint = Blueprint("machine", "Pip's lamp", (0, 200, 0), cells,
                                      style={"machine": "lamp_lever", "circuit": parts})
                number = start(db, grid, blueprint, BORN)
                finish_structure(db, number, BORN)
            advance_world(world, BORN + 1, 1.0)
            with world.transaction() as db:
                self.assertEqual(machine_state(db, number)["at"], BORN + 1)
                world_grid(db, world.seed).put(0, 200, 0, "lever_on")
            advance_world(world, BORN + 3, 1.0)
            with world.transaction() as db:
                grid = world_grid(db, world.seed)
                self.assertEqual([grid.material(x, 200, 0) for x in (1, 2, 3)],
                                 ["copper_wire_lit", "copper_wire_lit", "lamp_lit"])
                self.assertEqual(machine_state(db, number)["at"], BORN + 3)


if __name__ == "__main__":
    unittest.main()

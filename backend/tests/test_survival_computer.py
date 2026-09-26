import sqlite3
import time
import unittest

from backend.survival import brain
from backend.survival.computer import (
    CLOCK, COMPUTER, COMPUTER_ROWS, COUNTER, COUNTER_ROWS, DAY_COLUMNS, MEMORY, REMEMBERS, computer_start,
    observe_computer, readout,
)
from backend.survival.goals import GOALS
from backend.survival.grid import Grid
from backend.survival.machines import CLEAR, MACHINES, design, next_machine
from backend.survival.memory import know, structures
from backend.survival.signals import (
    FULL, MATERIALS, MAX_CELLS, compile_circuit, corner_of, create_signal_table, fresh_state, machine_state, parse,
    run_machine, run_signals, settle, step, step_bound,
)
from backend.tests.test_survival_machines import wired
from backend.tests.test_survival_signals import Bench, machine
from backend.tests.test_survival_workshop import Yard, shares

DAY = 3600.0
MORNING = 600.0
NOON = 1200.0


def circuit_of(rows):
    parts = tuple(((x, y, z), kind, facing, setting) for x, y, z, kind, facing, setting in parse(rows))
    return compile_circuit(parts), parts


def rough(x, y, z):
    """The yard's meadow, rough away from home: 3x3 plateaus a block high, and oaks (4 logs under a leaf) in rows."""
    ground = 0
    if abs(x - 1) > 4 or abs(z - 1) > 4:
        ground = (x // 3 + z // 3) % 2
        if x % 4 == 0 and z % 3 == 0:
            if ground < y <= ground + 4:
                return "oak_log"
            if y == ground + 5:
                return "leaves"
    return "grass" if y == ground else "dirt" if y < ground else "air"


def furrowed(x, y, z):
    """The yard's meadow, furrowed away from home: every third column a block low."""
    ground = -1 if (abs(x - 1) > 4 or abs(z - 1) > 4) and x % 3 == 0 else 0
    return "grass" if y == ground else "dirt" if y < ground else "air"


def plateaus(values, least=5):
    """The values that lasted at least `least` steps, in order, each once."""
    found, run = [], 0
    for index, value in enumerate(values):
        run = run + 1 if index and value == values[index - 1] else 1
        if run == least and (not found or found[-1] != value):
            found.append(value)
    return found


class LockTests(unittest.TestCase):
    def test_a_repeater_held_from_its_side_keeps_what_it_gives_out(self):
        bench = Bench(("L w 1>* ", ". . 1^. ", ". L w . "))
        bench.set((0, 0))
        bench.tick(3)
        self.assertTrue(bench.lit((3, 0)))
        bench.set((1, 2))  # powers the repeater below, which faces into the first one's side
        bench.tick(3)
        bench.set((0, 0), False)
        bench.tick(3)
        self.assertTrue(bench.lit((3, 0)))  # locked: it still gives out what it did
        bench.set((1, 2), False)
        bench.tick(3)
        self.assertFalse(bench.lit((3, 0)))  # let go: it follows its input again


class MachineTests(unittest.TestCase):
    def test_the_clock_blinks_every_seven_steps(self):
        bench = Bench(CLOCK)
        seen = bench.trace((4, 1), 60)
        rises = [index for index in range(1, 60) if seen[index] and not seen[index - 1]]
        self.assertEqual({later - earlier for earlier, later in zip(rises, rises[1:])}, {14})

    def test_the_memory_cell_starts_dark_and_holds_what_it_is_set_to(self):
        bench = Bench(MEMORY)
        self.assertFalse(any(bench.trace((2, 0), 20)))
        bench.press((3, 1))
        bench.tick(4)
        self.assertTrue(all(bench.trace((2, 0), 200)))
        bench.press((3, 3))
        bench.tick(4)
        self.assertFalse(any(bench.trace((2, 0), 200)))

    def test_the_counter_counts_in_binary_one_for_each_tick_of_its_clock(self):
        """Its lamps between ticks, once the count has rippled through: 0 to 15 and round again."""
        bench = Bench(COUNTER)
        lamps = [(column, 11) for column in DAY_COLUMNS]
        values = []
        for _ in range(26 * 40):
            bench.tick()
            values.append(sum(1 << bit for bit, lamp in enumerate(lamps) if bench.lit(lamp)))
        counted = plateaus(values)
        start = counted.index(0)
        self.assertEqual(counted[start:start + 17], list(range(16)) + [0])

    def test_the_computer_starts_from_any_count_and_counts_each_dawn_with_a_bell_and_a_lever(self):
        circuit, parts = circuit_of(COMPUTER)
        corner = corner_of(parts)
        sensor, lever = (next(index for index, part in enumerate(circuit.parts) if part[1] == kind)
                         for kind in ("sensor", "lever"))
        read = readout(COMPUTER_ROWS)
        for day in (1, 6, 14, 16):
            state = fresh_state(circuit)
            held, forced = computer_start({"born_at": 0.0}, (day - 1) * DAY + NOON, 1.0, circuit, corner)
            self.assertEqual(forced, {})
            settle(circuit, state, {sensor: 0, lever: FULL, **forced}, held)
            self.assertEqual(read(circuit, state, corner)["value"], (day - 1) % 16)  # before this dawn
        rings, counts = 0, []
        for dawn in range(18):
            for _ in range(60):
                rings += len(step(circuit, state, {sensor: FULL, lever: FULL})[1])
            counts.append(read(circuit, state, corner)["value"])
            for _ in range(40):
                step(circuit, state, {sensor: 0, lever: FULL})
        self.assertEqual(counts, [(15 + dawn + 1) % 16 for dawn in range(18)])
        self.assertEqual(rings, 18)
        lamps = [index for index, part in enumerate(circuit.parts) if part[1] == "lamp"]
        shown = sum(state["lit"][lamp] for lamp in lamps)
        for _ in range(4):
            step(circuit, state, {sensor: 0, lever: 0})
        self.assertEqual((shown > 0, sum(state["lit"][lamp] for lamp in lamps)), (True, 0))  # hidden
        self.assertFalse(read(circuit, state, corner)["shown"])

    def test_no_step_of_any_machine_works_out_more_than_the_budget(self):
        for name, machine_kind in MACHINES.items():
            if not machine_kind.layout:
                continue
            circuit, parts = circuit_of(machine_kind.layout)
            state = fresh_state(circuit)
            settle(circuit, state, {}, {})
            sources = [index for index, part in enumerate(circuit.parts) if part[1] in ("lever", "sensor", "button")]
            worst = 0
            for tick in range(600):
                readings = {source: FULL if (tick // 50) % 2 else 0 for source in sources}
                worst = max(worst, step_bound(circuit, state, readings))
                step(circuit, state, readings)
            self.assertLessEqual(worst, MAX_CELLS // 4, name)


class YardTests(unittest.TestCase):
    def test_rough_wooded_ground_is_levelled_and_its_tree_cleared_before_the_parts_go_in(self):
        yard = wired({"copper_ingot": 4, "cobblestone": 30, "coal": 4, "sticks": 10}, goal="thinking_machine",
                     natural=rough)
        know(yard.db, "clock", "lesson", 0.0)
        blueprint = design(yard.situation(), MACHINES["clock"])
        cleared = [planned.cell for planned in blueprint.parts(CLEAR)]
        floor = blueprint.anchor[1] - 1
        trunks = {(x, z) for x, y, z in cleared if yard.grid.material(x, y, z) == "oak_log"}
        self.assertTrue(trunks)  # every spot near home has an oak in it
        for x, z in trunks:  # the whole trunk comes out, the leaf over it stays
            self.assertEqual([y for cx, y, cz in cleared if (cx, cz) == (x, z) and y > floor], [4 + floor, 3 + floor,
                                                                                               2 + floor, 1 + floor])
        self.assertEqual(cleared, sorted(cleared, key=lambda cell: (-cell[1], cell)))  # the highest first
        yard.build("build_machine", batches=12)
        self.assertIn((1.0, "built", "Pip built a clock."), yard.events)
        parts = [planned.cell for planned in blueprint.parts("part")]
        self.assertTrue(all(yard.grid.material(*cell) == "air" for cell in cleared if cell not in parts))
        self.assertEqual({y for _, y, _ in parts}, {floor + 1})
        self.assertTrue(all(yard.grid.solid((x, floor, z)) for x, _, z in parts))
        self.assertEqual([yard.grid.material(x, floor + 5, z) for x, z in trunks], ["leaves"] * len(trunks))
        lamp = next(cell for cell in parts if yard.grid.material(*cell).startswith("lamp"))
        seen = set()
        for at in range(1, 16):
            run_signals(yard.state, yard.context(), float(at))
            seen.add(yard.grid.material(*lamp))
        self.assertEqual(seen, {"lamp", "lamp_lit"})  # it ticks


    def test_low_columns_are_filled_with_dirt_first(self):
        yard = wired({"copper_ingot": 4, "cobblestone": 30, "coal": 4, "sticks": 10, "dirt": 6},
                     goal="thinking_machine", natural=furrowed)
        know(yard.db, "clock", "lesson", 0.0)
        blueprint = design(yard.situation(), MACHINES["clock"])
        filled = [planned.cell for planned in blueprint.parts("floor")]
        self.assertEqual(blueprint.parts(CLEAR), [])
        self.assertTrue(filled)
        self.assertEqual({(y, x % 3) for x, y, _ in filled}, {(0, 0)})  # the low columns, up to the floor
        yard.build("build_machine", batches=12)
        self.assertIn((1.0, "built", "Pip built a clock."), yard.events)
        self.assertTrue(all(yard.grid.material(*cell) == "dirt" for cell in filled))


class RunTests(unittest.TestCase):
    def test_built_on_day_one_it_shows_the_day_in_binary_every_day_after(self):
        """The headless run: the computer, finished in the morning of day 1, is run as the tick runs it,
        every 60 game seconds for 17 game days; at noon each day its lamps spell the day number in binary."""
        yard = Yard()
        origin = (20, 1, 20)
        number = machine(yard, COMPUTER, origin=origin, name="computer")
        lever = (origin[0] + 19, 1, origin[2] + 9)
        yard.grid.put(*lever, "lever_on")
        lamps = [(origin[0] + column, 1, origin[2] + 7) for column in DAY_COLUMNS]
        shown, slowest = [], 0.0
        for tick in range(int(MORNING / 60), int(17 * DAY / 60)):
            at = tick * 60.0
            began = time.perf_counter()
            run_signals(yard.state, yard.context(), at)
            slowest = max(slowest, time.perf_counter() - began)
            if at % DAY == NOON:
                day = int(at // DAY) + 1
                bits = "".join("1" if yard.grid.material(*lamp) == "lamp_lit" else "0" for lamp in reversed(lamps))
                readout_now = machine_state(yard.db, number)["readout"]
                shown.append((day, bits, readout_now["bits"]))
        self.assertEqual(shown, [(day, format(day % 16, "04b"), format(day % 16, "04b")) for day in range(1, 18)])
        # Fix round 1: no spurious ring at build (its sensor is no longer forced to night while it settles).
        self.assertEqual(sum(1 for event in yard.events if event[1] == "bell"), 16)
        self.assertLess(slowest, 0.05)

    def test_a_computer_finished_late_in_the_day_does_not_stay_a_day_behind_for_good(self):
        """Fix round 1: af0a585's computer_start set the count to yesterday's number and forced the sensor
        to read night while the circuit settles, relying on the machine's first real step to see the sensor
        rise and count today. Finished late in the day beside a busy clock and counter (which, at 60x or in
        a catch-up, leave it little of a tick's budget), that rise can go unseen for so long that the quiet
        shortcut compares the sensor's reading only much later, once it reads the same as the forced 0 again
        (night), and jumps ahead without ever having counted today: the display stays one day behind for
        good. Smallest case from the brief: the clock, the counter and the computer, finished at 2280 s into
        day 1, a tick every 60 game seconds. Fails on af0a585's computer_start, which shows 0001, 0010, 0011
        on the noons of days 2-4 instead of 0010, 0011, 0100."""
        db = sqlite3.connect(":memory:")
        create_signal_table(db)
        grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        origin = (20, 1, 20)
        parts = tuple(((x, y, z), kind, facing, setting)
                      for x, y, z, kind, facing, setting in parse(COMPUTER, origin))
        for (x, y, z), kind, _, _ in parts:
            grid.put(x, y, z, MATERIALS[kind][0])
        grid.put(origin[0] + 19, 1, origin[2] + 9, "lever_on")
        lamps = [(origin[0] + column, 1, origin[2] + 7) for column in DAY_COLUMNS]
        life = {"born_at": 0.0}
        events: list = []
        run_machine(db, grid, life, 1, "computer", parts, 2280.0, 1.0, MAX_CELLS, events)  # finished at dusk
        shown, tick = [], int(2280.0 // 60)
        while tick * 60.0 < 4 * DAY:
            tick += 1
            at = tick * 60.0
            # What a tick's budget has left once a busy clock and counter go first (days 1-3; ample after).
            budget = 10 if at < 3 * DAY else MAX_CELLS
            run_machine(db, grid, life, 1, "computer", parts, at, 1.0, budget, events)
            if at % DAY == NOON:
                day = int(at // DAY) + 1
                bits = "".join("1" if grid.material(*lamp) == "lamp_lit" else "0" for lamp in reversed(lamps))
                shown.append((day, bits))
        self.assertEqual(shown, [(day, format(day % 16, "04b")) for day in (2, 3, 4)])


class GoalTests(unittest.TestCase):
    def test_the_thinking_machine_comes_after_the_first_circuits_and_builds_its_four_in_order(self):
        goal = GOALS["thinking_machine"]
        self.assertEqual(goal.after, ("first_circuits",))
        self.assertEqual([milestone.text for milestone in goal.milestones][-1], "Build a computer that counts its days")
        yard = wired(goal="thinking_machine")
        self.assertIsNone(next_machine(yard.situation()))  # the clock waits for its lesson
        know(yard.db, "clock", "lesson", 0.0)
        self.assertEqual(next_machine(yard.situation()).name, "clock")
        machine(yard, CLOCK, name="clock")
        self.assertIsNone(next_machine(yard.situation()))  # the memory cell waits for the latch
        know(yard.db, "latch", "lesson", 0.0)
        self.assertEqual(next_machine(yard.situation()).name, "memory_cell")

    def test_mimo_builds_its_computer_part_by_part_then_throws_its_lever(self):
        yard = wired({"copper_ingot": 20, "cobblestone": 96, "coal": 20, "sticks": 20, "planks": 30, "glass": 3},
                     goal="thinking_machine")
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        before = (("clock", CLOCK), ("memory_cell", MEMORY), ("counter", COUNTER))
        built = [machine(yard, rows, origin=(60 + 30 * index, 1, 60), name=name)
                 for index, (name, rows) in enumerate(before)]
        yard.state["brain"]["machines_tried"] = list(built)  # tried out already
        self.assertEqual(next_machine(yard.situation()).name, "computer")
        yard.build("build_machine", batches=20)
        self.assertIn((1.0, "built", "Pip built a computer."), yard.events)
        self.assertEqual(shares(yard.situation(), "thinking_machine")[-1], 1.0)
        (computer,) = [row for row in structures(yard.db, ("machine",)) if row["id"] not in built]
        lever = next(tuple(part[:3]) for part in computer["data"]["style"]["circuit"] if part[3] == "lever")
        self.assertEqual(yard.grid.material(*lever), "lever_on")  # tried out: its lamps are shown
        # The clock and the counter spend most of each tick's budget; each machine goes first one tick in four.
        for at in range(600, 1260, 60):
            run_signals(yard.state, yard.context(), float(at))
        self.assertEqual(machine_state(yard.db, computer["id"])["readout"],
                         {"value": 1, "bits": "0001", "shown": True})

    def test_throwing_the_computers_lever_the_first_time_is_a_moment(self):
        yard = Yard()
        machine(yard, COMPUTER, origin=(20, 1, 20), name="computer")
        flip = {"kind": "flip", "target": [39, 1, 29]}
        for _ in range(2):
            observe_computer(yard.state, flip, yard.context(), 5.0)
        self.assertEqual([event for event in yard.events if event[1] == "computer"],
                         [(5.0, "computer", "Pip built a machine that remembers how long it has been alive!")])
        self.assertEqual(yard.state["last_thought"], "I built a machine that remembers how long I've been alive!")

    def test_flipping_a_different_machines_lever_does_not_claim_the_computer_moment(self):
        """computer.py:148: observe_computer checks it really is the computer the flip found, not just any
        lamp on a lever."""
        yard = Yard()
        machine(yard, ("L w w * ",), name="lamp_lever")
        flip = {"kind": "flip", "target": [20, 1, 20]}
        observe_computer(yard.state, flip, yard.context(), 5.0)
        self.assertEqual([event for event in yard.events if event[1] == "computer"], [])
        self.assertNotEqual(yard.state.get("last_thought"), REMEMBERS)

    def test_the_brain_calls_observe_computer_when_a_step_finishes(self):
        """brain.py:270: brain.observe_step must call observe_computer itself, not merely offer a function
        of the same name that nothing invokes."""
        yard = Yard()
        machine(yard, COMPUTER, origin=(20, 1, 20), name="computer")
        flip = {"kind": "flip", "target": [39, 1, 29]}
        brain.observe_step(yard.state, flip, yard.context(), 5.0)
        self.assertEqual([event for event in yard.events if event[1] == "computer"],
                         [(5.0, "computer", "Pip built a machine that remembers how long it has been alive!")])

    def test_the_computer_keeps_its_reach_of_24(self):
        """computer.py:92: the computer (and the counter), being wide, may stand farther from the workshop
        than the usual yard reach."""
        self.assertEqual(MACHINES["computer"].reach, 24)

    def test_the_caption_hides_when_the_lever_is_gone_not_just_thrown_off(self):
        """computer.py:129 (fix round 1): `all` of no levers is true, so a computer whose lever block was
        destroyed (missing from the circuit entirely, not merely thrown off) used to still read as shown
        even though its lamps are dark. The counter, which never has a lever, stays always shown."""
        all_parts = tuple(((x, y, z), kind, facing, setting)
                          for x, y, z, kind, facing, setting in parse(COMPUTER))
        corner = corner_of(all_parts)
        present = tuple(part for part in all_parts if part[1] != "lever")  # the lever's block is gone
        circuit = compile_circuit(present)
        state = fresh_state(circuit)
        settle(circuit, state, {}, {})
        self.assertFalse(readout(COMPUTER_ROWS)(circuit, state, corner)["shown"])
        counter_parts = tuple(((x, y, z), kind, facing, setting)
                              for x, y, z, kind, facing, setting in parse(COUNTER))
        counter_circuit = compile_circuit(counter_parts)
        counter_state = fresh_state(counter_circuit)
        settle(counter_circuit, counter_state, {}, {})
        self.assertTrue(readout(COUNTER_ROWS, always_shown=True)(
            counter_circuit, counter_state, corner_of(counter_parts))["shown"])


if __name__ == "__main__":
    unittest.main()

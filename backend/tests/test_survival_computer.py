import time
import unittest
from unittest.mock import patch

from backend.survival import brain, signals
from backend.survival.computer import (
    CLOCK, COMPUTER, COMPUTER_ROWS, COUNTER, COUNTER_ROWS, DAY_COLUMNS, MEMORY, REMEMBERS, TRIED_OUT, computer_start,
    observe_computer, readout,
)
from backend.survival.goals import GOALS, advancing, day_plan
from backend.survival.machines import CLEAR, MACHINES, design, next_machine
from backend.survival.making import needs, raw_needs
from backend.survival.memory import know, remember, structures
from backend.survival.purposes import PURPOSES
from backend.survival.signals import (
    FULL, MAX_CELLS, compile_circuit, corner_of, fresh_state, machine_state, parse, run_signals, settle, step,
    step_bound,
)
from backend.survival.work import ore_targets
from backend.tests.test_survival_machines import furrowed, rough, wired
from backend.tests.test_survival_signals import Bench, machine
from backend.tests.test_survival_workshop import Yard, shares

DAY = 3600.0
MORNING = 600.0
NOON = 1200.0
TICK = 60  # the night tests' tick, in game seconds


def circuit_of(rows):
    parts = tuple(((x, y, z), kind, facing, setting) for x, y, z, kind, facing, setting in parse(rows))
    return compile_circuit(parts), parts


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
            settle(circuit, state, {sensor: FULL, lever: FULL, **forced}, held)  # noon: the sensor reads day
            self.assertEqual(read(circuit, state, corner)["value"], day % 16)  # today's dawn counted
        rings, counts = 0, []
        for dawn in range(18):
            for _ in range(40):
                step(circuit, state, {sensor: 0, lever: FULL})
            for _ in range(60):
                rings += len(step(circuit, state, {sensor: FULL, lever: FULL})[1])
            counts.append(read(circuit, state, corner)["value"])
        self.assertEqual(counts, [(dawn + 1) % 16 for dawn in range(18)])
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
        shown, slowest, cells = [], 0.0, []
        real = signals.run_machine

        def counted(*args, **kwargs):
            used = real(*args, **kwargs)
            cells[-1] += used
            return used

        for tick in range(int(MORNING / 60), int(17 * DAY / 60)):
            at = tick * 60.0
            began = time.perf_counter()
            cells.append(0)
            with patch("backend.survival.signals.run_machine", counted):
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
        # Making wave 2 (the final fix wave's re-review, Minor 7): "never 50 ms in a tick" failed under load on every
        # tree alike. The tick's cost is counted in cells instead, within the budget, and the wall-clock bound
        # stays, generous, for a regression of a wholly other size.
        self.assertLessEqual(max(cells), MAX_CELLS)
        self.assertLess(slowest, 0.5)

    @staticmethod
    def noons_after(first, out=None, back=None):
        """The computer alone at 1x, first run at `first`, a tick every TICK game seconds (the final fix wave:
        it was every game second, 11,400 ticks a test) up to noon on day 4 (its lowest lamp taken out at the
        first tick from `out` and put back at the first from `back`): its lamps at noon on days 2-4."""
        yard = Yard()
        origin = (20, 1, 20)
        machine(yard, COMPUTER, origin=origin, name="computer")
        yard.grid.put(origin[0] + 19, 1, origin[2] + 9, "lever_on")
        lamps = [(origin[0] + column, 1, origin[2] + 7) for column in DAY_COLUMNS]
        shown = []
        for second in range(int(first), int(3 * DAY + NOON) + 1, TICK):
            if out is not None and second - TICK < out <= second:
                yard.grid.put(*lamps[0], "air")
            if back is not None and second - TICK < back <= second:
                yard.grid.put(*lamps[0], "lamp")
            run_signals(yard.state, yard.context(), float(second))
            if second % DAY == NOON and second > DAY:
                shown.append("".join("1" if yard.grid.material(*lamp) == "lamp_lit" else "0"
                                     for lamp in reversed(lamps)))
        return shown

    def test_a_computer_first_run_at_night_counts_today_from_the_start(self):
        """Fix round 2: f09d32c set the count to yesterday's at every hour, which is right only by day
        (its settle sees the sensor high and counts today). By night the sensor is already low, no rise is
        left to count today, and the display stays a day behind for good: 0001, 0010, 0011 at noon on days
        2-4 for a first run at 3000 s into day 1."""
        self.assertEqual(self.noons_after(3000.0), ["0010", "0011", "0100"])

    def test_a_lamp_put_back_at_night_leaves_the_count_where_it_was(self):
        """Fix round 2: a part taken out or put back starts the machine again (signals.run_machine), so a
        lamp out at 2500 s and back at 3000 s, both by night, is a night start twice over; on f09d32c the
        count fell back a day for good."""
        self.assertEqual(self.noons_after(MORNING, out=2500, back=3000), ["0010", "0011", "0100"])

    def test_a_computer_finished_at_dusk_beside_a_busy_clock_and_counter_counts_today(self):
        """Fix round 1, with the clock and the counter really running: af0a585 set the count to yesterday's
        by day and forced the sensor to read night while it settled, leaving today to be counted when a
        later step saw the sensor high. The clock and the counter, ticking since the morning, spend most of
        each tick's budget, so the computer finished at 2280 s (dusk, still day) gets no step before night
        falls; then the sensor reads low again, the same as the forced 0, the quiet shortcut jumps ahead and
        today is never counted: af0a585 shows 0001, 0010, 0011 at noon on days 2-4 instead of 0010, 0011,
        0100."""
        yard = Yard()
        machine(yard, CLOCK, origin=(50, 1, 0), name="clock")
        machine(yard, COUNTER, origin=(60, 1, 0), name="counter")
        for tick in range(10, 38):  # 600-2220 s: the clock and the counter run from the morning
            run_signals(yard.state, yard.context(), tick * 60.0)
        origin = (20, 1, 20)
        machine(yard, COMPUTER, origin=origin, name="computer")
        yard.grid.put(origin[0] + 19, 1, origin[2] + 9, "lever_on")
        lamps = [(origin[0] + column, 1, origin[2] + 7) for column in DAY_COLUMNS]
        shown = []
        for tick in range(38, 241):  # 2280 s on, a tick every 60 game seconds
            at = tick * 60.0
            run_signals(yard.state, yard.context(), at)
            if at % DAY == NOON:
                day = int(at // DAY) + 1
                bits = "".join("1" if yard.grid.material(*lamp) == "lamp_lit" else "0" for lamp in reversed(lamps))
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

    def test_with_the_memory_cell_built_the_counters_copper_sends_mine_ore_eighty_blocks_out(self):
        """Making wave 2: the counter takes 11 copper ingots and the computer 16, and on the gate's route runs
        Juniper reached the memory cell with 8 copper ore on hand. The whole next machine's copper is wanted,
        and a mine trip for it reaches MAKING_ORE_RANGE, as it does for the workshop's iron."""
        yard = wired({"copper_ingot": 0, "iron_pickaxe": 1, "coal": 20}, goal="thinking_machine")
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        machine(yard, CLOCK, origin=(60, 1, 60), name="clock")
        machine(yard, MEMORY, origin=(90, 1, 60), name="memory_cell")
        s = yard.situation()
        self.assertEqual(next_machine(s).name, "counter")
        self.assertEqual(needs(s)["copper_wire"], 53)
        self.assertGreaterEqual(raw_needs(s)["copper_ore"], 9)  # 53 wires (5 ingots) and 4 lamps
        yard.state["inventory"]["copper_ore"] = 8  # what Juniper carried: not enough
        s = yard.situation()
        self.assertGreaterEqual(raw_needs(s)["copper_ore"], 1)
        # With none known within reach, the day plan says so rather than stalling in silence.
        self.assertIn({"text": "Find more copper for the computer", "kind": "copper", "done": False, "step": None},
                      day_plan(s, GOALS["thinking_machine"]))
        far = (92, -4, 1)  # 80 blocks from Mimo
        yard.grid.put(*far, "copper_ore")
        remember(yard.db, "ore", far, 0.0, "copper_ore")
        s = yard.situation()
        self.assertNotIn("copper", [entry.get("kind") for entry in day_plan(s, GOALS["thinking_machine"])])
        self.assertEqual([(place["x"], place["y"], place["z"]) for place in ore_targets(s)], [far])
        self.assertTrue(PURPOSES["mine_ore"].valid(s))
        self.assertIn("mine_ore", advancing(s, GOALS["thinking_machine"]))
        self.assertEqual(PURPOSES["mine_ore"].plan(s, yard.context())[-1], {"kind": "mine", "target": list(far)})

    def test_a_machine_goal_with_a_machine_started_pulls_harder(self):
        """Making wave 2: on the gate's route runs the counters stood half built for 20 to 70 game days, while a
        restless pet chose a discovery goal at nearly every dawn."""
        yard = wired({"copper_ingot": 20, "cobblestone": 96, "coal": 20, "sticks": 20, "planks": 30},
                     goal="thinking_machine")
        yard.state["traits"] = {"curiosity": 50, "creativity": 50, "diligence": 40}
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        built = [machine(yard, CLOCK, origin=(60, 1, 60), name="clock"),
                 machine(yard, MEMORY, origin=(90, 1, 60), name="memory_cell")]
        yard.state["brain"]["machines_tried"] = built
        self.assertEqual(GOALS["thinking_machine"].score(yard.situation()), 57.0)
        yard.build("build_machine", batches=1)  # the counter is started
        self.assertEqual(GOALS["thinking_machine"].score(yard.situation()), 82.0)
        self.assertEqual(GOALS["first_circuits"].score(yard.situation()), 50.0)  # not one of its machines

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
        self.assertIn((1.0, "built", "Pip built Pip's computer."), yard.events)  # M1: named for Mimo
        (computer,) = [row for row in structures(yard.db, ("machine",)) if row["id"] not in built]
        lever = next(tuple(part[:3]) for part in computer["data"]["style"]["circuit"] if part[3] == "lever")
        self.assertEqual(yard.grid.material(*lever), "lever_on")  # tried out: its lamps are shown
        # Making wave 2: the milestone is whole once the lever's throw is a moment Mimo remembers (the tick's
        # observe_step; this yard carries steps out without it).
        self.assertEqual(shares(yard.situation(), "thinking_machine")[-1], TRIED_OUT)
        observe_computer(yard.state, {"kind": "flip", "target": list(lever)}, yard.context(), 2.0)
        self.assertEqual(shares(yard.situation(), "thinking_machine")[-1], 1.0)
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

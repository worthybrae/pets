import math
import unittest
from dataclasses import replace
from unittest.mock import patch

from backend.services.crafting import craft
from backend.survival.blueprints import Blueprint, Planned
from backend.survival.building import PLACES_PER_BATCH, site_center
from backend.survival.computer import CLOCK, MEMORY
from backend.survival.goals import GOALS
from backend.survival.grid import Grid
from backend.survival.machines import (
    CLEAR, FIRST, MACHINES, SITE_CACHE, SITES, WIDE_REACH, design, layout_design, machine_batch, machine_valid,
    makeable, next_machine, untried, yard_column, yard_left,
)
from backend.survival.making import raw_needs
from backend.survival.memory import know, remember, structures
from backend.survival.purposes import PURPOSES
from backend.survival.signals import machine_state, run_signals
from backend.survival.situation import Situation
from backend.survival.steps import REACH, finish_step, start_step
from backend.survival.storage import kept
from backend.survival.structures import blueprint_of, start, todo
from backend.survival.work import prospecting, wanted_ores
from backend.tests.test_survival_signals import machine
from backend.tests.test_survival_workshop import DAY, NIGHT, Yard, shares

COPPER = {"copper_ingot": 4, "sticks": 6, "cobblestone": 12, "coal": 2, "planks": 12, "oak_log": 4}
SENSOR = {"glass": 3, "slab": 3}


def rough(x, y, z):
    """A yard's meadow, rough away from home: 3x3 plateaus a block high, and oaks (4 logs under a leaf) in
    rows."""
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
    """A yard's meadow, furrowed away from home: every third column a block low."""
    ground = -1 if (abs(x - 1) > 4 or abs(z - 1) > 4) and x % 3 == 0 else 0
    return "grass" if y == ground else "dirt" if y < ground else "air"


def wired(inventory=None, goal="first_circuits", lesson=True, natural=None):
    """The yard's pet with its first circuits for its goal and (unless `lesson` is False) the lesson."""
    yard = Yard({**COPPER, **(inventory or {})}, natural=natural)
    if lesson:
        know(yard.db, "copper_spark", "lesson", 0.0)
    yard.goal(goal)
    return yard


def machine_named(yard, name):
    return next(found for found in structures(yard.db, ("machine",)) if found["data"]["style"]["machine"] == name)


class PartTests(unittest.TestCase):
    def test_the_parts_are_made_of_copper_torches_stone_and_wood(self):
        cases = {"copper_wire": ({"copper_ingot": 1}, {"copper_wire": 12}),
                 "lever": ({"sticks": 1, "cobblestone": 1}, {"lever": 1}),
                 "button": ({"planks": 1}, {"button": 1}),
                 "pressure_plate": ({"planks": 2}, {"pressure_plate": 1}),
                 "daylight_sensor": ({"glass": 3, "slab": 3, "copper_wire": 1}, {"daylight_sensor": 1}),
                 "repeater": ({"cobblestone": 3, "torch": 2, "copper_wire": 1}, {"repeater": 1}),
                 "inverter": ({"torch": 1, "copper_wire": 1}, {"inverter": 1}),
                 "joiner": ({"cobblestone": 3, "torch": 1, "copper_wire": 2}, {"joiner": 1}),
                 "lamp": ({"copper_ingot": 1, "torch": 1}, {"lamp": 1}),
                 "bell": ({"copper_ingot": 2, "sticks": 1}, {"bell": 1})}
        for recipe, (inventory, made) in cases.items():
            self.assertEqual(craft(inventory, recipe, {"crafting_table"}), made, recipe)

    def test_the_flip_step_throws_a_lever_and_presses_a_button(self):
        yard = Yard(position=(12, 1, 1))
        yard.grid.put(13, 1, 1, "lever")
        yard.grid.put(12, 1, 3, "button")
        for cell, after in (((13, 1, 1), "lever_on"), ((13, 1, 1), "lever"), ((12, 1, 3), "button_on")):
            running = start_step({"kind": "flip", "target": list(cell)}, yard.state, yard.grid, 0.0)
            finish_step(running, yard.state, yard.grid, 0.3)
            self.assertEqual(yard.grid.material(*cell), after)
        with self.assertRaises(ValueError):
            start_step({"kind": "flip", "target": [12, 1, 3]}, yard.state, yard.grid, 0.0)  # pressed already
        with self.assertRaises(ValueError):
            start_step({"kind": "flip", "target": [20, 1, 1]}, yard.state, yard.grid, 0.0)  # out of reach


class LampTests(unittest.TestCase):
    def test_a_lamp_on_a_lever_goes_on_flat_ground_by_home_with_a_walkway_round_it(self):
        yard = wired()
        blueprint = design(yard.situation(), MACHINES["lamp_lever"])
        self.assertEqual([planned.block for planned in blueprint.parts("part")],
                         ["lever", "copper_wire", "copper_wire", "lamp"])
        self.assertEqual({planned.cell[1] for planned in blueprint.parts("part")}, {1})
        self.assertEqual(len(blueprint.stands), 14)
        self.assertEqual(blueprint.style["machine"], "lamp_lever")
        self.assertEqual(len(blueprint.style["circuit"]), 4)
        self.assertFalse(any(yard.grid.claimed(planned.cell) for planned in blueprint.cells))

    def test_it_waits_for_the_lesson_the_goal_and_the_day(self):
        build = PURPOSES["build_machine"]
        self.assertFalse(build.valid(wired(lesson=False).situation()))
        self.assertIsNone(next_machine(wired(lesson=False).situation()))
        self.assertFalse(build.valid(wired(goal="workshop").situation()))
        yard = wired()
        self.assertEqual(next_machine(yard.situation()).name, "lamp_lever")
        self.assertTrue(build.valid(yard.situation()))
        self.assertFalse(build.valid(yard.situation(NIGHT)))
        self.assertIn("building a lamp on a lever: 4 parts to go", build.facts(yard.situation()))

    def test_it_builds_the_lamp_throws_the_lever_and_the_lamp_lights(self):
        yard = wired()
        yard.build("build_machine", batches=1)
        found = machine_named(yard, "lamp_lever")
        self.assertEqual(found["status"], "done")
        self.assertIn((1.0, "built", "Pip built a lamp on a lever."), yard.events)
        self.assertIsNotNone(untried(yard.situation()))
        steps = yard.plan("build_machine")
        self.assertEqual([step["kind"] for step in steps if step["kind"] != "walk"], ["flip"])
        yard.carry_out(steps, "build_machine")
        self.assertIsNone(untried(yard.situation()))
        run_signals(yard.state, yard.context(), 5.0)
        lamp = tuple(found["data"]["style"]["circuit"][3][:3])
        self.assertEqual(yard.grid.material(*lamp), "lamp_lit")
        self.assertEqual(next_machine(yard.situation()).name, "auto_door")


    def test_a_try_out_that_did_not_happen_is_tried_again(self):
        """The Making final fix wave, M3: the machine was marked tried when the flip was planned, so a walk or
        flip cut short (a reflex, out of reach) left its lever off for good. It is marked once the flip is done."""
        yard = wired()
        yard.build("build_machine", batches=1)
        found = machine_named(yard, "lamp_lever")
        steps = yard.plan("build_machine")  # the try-out is planned, then cut short before the flip
        (flip,) = [step for step in steps if step["kind"] == "flip"]
        self.assertEqual(flip["machine"], found["id"])
        self.assertEqual(yard.state["brain"].get("machines_tried", []), [])
        self.assertIsNotNone(untried(yard.situation()))  # so it is tried again
        for walk in [step for step in steps if step["kind"] == "walk"]:
            yard.state["position"] = dict(zip("xyz", map(float, walk["target"])))
        running = start_step(flip, yard.state, yard.grid, 0.0)
        finish_step(running, yard.state, yard.grid, 0.3)
        self.assertEqual(yard.state["brain"]["machines_tried"], [found["id"]])
        yard.grid.put(*flip["target"], "lever")  # thrown back off later: tried already, it stays as it is
        self.assertIsNone(untried(yard.situation()))

    def test_mimos_computer_is_named_for_it(self):
        """The Making final fix wave, M1: "Pip built a computer." read like the planted one; it is Pip's."""
        yard = wired(goal="thinking_machine")
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        s = yard.situation()
        with patch("backend.survival.machines.next_machine", lambda s: MACHINES["computer"]):
            self.assertEqual(design(s, MACHINES["computer"]).name, "Pip's computer")
            self.assertIn("building Pip's computer:", PURPOSES["build_machine"].facts(s))
        self.assertEqual(design(s, MACHINES["clock"]).name, "a clock")


class DoorAndNightTests(unittest.TestCase):
    def test_an_automatic_door_puts_plates_by_home_door_and_opens_as_mimo_steps_on_one(self):
        yard = wired()
        yard.build("build_machine", batches=2)
        yard.build("build_machine", batches=2)
        door = machine_named(yard, "auto_door")
        self.assertEqual(door["status"], "done")
        plates = [tuple(part[:3]) for part in door["data"]["style"]["circuit"] if part[3] == "plate"]
        self.assertEqual(plates, [(1, 1, -2), (1, 1, 0)])  # in front of home's door and inside it
        self.assertEqual([yard.grid.material(*cell) for cell in plates], ["pressure_plate"] * 2)
        run_signals(yard.state, yard.context(), 1.0)
        self.assertEqual(machine_state(yard.db, door["id"])["lit"][2], 0)
        yard.state["position"] = {"x": 1.0, "y": 1.0, "z": -2.0}
        run_signals(yard.state, yard.context(), 2.0)
        self.assertEqual(machine_state(yard.db, door["id"])["lit"][2], 1)  # the door is open

    def test_a_night_light_by_home_is_dark_by_day_and_lit_at_night(self):
        yard = wired(SENSOR)
        yard.build("build_machine", batches=6)
        light = machine_named(yard, "night_light")
        self.assertEqual(light["status"], "done")
        lamp = tuple(light["data"]["style"]["circuit"][2][:3])
        run_signals(yard.state, yard.context(), 1000.0)
        self.assertEqual(yard.grid.material(*lamp), "lamp")
        run_signals(yard.state, yard.context(), 2500.0)
        self.assertEqual(yard.grid.material(*lamp), "lamp_lit")
        self.assertEqual(shares(yard.situation(), "first_circuits")[2:], [1.0, 1.0, 1.0])


class CopperTests(unittest.TestCase):
    def test_the_next_machine_sends_mine_ore_after_copper_and_digging_on_to_find_some(self):
        yard = wired({"copper_ingot": 0, "stone_pickaxe": 1, "iron_pickaxe": 1})
        s = yard.situation()
        self.assertEqual(raw_needs(s)["copper_ore"], 2)
        self.assertIn("copper_ore", wanted_ores(s))
        self.assertTrue(prospecting(s))
        remember(yard.db, "ore", (30, -2, 30), 0.0, "copper_ore")
        self.assertFalse(prospecting(yard.situation()))

    def test_the_goal_mines_copper_learns_the_spark_and_builds_the_three(self):
        yard = wired({"copper_ingot": 0}, lesson=False)
        self.assertEqual(shares(yard.situation(), "first_circuits"), [0.0, 0.0, 0.0, 0.0, 0.0])
        yard.state["inventory"]["copper_ore"] = 3
        know(yard.db, "copper_spark", "lesson", 0.0)
        self.assertEqual(shares(yard.situation(), "first_circuits")[:2], [1.0, 1.0])


# Fix round 1 -----------------------------------------------------------------------------------------

class YardColumnTests(unittest.TestCase):
    def test_a_column_over_a_frozen_lake_is_refused(self):
        """machines.py:116-130: yard_column checked only the cells above the ground for water; it did not
        require the ground to rest on something solid, as blueprints.look_at's firm check does. Ice sitting
        right on a lake reads as solid ground unless the cell under it is checked too."""
        def icy(x, y, z):
            return "ice" if y == 1 else "water" if y == 0 else "air" if y > 1 else "dirt"
        self.assertIsNone(yard_column(Grid(icy), 5, 5, 0))

    def test_solid_ground_is_still_accepted(self):
        def solid(x, y, z):
            return "grass" if y == 1 else "dirt" if y < 1 else "air"
        self.assertEqual(yard_column(Grid(solid), 5, 5, 0), (1, []))

    def test_a_chopped_trunk_leaves_natural_ground_but_dug_ground_or_a_placed_block_does_not(self):
        """Making wave 2: on the gate's route runs a column Mimo had only taken growth from (a chopped trunk,
        a picked flower) was refused like one it had dug or built on, and with its farm, pen and staircases
        that left three pets no spot for the counter within 24 blocks of their workshop."""
        def wooded(x, y, z):
            if (x, z) == (5, 5) and 2 <= y <= 5:
                return "oak_log"
            if (x, z) == (6, 6) and y == 2:
                return "flower_pink"
            return "grass" if y == 1 else "dirt" if y < 1 else "air"
        grid = Grid(wooded)
        for y in range(2, 6):
            grid.put(5, y, 5, "air")  # chopped
        grid.put(6, 2, 6, "air")  # picked
        self.assertEqual((yard_column(grid, 5, 5, 0), yard_column(grid, 6, 6, 0)), ((1, []), (1, [])))
        grid.put(7, 1, 7, "air")  # dug
        grid.put(8, 2, 8, "cobblestone")  # built
        self.assertEqual((yard_column(grid, 7, 7, 0), yard_column(grid, 8, 8, 0)), (None, None))


def sunk(x, y, z):
    """A meadow with oak trunks standing in pits a block deep, every other column away from home."""
    pit = x % 2 == 0 and z % 2 == 0 and (abs(x - 1) > 2 or abs(z - 1) > 2)
    ground = -1 if pit else 0
    if pit and 0 <= y <= 3:
        return "oak_log"
    return "grass" if y == ground else "dirt" if y < ground else "air"


class SunkTrunkTests(unittest.TestCase):
    def test_a_trunks_foot_at_the_floor_is_floor_not_dug_out_and_filled_in_again_for_good(self):
        """Making wave 2: on the gate's route Hazel's computer stood 93 game days with no part in: its yard both
        cleared a birch trunk's foot at the floor's height and filled that cell in as floor, so each batch dug it
        out and the next filled it again."""
        yard = wired({"copper_ingot": 4, "cobblestone": 30, "coal": 4, "sticks": 10, "dirt": 20},
                     goal="thinking_machine", natural=sunk)
        know(yard.db, "clock", "lesson", 0.0)
        blueprint = design(yard.situation(), MACHINES["clock"])
        floor = blueprint.anchor[1] - 1
        self.assertTrue(any(yard.grid.material(*planned.cell) == "oak_log"
                            for planned in blueprint.parts("floor")))  # a trunk's foot where the floor is filled in
        clears = {planned.cell for planned in blueprint.parts(CLEAR)}
        self.assertFalse(clears & {planned.cell for planned in blueprint.parts("floor")})
        self.assertTrue(all(y > floor for _, y, _ in clears))
        stale = replace(blueprint, cells=blueprint.cells + tuple(  # a design made before: the foot cleared too
            Planned(planned.cell, CLEAR, "air") for planned in blueprint.parts("floor")))
        self.assertFalse({planned.cell for planned in yard_left(yard.situation(), stale)}
                         & {planned.cell for planned in blueprint.parts("floor")})
        yard.build("build_machine", batches=12)
        self.assertIn((1.0, "built", "Pip built a clock."), yard.events)


class RaisedYardTests(unittest.TestCase):
    def test_a_part_put_in_where_the_ground_was_dug_down_is_not_dug_out_again(self):
        """Making wave 2: where the yard's ground stands above the floor, the cell dug down is where a part goes
        in; the next batch took the part for ground still to dig, dug it out and put it in again, so a machine of
        more than one batch never got done (on the gate's route Sorrel's computer, from day 99 to 150)."""
        yard = wired({"copper_ingot": 20, "cobblestone": 96, "coal": 30, "sticks": 30, "planks": 30},
                     goal="thinking_machine", natural=rough)
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        built = [machine(yard, CLOCK, origin=(-60, 1, -60), name="clock"),
                 machine(yard, MEMORY, origin=(-60, 1, -50), name="memory_cell")]
        yard.state["brain"]["machines_tried"] = built
        blueprint = design(yard.situation(), MACHINES["counter"])
        parts = {planned.cell: planned.block for planned in blueprint.parts("part")}
        dug = [planned.cell for planned in blueprint.parts(CLEAR) if planned.cell in parts]
        self.assertTrue(dug)  # ground dug down to the floor, where parts go in
        yard.grid.put(*dug[0], parts[dug[0]])  # its part is in
        self.assertNotIn(dug[0], [planned.cell for planned in yard_left(yard.situation(), blueprint)])
        yard.grid.put(*dug[0], "grass")
        yard.build("build_machine", batches=1)  # started: the dirt its yard is still to be filled in with is kept
        started = blueprint_of(machine_named(yard, "counter"))
        self.assertEqual(kept(yard.situation(), "dirt"), len(todo(yard.grid, started, ("floor",))))
        # The fill spares the parts' wood and stone: before, it took all 96 cobblestone, and 23 parts never went in.
        yard.build("build_machine", batches=30)
        self.assertEqual(machine_named(yard, "counter")["status"], "done")


def moat(x, y, z):
    """A meadow whose home stands on an island: water on every column 8 to 30 blocks out (either way)."""
    if y == 0 and 8 <= max(abs(x - 1), abs(z - 1)) <= 30:
        return "water"
    return "grass" if y == 0 else "dirt" if y < 0 else "air"


class WideSiteTests(unittest.TestCase):
    """Making wave 2: the counter is 23 blocks wide and 12 deep, the computer 21 by 10."""

    def yard(self):
        yard = wired({"copper_ingot": 20, "cobblestone": 90, "coal": 20, "sticks": 20, "planks": 20},
                     goal="thinking_machine", natural=moat)
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        built = [machine(yard, CLOCK, origin=(-40, 1, -40), name="clock"),
                 machine(yard, MEMORY, origin=(-40, 1, -30), name="memory_cell")]
        yard.state["brain"]["machines_tried"] = built  # tried out already
        return yard

    def test_with_no_spot_within_its_reach_a_wide_machine_looks_out_to_48_blocks(self):
        yard = self.yard()
        s = yard.situation()
        self.assertEqual(next_machine(s).name, "counter")
        self.assertIsNone(layout_design(s.grid, MACHINES["counter"], site_center(s), MACHINES["counter"].reach))
        found = design(s, MACHINES["counter"])
        self.assertIsNotNone(found)
        self.assertGreater(max(abs(found.anchor[0] - 1), abs(found.anchor[2] - 1)), MACHINES["counter"].reach)
        self.assertEqual(WIDE_REACH, 48)

    def test_a_wide_site_is_looked_for_once_a_game_day_while_its_cells_stay_free_and_forgotten_once_started(self):
        """The look reads thousands of columns (up to 3 s on the gate's worlds, the review's M4)."""
        yard = self.yard()
        calls = []

        def counted(*args, **kwargs):
            calls.append(args[3])
            return layout_design(*args, **kwargs)

        with patch("backend.survival.machines.layout_design", counted):
            first = design(yard.situation(), MACHINES["counter"])
            self.assertEqual(calls, [24, 48])  # its own reach, then farther out
            self.assertEqual(design(yard.situation(), MACHINES["counter"]), first)
            self.assertEqual(len(calls), 2)  # kept for the day
            design(yard.situation({**DAY, "day_number": 2}), MACHINES["counter"])  # a new game day: looked again
            self.assertEqual(len(calls), 4)
            taken = first.parts("part")[0].cell
            yard.grid.claims.add(taken)  # something built on it since: looked again
            design(yard.situation({**DAY, "day_number": 2}), MACHINES["counter"])
            self.assertEqual(len(calls), 6)
            yard.grid.claims.discard(taken)
            self.assertIn("counter", yard.state["brain"][SITES])
            yard.plan("build_machine")
        self.assertNotIn("counter", yard.state["brain"][SITES])  # started: the site is the structure's now
        self.assertEqual(machine_named(yard, "counter")["status"], "building")

    def test_the_chooser_shares_the_site_the_tick_found(self):
        """The Chooser weighs goals on a read-only copy of the state (the final fix wave's re-review found the far
        scan's cache lost so): a world's site is also kept by its file for the process."""
        yard = self.yard()
        calls = []

        def counted(*args, **kwargs):
            calls.append(args[3])
            return layout_design(*args, **kwargs)

        with patch("backend.survival.machines.layout_design", counted), \
                patch("backend.survival.machines.world_file", lambda s: "world.sqlite3"):
            first = design(yard.situation(), MACHINES["counter"])
            brain = {key: value for key, value in yard.state["brain"].items() if key != SITES}
            snapshot = {**yard.state, "brain": brain}
            chooser = Situation(snapshot, yard.grid, DAY, 0.0, yard.db)
            self.assertEqual((design(chooser, MACHINES["counter"]), len(calls)), (first, 2))  # not looked for again
        SITE_CACHE.clear()


class StandsTests(unittest.TestCase):
    def test_a_design_with_no_stands_is_left_alone_not_crashed_on(self):
        """machines.py:387: blueprint.stands[0] raised IndexError when a design had no stands (here, one
        whose low columns still want filling with dirt), which machine_valid's caller swallowed, silently
        never building it."""
        yard = wired({"dirt": 6}, goal="thinking_machine", natural=furrowed)
        know(yard.db, "clock", "lesson", 0.0)
        s = yard.situation()
        blueprint = design(s, MACHINES["clock"])
        self.assertTrue(todo(s.grid, blueprint))  # the low columns still want filling
        stripped = replace(blueprint, stands=())
        self.assertEqual(machine_batch(s, stripped), [])


class FootingTests(unittest.TestCase):
    def test_mimo_walks_only_to_stands_with_ground_under_them_while_the_floor_is_filled(self):
        """Making wave 2: a stand in the layout's gaps is over a floor block still to fill; on the gate's route
        Willow walked for one over the air of its counter's unfilled floor, gave up (no way there) and did so
        again, from day 10 past day 57."""
        yard = wired({"copper_ingot": 20, "cobblestone": 96, "coal": 30, "sticks": 30, "planks": 30, "dirt": 60},
                     goal="thinking_machine", natural=furrowed)
        for lesson in ("clock", "latch", "adder"):
            know(yard.db, lesson, "lesson", 0.0)
        yard.state["brain"]["machines_tried"] = [machine(yard, CLOCK, origin=(-60, 1, -60), name="clock"),
                                                 machine(yard, MEMORY, origin=(-60, 1, -50), name="memory_cell")]
        s = yard.situation()
        blueprint = design(s, MACHINES["counter"])
        hanging = {stand for stand in blueprint.stands if not s.grid.solid((stand[0], stand[1] - 1, stand[2]))}
        self.assertTrue(hanging)  # stands over floor cells still to fill
        walks = []
        for _ in range(8):  # its floor goes in, 12 blocks a batch
            s = yard.situation()
            steps = machine_batch(s, blueprint)
            walks += [tuple(step["target"]) for step in steps if step["kind"] == "walk"]
            self.assertFalse({tuple(step["target"]) for step in steps if step["kind"] == "walk"}
                             & {stand for stand in blueprint.stands if not s.grid.solid((stand[0], stand[1] - 1, stand[2]))})
            yard.build("build_machine", batches=1)
        self.assertTrue(walks)
        self.assertEqual(todo(yard.grid, blueprint), [])  # the floor is all in
        self.assertLess(len(todo(yard.grid, blueprint, ("part",))), len(blueprint.parts("part")))  # and parts go in


    def test_the_floor_its_stands_reach_goes_in_first(self):
        """Fix round 1 (the re-review's Minor 3): `filling` puts in first the floor blocks the stands Mimo can stand
        on reach. In the design's order the first 12 went to cells no such stand reached, and the batch placed none."""
        yard = wired({"dirt": 40}, goal="thinking_machine")
        far = [(50 + n, 0, 30) for n in range(PLACES_PER_BATCH + 4)]
        near = [(31, 0, 30), (32, 0, 30), (33, 0, 30)]
        for cell in far + near:
            yard.grid.put(*cell, "air")  # floor still to fill
        cells = tuple(Planned(cell, "floor", "dirt") for cell in far + near)
        blueprint = Blueprint("machine", "Pip's test", (30, 1, 30), cells, stands=((30, 1, 30), (40, 1, 30)),
                              style={"machine": "test", "circuit": []})
        yard.grid.put(40, 0, 30, "air")  # that stand hangs over a hole
        yard.state["position"] = {"x": 30.0, "y": 1.0, "z": 30.0}
        steps = machine_batch(yard.situation(), blueprint)
        self.assertEqual([tuple(step["target"]) for step in steps if step["kind"] == "place"], near)

    def test_the_try_out_walks_only_to_a_stand_with_ground_under_it(self):
        """Fix round 1 (the re-review's Minor 3): the try-out's flips go through `footing` too."""
        yard = wired()
        yard.build("build_machine", batches=1)
        found, blueprint = untried(yard.situation())
        lever = next(tuple(part[:3]) for part in blueprint.style["circuit"] if part[3] == "lever")
        yard.state["position"] = {"x": 12.0, "y": 1.0, "z": 30.0}  # away: it walks to a stand first
        s = yard.situation()
        reaching = sorted((stand for stand in blueprint.stands if math.dist(stand, lever) <= REACH and stand != lever),
                          key=lambda stand: (math.dist(stand, s.here), stand))
        yard.grid.put(reaching[0][0], reaching[0][1] - 1, reaching[0][2], "air")  # the nearest one hangs now
        walks = [tuple(step["target"]) for step in yard.plan("build_machine") if step["kind"] == "walk"]
        self.assertTrue(walks)
        self.assertNotIn(reaching[0], walks)
        self.assertTrue(all(yard.grid.solid((x, y - 1, z)) for x, y, z in walks))


class FirstCircuitsTests(unittest.TestCase):
    def test_with_one_of_its_machines_started_the_first_circuits_pull_harder(self):
        """Fix round 1 (the re-review's Minor 3): the first circuits score workshop.UNDER_WAY (25) more while one of
        their machines is started, as the thinking machine does."""
        yard = wired()
        before = GOALS[FIRST].score(yard.situation())
        start(yard.db, yard.grid, design(yard.situation(), MACHINES["night_light"]), 0.0)
        self.assertEqual(GOALS[FIRST].score(yard.situation()), before + 25.0)
        self.assertEqual(GOALS["thinking_machine"].score(yard.situation()),
                         GOALS["thinking_machine"].score(wired().situation()))  # not one of its machines


class MachineValidTests(unittest.TestCase):
    def test_it_stays_valid_for_yard_clearing_alone_even_with_nothing_to_craft(self):
        """machines.py:411: machine_valid must check machine_batch (which also covers the yard's levelling,
        T3), not makeable (which only looks at parts Mimo could craft now); a yard that still needs
        levelling but has no materials for any part would otherwise read as invalid."""
        yard = Yard(natural=rough)  # no inventory at all: nothing craftable
        yard.goal("thinking_machine")
        know(yard.db, "clock", "lesson", 0.0)
        s = yard.situation()
        blueprint = design(s, MACHINES["clock"])
        self.assertTrue(yard_left(s, blueprint))
        self.assertEqual(makeable(s, blueprint), [])
        self.assertTrue(machine_batch(s, blueprint))
        self.assertTrue(machine_valid(s))


if __name__ == "__main__":
    unittest.main()

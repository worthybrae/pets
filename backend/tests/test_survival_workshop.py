import sqlite3
import unittest

from backend.services.crafting import BLOCKS, add_item, craft, smelt
from backend.survival import brain  # noqa: F401  (registers every purpose and goal)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.blueprints import Style, find_site, shelter
from backend.survival.building import building_need, note_building
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.goals import GOALS, adopt_goal, share_of
from backend.survival.grid import Grid
from backend.survival.making import raw_needs
from backend.survival.memory import create_memory_tables, finish_structure, set_home, structures
from backend.survival.purposes import PURPOSES
from backend.survival.signals import create_signal_table
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of, start, todo
from backend.survival.vitals import START_VITALS
from backend.survival.workshop import FIXTURE, current_workshop, design_workshop, fixtures_left

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
STATIONS = {"crafting_table", "furnace", "kiln", "campfire"}
BLOCKS_FOR_IT = {"cobblestone": 60, "planks": 30, "oak_log": 6}
FITTINGS = {"brick": 3, "iron_ingot": 6, "sticks": 4, "coal": 2}


class Yard:
    """A pet on a flat meadow whose home, a 3x3 cobblestone shelter by (1, 1, 1), is built: where the
    workshop and (T2, T3) the machines go up. Steps are carried out at once, the way they would end."""

    def __init__(self, inventory=None, position=(12, 1, 1), traits=None):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        create_creature_tables(self.db)
        create_signal_table(self.db)  # T2: the machines' signals
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        self.grid.herd = Herd(self.db)
        site = find_site(self.grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
        self.home = shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Snug Cottage")
        for planned in self.home.parts("floor", "wall", "roof"):
            self.grid.put(*planned.cell, "cobblestone")
        self.grid.put(*self.home.one("door"), "door")
        finish_structure(self.db, start(self.db, self.grid, self.home, 0.0), 1.0)
        set_home(self.db, self.home.anchor, 1.0)
        self.state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                      "inventory": dict(inventory or {}), "vitals": dict(START_VITALS),
                      "traits": dict(traits or {"creativity": 50}), "last_tick_at": 0.0, "born_at": 0.0}
        ensure_actions(self.state)
        self.events = []

    def situation(self, clock=DAY):
        return Situation(self.state, self.grid, clock, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=self.events,
                             db=self.db)

    def goal(self, name):
        adopt_goal(self.state, name, "rules", "", 0.0)

    def plan(self, purpose, clock=DAY):
        return PURPOSES[purpose].plan(self.situation(clock), self.context())

    def carry_out(self, steps, purpose="build_workshop"):
        inventory = self.state["inventory"]
        for step in steps:
            kind = step["kind"]
            if kind == "walk":
                self.state["position"] = dict(zip("xyz", map(float, step["target"])))
            elif kind == "craft":
                inventory = craft(inventory, step["recipe"], STATIONS)
            elif kind == "smelt":
                inventory = smelt(inventory, step["item"], {"furnace"})
            elif kind == "place":
                inventory[step["block"]] -= 1
                inventory = {item: count for item, count in inventory.items() if count}
                self.grid.put(*step["target"], step["block"])
            elif kind == "mine":
                drop = BLOCKS.get(self.grid.material(*step["target"]), {}).get("drop")
                self.grid.put(*step["target"], "air")
                if drop:
                    add_item(inventory, drop)
            elif kind == "flip":  # T2: a lever thrown, a button pressed
                material = self.grid.material(*step["target"])
                flipped = {"lever": "lever_on", "lever_on": "lever", "button": "button_on"}[material]
                self.grid.put(*step["target"], flipped)
            self.state["inventory"] = inventory
            if kind in ("place", "mine"):
                note_building(self.state, {**step, "purpose": purpose}, self.context(), 1.0)

    def build(self, purpose="build_workshop", batches=20):
        for _ in range(batches):
            steps = self.plan(purpose)
            if not steps:
                return
            self.carry_out(steps, purpose)


class DesignTests(unittest.TestCase):
    def test_a_workshop_is_a_shelter_fitted_out_for_making(self):
        yard = Yard()
        design = design_workshop(yard.grid, "1", (1, 1, 1), {"creativity": 50}, "Pip")
        self.assertEqual((design.kind, design.name), ("workshop", "Pip's Workshop"))
        fixtures = sorted(planned.block for planned in design.parts(FIXTURE))
        for block in ("crafting_table", "furnace", "kiln", "barrel", "stairs", "trapdoor"):
            self.assertIn(block, fixtures)
        self.assertEqual(fixtures.count("iron_bars"), 2)
        self.assertEqual({planned.block for planned in design.parts("roof")}, {"slab"})
        self.assertEqual(len(design.parts("roof")), 8)  # nine over the inside, less the hatch
        self.assertEqual(design.parts("bed") + design.parts("chest") + design.parts("campfire"), [])
        taken = {planned.cell for planned in design.parts(FIXTURE)}
        self.assertEqual(len(design.stands), 4)
        self.assertFalse(taken & set(design.stands))
        self.assertFalse(any(yard.grid.claimed(planned.cell) for planned in design.cells))  # clear of home


class BuildTests(unittest.TestCase):
    def test_offered_while_it_is_the_goal_by_day_by_home_with_half_its_blocks(self):
        build = PURPOSES["build_workshop"]
        yard = Yard(BLOCKS_FOR_IT)
        self.assertFalse(build.valid(yard.situation()))  # not its goal
        yard.goal("workshop")
        self.assertTrue(build.valid(yard.situation()))
        self.assertFalse(build.valid(yard.situation(NIGHT)))
        self.assertFalse(build.valid(Yard(BLOCKS_FOR_IT, position=(120, 1, 1)).situation()))  # far from home
        few = Yard({"cobblestone": 10})
        few.goal("workshop")
        self.assertFalse(build.valid(few.situation()))
        self.assertIn("no workshop yet", build.facts(yard.situation()))

    def test_it_rises_wall_by_wall_under_a_roof_of_slabs_and_is_done(self):
        yard = Yard(BLOCKS_FOR_IT)
        yard.goal("workshop")
        first = yard.plan("build_workshop")
        (workshop,) = structures(yard.db, ("workshop",))
        self.assertEqual(workshop["status"], "building")
        # From outside it first makes the roof's slabs at a table it puts down and takes back...
        self.assertEqual([step["recipe"] for step in first if step["kind"] == "craft"][-2:], ["slab", "slab"])
        self.assertEqual([step["block"] for step in first if step["kind"] == "place"][0], "crafting_table")
        # ...then walks in and raises the first 12 blocks of wall.
        self.assertEqual([step["block"] for step in first if step["kind"] == "place"][1:], ["cobblestone"] * 12)
        yard.carry_out(first)
        yard.build()
        workshop = current_workshop(yard.situation())
        self.assertEqual(workshop["status"], "done")
        blueprint = blueprint_of(workshop)
        self.assertEqual({yard.grid.material(*planned.cell) for planned in blueprint.parts("roof")}, {"slab"})
        self.assertIn((1.0, "built", "Pip built Pip's Workshop."), yard.events)

    def test_then_it_is_fitted_out_the_crafting_table_furnace_kiln_and_barrel_first(self):
        yard = Yard({**BLOCKS_FOR_IT, **FITTINGS})
        yard.goal("workshop")
        yard.build()
        blueprint = blueprint_of(current_workshop(yard.situation()))
        self.assertEqual([planned.block for planned in fixtures_left(yard.situation(), blueprint)], [])
        for planned in blueprint.parts(FIXTURE):
            self.assertEqual(yard.grid.material(*planned.cell), planned.block)
        self.assertEqual(shares(yard.situation(), "workshop"), [1.0, 1.0, 1.0, 1.0])

    def test_what_it_wants_brings_clay_for_the_kiln_and_blocks_for_its_walls(self):
        yard = Yard({"cobblestone": 5, "oak_log": 2})
        s = yard.situation()
        self.assertEqual((raw_needs(s), building_need(s)), ({}, 0))
        yard.goal("workshop")
        s = yard.situation()
        self.assertEqual(raw_needs(s)["clay"], 3)  # three bricks for the kiln; the bars' iron waits for mine_ore
        self.assertEqual(building_need(s), 28 - 5)  # its walls, less the cobblestone carried


def shares(s, name):
    return [round(share_of(s, milestone), 2) for milestone in GOALS[name].milestones]


class GoalTests(unittest.TestCase):
    def test_the_workshop_comes_after_a_home_and_iron_tools(self):
        self.assertEqual(GOALS["workshop"].after, ("first_shelter", "iron_tools"))
        yard = Yard({"brick": 2})
        self.assertEqual(shares(yard.situation(), "workshop"), [0.67, 0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()

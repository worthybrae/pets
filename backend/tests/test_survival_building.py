import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import building  # noqa: F401  (registers build_shelter)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.building import building_need, note_building
from backend.survival.grid import Grid
from backend.survival.memory import BUILT, create_memory_tables, places, remember, set_home, structures
from backend.survival.purposes import PURPOSES, home_of
from backend.survival.reflexes import by_name
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of, todo
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
AFTERNOON = {**DAY, "seconds_into_day": 1500.0}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}
TRAITS = {"creativity": 0, "thrift": 90, "caution": 50}  # a flat cobblestone roof, no windows: a 39-block hut


def meadow(cells=None):
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (cells or {}).items():
        grid.put(*cell, block)
    return grid


class World:
    """One pet on a flat meadow with its memory, kept across situations like the tick keeps them."""

    def __init__(self, inventory=None, position=(1, 1, 1), grid=None):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = grid or meadow()
        self.state = {"name": "Pip", "world_seed": "1", "position": dict(zip("xyz", map(float, position))),
                      "inventory": dict(inventory or {}), "vitals": dict(START_VITALS), "traits": dict(TRAITS),
                      "last_tick_at": 0.0}
        ensure_actions(self.state)

    def situation(self, clock=DAY):
        return Situation(self.state, self.grid, clock, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=self.db)

    def plan(self, clock=DAY):
        s = self.situation(clock)
        return PURPOSES["build_shelter"].plan(s, self.context())

    def carry_out(self, steps):
        """Do the planned steps at once, the way they would end: walks move Mimo, places use a block."""
        context = self.context()
        for step in steps:
            if step["kind"] == "walk":
                self.state["position"] = dict(zip("xyz", map(float, step["target"])))
            elif step["kind"] == "craft":
                from backend.services.crafting import craft
                self.state["inventory"] = craft(self.state["inventory"], step["recipe"], set())
            elif step["kind"] == "place":
                self.state["inventory"][step["block"]] -= 1
                self.grid.put(*step["target"], step["block"])
                note_building(self.state, {**step, "purpose": "build_shelter"}, context, 1.0)
            elif step["kind"] == "mine":
                self.grid.put(*step["target"], "air")
        return context


def places_of(steps):
    return [step for step in steps if step["kind"] == "place"]


class ShelterTests(unittest.TestCase):
    def test_offered_by_day_once_mimo_carries_half_the_blocks(self):
        shelter = PURPOSES["build_shelter"]
        self.assertFalse(shelter.valid(World({"cobblestone": 19}).situation()))
        self.assertTrue(shelter.valid(World({"cobblestone": 20}).situation()))
        self.assertFalse(shelter.valid(World({"cobblestone": 60}).situation(NIGHT)))
        self.assertIn("would need 39 blocks, carrying 20 (short 19)", shelter.facts(World({"cobblestone": 20}).situation()))

    def test_the_first_batch_starts_the_design_walks_in_and_places_twelve_blocks_in_order(self):
        world = World({"cobblestone": 60}, position=(6, 1, 6))
        remember(world.db, "home", (1, -3, 1), 0.0)  # a mine staircase: the shelter goes on the surface above
        steps = world.plan()
        self.assertEqual(steps[0], {"kind": "walk", "target": [1, 1, 1], "reach": 0.0, "whole": True})
        placed = places_of(steps)
        self.assertEqual(len(placed), 12)
        self.assertEqual({step["block"] for step in placed}, {"cobblestone"})
        self.assertEqual([row["status"] for row in structures(world.db)], ["building"])
        self.assertTrue(world.grid.claimed((1, 1, 1)))
        design = blueprint_of(structures(world.db)[0])
        self.assertEqual([step["target"] for step in placed], [list(planned.cell) for planned in todo(world.grid, design)[:12]])

    def test_logs_become_planks_when_the_planks_run_short(self):
        world = World({"oak_log": 10})
        steps = world.plan()
        self.assertEqual(steps[:3], [{"kind": "craft", "recipe": "planks"}] * 3)
        self.assertEqual({step["block"] for step in places_of(steps)}, {"planks"})

    def test_it_pauses_when_the_blocks_run_out_and_gathering_aims_higher(self):
        world = World({"cobblestone": 20, "wooden_pickaxe": 1})
        world.carry_out(world.plan())
        world.carry_out(world.plan())
        self.assertEqual(world.state["inventory"]["cobblestone"], 0)
        s = world.situation()
        self.assertEqual(world.plan(), [])
        self.assertFalse(PURPOSES["build_shelter"].valid(s))
        self.assertEqual(building_need(s), 19)
        self.assertIn("19 blocks to go, carrying 0 (short 19)", PURPOSES["build_shelter"].facts(s))
        world.state["inventory"]["dirt"] = 8
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))
        self.assertEqual({step["block"] for step in places_of(world.plan())}, {"dirt"})

    def test_the_last_block_finishes_it_and_home_moves_in(self):
        world = World({"cobblestone": 40})
        remember(world.db, "home", (30, -4, 30), 0.0)
        with patch("backend.survival.building.site_center", lambda s: (1, 1, 1)):
            for _ in range(4):
                context = world.carry_out(world.plan())
        self.assertEqual(structures(world.db)[0]["status"], "done")
        home = places(world.db, ("home",))[0]
        self.assertEqual(((home["x"], home["y"], home["z"]), home["note"]), ((1, 1, 1), BUILT))
        self.assertEqual(context.events[-1][1:], ("built", "Pip finished building Pip's Snug Cottage and moved in."))
        self.assertIn("built", world.state["brain"]["pending"]["reasons"])
        self.assertEqual(world.state["vitals"]["mood"], 80.0)

    def test_a_finished_shelter_gets_a_bed_and_a_campfire(self):
        world = World({"cobblestone": 40})
        for _ in range(4):
            world.carry_out(world.plan())
        world.state["inventory"] = {"oak_log": 4}
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))
        self.assertEqual(PURPOSES["build_shelter"].score(world.situation()), 45.0)
        steps = world.plan()
        design = blueprint_of(structures(world.db)[0])
        self.assertEqual(places_of(steps), [{"kind": "place", "target": list(design.one("bed")), "block": "bed"},
                                            {"kind": "place", "target": list(design.one("campfire")), "block": "campfire"}])
        self.assertIn({"kind": "craft", "recipe": "bed"}, steps)
        world.carry_out(steps)
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))

    def test_a_damaged_shelter_is_repaired_and_a_blocked_door_cleared(self):
        world = World({"cobblestone": 40})
        for _ in range(4):
            world.carry_out(world.plan())
        design = blueprint_of(structures(world.db)[0])
        wall = design.parts("wall")[5].cell
        world.grid.put(*wall, "air")
        world.grid.put(*design.front, "furnace")
        world.state["inventory"] = {"dirt": 3}
        s = world.situation()
        self.assertTrue(PURPOSES["build_shelter"].valid(s))
        self.assertEqual(PURPOSES["build_shelter"].score(s), 75.0)
        self.assertIn("damaged: 1 blocks missing", PURPOSES["build_shelter"].facts(s))
        self.assertEqual(world.plan(), [{"kind": "mine", "target": list(design.front)},
                                        {"kind": "place", "target": list(wall), "block": "dirt"}])
        world.state["position"] = {"x": 9.0, "y": 1.0, "z": 9.0}  # outside: the way in is cleared from outside
        steps = world.plan()
        self.assertEqual(steps[1], {"kind": "mine", "target": list(design.front)})
        self.assertEqual(steps[0]["reach"], 2.0)
        self.assertEqual(steps[2], {"kind": "walk", "target": list(design.anchor), "reach": 0.0, "whole": True})

    def test_it_scores_in_the_needs_band_and_more_in_the_afternoon(self):
        world = World({"cobblestone": 40})
        self.assertEqual(PURPOSES["build_shelter"].score(world.situation()), 65.0)
        self.assertEqual(PURPOSES["build_shelter"].score(world.situation(AFTERNOON)), 75.0)

    def test_one_shelter_within_128_blocks_is_enough(self):
        world = World({"cobblestone": 40})
        world.plan()
        world.state["position"] = {"x": 90.0, "y": 1.0, "z": 1.0}
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))
        world.state["position"] = {"x": 200.0, "y": 1.0, "z": 1.0}
        self.assertTrue(PURPOSES["build_shelter"].valid(world.situation()))


class HomeTests(unittest.TestCase):
    def test_the_built_home_comes_before_a_nearer_shelter(self):
        world = World()
        remember(world.db, "shelter", (5, 1, 1), 0.0)
        set_home(world.db, (20, 1, 1), 0.0)
        self.assertEqual(home_of(world.situation())["x"], 20)
        found = World()
        remember(found.db, "shelter", (5, 1, 1), 0.0)
        remember(found.db, "home", (20, 1, 1), 0.0)
        self.assertEqual(home_of(found.situation())["x"], 5)

    def test_head_home_leaves_building_and_lighting_at_home_alone(self):
        world = World(position=(10, 1, 10))
        set_home(world.db, (1, 1, 1), 0.0)
        head_home = by_name("head_home")
        dusk = {**DAY, "seconds_into_day": 2100.0}
        self.assertTrue(head_home.trigger(world.situation(dusk)))
        for purpose in ("build_shelter", "light_up"):
            world.state["brain"]["purpose"] = purpose
            self.assertFalse(head_home.trigger(world.situation(dusk)), purpose)


class LessonTests(unittest.TestCase):
    def test_a_planted_sapling_is_remembered_so_its_tree_is_mimos_to_chop(self):
        world = World()
        note_building(world.state, {"kind": "plant", "target": [5, 1, 0], "item": "sapling"}, world.context(), 3.0)
        self.assertEqual([(place["kind"], place["x"], place["z"]) for place in places(world.db, ("tree",))],
                         [("tree", 5, 0)])

    def test_full_arms_ask_for_a_choice(self):
        world = World()
        world.state["full_at"] = 4.0
        note_building(world.state, {"kind": "mine", "target": [5, 0, 0], "block": "dirt"}, world.context(), 4.0)
        self.assertIn("full", world.state["brain"]["pending"]["reasons"])

    def test_each_torch_lifts_mood_a_little(self):
        world = World()
        note_building(world.state, {"kind": "place", "target": [5, 1, 0], "block": "torch"}, world.context(), 4.0)
        self.assertEqual(world.state["vitals"]["mood"], 72.0)


if __name__ == "__main__":
    unittest.main()

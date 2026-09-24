import math
import unittest

from backend.services.blocks import hardness, is_replaceable, is_solid, mining_tool
from backend.services.crafting import BLOCKS, craft
from backend.survival.blueprints import Style, find_site, from_data, shelter, with_door
from backend.survival.creatures.moves import steps
from backend.survival.creatures.table import Herd, cell_of, create_creature_tables
from backend.survival.grid import Grid
from backend.survival.memory import remember, set_home, structures
from backend.survival.pathing import route
from backend.survival.purposes import BUILT_HOME_RANGE, HOME_RANGE, PURPOSES, home_of
from backend.survival.structures import blueprint_of, todo
from backend.tests.test_survival_building import World, places_of


def meadow():
    return Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")


def hut():
    grid = meadow()
    site = find_site(grid, (1, 1, 1), (3, 3), ("north",), "flat", reach=0)
    return shelter(site, Style("flat", "cobblestone", "planks", "none", ("north",)), "Pip's Hut")


class DoorBlockTests(unittest.TestCase):
    def test_a_door_takes_six_planks_and_is_no_wall_and_no_floor(self):
        self.assertEqual(craft({"planks": 6}, "door", set()), {"door": 1})
        self.assertFalse(is_solid("door"))
        self.assertFalse(is_replaceable("door"))
        self.assertEqual((hardness("door"), mining_tool("door"), BLOCKS["door"]["drop"]), (2.0, "axe", "door"))

    def test_mimo_walks_through_a_door_in_a_wall(self):
        grid = meadow()
        for z in range(-6, 7):
            for y in (1, 2):
                grid.put(2, y, z, "cobblestone")
        grid.put(2, 1, 0, "door")
        grid.put(2, 2, 0, "air")
        cells, reached = route(grid, (0, 1, 0), (4, 1, 0))
        self.assertTrue(reached)
        self.assertIn((2, 1, 0), cells)

    def test_creatures_never_step_into_a_door_or_a_cell_mimo_built(self):
        grid = meadow()
        grid.put(1, 1, 0, "door")
        grid.claims.add((0, 1, 1))
        self.assertEqual(sorted(steps(grid, (0, 1, 0), False)), [(-1, 1, 0), (0, 1, -1)])
        hole = meadow()
        hole.put(1, 0, 0, "air")  # a hole under a door: dropping into it passes through the door
        hole.put(1, 1, 0, "door")
        self.assertNotIn((1, 0, 0), steps(hole, (0, 1, 0), False))
        hole.put(1, 1, 0, "air")
        self.assertIn((1, 0, 0), steps(hole, (0, 1, 0), False))


class ShelterDoorTests(unittest.TestCase):
    def test_a_new_shelter_plans_a_door_in_the_lower_gap_and_keeps_the_cell_above_open(self):
        design = hut()
        self.assertEqual([(planned.cell, planned.block) for planned in design.parts("door")],
                         [((1, 1, -1), "door"), ((1, 2, -1), "air")])
        self.assertEqual([planned.cell for planned in todo(meadow(), design, ("door",))], [(1, 1, -1)])

    def test_a_shelter_designed_before_doors_gets_one_when_it_is_read(self):
        data = hut().to_data()
        data["cells"] = [[x, y, z, part, "air" if part == "door" else block] for x, y, z, part, block in data["cells"]]
        old = from_data(data)
        self.assertEqual({planned.block for planned in old.parts("door")}, {"air"})
        upgraded = blueprint_of({"data": data})
        self.assertEqual([planned.block for planned in upgraded.parts("door")], ["door", "air"])
        self.assertEqual(with_door(upgraded), upgraded)

    def test_a_finished_shelter_is_furnished_with_a_door_and_mimo_still_walks_in(self):
        world = World({"cobblestone": 40})
        create_creature_tables(world.db)
        world.grid.herd = Herd(world.db)
        for _ in range(4):
            world.carry_out(world.plan())
        design = blueprint_of(structures(world.db)[0])
        rabbit = world.grid.herd.add("rabbit", design.anchor, 3.0, 0.0, 0.0, {"home": list(design.anchor)})
        self.assertTrue(world.grid.claimed(design.anchor))  # it wandered in while the walls went up
        world.state["inventory"] = {"bed": 1, "campfire": 1, "planks": 6}
        self.assertIn("a bed and a campfire and a door", PURPOSES["build_shelter"].facts(world.situation()))
        steps_planned = world.plan()
        self.assertIn({"kind": "craft", "recipe": "door"}, steps_planned)
        door = design.one("door")
        self.assertEqual(places_of(steps_planned)[-1], {"kind": "place", "target": list(door), "block": "door"})
        world.carry_out(steps_planned)
        self.assertEqual(world.grid.material(*door), "door")
        put_out = cell_of(world.grid.herd.get(rabbit["id"]))
        self.assertFalse(world.grid.claimed(put_out))
        self.assertLessEqual(math.dist(put_out, design.front), 3)
        self.assertFalse(PURPOSES["build_shelter"].valid(world.situation()))
        outside = tuple(2 * front - gap for front, gap in zip(design.front, door))  # one beyond the front
        cells, reached = route(world.grid, outside, design.anchor)
        self.assertTrue(reached)
        self.assertIn(door, cells)

    def test_the_home_mimo_built_stays_home_from_twice_as_far_as_any_other_shelter(self):
        self.assertEqual(BUILT_HOME_RANGE, 2 * HOME_RANGE)
        world = World(position=(101, 1, 1))
        set_home(world.db, (1, 1, 1), 0.0)
        remember(world.db, "shelter", (90, 1, 1), 0.0)
        self.assertEqual(home_of(world.situation())["x"], 1)
        world.state["position"]["x"] = 140.0
        self.assertEqual(home_of(world.situation())["x"], 90)


if __name__ == "__main__":
    unittest.main()

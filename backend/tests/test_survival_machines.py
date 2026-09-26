import unittest

from backend.services.crafting import craft
from backend.survival.machines import MACHINES, design, next_machine, untried
from backend.survival.making import raw_needs
from backend.survival.memory import know, remember, structures
from backend.survival.purposes import PURPOSES
from backend.survival.signals import machine_state, run_signals
from backend.survival.steps import finish_step, start_step
from backend.survival.work import prospecting, wanted_ores
from backend.tests.test_survival_workshop import NIGHT, Yard, shares

COPPER = {"copper_ingot": 4, "sticks": 6, "cobblestone": 12, "coal": 2, "planks": 12, "oak_log": 4}
SENSOR = {"glass": 3, "slab": 3}


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


if __name__ == "__main__":
    unittest.main()

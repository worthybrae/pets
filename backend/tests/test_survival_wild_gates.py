"""W1: what a wild newborn does not know yet, and a gentle pet always does (the lessons table's gates)."""

import unittest
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival.camp import lit_camp
from backend.survival.goals import GOALS, is_open
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.reflexes import plan_warm_up
from backend.survival.memory import know, structures
from backend.survival.structures import blueprint_of
from backend.survival.wild import thing
from backend.tests.test_survival_building import World, places_of
from backend.tests.test_survival_cooking import plan as cook_plan, situation as cook_situation
from backend.tests.test_survival_expedition import DUSK, FLAT, Expedition
from backend.tests import test_survival_lighting as lighting


def wild(s, *lessons):
    """`s` made a wild pet's, knowing `lessons`."""
    s.state["difficulty"] = "wild"
    for name in lessons:
        know(s.db, thing(name), "lesson", 0.0)
    s.__dict__.pop("lessons", None)  # read again
    return s


class FireAndCookingTests(unittest.TestCase):
    def test_a_wild_pet_cooks_meat_only_once_it_knows_cooking(self):
        self.assertEqual(cook_plan(wild(cook_situation({"raw_fish": 1, "oak_log": 3}))), [])
        self.assertFalse(is_valid(PURPOSES["cook"], wild(cook_situation({"raw_fish": 1, "oak_log": 3}))))
        bread = cook_plan(wild(cook_situation({"wheat": 3, "crafting_table": 1})))
        self.assertIn({"kind": "craft", "recipe": "bread"}, bread)  # baking is no lesson

    def test_it_makes_a_campfire_only_once_it_knows_fire(self):
        steps = cook_plan(wild(cook_situation({"raw_fish": 1, "oak_log": 3}), "cooking"))
        self.assertEqual(steps, [])  # no fire, and none it knows how to make
        steps = cook_plan(wild(cook_situation({"raw_fish": 1, "furnace": 1}), "cooking"))
        self.assertIn({"kind": "place", "target": [1, 1, 0], "block": "furnace"}, steps)
        steps = cook_plan(wild(cook_situation({"raw_fish": 1, "oak_log": 3}), "cooking", "fire"))
        self.assertIn({"kind": "craft", "recipe": "campfire"}, steps)

    def test_warm_up_lights_a_carried_campfire_only_once_it_knows_fire(self):
        cold = cook_situation({"campfire": 1})
        context = None
        self.assertEqual(plan_warm_up(wild(cold), context), [])
        self.assertTrue(any(step.get("block") == "campfire" for step in plan_warm_up(wild(cook_situation({"campfire": 1}),
                                                                                          "fire"), context)))
        self.assertTrue(any(step.get("block") == "furnace" for step in plan_warm_up(wild(cook_situation({"furnace": 1})),
                                                                                   context)))

    def test_a_gentle_pet_is_never_gated(self):
        s = cook_situation({"raw_fish": 1, "oak_log": 3})
        s.state["difficulty"] = "gentle"
        self.assertIn({"kind": "craft", "recipe": "campfire"}, cook_plan(s))

    def test_camp_places_a_carried_campfire_only_once_it_knows_fire(self):
        # Fix round A, Task 3: lit_camp placed any carried campfire with no wild:fire check, reachable
        # since the owner can craft one for Mimo and camp itself needs only wild:shelter.
        pet = Expedition()
        with patch("backend.survival.expedition.terrain_height", FLAT):
            pet.set_out()  # packs a campfire and torches (test_survival_expedition.PACKED)
        pet.go(101, 1)
        untaught = wild(pet.situation(DUSK), "shelter", "light")
        steps, inventory = lit_camp(untaught, (101, 1, 1))
        self.assertFalse(any(step.get("block") == "campfire" for step in steps))
        self.assertEqual(inventory["campfire"], 1)  # still carried: never placed without wild:fire
        taught = wild(pet.situation(DUSK), "shelter", "light", "fire")
        steps, inventory = lit_camp(taught, (101, 1, 1))
        self.assertIn({"kind": "place", "target": [102, 1, 1], "block": "campfire"}, steps)
        self.assertEqual(inventory["campfire"], 0)


class ShelterAndBedTests(unittest.TestCase):
    def test_build_shelter_and_a_home_of_its_own_wait_for_the_shelter_lesson(self):
        world = World({"cobblestone": 40})
        world.state["difficulty"] = "wild"
        self.assertFalse(is_valid(PURPOSES["build_shelter"], world.situation()))
        self.assertFalse(is_open(world.situation(), GOALS["first_shelter"]))
        know(world.db, thing("shelter"), "lesson", 0.0)
        self.assertTrue(is_valid(PURPOSES["build_shelter"], world.situation()))
        self.assertTrue(is_open(world.situation(), GOALS["first_shelter"]))
        for name in ("improve_home", "camp"):
            self.assertIn(name, PURPOSES)

    def test_a_finished_shelter_gets_a_bed_only_once_it_knows_beds_and_a_campfire_once_it_knows_fire(self):
        world = World({"cobblestone": 40})
        world.state["difficulty"] = "wild"
        know(world.db, thing("shelter"), "lesson", 0.0)
        for _ in range(4):
            world.carry_out(world.plan())
        world.state["inventory"] = {"oak_log": 4}
        design = blueprint_of(structures(world.db)[0])
        self.assertEqual(places_of(world.plan()), [{"kind": "place", "target": list(design.one("door")), "block": "door"}])
        know(world.db, thing("bed"), "lesson", 0.0)
        self.assertEqual([step["block"] for step in places_of(world.plan())], ["bed", "door"])
        know(world.db, thing("fire"), "lesson", 0.0)  # 4 logs make a bed and a campfire, with none left for a door
        self.assertEqual([step["block"] for step in places_of(world.plan())], ["bed", "campfire"])


class LightGateTests(unittest.TestCase):
    """light_up and a safe yard wait for the light lesson (the lighting tests' home, torches and evening)."""

    setUp = lighting.LightTests.setUp
    situation = lighting.LightTests.situation

    def test_light_up_and_a_safe_yard_wait_for_the_light_lesson(self):
        s = self.situation({"torch": 4})
        s.state["difficulty"] = "wild"
        know(self.db, thing("shelter"), "lesson", 0.0)
        self.assertFalse(is_valid(PURPOSES["light_up"], s))
        self.assertFalse(is_open(s, GOALS["safe_yard"]))
        know(self.db, thing("light"), "lesson", 0.0)
        s = self.situation({"torch": 4})
        s.state["difficulty"] = "wild"
        self.assertTrue(is_valid(PURPOSES["light_up"], s))


if __name__ == "__main__":
    unittest.main()

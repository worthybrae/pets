import unittest

from backend.survival.blueprints import Blueprint, Planned
from backend.survival.cozy import BOOKSHELF_MOOD, tend_comfort, touches, touches_left
from backend.survival.creatures.hunting import hunt_for
from backend.survival.light import BLOCK_LIGHT
from backend.survival.making import favourite_colour, raw_needs
from backend.survival.memory import finish_structure
from backend.survival.purposes import PURPOSES
from backend.survival.renewal import CROP_STAGE_DRY, stage_seconds
from backend.survival.structures import start, todo
from backend.tests.test_survival_workshop import NIGHT, Yard, shares

PANES = {"glass": 6, "planks": 12, "cobblestone": 8}


class TouchTests(unittest.TestCase):
    def test_the_touches_fit_the_home_it_lives_in(self):
        yard = Yard()
        found = {touch.kind: touch for touch in touches(yard.situation())}
        self.assertEqual(sorted(found), ["bookshelf", "candle", "pot", "rug", "sign", "window"])
        windows = [touch for touch in touches(yard.situation()) if touch.kind == "window"]
        walls = {planned.cell for planned in yard.home.parts("wall")}
        self.assertEqual(len(windows), 2)
        self.assertTrue(all(touch.cell in walls and touch.replaces for touch in windows))  # a home without windows
        self.assertIn(found["bookshelf"].cell, walls)
        rugs = [touch for touch in touches(yard.situation()) if touch.kind == "rug"]
        self.assertEqual({touch.cell for touch in rugs}, {planned.cell for planned in yard.home.parts("passage")})
        self.assertEqual({touch.block for touch in rugs}, {f"rug_{favourite_colour(yard.state)}"})
        self.assertFalse(found["sign"].inside)
        self.assertFalse(yard.grid.claimed(found["sign"].cell))  # the campfire's side is the other one
        self.assertEqual(touches(Yard(position=(12, 1, 1)).situation())[0].block, "glass_pane")

    def test_a_farm_by_home_gets_a_composter_at_its_corner(self):
        yard = Yard()
        plots = tuple(Planned((x, 0, z), "plot", "farmland") for x in range(10, 13) for z in range(8, 11))
        farm = Blueprint("farm", "Pip's farm", (11, 0, 9), plots)
        finish_structure(yard.db, start(yard.db, yard.grid, farm, 0.0), 1.0)
        (composter,) = [touch for touch in touches(yard.situation()) if touch.kind == "composter"]
        self.assertEqual((composter.cell, composter.inside), ((9, 1, 7), False))


class DecorateTests(unittest.TestCase):
    def test_offered_while_it_is_the_goal_by_day_when_a_touch_can_be_made(self):
        decorate = PURPOSES["decorate_home"]
        yard = Yard(PANES)
        self.assertFalse(decorate.valid(yard.situation()))
        yard.goal("cozy_home")
        self.assertTrue(decorate.valid(yard.situation()))
        self.assertFalse(decorate.valid(yard.situation(NIGHT)))
        empty = Yard()
        empty.goal("cozy_home")
        self.assertFalse(decorate.valid(empty.situation()))
        self.assertIn("home still wants glass pane", decorate.facts(yard.situation()))

    def test_it_makes_the_panes_outside_then_puts_them_in_from_inside_and_the_walls_stay_whole(self):
        yard = Yard(PANES)
        yard.goal("cozy_home")
        steps = yard.plan("decorate_home")
        kinds = [step["kind"] for step in steps]
        self.assertLess(kinds.index("craft"), kinds.index("walk"))
        yard.carry_out(steps, "decorate_home")
        for touch in touches(yard.situation()):
            if touch.kind == "window":
                self.assertEqual(yard.grid.material(*touch.cell), "glass_pane")
        self.assertEqual(todo(yard.grid, yard.home), [])
        self.assertEqual(shares(yard.situation(), "cozy_home")[0], 1.0)

    def test_the_rug_and_the_bookshelf_go_in_and_a_bookshelf_makes_waking_at_home_content(self):
        colour = favourite_colour({"name": "Pip", "world_seed": "1"})
        yard = Yard({f"rug_{colour}": 2, "bookshelf": 1})
        yard.goal("cozy_home")
        yard.carry_out(yard.plan("decorate_home"), "decorate_home")
        self.assertEqual([touch.kind for touch in touches_left(yard.situation())],
                         ["window", "window", "pot", "candle", "sign"])
        yard.state["position"] = dict(zip("xyz", map(float, yard.home.anchor)))
        mood = yard.state["vitals"]["mood"]
        tend_comfort(yard.state, yard.context(), 5.0, "day")
        self.assertEqual(yard.state["vitals"]["mood"], mood)
        tend_comfort(yard.state, yard.context(), 5.0, "dawn")
        self.assertEqual(yard.state["vitals"]["mood"], min(100.0, mood + BOOKSHELF_MOOD))

    def test_what_the_touches_want_brings_gathering_and_a_hunt_for_leather_and_wool(self):
        yard = Yard({"planks": 30, "sticks": 4, "oak_log": 4, "cobblestone": 8})
        yard.goal("cozy_home")
        s = yard.situation()
        raw = raw_needs(s)
        self.assertEqual(raw["sand"], 6)
        self.assertEqual(raw["sugar_cane"], 3)
        self.assertEqual(raw["clay"], 3)
        flower = f"flower_{favourite_colour(yard.state)}"
        self.assertNotIn(flower, raw)  # the rug waits for wool first...
        self.assertTrue(hunt_for(s))  # ...which a hunt brings, with the book's leather
        yard.state["inventory"].update(wool=2, leather=1, tallow=1)
        self.assertEqual(raw_needs(yard.situation())[flower], 1)
        self.assertFalse(hunt_for(yard.situation()))


class ComfortTests(unittest.TestCase):
    def test_a_composter_near_a_crop_makes_each_stage_a_quarter_quicker_and_candles_give_light(self):
        yard = Yard()
        crop = (20, 1, 20)
        yard.grid.put(20, 0, 20, "farmland")
        self.assertEqual(stage_seconds(yard.grid, crop), CROP_STAGE_DRY)
        yard.grid.put(23, 1, 20, "composter")
        self.assertEqual(stage_seconds(yard.grid, crop), CROP_STAGE_DRY * 0.75)
        self.assertEqual(BLOCK_LIGHT["candle"], 12)


if __name__ == "__main__":
    unittest.main()

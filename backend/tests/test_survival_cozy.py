import sqlite3
import unittest
from unittest.mock import patch

from backend.services.crafting import RECIPES
from backend.survival.blueprints import TIERS, Blueprint, Planned, Style, find_site, shelter
from backend.survival.cozy import (
    BOOKSHELF_MOOD, chosen_touches, hunt_for_goods, prey_for_goods, tend_comfort, touches, touches_left,
)
from backend.survival.creatures.hunting import hunt_for, quarry
from backend.survival.creatures.table import Herd, create_creature_tables
from backend.survival.goals import GOALS, advancing
from backend.survival.grid import Grid
from backend.survival.life_goals import HIDE_HUNT_GAP
from backend.survival.machines import MACHINES, PART, door_design, machine_needs
from backend.survival.light import BLOCK_LIGHT
from backend.survival.making import favourite_colour, needs, raw_needs
from backend.survival.memory import create_memory_tables, finish_structure, know, set_home
from backend.survival.purposes import PURPOSES
from backend.survival.renewal import CROP_STAGE_DRY, stage_seconds
from backend.survival.structures import start, todo
from backend.tests.test_survival_combat import animal
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
        inside = door_design(yard.situation(), MACHINES["auto_door"]).parts(PART)[-1].cell  # the plate inside
        self.assertEqual({touch.cell for touch in rugs},
                         {planned.cell for planned in yard.home.parts("passage")} - {inside})  # I4: from j = 1
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
        know(yard.db, "workshop", "goal", 0.0)  # the workshop reached: the flower pot need not wait for its kiln
        yard.goal("cozy_home")
        s = yard.situation()
        raw = raw_needs(s)
        self.assertEqual(raw["sand"], 6)
        self.assertEqual(raw["sugar_cane"], 3)
        self.assertEqual(raw["clay"], 3)
        flower = f"flower_{favourite_colour(yard.state)}"
        self.assertNotIn(flower, raw)  # the rug waits for wool first...
        self.assertFalse(hunt_for(s))  # (I3: only with an animal in sight that drops it)
        animal(yard.grid, "cow", (8, 1, 4))
        self.assertTrue(hunt_for(yard.situation()))  # ...which a hunt brings, with the book's leather
        yard.state["inventory"].update(wool=2, leather=1, tallow=1)
        self.assertEqual(raw_needs(yard.situation())[flower], 1)
        self.assertFalse(hunt_for(yard.situation()))

    def test_the_cozy_hunt_waits_its_gap_and_ignores_rabbits_when_only_tallow_is_missing(self):
        """The Making final fix wave, I3: the cozy home hunted any animal, with no gap, while leather, wool or
        tallow was missing: 66 to 157 hunts a life "toward a cozy home", mostly rabbits, cows and chickens."""
        yard = Yard({"planks": 30, "sticks": 4, "oak_log": 4, "cobblestone": 8, "wool": 2, "leather": 1, "bread": 20})
        yard.goal("cozy_home")
        self.assertEqual(prey_for_goods(yard.situation()), ("sheep",))  # only the candle's tallow is missing
        animal(yard.grid, "rabbit", (6, 1, 3))
        self.assertFalse(hunt_for_goods(yard.situation()))  # a rabbit drops no tallow...
        self.assertNotIn("hunt", advancing(yard.situation(), GOALS["cozy_home"]))  # ...so no hunt works toward it
        sheep = animal(yard.grid, "sheep", (16, 1, 9))
        s = yard.situation()
        self.assertTrue(hunt_for_goods(s))
        self.assertIn("hunt", advancing(s, GOALS["cozy_home"]))
        self.assertLess(s.distance((6, 1, 3)), s.distance((16, 1, 9)))
        self.assertEqual(quarry(s)["id"], sheep["id"])  # the sheep, though the rabbit is nearer
        yard.state["hunted_at"] = -HIDE_HUNT_GAP + 60.0  # it killed something less than HIDE_HUNT_GAP ago
        self.assertFalse(hunt_for_goods(yard.situation()))
        yard.state["hunted_at"] = -HIDE_HUNT_GAP
        self.assertTrue(hunt_for_goods(yard.situation()))
        yard.state["inventory"]["tallow"] = 1
        self.assertFalse(hunt_for_goods(yard.situation()))

    def test_the_flower_pot_waits_for_the_workshops_kiln(self):
        """The Making final fix wave: both are fired from clay, which is rare, and the kiln is on the way to the
        computer, so while the workshop still wants its kiln the pot is neither wanted nor made."""
        yard = Yard({"planks": 30, "sticks": 4, "oak_log": 4, "cobblestone": 8, "brick": 3})
        yard.goal("cozy_home")
        s = yard.situation()
        self.assertNotIn("flower_pot", needs(s))
        self.assertNotIn("pot", [touch.kind for touch in chosen_touches(s)])
        self.assertIn("pot", [touch.kind for touch in touches_left(s)])  # still a touch the goal counts
        know(yard.db, "workshop", "goal", 0.0)
        s = yard.situation()
        self.assertEqual(needs(s)["flower_pot"], 1)
        self.assertIn("pot", [touch.kind for touch in chosen_touches(s)])

    def test_a_candle_is_tallow_and_a_stick(self):
        """The final fix wave's ruling: string only comes from skitters, so no pet ever made a candle."""
        self.assertEqual(RECIPES["candle"]["ingredients"], {"tallow": 1, "sticks": 1})


def home_of(size, side, natural=None):
    """The yard's pet, by a finished flat-roofed shelter of `size` (inside) with its door on `side`."""
    yard = Yard()
    yard.db = sqlite3.connect(":memory:")
    create_memory_tables(yard.db)
    create_creature_tables(yard.db)
    yard.grid = Grid(natural or (lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air"))
    yard.grid.herd = Herd(yard.db)
    site = find_site(yard.grid, (1, 1, 1), size, (side,), "flat", reach=0)
    yard.home = shelter(site, Style("flat", "cobblestone", "planks", "none", (side,)), "Pip's home")
    for planned in yard.home.parts("floor", "wall", "roof"):
        yard.grid.put(*planned.cell, "cobblestone")
    yard.grid.put(*yard.home.one("door"), "door")
    finish_structure(yard.db, start(yard.db, yard.grid, yard.home, 0.0), 1.0)
    set_home(yard.db, yard.home.anchor, 1.0)
    return yard


class RugAndPlateTests(unittest.TestCase):
    def test_the_rug_and_the_automatic_doors_plates_never_share_a_cell(self):
        """The Making final fix wave, I4: the rug started on the cell just inside the door, where the automatic
        door lays its inside plate, so whichever went in second could not."""
        for size in TIERS:
            for side in ("north", "south", "east", "west"):
                yard = home_of(size, side)
                s = yard.situation()
                rugs = {touch.cell for touch in touches(s) if touch.kind == "rug"}
                plates = {planned.cell for planned in door_design(s, MACHINES["auto_door"]).parts(PART)}
                self.assertTrue(rugs, (size, side))
                self.assertEqual(len(plates), 2, (size, side))
                self.assertFalse(rugs & plates, (size, side))

    def test_the_automatic_door_wants_only_the_plates_its_design_lays(self):
        """The carried Task 9 minor: where the ground in front of the door lies lower, door_design lays only the
        inside plate, and machine_needs used to ask for two anyway."""
        def dip(x, y, z):
            ground = -1 if (x, z) == (1, -2) else 0  # the cell in front of the north door is a block low
            return "grass" if y == ground else "dirt" if y < ground else "air"

        for natural, plates in ((None, 2), (dip, 1)):
            yard = home_of(TIERS[0], "north", natural)
            yard.goal("first_circuits")
            s = yard.situation()
            self.assertEqual(len(door_design(s, MACHINES["auto_door"]).parts(PART)), plates)
            with patch("backend.survival.machines.next_machine", lambda s: MACHINES["auto_door"]):
                self.assertEqual(machine_needs(s), {"pressure_plate": plates})


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

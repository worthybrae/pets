import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import farmstead  # noqa: F401  (registers build_farm)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.building import note_building
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember, structures
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.structures import reserved
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
SHORE = ((8, 1, 0), (9, 0, 0))


class Farmstead:
    def __init__(self, inventory, farmland=()):
        self.db = sqlite3.connect(":memory:")
        create_memory_tables(self.db)
        self.grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
        for cell in farmland:
            self.grid.put(*cell, "farmland")
        remember(self.db, "home", (0, 1, 0), 0.0)
        self.state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                      "inventory": dict(inventory), "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
        ensure_actions(self.state)

    def situation(self):
        return Situation(self.state, self.grid, DAY, 0.0, self.db)

    def context(self):
        return ActionContext(grid=self.grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=self.db)

    def plan(self):
        return PURPOSES["build_farm"].plan(self.situation(), self.context())


@patch("backend.survival.farmstead.shores_near", lambda grid, seed, here, radius: [SHORE])
class BuildFarmTests(unittest.TestCase):
    def test_a_first_farm_is_laid_out_beside_the_nearest_shore_four_plots_a_batch(self):
        farm = Farmstead({"seeds": 5, "carrot": 2})
        self.assertTrue(PURPOSES["build_farm"].valid(farm.situation()))
        steps = farm.plan()
        tills = [step["target"] for step in steps if step["kind"] == "till"]
        sown = [step["item"] for step in steps if step["kind"] == "plant"]
        self.assertEqual(len(tills), 4)
        self.assertEqual(sown, ["carrot", "carrot", "seeds", "seeds"])
        self.assertTrue(all(abs(x - 8) <= 1 and abs(z) <= 1 and y == 0 for x, y, z in tills))
        self.assertEqual([(row["kind"], row["status"]) for row in structures(farm.db)], [("farm", "building")])
        self.assertTrue(reserved(farm.grid, tuple(tills[0])))

    def test_needs_a_home_and_two_things_to_plant(self):
        self.assertFalse(PURPOSES["build_farm"].valid(Farmstead({"seeds": 1}).situation()))
        homeless = Farmstead({"seeds": 5})
        homeless.db.execute("DELETE FROM memory_places")
        self.assertFalse(PURPOSES["build_farm"].valid(homeless.situation()))

    def test_an_old_farm_grows_into_the_square_instead_of_a_second_farm(self):
        old = ((3, 0, 3), (4, 0, 3))
        farm = Farmstead({"seeds": 9}, farmland=old)
        remember(farm.db, "farm", (3, 0, 3), 0.0)
        farm.plan()
        plots = structures(farm.db)[0]["data"]["cells"]
        self.assertIn([3, 0, 3, "plot", "farmland"], plots)
        self.assertIn([4, 0, 3, "plot", "farmland"], plots)

    def test_the_last_plot_tilled_finishes_the_farm(self):
        farm = Farmstead({"seeds": 20})
        context = farm.context()
        for _ in range(3):
            for step in farm.plan():
                if step["kind"] == "till":
                    farm.grid.put(*step["target"], "farmland")
                    note_building(farm.state, step, context, 2.0)
        self.assertEqual(structures(farm.db)[0]["status"], "done")
        self.assertEqual(context.events[-1][1:], ("built", "Pip laid out Pip's farm."))
        self.assertFalse(PURPOSES["build_farm"].valid(farm.situation()))

    def test_plots_that_turned_back_into_dirt_are_tilled_again(self):
        farm = Farmstead({"seeds": 20})
        for _ in range(3):
            for step in farm.plan():
                if step["kind"] == "till":
                    farm.grid.put(*step["target"], "farmland")
        cells = structures(farm.db)[0]["data"]["cells"]
        farm.grid.put(*cells[0][:3], "dirt")
        self.assertTrue(PURPOSES["build_farm"].valid(farm.situation()))
        self.assertIn({"kind": "till", "target": cells[0][:3]}, farm.plan())


if __name__ == "__main__":
    unittest.main()

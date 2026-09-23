import unittest
from unittest.mock import patch

from backend.survival import nature
from backend.survival.grid import Grid
from backend.survival.steps import STEP_KINDS, StepFailed, finish_step, start_step
from backend.survival.vitals import START_VITALS


def meadow(cells=None):
    """Grass at y 0 over dirt, air above; `cells` override single cells. Mimo stands at (0, 1, 0)."""
    cells = cells or {}
    return Grid(lambda x, y, z: cells.get((x, y, z)) or ("grass" if y == 0 else "dirt" if y < 0 else "air"))


def pet(**changes):
    state = {"name": "Pip", "world_seed": "7", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS)}
    state.update(changes)
    return state


def run(spec, state, grid, at=0.0):
    """Start a step and finish it at its end. Returns the running step and the event."""
    step = start_step(spec, state, grid, at)
    return step, finish_step(step, state, grid, step["ends_at"])


class NatureTests(unittest.TestCase):
    def test_crop_stages(self):
        self.assertEqual(nature.crop_stage("wheat_2"), ("wheat", 2))
        self.assertIsNone(nature.crop_stage("berry_bush"))
        self.assertIsNone(nature.crop_stage("wheat_9"))
        self.assertEqual(nature.next_stage("carrot_0"), "carrot_1")
        self.assertIsNone(nature.next_stage("carrot_3"))
        self.assertEqual(nature.RIPE_CROPS, ("wheat_3", "carrot_3"))

    def test_rolls_are_fixed_by_seed_cell_channel_and_salt(self):
        first = nature.roll("7", (1, 2, 3), 30)
        self.assertEqual(first, nature.roll("7", (1, 2, 3), 30))
        self.assertTrue(0.0 <= first < 1.0)
        self.assertNotEqual(first, nature.roll("7", (1, 2, 3), 30, salt=5))
        self.assertNotEqual(first, nature.roll("8", (1, 2, 3), 30))

    def test_chance_drops_follow_the_roll(self):
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "leaves"), ["sapling", "apple"])
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "tall_grass"), ["seeds", "carrot"])
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "stone"), [])
        with patch("backend.survival.nature.roll", lambda *args: 0.1):
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "tall_grass"), ["seeds"])
        with patch("backend.survival.nature.roll", lambda *args: 0.99):
            self.assertEqual(nature.chance_drops("7", (0, 1, 0), "leaves"), [])

    def test_fish_stocks_fall_with_each_catch_and_recover_one_a_game_day(self):
        state = pet()
        self.assertEqual(nature.fish_stock(state, (20, 2, 5)), 12)
        nature.take_fish(state, (20, 2, 5), 100.0)
        nature.take_fish(state, (31, 2, 15), 110.0)
        self.assertEqual(state["fish"], {"1,0": {"stock": 10, "since": 100.0}})
        self.assertEqual(nature.fish_stock(state, (16, 2, 0)), 10)
        nature.recover_fish(state, 100.0 + 3599.0, 1.0)
        self.assertEqual(state["fish"]["1,0"]["stock"], 10)
        nature.recover_fish(state, 100.0 + 3600.0, 1.0)
        self.assertEqual(state["fish"]["1,0"], {"stock": 11, "since": 3700.0})
        nature.recover_fish(state, 3700.0 + 60.0, 60.0)
        self.assertEqual(state["fish"], {})


class PickAndHarvestTests(unittest.TestCase):
    def test_picking_a_ripe_bush_gives_berries_and_leaves_the_bush(self):
        grid, state = meadow({(1, 1, 0): "berry_bush_ripe"}), pet()
        step, event = run({"kind": "pick", "target": [1, 1, 0]}, state, grid, 2.0)
        self.assertEqual((step["ends_at"], step["block"], event), (2.5, "berry_bush_ripe", None))
        self.assertEqual(state["inventory"], {"berries": 3})
        self.assertEqual(grid.material(1, 1, 0), "berry_bush")
        with self.assertRaises(StepFailed) as caught:
            start_step({"kind": "pick", "target": [1, 1, 0]}, state, grid, 3.0)
        self.assertEqual(caught.exception.code, "gone")

    def test_picking_a_mushroom_takes_it_whole(self):
        grid, state = meadow({(0, 1, 2): "red_mushroom"}), pet()
        run({"kind": "pick", "target": [0, 1, 2]}, state, grid)
        self.assertEqual((state["inventory"], grid.material(0, 1, 2)), ({"red_mushroom": 1}, "air"))

    def test_a_ripe_crop_is_harvested_and_the_farmland_stays(self):
        grid = meadow({(1, 0, 0): "farmland", (1, 1, 0): "wheat_3", (2, 0, 0): "farmland", (2, 1, 0): "carrot_1"})
        state = pet()
        run({"kind": "harvest", "target": [1, 1, 0]}, state, grid)
        self.assertEqual(state["inventory"], {"wheat": 1, "seeds": 2})
        self.assertEqual((grid.material(1, 1, 0), grid.material(1, 0, 0)), ("air", "farmland"))
        with self.assertRaisesRegex(StepFailed, "not ripe yet") as caught:
            start_step({"kind": "harvest", "target": [2, 1, 0]}, state, grid, 1.0)
        self.assertEqual(caught.exception.code, "blocked")

    def test_a_plant_that_changed_before_the_step_ended_is_gone(self):
        grid, state = meadow({(1, 1, 0): "berry_bush_ripe"}), pet()
        step = start_step({"kind": "pick", "target": [1, 1, 0]}, state, grid, 0.0)
        grid.put(1, 1, 0, "berry_bush")
        with self.assertRaises(StepFailed) as caught:
            finish_step(step, state, grid, 0.5)
        self.assertEqual(caught.exception.code, "gone")
        self.assertEqual(state["inventory"], {})


class TillAndPlantTests(unittest.TestCase):
    def test_tilling_turns_grass_into_farmland_and_the_tall_grass_on_it_goes(self):
        grid = Grid(lambda x, y, z: {(1, 1, 0): "tall_grass"}.get((x, y, z)) or ("grass" if y == 0 else "air"))
        state = pet()
        step, _ = run({"kind": "till", "target": [1, 0, 0]}, state, grid)
        self.assertEqual(step["ends_at"], 1.0)
        self.assertEqual((grid.material(1, 0, 0), grid.material(1, 1, 0)), ("farmland", "air"))
        with self.assertRaisesRegex(StepFailed, "cannot be tilled"):
            start_step({"kind": "till", "target": [1, 0, 0]}, state, grid, 2.0)
        bush = meadow({(0, 1, 1): "berry_bush"})
        with self.assertRaisesRegex(StepFailed, "something is on it"):
            start_step({"kind": "till", "target": [0, 0, 1]}, state, bush, 0.0)

    def test_seeds_go_on_farmland_and_saplings_on_grass(self):
        grid = meadow({(1, 0, 0): "farmland"})
        state = pet(inventory={"seeds": 1, "carrot": 1, "sapling": 1})
        step, _ = run({"kind": "plant", "target": [1, 1, 0], "item": "seeds"}, state, grid)
        self.assertEqual((step["block"], grid.material(1, 1, 0)), ("wheat_0", "wheat_0"))
        with self.assertRaisesRegex(StepFailed, "needs farmland") as caught:
            start_step({"kind": "plant", "target": [0, 1, 1], "item": "carrot"}, state, grid, 1.0)
        self.assertEqual(caught.exception.code, "blocked")
        run({"kind": "plant", "target": [0, 1, 2], "item": "sapling"}, state, grid)
        self.assertEqual(grid.material(0, 1, 2), "sapling")
        self.assertEqual(state["inventory"], {"carrot": 1})
        for spec, code in (({"kind": "plant", "target": [2, 1, 0], "item": "seeds"}, "missing_item"),
                           ({"kind": "plant", "target": [2, 1, 0], "item": "stone"}, "bad_step"),
                           ({"kind": "plant", "target": [1, 1, 0], "item": "carrot"}, "blocked")):
            with self.assertRaises(StepFailed, msg=spec) as caught:
                start_step(spec, state, grid, 2.0)
            self.assertEqual(caught.exception.code, code, spec)


class FishAndCookTests(unittest.TestCase):
    def test_fishing_takes_20_to_60_seconds_and_a_catch_lowers_the_stock(self):
        grid, state = meadow({(2, 0, 0): "water"}), pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.5):
            step, event = run({"kind": "fish", "target": [2, 0, 0]}, state, grid, 10.0)
        self.assertEqual(step["ends_at"], 50.0)
        self.assertEqual(event, ("fish", "Pip caught a fish."))
        self.assertEqual((state["inventory"], nature.fish_stock(state, (2, 0, 0))), ({"raw_fish": 1}, 11))
        with patch("backend.survival.nature.roll", lambda *args: 0.95):
            step, event = run({"kind": "fish", "target": [2, 0, 0]}, state, grid, 60.0)
        self.assertEqual((step["ends_at"], event, state["inventory"]), (118.0, None, {"raw_fish": 1}))
        self.assertTrue(STEP_KINDS["fish"].interruptible)
        with self.assertRaisesRegex(StepFailed, "no water"):
            start_step({"kind": "fish", "target": [1, 0, 0]}, state, grid, 0.0)

    def test_an_empty_region_never_bites(self):
        grid, state = meadow({(2, 0, 0): "water"}), pet(fish={"0,0": {"stock": 0, "since": 0.0}})
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            self.assertIsNone(run({"kind": "fish", "target": [2, 0, 0]}, state, grid)[1])

    def test_cooking_needs_a_fire_within_reach_and_no_fuel(self):
        grid, state = meadow(), pet(inventory={"raw_fish": 1})
        with self.assertRaises(StepFailed) as caught:
            start_step({"kind": "cook", "item": "raw_fish"}, state, grid, 0.0)
        self.assertEqual(caught.exception.code, "missing_item")
        grid.put(2, 1, 0, "campfire")
        step, event = run({"kind": "cook", "item": "raw_fish"}, state, grid)
        self.assertEqual((step["ends_at"], event), (5.0, ("cook", "Pip cooked raw fish.")))
        self.assertEqual(state["inventory"], {"cooked_fish": 1})
        with self.assertRaisesRegex(StepFailed, "cannot be cooked"):
            start_step({"kind": "cook", "item": "iron_ore"}, pet(inventory={"iron_ore": 1}), grid, 0.0)

    def test_the_new_kinds_show_how_mimo_works(self):
        shown = {name: (STEP_KINDS[name].status, STEP_KINDS[name].working)
                 for name in ("pick", "harvest", "till", "plant", "fish", "cook")}
        self.assertEqual(shown, {"pick": ("picking", True), "harvest": ("harvesting", True), "till": ("tilling", True),
                                 "plant": ("planting", True), "fish": ("fishing", False), "cook": ("cooking", False)})


class ChanceDropTests(unittest.TestCase):
    def test_mining_leaves_and_tall_grass_may_drop_more(self):
        grid, state = meadow({(1, 1, 0): "leaves", (0, 1, 1): "tall_grass"}), pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.0):
            run({"kind": "mine", "target": [1, 1, 0]}, state, grid)
            run({"kind": "mine", "target": [0, 1, 1]}, state, grid)
        self.assertEqual(state["inventory"], {"sapling": 1, "apple": 1, "seeds": 1, "carrot": 1})
        state = pet()
        with patch("backend.survival.nature.roll", lambda *args: 0.99):
            run({"kind": "mine", "target": [1, 1, 0]}, state, meadow({(1, 1, 0): "leaves"}))
        self.assertEqual(state["inventory"], {})


if __name__ == "__main__":
    unittest.main()

import random
import sqlite3
import unittest
from unittest.mock import patch

from backend.survival import farming  # noqa: F401  (registers farm)
from backend.survival.actions import ActionContext, ensure_actions
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, remember
from backend.survival.pickers import JITTER, options, utility_pick
from backend.survival.purposes import PURPOSES
from backend.survival.situation import Situation
from backend.survival.vitals import START_VITALS

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}
NIGHT = {**DAY, "phase": "night", "seconds_into_day": 3000.0}


def meadow(edits=None):
    """Grass at y 0 and air above, with `edits` placed the way Mimo placed them."""
    grid = Grid(lambda x, y, z: "grass" if y == 0 else "dirt" if y < 0 else "air")
    for cell, block in (edits or {}).items():
        grid.put(*cell, block)
    return grid


def pet(**changes):
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "vitals": dict(START_VITALS), "traits": {}, "last_tick_at": 0.0}
    state.update(changes)
    ensure_actions(state)
    return state


def situation(state=None, grid=None, clock=DAY):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return Situation(state or pet(), grid or meadow(), clock, 0.0, db)


def plan(s):
    return PURPOSES["farm"].plan(s, ActionContext(grid=s.grid, clock_at=lambda at: s.clock, planner=lambda *args: [],
                                                  events=[], db=s.db))


def till(x, y, z):
    return {"kind": "till", "target": [x, y, z]}


def sow(x, y, z, item):
    return {"kind": "plant", "target": [x, y, z], "item": item}


def harvest(x, y, z):
    return {"kind": "harvest", "target": [x, y, z]}


class FarmTests(unittest.TestCase):
    @patch("backend.survival.farming.shores_near", lambda grid, seed, here, radius: [((2, 1, 0), (3, 0, 0))])
    def test_a_new_farm_starts_beside_the_nearest_shore(self):
        s = situation(pet(inventory={"seeds": 2}))
        self.assertTrue(PURPOSES["farm"].valid(s))
        self.assertEqual(plan(s), [till(2, 0, 0), sow(2, 1, 0, "seeds"), till(1, 0, 0), sow(1, 1, 0, "seeds")])

    def test_ripe_crops_are_harvested_and_planted_again_then_new_plots_take_the_rest(self):
        grid = meadow({(1, 0, 0): "farmland", (2, 0, 0): "farmland", (3, 0, 0): "farmland",
                       (1, 1, 0): "wheat_3", (2, 1, 0): "carrot_3", (3, 1, 0): "carrot_1"})
        self.assertEqual(plan(situation(grid=grid)), [
            harvest(1, 1, 0), sow(1, 1, 0, "seeds"), harvest(2, 1, 0), sow(2, 1, 0, "carrot"),
            till(0, 0, 0), sow(0, 1, 0, "carrot"), till(-1, 0, 0), sow(-1, 1, 0, "carrot")])

    def test_empty_farmland_gets_carrots_first_then_seeds(self):
        grid = meadow({(1, 0, 0): "farmland", (2, 0, 0): "farmland"})
        steps = plan(situation(pet(inventory={"carrot": 1, "seeds": 1}), grid))
        self.assertEqual(steps, [sow(1, 1, 0, "carrot"), sow(2, 1, 0, "seeds")])

    @patch("backend.survival.farming.grass_near", lambda grid, seed, here, radius: [(5, 1, 0), (6, 1, 0)])
    def test_with_nothing_to_plant_mimo_breaks_tall_grass_for_seeds(self):
        self.assertEqual(plan(situation()), [{"kind": "walk", "target": [5, 1, 0], "reach": 2.0, "whole": True},
                                             {"kind": "mine", "target": [5, 1, 0]}, {"kind": "mine", "target": [6, 1, 0]}])

    def test_a_plot_where_a_step_just_failed_is_left_alone(self):
        state = pet()
        state["recent_actions"] = [{"kind": "walk", "started_at": 0.0, "ended_at": 0.0, "result": "failed",
                                    "target": {"x": 1, "y": 1, "z": 0}, "reason": "no way there", "code": "no_path"}]
        grid = meadow({(1, 0, 0): "farmland", (1, 1, 0): "carrot_3", (6, 0, 0): "farmland", (6, 1, 0): "carrot_3"})
        self.assertEqual(plan(situation(state, grid))[:3], [
            {"kind": "walk", "target": [6, 1, 0], "reach": 2.0, "whole": True}, harvest(6, 1, 0), sow(6, 1, 0, "carrot")])

    def test_a_farm_far_away_is_walked_to_first(self):
        s = situation(pet(inventory={"seeds": 3}))
        remember(s.db, "farm", (50, 0, 0), 0.0)
        self.assertEqual(plan(s), [{"kind": "walk", "target": [50, 1, 0], "reach": 2.0, "whole": True}])

    @patch("backend.survival.farming.grass_near", lambda grid, seed, here, radius: [(5, 1, 0)])
    def test_a_far_farm_with_nothing_waiting_is_not_worth_the_trip(self):
        idle = situation()
        remember(idle.db, "farm", (50, 0, 0), 0.0)
        self.assertFalse(PURPOSES["farm"].valid(idle))
        ripe = situation(grid=meadow({(50, 0, 0): "farmland", (50, 1, 0): "wheat_3"}))
        remember(ripe.db, "farm", (50, 0, 0), 0.0)
        self.assertEqual(plan(ripe), [{"kind": "walk", "target": [50, 1, 0], "reach": 2.0, "whole": True}])

    @patch("backend.survival.farming.grass_near", lambda grid, seed, here, radius: [])
    def test_nothing_to_do_or_night_means_no_farming(self):
        self.assertFalse(PURPOSES["farm"].valid(situation()))
        self.assertFalse(PURPOSES["farm"].valid(situation(pet(inventory={"seeds": 3}), clock=NIGHT)))

    def test_ripe_crops_and_seeds_raise_the_score(self):
        score = PURPOSES["farm"].score
        bare = score(situation())
        seeded = score(situation(pet(inventory={"seeds": 1})))
        field = {(1, 0, 0): "farmland", (1, 1, 0): "wheat_3"}
        ripe = score(situation(pet(inventory={"seeds": 1}), meadow(field)))
        keen = score(situation(pet(inventory={"seeds": 1}, traits={"diligence": 100, "patience": 100}), meadow(field)))
        # Ripe crops count for as much food as Mimo lacks: 2 bread (50 of the 60 it likes to carry)
        # leave a sixth of the bonus. The score never climbs past 80, the top of the needs band.
        fed = score(situation(pet(inventory={"seeds": 1, "bread": 2}), meadow(field)))
        self.assertEqual((bare, seeded, ripe, keen), (47.5, 57.5, 80.0, 80.0))
        self.assertAlmostEqual(fed, 57.5 + 25.0 / 6)

    def test_a_hungry_pet_with_food_eats_before_it_harvests_a_ripe_farm(self):
        hungry = pet(inventory={"seeds": 1, "bread": 2}, vitals={**START_VITALS, "hunger": 25.0})
        s = situation(hungry, meadow({(1, 0, 0): "farmland", (1, 1, 0): "wheat_3", (2, 0, 0): "farmland",
                                      (2, 1, 0): "carrot_3"}))
        scores = {option.name: option.score for option in options(s)}
        self.assertGreater(scores["eat"] - scores["farm"], JITTER)
        self.assertEqual(max(scores, key=scores.get), "eat")
        self.assertEqual({utility_pick(options(s), random.Random(seed)) for seed in range(20)}, {"eat"})


if __name__ == "__main__":
    unittest.main()

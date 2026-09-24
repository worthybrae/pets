import sqlite3
import unittest
from unittest.mock import patch

from backend.survival.memory import create_memory_tables, remember
from backend.survival.renewal import kept_clear
from backend.survival.steps import finish_step, start_step
from backend.survival.work import PASSAGE_TALL, side_of, stair
from backend.tests.test_survival_work import ground, mine, walk

PICK = {"wooden_pickaxe": 1}


def rubble(x, y, z):
    return {**mine(x, y, z), "rubble": True}


@patch("backend.survival.work.terrain_height", lambda x, z, seed: 0)
class WidePassageTests(unittest.TestCase):
    def test_a_passage_is_three_tall_and_its_second_column_is_to_the_left(self):
        self.assertEqual(PASSAGE_TALL, 3)
        self.assertEqual([side_of(heading) for heading in ((1, 0), (0, 1), (-1, 0), (0, -1))],
                         [(0, 1), (-1, 0), (0, -1), (1, 0)])
        steps, to, stones = stair(ground({(4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), PICK, "1")
        self.assertEqual({tuple(step["target"]) for step in steps if step["kind"] == "mine"},
                         {(x, y, z) for x in (5,) for y in (-3, -2, -1) for z in (0, 1)})
        self.assertEqual((to, stones), ((5, -3, 0), 1))  # only the cell Mimo walks through is kept

    def test_it_narrows_where_the_side_cannot_be_cut_and_lowers_where_the_top_cannot(self):
        start = (0, 1, 0)
        self.assertEqual(stair(ground({(1, 0, 1): "bedrock"}), {}, start, (1, 0), PICK, "1")[0],
                         [mine(1, 0, 0), walk(1, 0, 0)])
        self.assertEqual(stair(ground({(1, -1, 1): "air"}), {}, start, (1, 0), PICK, "1")[0],
                         [mine(1, 0, 0), walk(1, 0, 0)])  # never over a hole
        self.assertEqual(stair(ground({(5, -1, 0): "bedrock", (4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), PICK, "1")[0],
                         [rubble(5, -2, 0), mine(5, -3, 0), rubble(5, -1, 1), rubble(5, -2, 1), rubble(5, -3, 1),
                          walk(5, -3, 0)])
        self.assertEqual(stair(ground({(5, -2, 1): "water", (4, -3, 0): "air"}), {}, (4, -3, 0), (1, 0), PICK, "1")[0],
                         [rubble(5, -1, 0), rubble(5, -2, 0), mine(5, -3, 0), rubble(5, -1, 1), walk(5, -3, 0)])

    def test_the_cells_mimo_walks_through_are_still_needed(self):
        self.assertIsNone(stair(ground({(1, 0, 0): "bedrock"}), {}, (0, 1, 0), (1, 0), PICK, "1"))
        self.assertIsNone(stair(ground({(2, 0, 0): "bedrock"}), {}, (1, 0, 0), (1, 0), PICK, "1"))  # the headroom


class RubbleTests(unittest.TestCase):
    def test_a_widening_cell_breaks_into_rubble_mimo_leaves_behind(self):
        grid = ground()
        state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0},
                 "inventory": dict(PICK)}
        running = start_step(rubble(1, -1, 0), state, grid, 0.0)
        self.assertTrue(running["rubble"])
        finish_step(running, state, grid, running["ends_at"])
        self.assertEqual((grid.material(1, -1, 0), state["inventory"]), ("air", PICK))
        kept = start_step(mine(0, -2, 1), state, grid, 0.0)
        finish_step(kept, state, grid, kept["ends_at"])
        self.assertEqual(state["inventory"]["dirt"], 1)


class HomeRoomTests(unittest.TestCase):
    def test_a_tree_keeps_three_cells_clear_over_mimo_and_its_home(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        remember(db, "home", (1, -3, 0), 0.0)
        state = {"position": {"x": 0.0, "y": 1.0, "z": 0.0}}
        self.assertEqual(kept_clear(db, state, (0, 1, 2)),
                         {(0, 1, 0), (0, 2, 0), (0, 3, 0), (1, -3, 0), (1, -2, 0), (1, -1, 0)})


if __name__ == "__main__":
    unittest.main()

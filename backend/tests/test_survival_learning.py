import sqlite3
import unittest

from backend.survival.actions import ActionContext
from backend.survival.brain import observe_step
from backend.survival.grid import Grid
from backend.survival.memory import create_memory_tables, known, places
from backend.survival.triggers import ensure_brain

DAY = {"phase": "day", "seconds_into_day": 1000.0, "time_scale": 1.0, "day_number": 1}


def pet():
    state = {"name": "Pip", "world_seed": "1", "position": {"x": 0.0, "y": 1.0, "z": 0.0}, "inventory": {},
             "recent_actions": [], "last_tick_at": 0.0}
    ensure_brain(state)["pending"] = None
    return state


def remembering(grid=None):
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    grid = grid or Grid(lambda x, y, z: "grass" if y == 0 else "air")
    return ActionContext(grid=grid, clock_at=lambda at: DAY, planner=lambda *args: [], events=[], db=db)


def at(x, y, z):
    return {"x": x, "y": y, "z": z}


class LearningTests(unittest.TestCase):
    def test_being_sick_teaches_that_a_food_is_poisonous(self):
        ctx = remembering()
        observe_step(pet(), {"kind": "eat", "item": "berries"}, ctx, 1.0)
        observe_step(pet(), {"kind": "eat", "item": "red_mushroom"}, ctx, 2.0)
        self.assertEqual(known(ctx.db, "poisonous"), ["red_mushroom"])

    def test_picking_remembers_the_patch_with_its_ripe_food_and_when(self):
        ctx = remembering()
        for cell in ((3, 1, 0), (4, 1, 0), (5, 1, 1)):
            ctx.grid.put(*cell, "berry_bush_ripe")
        ctx.grid.put(3, 1, 0, "berry_bush")
        observe_step(pet(), {"kind": "pick", "target": at(3, 1, 0), "block": "berry_bush_ripe"}, ctx, 5.0)
        ctx.grid.put(4, 1, 0, "berry_bush")
        observe_step(pet(), {"kind": "pick", "target": at(4, 1, 0), "block": "berry_bush_ripe"}, ctx, 6.0)
        patches = [(place["x"], place["data"]) for place in places(ctx.db, ("food",))]
        self.assertEqual(patches, [(3, {"ripe": 1, "seen_at": 6.0})])

    def test_fires_are_remembered_while_they_stand_and_farms_where_mimo_tilled(self):
        ctx = remembering()
        observe_step(pet(), {"kind": "place", "target": at(1, 1, 0), "block": "campfire"}, ctx, 1.0)
        observe_step(pet(), {"kind": "place", "target": at(2, 1, 0), "block": "crafting_table"}, ctx, 1.0)
        observe_step(pet(), {"kind": "till", "target": at(0, 0, 3), "block": "grass"}, ctx, 2.0)
        self.assertEqual([(place["kind"], place["x"], place["note"]) for place in places(ctx.db)],
                         [("fire", 1, "campfire"), ("farm", 0, "")])
        observe_step(pet(), {"kind": "mine", "target": at(1, 1, 0), "block": "campfire"}, ctx, 3.0)
        self.assertEqual([place["kind"] for place in places(ctx.db)], ["farm"])


if __name__ == "__main__":
    unittest.main()

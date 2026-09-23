import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival import world as world_module
from backend.survival.memory import (
    create_memory_tables, forget, known_recipes, learn, nearest, places, remember, visit,
)
from backend.survival.triggers import crossings, ensure_brain, hour_passed, mark_trigger, phase_trigger
from backend.survival.world import SurvivalWorld, new_survival_state, read_state, write_state

SEED = "123456789123456789"
SPAWN = {"x": 3682, "y": 5, "z": 4143}


def memory_db():
    db = sqlite3.connect(":memory:")
    create_memory_tables(db)
    return db


class MemoryTests(unittest.TestCase):
    def test_places_are_remembered_once_with_their_note(self):
        db = memory_db()
        self.assertTrue(remember(db, "ore", (1, -2, 3), 10.0, "iron_ore"))
        self.assertFalse(remember(db, "ore", (1, -2, 3), 11.0, "iron_ore"))
        self.assertTrue(remember(db, "ore", (2, -2, 3), 12.0, "coal_ore"))
        self.assertEqual([(p["kind"], p["x"], p["note"], p["found_at"], p["visited_at"]) for p in places(db)],
                         [("ore", 1, "iron_ore", 10.0, None), ("ore", 2, "coal_ore", 12.0, None)])

    def test_home_is_one_place_and_close_spots_are_the_same_place(self):
        db = memory_db()
        self.assertTrue(remember(db, "home", (0, 5, 0), 1.0))
        self.assertFalse(remember(db, "home", (50, 5, 0), 2.0))
        self.assertFalse(remember(db, "shelter", (5, 5, 0), 3.0))
        self.assertTrue(remember(db, "shelter", (20, 5, 0), 4.0))
        self.assertTrue(remember(db, "water", (30, 2, 10), 5.0))
        self.assertFalse(remember(db, "water", (40, 2, 10), 6.0))
        self.assertEqual([p["kind"] for p in places(db, ("home", "shelter"))], ["home", "shelter"])

    def test_forget_visit_and_nearest(self):
        db = memory_db()
        remember(db, "ore", (1, 0, 1), 1.0, "coal_ore")
        remember(db, "home", (10, 5, 0), 1.0)
        remember(db, "shelter", (40, 5, 0), 1.0)
        visit(db, (11, 5, 1), 9.0)
        found = places(db)
        self.assertEqual(nearest(found, (30, 5, 0), ("home", "shelter"))["x"], 40)
        self.assertEqual(nearest(found, (30, 5, 0), ("home",))["visited_at"], 9.0)
        self.assertIsNone(nearest(found, (100, 5, 0), ("home", "shelter"), max_distance=50))
        forget(db, "ore", (1, 0, 1))
        self.assertEqual([p["kind"] for p in places(db)], ["home", "shelter"])

    def test_recipes_are_learned_once_and_counted(self):
        db = memory_db()
        self.assertTrue(learn(db, "planks", 1.0))
        self.assertFalse(learn(db, "planks", 2.0))
        self.assertTrue(learn(db, "sticks", 3.0))
        self.assertEqual(known_recipes(db), ["planks", "sticks"])
        self.assertEqual(db.execute("SELECT uses FROM memory_recipes WHERE recipe='planks'").fetchone()[0], 2)


class WorldMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "lives" / "2.sqlite3"
        self.world = SurvivalWorld.create(self.path, new_survival_state(
            name="Pip", seed=SEED, spawn=SPAWN, born_at=1000.0, traits={}))

    def tearDown(self):
        self.directory.cleanup()

    def test_a_new_world_starts_with_empty_memory(self):
        with self.world.connect() as db:
            self.assertEqual(places(db), [])
            self.assertEqual(known_recipes(db), [])

    def test_worlds_from_before_m3_get_the_memory_tables(self):
        with self.world.connect() as db:
            db.execute("DROP TABLE memory_places")
            db.execute("DROP TABLE memory_recipes")
        world_module._schema_ready.discard(self.path.resolve())
        with SurvivalWorld(self.path).connect() as db:
            self.assertEqual(places(db), [])
            self.assertEqual(known_recipes(db), [])

    def test_a_hello_asks_for_a_new_choice(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["last_tick_at"] = 1495.0
            write_state(db, state)
        self.world.greet(1500.0)
        self.assertIn("hello", self.world.state()["brain"]["pending"]["reasons"])


class TriggerTests(unittest.TestCase):
    def test_a_new_brain_waits_for_its_first_choice(self):
        state = {"last_tick_at": 50.0}
        brain = ensure_brain(state)
        self.assertEqual(brain["pending"], {"id": 1, "reasons": ["born"], "since": 50.0, "urgent": False})
        self.assertIsNone(brain["purpose"])
        self.assertIs(ensure_brain(state), brain)

    def test_triggers_merge_and_urgent_ones_get_a_new_id(self):
        state = {"last_tick_at": 0.0}
        brain = ensure_brain(state)
        brain["pending"] = None
        mark_trigger(state, "plan_done", 10.0)
        mark_trigger(state, "dusk", 11.0)
        mark_trigger(state, "dusk", 12.0)
        self.assertEqual(brain["pending"], {"id": 2, "reasons": ["plan_done", "dusk"], "since": 10.0, "urgent": False})
        mark_trigger(state, "hunger_30", 13.0, urgent=True)
        self.assertEqual(brain["pending"], {"id": 3, "reasons": ["plan_done", "dusk", "hunger_30"], "since": 10.0,
                                            "urgent": True})

    def test_crossings_phases_and_the_game_hour(self):
        before = {"health": 100.0, "hunger": 50.2, "warmth": 31.0, "energy": 16.0}
        after = {"health": 100.0, "hunger": 49.9, "warmth": 14.0, "energy": 15.0}
        self.assertEqual(crossings(before, after), ["hunger_50", "warmth_30", "warmth_15"])
        self.assertEqual([phase_trigger("pre_dawn", "dawn"), phase_trigger("day", "dusk"),
                          phase_trigger("dusk", "night"), phase_trigger("day", "day")], ["dawn", "dusk", None, None])
        brain = ensure_brain({"last_tick_at": 0.0})
        self.assertFalse(hour_passed(brain, 100.0, 60.0))
        brain["chosen_at"] = 0.0
        self.assertFalse(hour_passed(brain, 59.0, 60.0))
        self.assertTrue(hour_passed(brain, 60.0, 60.0))


if __name__ == "__main__":
    unittest.main()

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival import world as world_module
from backend.survival.memory import (
    create_memory_tables, forget, know, known, known_recipes, learn, nearest, places, remember, update_place, visit,
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

    def test_a_place_keeps_data_that_updates_merge_into(self):
        db = memory_db()
        remember(db, "food", (5, 3, 5), 1.0)
        self.assertTrue(update_place(db, "food", (5, 3, 5), {"ripe": 3, "seen_at": 1.0}))
        self.assertTrue(update_place(db, "food", (5, 3, 5), {"ripe": 1}))
        self.assertFalse(update_place(db, "food", (9, 3, 9), {"ripe": 1}))
        self.assertEqual(places(db)[0]["data"], {"ripe": 1, "seen_at": 1.0})
        self.assertFalse(remember(db, "food", (10, 3, 5), 2.0))
        self.assertTrue(remember(db, "fire", (6, 3, 5), 2.0, "campfire"))
        self.assertEqual(places(db, ("fire",))[0]["data"], {})

    def test_places_are_read_in_a_box_around_a_cell(self):
        db = memory_db()
        remember(db, "ore", (0, 0, 0), 1.0, "coal_ore")
        remember(db, "ore", (300, 0, 0), 2.0, "coal_ore")
        remember(db, "home", (10, 5, -20), 3.0)
        self.assertEqual([place["x"] for place in places(db, around=(0, 0, 0), reach=32)], [0, 10])
        self.assertEqual([place["x"] for place in places(db, ("ore",), around=(290, 0, 0), reach=32)], [300])

    def test_facts_are_learned_once(self):
        db = memory_db()
        self.assertTrue(know(db, "red_mushroom", "poisonous", 1.0))
        self.assertFalse(know(db, "red_mushroom", "poisonous", 2.0))
        self.assertEqual((known(db, "poisonous"), known(db, "tasty")), (["red_mushroom"], []))



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

    def test_memory_from_m3_gets_place_data_and_facts_and_keeps_its_places(self):
        with self.world.connect() as db:
            db.execute("DROP TABLE memory_places")
            db.execute("CREATE TABLE memory_places (kind TEXT NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL, "
                       "z INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '', found_at REAL NOT NULL, visited_at REAL, "
                       "PRIMARY KEY (kind, x, y, z))")
            db.execute("INSERT INTO memory_places(kind, x, y, z, found_at) VALUES ('home', 1, 5, 1, 9.0)")
            db.execute("DROP TABLE memory_knowledge")
        world_module._schema_ready.discard(self.path.resolve())
        with SurvivalWorld(self.path).connect() as db:
            self.assertEqual([(place["kind"], place["data"]) for place in places(db)], [("home", {})])
            self.assertEqual(known(db, "poisonous"), [])
            create_memory_tables(db)
            self.assertEqual(len(places(db)), 1)



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

import os
import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import lives
from backend.api.lives import Hatching, hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.insights import insights
from backend.survival.journal import journal_payload, journal_view, learned
from backend.survival.memory import create_memory_tables, know
from backend.survival.registry import LifeRegistry
from backend.survival.replies import Heard, journal
from backend.survival.situation import from_db
from backend.survival.tick import tick_life
from backend.survival.wild import (
    BORN_KNOWING, GENTLE, SURVIVAL, WILD, difficulty, is_wild, settle, survival_view, thing, unlocked,
)
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_pickers import situation

BORN = 1_000_000.0


class Lives:
    """A fresh registry in a temporary directory."""

    def __init__(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")

    def hatch(self, seed=8, **kwargs):
        life = hatch(self.registry, random.Random(seed), timestamp=BORN, **kwargs)
        return life, SurvivalWorld(self.registry.world_path(life))


class DifficultyTests(unittest.TestCase):
    def setUp(self):
        self.lives = Lives()

    def tearDown(self):
        self.lives.directory.cleanup()

    def test_hatch_is_gentle_unless_told_and_a_life_is_wild_or_gentle(self):
        with self.assertRaises(ValueError):
            self.lives.hatch(difficulty="hard")
        _, world = self.lives.hatch()
        self.assertEqual(world.state()["difficulty"], GENTLE)

    def test_a_world_from_before_w1_reads_gentle_and_its_first_tick_writes_it(self):
        _, world = self.lives.hatch()
        with world.transaction() as db:
            state = read_state(db)
            del state["difficulty"]
            write_state(db, state)
        self.assertEqual(difficulty(world.state()), GENTLE)
        self.assertFalse(is_wild(world.state()))
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertEqual(world.state()["difficulty"], GENTLE)

    def test_a_gentle_pet_is_granted_every_survival_lesson_on_its_first_tick_silently(self):
        _, world = self.lives.hatch()
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        with world.connect() as db:
            rows = {tuple(row) for row in db.execute("SELECT subject, fact FROM memory_knowledge WHERE subject LIKE 'wild:%'")}
            memories = db.execute("SELECT COUNT(*) FROM mind_memories").fetchone()[0]
            view = survival_view(db)
        self.assertEqual(rows, {(thing(lesson.name), fact) for lesson in SURVIVAL for fact in ("lesson", BORN_KNOWING)})
        self.assertEqual(memories, 0)
        self.assertEqual({entry["source"] for entry in view}, {"from_start"})
        self.assertFalse(any(event["kind"] in ("learned", "figured") for event in world.events(100)))
        self.assertEqual(world.state()["wild"], {"granted": 1})
        tick_life(self.lives.registry, BORN + 2, scale=1.0, mind=BRAIN)  # granted once
        self.assertEqual(world.state()["wild"], {"granted": 1})

    def test_a_wild_pet_is_granted_nothing_and_knows_only_instinct(self):
        _, world = self.lives.hatch(difficulty=WILD)
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        with world.connect() as db:
            view = survival_view(db)
        self.assertEqual(world.state()["difficulty"], WILD)
        self.assertEqual([entry["known"] for entry in view], [False] * len(SURVIVAL))
        self.assertIsNone(view[0]["source"])

    def test_a_dead_pets_world_is_never_written(self):
        _, world = self.lives.hatch()
        with world.transaction() as db:
            state = read_state(db)
            del state["difficulty"]
            state.update(died_at=BORN + 0.5, cause="starvation")
            write_state(db, state)
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertNotIn("difficulty", world.state())
        with world.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_knowledge").fetchone()[0], 0)

    def test_settle_leaves_a_wild_pet_and_a_granted_pet_alone(self):
        db = sqlite3.connect(":memory:")
        create_memory_tables(db)
        wild = {"difficulty": WILD}
        settle(wild, db, 1.0)
        self.assertEqual(wild, {"difficulty": WILD})
        gentle = {"wild": {"granted": 1}}
        settle(gentle, db, 1.0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM memory_knowledge").fetchone()[0], 0)


class LessonTests(unittest.TestCase):
    def test_a_gate_is_open_for_a_gentle_pet_and_for_a_wild_one_that_knows(self):
        gentle = situation()
        self.assertTrue(unlocked(gentle, "fire"))
        wild = situation()
        wild.state["difficulty"] = WILD
        self.assertFalse(unlocked(wild, "fire"))
        know(wild.db, "wild:fire", "lesson", 1.0)
        taught = situation()
        taught.state["difficulty"] = WILD
        taught.db = wild.db
        self.assertTrue(unlocked(taught, "fire"))
        self.assertFalse(unlocked(taught, "shelter"))


class BornKnowingTests(unittest.TestCase):
    """Lessons known from birth never count as lessons learned."""

    def setUp(self):
        self.lives = Lives()
        _, self.world = self.lives.hatch()
        tick_life(self.lives.registry, BORN + 1, scale=1.0, mind=BRAIN)

    def tearDown(self):
        self.lives.directory.cleanup()

    def test_the_journal_the_situation_and_the_thoughts_leave_them_out(self):
        with self.world.transaction() as db:
            know(db, "gravel", "lesson", BORN + 2)
            state = read_state(db)
            s = from_db(db, state, BORN + 3, 1.0)
            self.assertEqual(s.lessons, ("gravel",))
            self.assertEqual([name for name, _ in learned(db)], ["gravel"])
            self.assertEqual([entry["thing"] for entry in journal_view(db, state.get("brain"))], ["gravel"])
            self.assertEqual(journal_view(db, None)[0]["source"], "figured")
            self.assertEqual(journal_payload(s)["lessons"], 1)
            self.assertFalse(any(insight.key.startswith("learned:") for insight in insights(db, state, 1, 1.0)))

    def test_the_replies_journal_line_tells_a_survival_lesson_learned_but_never_one_known_from_birth(self):
        # Carried item 1 (Task 1's review): replies.journal reads s.lessons, which holds wild:* lessons now.
        asked, nothing = Heard("What did you learn today?"), "Nothing new yet. I'm still looking!"
        with self.world.transaction() as db:  # a gentle pet knows every survival lesson from birth
            self.assertEqual(journal(from_db(db, read_state(db), BORN + 2, 1.0), asked), nothing)
        other = Lives()
        self.addCleanup(other.directory.cleanup)
        _, wild = other.hatch(difficulty=WILD)
        with wild.transaction() as db:
            know(db, thing("fire"), "lesson", BORN + 2)
            self.assertEqual(journal(from_db(db, read_state(db), BORN + 3, 1.0), asked),
                             "I learned something new: two logs and three sticks make a campfire, and a fire keeps you "
                             "warm at night.")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"), "MIMO_DB_PATH": str(root / "mimo.sqlite3"),
                                           "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_api_hatches_wild_by_default_and_gentle_when_asked(self):
        hatch_egg()
        mimo = get_mimo()
        self.assertEqual(mimo["difficulty"], WILD)
        self.assertEqual(len(mimo["survival"]), 11)
        registry = LifeRegistry()
        registry.mark_dead(registry.active_life()["id"], BORN, "starvation")
        memorial = get_mimo()["last_life"]
        self.assertEqual(len(memorial["survival"]), 11)  # the memorial tallies where its lessons came from
        hatch_egg(Hatching(difficulty="gentle"))
        self.assertEqual(get_mimo()["difficulty"], GENTLE)

    def test_the_api_refuses_a_difficulty_it_does_not_know(self):
        # Carried item 1 (Task 1's review): a bad difficulty is a 422 (pydantic's Literal), and nothing hatches.
        app = FastAPI()
        app.include_router(lives.router)
        client = TestClient(app)
        self.assertEqual(client.post("/lives/hatch", json={"difficulty": "hard"}).status_code, 422)
        self.assertIsNone(LifeRegistry().active_life())
        self.assertEqual(client.post("/lives/hatch", json={"difficulty": "gentle"}).status_code, 200)


if __name__ == "__main__":
    unittest.main()

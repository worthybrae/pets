import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.bond import visit_mimo
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.survival.bond import (
    DAILY, FADE, GAINS, GRACE, REAL_DAY, START, bond_level, bond_view, feeling, grow_bond, visit,
)
from backend.survival.brain import BRAIN
from backend.survival.care import give_care
from backend.survival.hatch import hatch
from backend.survival.registry import LifeRegistry
from backend.survival.replies import Heard
from backend.survival.situation import from_db
from backend.survival.talk import hear, owner_says
from backend.survival.tick import tick_life
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0  # 13:46:40 UTC: ten hours of the UTC day are left
TOMORROW = BORN + 11 * 3600


class BondValueTests(unittest.TestCase):
    def test_a_new_pet_starts_shy_and_every_kind_of_care_counts(self):
        state = {}
        self.assertEqual(bond_view(state, BORN), {"level": START, "feeling": "shy"})
        self.assertEqual(grow_bond(state, "snack", BORN), START + GAINS["snack"])
        self.assertEqual(grow_bond(state, "bandage", BORN + 1), START + GAINS["snack"] + GAINS["bandage"])
        self.assertEqual(grow_bond(state, "promise", BORN + 2), START + 16.0)
        self.assertEqual(feeling(bond_level(state, BORN + 2)), "friendly")

    def test_hellos_and_chats_count_only_so_often_a_utc_day(self):
        state = {}
        for second in range(10):
            grow_bond(state, "hello", BORN + second)
        self.assertEqual(bond_level(state, BORN + 10), START + DAILY["hello"] * GAINS["hello"])
        for second in range(30):
            grow_bond(state, "chat", BORN + 20 + second)
        self.assertEqual(bond_level(state, BORN + 60), START + DAILY["hello"] * GAINS["hello"] + DAILY["chat"])
        grow_bond(state, "hello", TOMORROW)
        self.assertEqual(bond_level(state, TOMORROW), START + (DAILY["hello"] + 1) * GAINS["hello"] + DAILY["chat"])

    def test_it_never_passes_a_hundred(self):
        state = {"bond": {"value": 98.0, "seen_at": BORN, "gains": {"day": None}}}
        self.assertEqual(grow_bond(state, "promise", BORN + 1), 100.0)

    def test_it_fades_while_the_owner_stays_away_and_a_visit_settles_it(self):
        state = {}
        grow_bond(state, "snack", BORN)
        level = START + GAINS["snack"]
        self.assertEqual(bond_level(state, BORN + GRACE), level)  # a day away: not yet
        self.assertAlmostEqual(bond_level(state, BORN + GRACE + 2 * REAL_DAY), level - 2 * FADE)
        self.assertEqual(state["bond"]["value"], level)  # reading never writes
        visit(state, BORN + GRACE + 2 * REAL_DAY)
        self.assertAlmostEqual(state["bond"]["value"], level - 2 * FADE)
        self.assertAlmostEqual(bond_level(state, BORN + 2 * GRACE + 2 * REAL_DAY), level - 2 * FADE)  # starts over
        self.assertEqual(bond_level(state, BORN + 100 * REAL_DAY), 0.0)  # never below nothing


class BondInTheWorldTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def level(self, now):
        return bond_level(self.world.state(), now)

    def test_care_hello_and_talk_grow_the_bond(self):
        give_care(self.world, "snack", BORN + 1)
        give_care(self.world, "bandage", BORN + 2)
        self.world.greet(BORN + 3)
        owner_says(self.world, "hi", BORN + 4, 1.0)
        self.assertEqual(self.level(BORN + 5), START + GAINS["snack"] + GAINS["bandage"] + GAINS["hello"] + GAINS["chat"])
        self.assertEqual(self.world.state()["bond"]["seen_at"], BORN + 4)

    def test_the_bond_sets_the_tone_of_a_reply(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["bond"] = {"value": 80.0, "seen_at": BORN, "gains": {"day": None}}
            write_state(db, state)
        with self.world.connect() as db:
            heard = hear(db, from_db(db, read_state(db), BORN + 5, 1.0), "hi")
        self.assertEqual(heard.bond, 80.0)
        self.assertEqual(Heard("hi").bond, 30.0)

    def test_the_bond_changes_nothing_about_survival(self):
        other_root = Path(self.directory.name) / "other"
        other = LifeRegistry(other_root / "data", other_root / "no-legacy.sqlite3")
        hatch(other, random.Random(8), timestamp=BORN)
        for registry, value in ((self.registry, 0.0), (other, 100.0)):
            world = SurvivalWorld(registry.world_path(registry.active_life()))
            with world.transaction() as db:
                state = read_state(db)
                state["bond"] = {"value": value, "seen_at": BORN, "gains": {"day": None}}
                write_state(db, state)
            for second in range(1, 121):
                tick_life(registry, BORN + second, scale=1.0, mind=BRAIN, action_scale=1.0)
        states = [SurvivalWorld(registry.world_path(registry.active_life())).state() for registry in (self.registry, other)]
        for state in states:
            state.pop("bond")
        self.assertEqual(states[0], states[1])


class VisitApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "no-legacy.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_a_visit_is_noted_and_the_stream_shows_the_bond(self):
        with self.assertRaises(HTTPException) as caught:
            visit_mimo()
        self.assertEqual(caught.exception.status_code, 409)
        hatch_egg()
        self.assertEqual(visit_mimo(), {"bond": {"level": 20, "feeling": "shy"}})
        self.assertEqual(get_mimo()["bond"], {"level": 20, "feeling": "shy"})
        registry = LifeRegistry()
        self.assertIsNotNone(SurvivalWorld(registry.world_path(registry.active_life())).state()["bond"]["seen_at"])


if __name__ == "__main__":
    unittest.main()

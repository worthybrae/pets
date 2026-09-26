import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.expedition import expedition_view
from backend.survival.hatch import hatch
from backend.survival.journal import LESSONS, journal_payload, journal_state, journal_view, learn_lesson
from backend.survival.memory import know, remember
from backend.survival.pickers import context_payload
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import survival_view
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_journal import Studying

BORN = 1_000_000.0


class JournalViewTests(Studying):
    def test_the_journal_newest_first_with_the_line_jev_chose(self):
        for at, thing in ((1.0, "gravel"), (2.0, "skitter")):
            learn_lesson(self.world.state, self.context, at, thing)
        journal_state(self.world.state)["words"]["skitter"] = LESSONS["skitter"].lines[0]
        view = journal_view(self.world.db, self.world.state["brain"])
        self.assertEqual([(entry["thing"], entry["line"]) for entry in view],
                         [("skitter", "Skitters crawl out of the caves at night."),
                          ("gravel", "Gravel sometimes hides flint.")])
        self.assertEqual({key: view[1][key] for key in ("kind", "words", "fact", "unlocks", "at")},
                         {"kind": "block", "words": "gravel", "fact": "Gravel sometimes hides flint.",
                          "unlocks": "digs gravel for flint", "at": 1.0})

    def test_the_model_is_told_what_mimo_learned_what_it_could_study_and_its_expedition(self):
        self.world.grid.put(6, 0, 0, "gravel")
        remember(self.world.db, "sight", (6, 0, 0), 0.0, "gravel")
        know(self.world.db, "skitter", "lesson", 1.0)
        payload = context_payload(self.world.situation(), [])
        self.assertEqual(payload["journal"], {"lessons": 1, "newest": "Skitters come out of caves at night.",
                                              "could_study": ["gravel"]})
        self.assertIsNone(payload["expedition"])
        self.assertEqual(journal_payload(self.world.situation())["could_study"], ["gravel"])
        self.assertIsNone(expedition_view({"goal": None, "expedition": {"since": 1.0}}))  # not the goal now


class StreamTests(unittest.TestCase):
    def test_api_mimo_streams_the_journal_and_the_expedition(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            fresh = survival_view(world, BORN + 1, 1.0)
            self.assertEqual((fresh["journal"], fresh["expedition"]), ([], None))
            with world.transaction() as db:
                state = read_state(db)
                know(db, "skitter", "lesson", BORN)
                journal_state(state)["words"]["skitter"] = LESSONS["skitter"].lines[1]
                state["brain"]["goal"] = {"name": "expedition", "since": BORN}
                state["brain"]["expedition"] = {"since": BORN, "phase": "out", "direction": "east", "far": 132.4,
                                                "target": 180, "nights": 1}
                write_state(db, state)
            view = survival_view(world, BORN + 2, 1.0)
        self.assertEqual(view["journal"][0]["line"], "Skitters live in the caves. Careful after dark.")
        self.assertEqual(view["expedition"], {"phase": "out", "direction": "east", "far": 132, "target": 180,
                                              "nights": 1, "camping": False})


if __name__ == "__main__":
    unittest.main()

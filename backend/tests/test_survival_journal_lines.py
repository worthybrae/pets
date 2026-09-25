import random
import tempfile
import unittest
from pathlib import Path

from backend.survival.choosing import Chooser, InlineExecutor
from backend.survival.hatch import hatch
from backend.survival.journal import journal_state
from backend.survival.memory import know
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.triggers import mark_trigger
from backend.survival.world import SurvivalWorld, read_state, write_state
from backend.tests.test_survival_goal_choice import Recorder

BORN = 1_000_000.0


class JevLineTests(unittest.TestCase):
    """Jev phrases the journal in the purpose call it makes anyway, never in the tick."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(life))
        with self.world.transaction() as db:
            state = read_state(db)
            know(db, "skitter", "lesson", BORN)
            journal_state(state)["unphrased"] = ["skitter"]
            mark_trigger(state, "hello", BORN)
            write_state(db, state)

    def tearDown(self):
        self.directory.cleanup()

    def poll(self, env, http):
        chooser = Chooser(env=env, http=http, executor=InlineExecutor(), rng=random.Random(1), scale=1.0)
        chooser.poll(self.registry, BORN + 5)
        return journal_state(self.world.state())

    def test_a_purpose_call_to_jev_also_chooses_the_journal_line(self):
        jev = Recorder({"answers": {"purpose": {"choice": "rest"}, "journal_line": {"choice": "line_1"}}})
        journal = self.poll({"TYPESAFE_API_KEY": "k"}, jev)
        body = jev.bodies[0]
        self.assertEqual(set(body["questions"]), {"purpose", "journal_line"})
        self.assertEqual(sorted(body["questions"]["journal_line"]["criteria"]), ["line_0", "line_1", "line_2"])
        self.assertEqual(body["state"]["learned"], "Skitters come out of caves at night.")
        self.assertEqual((journal["words"], journal["unphrased"]),
                         ({"skitter": "Skitters crawl out of the caves at night."}, []))

    def test_a_failed_call_leaves_the_lesson_waiting(self):
        jev = Recorder({"answers": {"purpose": {"choice": "rest"}}})  # no line chosen: the call fails
        forget_logged()
        with self.assertLogs("backend.survival.choosing", level="ERROR"):
            journal = self.poll({"TYPESAFE_API_KEY": "k"}, jev)
        self.assertEqual((journal["words"], journal["unphrased"]), ({}, ["skitter"]))

    def test_without_jev_the_lesson_waits_for_its_line(self):
        nobody = Recorder({})
        journal = self.poll({}, nobody)
        self.assertEqual((nobody.bodies, journal["words"], journal["unphrased"]), ([], {}, ["skitter"]))


if __name__ == "__main__":
    unittest.main()

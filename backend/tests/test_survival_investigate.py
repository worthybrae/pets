import math
import unittest

from backend.survival.journal import curios, journal_state, observe_journal
from backend.survival.memory import know, known, places, remember
from backend.survival.purposes import PURPOSES
from backend.tests.test_survival_journal import Studying


class Herd:
    """Creatures that only answer who is near, where."""

    def __init__(self, *creatures):
        self.creatures = creatures

    def near(self, x, z, reach):
        return [{"kind": kind, "x": cx, "y": 1.0, "z": cz, "state": {}} for kind, cx, cz in self.creatures
                if math.hypot(cx - x, cz - z) <= reach]


class InvestigateTests(Studying):
    def test_it_walks_up_takes_a_sample_looks_it_over_and_then_learns(self):
        self.world.grid.put(6, 0, 0, "gravel")
        remember(self.world.db, "sight", (6, 0, 0), 0.0, "gravel")
        s = self.world.situation()
        investigate = PURPOSES["investigate"]
        self.assertTrue(investigate.valid(s))
        self.assertEqual(investigate.score(s), 50.0)  # 40 and a quarter of curiosity (40)
        self.assertIn("gravel 5 blocks away", investigate.facts(s))
        steps = investigate.plan(s, self.context)
        self.assertEqual(steps, [{"kind": "walk", "target": [6, 0, 0], "reach": 2.0, "whole": True},
                                 {"kind": "mine", "target": [6, 0, 0]}, {"kind": "wait", "seconds": 4.0}])
        self.assertEqual(journal_state(self.world.state)["studying"], {"thing": "gravel", "cell": [6, 0, 0]})
        observe_journal(self.world.state, {"kind": "wait", "purpose": "investigate"}, self.context, 9.0)
        self.assertEqual(known(self.world.db, "lesson"), ["gravel"])
        self.assertEqual(places(self.world.db, ("sight",)), [])
        self.assertFalse(investigate.valid(self.world.situation()))

    def test_a_sight_that_is_gone_is_not_worth_the_walk(self):
        remember(self.world.db, "sight", (6, 0, 0), 0.0, "gravel")  # the grid holds grass there
        self.assertEqual(curios(self.world.situation()), [])

    def test_creatures_it_met_are_watched_and_a_failed_look_leaves_the_thing_alone(self):
        self.world.grid.herd = Herd(("sheep", 12.0, 1.0), ("cow", 30.0, 1.0))
        know(self.world.db, "sheep", "creature", 0.0)
        know(self.world.db, "cow", "creature", 0.0)
        s = self.world.situation()
        self.assertEqual([(curio.thing, curio.cell) for curio in curios(s)], [("sheep", (12, 1, 1))])  # cow: too far
        self.assertEqual(PURPOSES["investigate"].plan(s, self.context),
                         [{"kind": "walk", "target": [12, 1, 1], "reach": 4.0, "whole": True},
                          {"kind": "wait", "seconds": 8.0}])
        self.world.state["brain"]["replans"] = 1  # the walk failed
        self.assertEqual(PURPOSES["investigate"].plan(self.world.situation(), self.context), [])
        self.assertEqual(curios(self.world.situation()), [])  # the sheep is left alone for half a day


if __name__ == "__main__":
    unittest.main()

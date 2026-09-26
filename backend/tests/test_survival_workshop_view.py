import random
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.survival.hatch import hatch
from backend.survival.machines import workshop_view
from backend.survival.registry import LifeRegistry
from backend.survival.signals import run_signals
from backend.survival.snapshot import survival_view
from backend.survival.world import SurvivalWorld
from backend.tests.test_survival_machines import wired

BORN = 1_000_000.0
NOTHING = {"workshop": None, "machines": [], "doors_open": []}


class WorkshopViewTests(unittest.TestCase):
    def test_the_machines_their_lamps_and_the_doors_they_hold_open(self):
        yard = wired()
        yard.build("build_machine", batches=3)  # the lamp on a lever, built and tried; the door
        run_signals(yard.state, yard.context(), 1.0)
        view = workshop_view(yard.db)
        self.assertIsNone(view["workshop"])
        self.assertEqual([(machine["name"], machine["machine"], machine["status"]) for machine in view["machines"]],
                         [("a lamp on a lever", "lamp_lever", "done"), ("an automatic door", "auto_door", "done")])
        self.assertEqual([machine["lamps"] for machine in view["machines"]], [1, 0])
        self.assertEqual(view["doors_open"], [])
        yard.state["position"] = {"x": 1.0, "y": 1.0, "z": 0.0}  # on the plate inside the door
        run_signals(yard.state, yard.context(), 2.0)
        self.assertEqual(workshop_view(yard.db)["doors_open"], [[1, 1, -1]])

    def test_a_world_that_made_nothing_and_an_archive_from_before_read_as_nothing(self):
        self.assertEqual(workshop_view(sqlite3.connect(":memory:")), NOTHING)
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            view = survival_view(SurvivalWorld(registry.world_path(life)), BORN + 1, 1.0)
        self.assertEqual(view["workshop"], NOTHING)


if __name__ == "__main__":
    unittest.main()

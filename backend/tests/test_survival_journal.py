import unittest
from unittest.mock import patch

from backend.survival import brain  # noqa: F401  (registers every purpose)
from backend.survival.curiosity import curiosity_state
from backend.survival.journal import NEW_LESSON, journal_state, learn_lesson, observe_journal
from backend.survival.memory import known, places, remember
from backend.survival.once import forget_logged
from backend.tests.test_survival_building import World

MEADOW = lambda x, z, seed: "meadow"  # noqa: E731
FLAT = lambda x, z, seed: 0  # noqa: E731


def gravel_shore(x, z, seed):
    return "gravel" if 6 <= x <= 7 and z == 0 else "grass"


class Studying(unittest.TestCase):
    """A pet on the flat meadow whose curiosity the tick already tends, where worldgen would put
    gravel at (6, 0, 0) and (7, 0, 0)."""

    def setUp(self):
        for name, value in (("backend.survival.journal.biome_at", MEADOW),
                            ("backend.survival.journal.terrain_height", FLAT),
                            ("backend.survival.journal.surface_material", gravel_shore),
                            ("backend.survival.journal.natural_plants", lambda *args: []),
                            ("backend.survival.journal.SEA_LEVEL", 0)):
            patcher = patch(name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.world = World({"stone_pickaxe": 1})
        self.context = self.world.context()
        curiosity_state(self.world.state, 0.0)


class JournalTests(Studying):
    def test_what_it_digs_or_lays_bare_it_learns_at_once(self):
        self.world.grid.put(3, -1, 1, "coal_ore")
        before = self.world.state["brain"]["curiosity"]["value"]
        observe_journal(self.world.state, {"kind": "mine", "target": {"x": 3, "y": 0, "z": 1}, "block": "gravel"},
                        self.context, 5.0)
        self.assertEqual(known(self.world.db, "lesson"), ["coal_ore", "gravel"])
        self.assertEqual([text for _, kind, text in self.context.events if kind == "learned"],
                         ["Pip learned that gravel sometimes hides flint.",
                          "Pip learned that coal burns: a coal and a stick make four torches."])
        self.assertEqual(self.world.state["brain"]["curiosity"]["value"], before - 2 * NEW_LESSON)
        self.assertEqual(journal_state(self.world.state)["unphrased"], ["gravel", "coal_ore"])
        self.assertEqual(self.world.situation().lessons, ("coal_ore", "gravel"))
        self.assertIn("discovery", self.world.state["brain"]["pending"]["reasons"])  # gravel unlocks flint
        self.assertFalse(learn_lesson(self.world.state, self.context, 6.0, "gravel"))  # once only
        self.assertFalse(learn_lesson(self.world.state, self.context, 6.0, "stone"))  # no lesson for stone

    def test_a_walk_teaches_the_biome_and_landmarks_and_notes_what_to_study_later(self):
        remember(self.world.db, "water", (4, 0, 4), 0.0)
        self.world.state["position"] = {"x": 0.0, "y": 1.0, "z": 0.0}
        observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, 5.0)
        self.assertEqual(known(self.world.db, "lesson"), ["lake", "meadow"])
        self.assertEqual(places(self.world.db, ("sight",)), [])  # the worldgen's gravel is not in this grid
        self.world.grid.put(6, 0, 0, "gravel")
        for at in (6.0, 7.0):
            observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, at)
        self.assertEqual([(place["note"], place["x"], place["z"]) for place in places(self.world.db, ("sight",))],
                         [("gravel", 6, 0)])  # one sight of each kind
        learn_lesson(self.world.state, self.context, 8.0, "gravel")
        self.assertEqual(places(self.world.db, ("sight",)), [])  # learned: no longer a sight

    def test_before_the_tick_tends_curiosity_the_journal_waits(self):
        del self.world.state["brain"]["curiosity"]
        observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, 5.0)
        self.assertEqual((known(self.world.db, "lesson"), self.context.events), ([], []))

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        with patch("backend.survival.journal.note_sights", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.journal", level="ERROR") as logs:
            for at in (1.0, 2.0):
                observe_journal(self.world.state, {"kind": "walk", "path": []}, self.context, at)
        self.assertEqual(len(logs.output), 1)


if __name__ == "__main__":
    unittest.main()

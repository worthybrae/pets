import random
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every purpose and goal registered)
from backend.survival import expedition, pickers
from backend.survival import minding  # noqa: F401  (the nudges registered)
from backend.survival.actions import ensure_actions
from backend.survival.clock import DAY_SECONDS
from backend.survival.expedition import PACK_FOOD, PACK_MORE_TOP, pack_food
from backend.survival.hatch import hatch
from backend.survival.mind import mind_state
from backend.survival.nudges import LIKED, PACK_MORE, WARY, thought_nudge
from backend.survival.once import forget_logged
from backend.survival.pickers import NUDGE_TOP, nudged, options
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.world import SurvivalWorld, read_state

BORN = 1_000_000.0
NOON, NIGHT = 1200.0, 2600.0


class NudgeTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.world = SurvivalWorld(registry.world_path(hatch(registry, random.Random(8), timestamp=BORN)))

    def tearDown(self):
        self.directory.cleanup()

    def situation(self, nudges, day=3, seconds=NOON):
        stack = ExitStack()
        self.addCleanup(stack.close)
        db = stack.enter_context(self.world.connect())
        state = read_state(db)
        ensure_actions(state)
        mind_state(state)["nudges"] = nudges
        return from_db(db, state, BORN + (day - 1) * DAY_SECONDS + seconds, 1.0)

    def test_a_liked_purpose_scores_more_while_its_thought_holds(self):
        self.assertEqual(thought_nudge(self.situation({"likes:fish": 5}), "fish"), LIKED)
        self.assertEqual(thought_nudge(self.situation({"likes:fish": 5}), "hunt"), 0.0)
        self.assertEqual(thought_nudge(self.situation({"likes:fish": 2}), "fish"), 0.0)  # it held until day 2

    def test_what_mimo_is_wary_of_makes_that_work_score_less_at_night(self):
        wary = {"wary:skitter": 9}
        self.assertEqual(thought_nudge(self.situation(wary, seconds=NIGHT), "mine_ore"), -WARY)
        self.assertEqual(thought_nudge(self.situation(wary, seconds=NIGHT), "gather_wood"), 0.0)
        self.assertEqual(thought_nudge(self.situation(wary, seconds=NOON), "mine_ore"), 0.0)

    def test_the_offered_scores_carry_the_nudges_within_their_bound(self):
        s = self.situation({})
        plain = {option.name: option.score for option in options(s)}
        with patch.object(pickers, "NUDGES", [lambda s, name: 100.0 if name == "rest" else 0.0, lambda s, name: 1 / 0]):
            with self.assertLogs("backend.survival.pickers", level="ERROR") as logs:
                nudged_scores = {option.name: option.score for option in options(self.situation({}))}
                self.assertEqual(nudged(self.situation({}), "rest"), NUDGE_TOP)
        self.assertAlmostEqual(nudged_scores["rest"] - plain["rest"], NUDGE_TOP)
        self.assertEqual(len(logs.records), 1)

    def test_an_expedition_packs_more_food_while_its_thought_holds(self):
        self.assertEqual(pack_food(self.situation({})), PACK_FOOD)
        self.assertEqual(pack_food(self.situation({"pack": 3})), PACK_FOOD + PACK_MORE)
        with patch.object(expedition, "PACK_MORE", [lambda s: 100.0]):
            self.assertEqual(pack_food(self.situation({})), PACK_FOOD + PACK_MORE_TOP)


if __name__ == "__main__":
    unittest.main()

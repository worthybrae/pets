import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival import curiosity
from backend.survival.brain import BRAIN, observe_step
from backend.survival.curiosity import (
    CLOCK_HOUR, NEW_BIOME, NEW_BLOCK, NEW_CREATURE, NEW_GROUND, NEW_PLACE, START, curiosity_state, curiosity_view,
    lift, note_discoveries, tend_curiosity, time_to_wander,
)
from backend.survival.goals import GOALS, URGES, Goal, adopt_goal, goal_state
from backend.survival.hatch import hatch
from backend.survival.memory import known, mark_explored
from backend.survival.once import forget_logged
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.trips import REASONS
from backend.tests.test_survival_life_goals import built

BORN = 1_000_000.0
DAY = 3600.0


class Creatures:
    """A herd that only answers who is near."""

    def __init__(self, *kinds):
        self.kinds = kinds

    def near(self, x, z, reach):
        return [{"kind": kind, "state": {}} for kind in self.kinds]


class CuriosityTests(unittest.TestCase):
    def setUp(self):
        self.world = built()
        self.state = self.world.state
        self.context = self.world.context()
        self.context.events = []

    def value(self):
        return self.state["brain"]["curiosity"]["value"]

    def test_it_grows_on_known_ground_and_faster_once_needs_are_met(self):
        tend_curiosity(self.state, self.context, 0.0)  # a newborn's, at START; the home biome is known
        self.assertEqual(self.value(), START)
        self.assertEqual(len(known(self.world.db, "biome")), 1)
        self.state["vitals"]["hunger"] = 30.0  # hungry: needs not met
        tend_curiosity(self.state, self.context, 3 * CLOCK_HOUR)
        self.assertEqual(self.value(), START + 6.0)  # 2 an hour of the clock
        self.state["vitals"]["hunger"] = 100.0  # fed, rested, warm, well, with a home it built
        tend_curiosity(self.state, self.context, 5 * CLOCK_HOUR)
        self.assertEqual(self.value(), START + 12.0)  # 3 an hour
        tend_curiosity(self.state, self.context, 2 * DAY)
        self.assertEqual(self.value(), 100.0)

    def test_discoveries_lower_it_and_are_remembered(self):
        tend_curiosity(self.state, self.context, 0.0)
        curiosity_state(self.state, 0.0)["value"] = 90.0
        self.state["brain"]["new_ground_at"] = 5.0
        with patch("backend.survival.curiosity.biome_at", lambda x, z, seed: "taiga"):
            note_discoveries(self.state, {"kind": "mine", "block": "gravel"}, self.context, 5.0,
                             [(5.0, "found", "Pip spotted iron ore."), (5.0, "plan", "")])
        self.assertEqual(self.value(), 90.0 - NEW_PLACE - NEW_GROUND - NEW_BIOME - NEW_BLOCK)
        self.assertEqual(self.context.events, [(5.0, "found", "Pip saw the taiga for the first time.")])
        self.assertIn("gravel", known(self.world.db, "block"))
        self.assertEqual({key: self.state["brain"]["curiosity"][key] for key in ("new_at", "noticed_at", "seen")},
                         {"new_at": 5.0, "noticed_at": 5.0, "seen": 1})
        self.state["brain"]["new_ground_at"] = 9.0  # new ground alone: a discovery, but not a notable one
        note_discoveries(self.state, {"kind": "walk"}, self.context, 9.0, [])
        self.assertEqual({key: self.state["brain"]["curiosity"][key] for key in ("new_at", "noticed_at", "seen")},
                         {"new_at": 9.0, "noticed_at": 5.0, "seen": 2})

    def test_creatures_in_sight_are_met_once_a_game_minute(self):
        tend_curiosity(self.state, self.context, 0.0)
        self.world.grid.herd = Creatures("sheep", "cow")
        tend_curiosity(self.state, self.context, 30.0)  # looked over at 0.0 already
        self.assertEqual(known(self.world.db, "creature"), [])
        tend_curiosity(self.state, self.context, 61.0)
        self.assertEqual(sorted(known(self.world.db, "creature")), ["cow", "sheep"])
        self.assertEqual([text for _, _, text in self.context.events],
                         ["Pip met its first cow.", "Pip met its first sheep."])
        self.assertAlmostEqual(self.value(), START + 61.0 / CLOCK_HOUR * 3.0 - 2 * NEW_CREATURE)

    def test_high_curiosity_lifts_explore_makes_it_a_need_and_is_a_reason_to_wander(self):
        tend_curiosity(self.state, self.context, 0.0)
        self.state["inventory"] = {"berries": 4}  # (the final fix wave: no food trip, whose need is its own)
        levels = ((10.0, 0.0, False), (50.0, 0.0, False), (65.0, 9.0, False), (90.0, 24.0, True))
        for value, lifted, urge in levels:
            curiosity_state(self.state, 0.0)["value"] = value
            s = self.world.situation()
            self.assertEqual((lift(s), URGES["explore"](s)), (lifted, urge))
        self.assertEqual(REASONS["wander"].wanted(self.world.situation()), "I feel very restless; nothing new yet")
        curiosity_state(self.state, 0.0)["value"] = 10.0  # content, but there is always something new to see
        self.assertEqual(REASONS["wander"].wanted(self.world.situation()), "there is always more to see")
        del self.state["brain"]["curiosity"]
        self.assertIsNone(REASONS["wander"].wanted(self.world.situation()))  # not before the tick tends it

    def test_the_lift_is_zero_while_hungry_or_tired_even_at_max_curiosity(self):
        # Fix round 2: the SURVIVAL_FLOOR cap (purposes.explore_score) only stops the lift once eat
        # or sleep already score above 80 -- at hunger 20-28 or energy 20-29 explore still won
        # 49-100% of the time. Zeroing the lift itself while a real need is more urgent fixes it at
        # the source, whatever explore's own reason score is.
        tend_curiosity(self.state, self.context, 0.0)
        curiosity_state(self.state, 0.0)["value"] = 100.0
        self.assertEqual(lift(self.world.situation()), 30.0)  # fed and rested: the full lift
        self.state["vitals"]["hunger"] = 25.0
        self.assertEqual(lift(self.world.situation()), 0.0)
        self.state["vitals"]["hunger"] = 100.0
        self.state["vitals"]["energy"] = 25.0
        self.assertEqual(lift(self.world.situation()), 0.0)

    def test_eat_and_sleep_outrank_explore_at_hunger_and_energy_25(self):
        # Fix round 2's own repro of the reviewer's numbers: hunger 25 (eat 75) and energy 25
        # (sleep 75), curiosity maxed, real reasons and real scores throughout (no mocked lift).
        tend_curiosity(self.state, self.context, 0.0)
        curiosity_state(self.state, 0.0)["value"] = 100.0
        self.state["inventory"]["berries"] = 20  # carrying enough that the "food" trip is not wanted
        self.state["vitals"]["hunger"] = 25.0
        s = self.world.situation()
        self.assertGreater(PURPOSES["eat"].score(s), PURPOSES["explore"].score(s))
        self.state["vitals"]["hunger"] = 100.0
        self.state["vitals"]["energy"] = 25.0
        s = self.world.situation()
        self.assertGreater(PURPOSES["sleep"].score(s), PURPOSES["explore"].score(s))

    def test_the_model_and_the_viewer_are_told_how_it_feels(self):
        brain = {"curiosity": {"value": 80.0, "new_at": 0.0}}
        self.assertEqual(curiosity_view(brain, 2 * CLOCK_HOUR + 5.0, 1.0),
                         {"level": 80, "feeling": "restless; nothing new for 2 hours"})
        self.assertEqual(curiosity_view(brain, 3 * DAY, 1.0)["feeling"], "restless; nothing new for 3 game days")
        self.assertEqual(curiosity_view({"curiosity": {"value": 10.0, "new_at": 0.0}}, 5.0, 1.0)["feeling"],
                         "content; just saw something new")
        self.assertIsNone(curiosity_view({}, 5.0, 1.0))

    def test_once_needs_are_met_the_day_sets_time_aside_to_wander_until_a_discovery(self):
        tend_curiosity(self.state, self.context, 0.0)
        adopt_goal(self.state, "iron_tools", "utility", "", 0.0)
        goal = goal_state(self.state)["goal"]
        self.assertEqual(time_to_wander(self.world.situation(), GOALS["iron_tools"]),
                         {"text": "Take time to wander and see something new", "kind": "wander"})
        wandering = Goal("wandering", "Wandering", "", GOALS["iron_tools"].milestones, score=lambda s: 1.0, thought="",
                         repeat=True)
        self.assertIsNone(time_to_wander(self.world.situation(), wandering))  # a discovery goal wanders already
        goal["plan"] = [{"text": "Take time to wander and see something new", "kind": "wander", "done": False,
                         "step": None}]
        curiosity.discovered(self.state, 5.0, NEW_PLACE)
        self.assertTrue(goal["plan"][0]["done"])
        curiosity_state(self.state, 0.0)["value"] = 20.0
        self.assertIsNone(time_to_wander(self.world.situation(), GOALS["iron_tools"]))

    def test_an_old_saves_first_tend_learns_quietly_and_keeps_curiosity_at_start(self):
        # Fix round 1: a life curiosity did not exist for yet -- it already explored ground before
        # this tick (mark_explored, as the brain would have from every walk), already carries a
        # block kind, and already built with another (built()'s shelter is cobblestone). None of
        # that should announce a false "first" or cost curiosity, the way an upgraded save's first
        # tend used to.
        mark_explored(self.world.db, [(0, 0), (3, -2)], 0.0)
        self.world.grid.herd = Creatures("sheep")
        self.state["inventory"]["oak_log"] = 2
        tend_curiosity(self.state, self.context, 0.0)
        self.assertEqual(self.value(), START)
        self.assertEqual(self.context.events, [])
        self.assertIn("sheep", known(self.world.db, "creature"))
        self.assertIn("oak_log", known(self.world.db, "block"))
        self.assertIn("cobblestone", known(self.world.db, "block"))  # built with it, per structure_cells
        self.assertTrue(known(self.world.db, "biome"))

    def test_an_old_save_learns_the_creatures_it_saw_coming_or_fought_off_too(self):
        """L4a final fix wave, minor: one upgrade logged a false "met its first skitter" -- a kind
        Mimo had already seen coming at it (a "threat" event) or fought off (a "fight" event)."""
        db = self.world.db
        db.execute("CREATE TABLE mimo_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, "
                   "kind TEXT NOT NULL, text TEXT NOT NULL)")
        for kind, text in (("hunt", "Pip hunted a sheep."), ("fish", "Pip caught a fish."),
                           ("threat", "Pip saw a skitter coming."), ("fight", "Pip fought off a gloomling."),
                           ("threat", "Pip saw a dragon coming."), ("fight", "Wren fought off a cow.")):
            db.execute("INSERT INTO mimo_events(at, kind, text) VALUES (0, ?, ?)", (kind, text))
        self.assertEqual(curiosity.past_creatures(db, "Pip"), {"sheep", "fish", "skitter", "gloomling"})

    def test_a_crash_is_logged_once_and_the_tick_goes_on(self):
        forget_logged()
        with patch("backend.survival.curiosity.needs_met", side_effect=RuntimeError("boom")), \
                self.assertLogs("backend.survival.curiosity", level="ERROR") as logs:
            tend_curiosity(self.state, self.context, 0.0)
            tend_curiosity(self.state, self.context, 5.0)
        self.assertEqual(len(logs.output), 1)


class BrainTests(unittest.TestCase):
    def test_the_brain_tends_curiosity_after_each_vitals_step(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            hatch(registry, random.Random(8), timestamp=BORN)
            state = tick_life(registry, BORN + 1, scale=1.0, mind=BRAIN)
        self.assertIn(state["brain"]["curiosity"]["value"], (START, START - NEW_GROUND))  # it may walk new ground

    def test_observe_step_wires_note_discoveries_into_a_finished_step(self):
        # Fix round 1: unwiring note_discoveries from brain.observe_step still passed all 8
        # original curiosity tests, since every one of them called note_discoveries (or
        # tend_curiosity) directly. This one goes through the real wiring: a finished mine step
        # with a block kind Mimo never dug before should be learned and counted.
        world = built()
        context = world.context()
        context.events = []
        tend_curiosity(world.state, context, 0.0)  # curiosity exists, at START
        seen_before = world.state["brain"]["curiosity"]["seen"]
        self.assertNotIn("iron_ore", known(world.db, "block"))
        observe_step(world.state, {"kind": "mine", "target": [1, 0, 1], "block": "iron_ore"}, context, 1.0)
        self.assertIn("iron_ore", known(world.db, "block"))
        self.assertGreater(world.state["brain"]["curiosity"]["seen"], seen_before)


if __name__ == "__main__":
    unittest.main()

import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every purpose, goal and creature registered)
from backend.survival import minding  # noqa: F401  (reflection, its asides and nightly hook registered)
from backend.survival.choosing import Choice, Chooser, InlineExecutor, prepare, prepare_goal, store_goal
from backend.survival.clock import DAY_SECONDS
from backend.survival.goals import ask_for_goal
from backend.survival.hatch import hatch
from backend.survival.insights import NUDGE_DAYS, THOUGHT_REST, insights, think
from backend.survival.mind import add_memory, mind_state
from backend.survival.models import ModelError
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.talker import run_chores
from backend.survival.triggers import mark_trigger
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state
from backend.tests.test_survival_talker import FakeJev

BORN = 1_000_000.0
JEV = {"TYPESAFE_API_KEY": "k"}
DUSK = 2230.0
NIGHT = 2500.0


def at(day, seconds):
    return BORN + (day - 1) * DAY_SECONDS + seconds


class ReflectionTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))

    def tearDown(self):
        self.directory.cleanup()

    def remember(self, day, seconds, source, text, about=(), count=1, kind="episode", importance=3):
        with self.world.transaction() as db:
            return add_memory(db, at(day, seconds), day, kind, text, about, importance, 0, source, count)

    def a_week(self):
        """Two trips home hungry, two blows from skitters at night, a lot of fishing and evening visits."""
        for day in (2, 3):
            self.remember(day, 400, "expedition", "I set out on an expedition to the east.", importance=7)
            self.remember(day, 900, "hungry", "I got hungry.", importance=2)
            self.remember(day, 1000, "fish", "I caught 2 fish.", count=2, importance=2)
            self.remember(day, NIGHT, "hurt", "I was hit by a skitter.", ("skitter",), importance=4)
            self.remember(day, DUSK + 20, "hello", "You said hello to me.", ("owner",))
        self.remember(3, DUSK + 40, "care", "You gave me a snack.", ("owner",), importance=5)

    def keys(self, day=3):
        with self.world.connect() as db:
            return [insight.key for insight in insights(db, read_state(db), day, 1.0)]

    def thoughts(self):
        with self.world.connect() as db:
            return [tuple(row) for row in db.execute("SELECT game_day, text, source, importance, strength "
                                                     "FROM mind_memories WHERE kind='thought' ORDER BY id")]

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def test_the_rules_find_insights_in_what_mimo_remembers(self):
        self.assertEqual(self.keys(), [])
        self.a_week()
        self.assertEqual(self.keys(), ["hungry_trips", "wary:skitter", "evenings"])
        self.remember(3, 1100, "fish", "I caught 3 fish.", count=3, importance=2)
        self.remember(3, 1500, "near_death", "I nearly died.", importance=9)
        self.assertEqual(self.keys(), ["careful", "hungry_trips", "wary:skitter", "likes:fish", "evenings"])
        with self.world.connect() as db:
            texts = {insight.key: insight.text for insight in insights(db, read_state(db), 3, 1.0)}
        self.assertEqual(texts["hungry_trips"], "I keep coming home hungry from long trips. I should pack more food.")
        self.assertEqual(texts["wary:skitter"], "Skitters come out near the caves at night.")
        self.assertEqual(texts["likes:fish"], "I love fishing by the lake.")
        self.assertEqual(texts["evenings"], "You visit me in the evenings.")

    def test_a_thought_is_kept_once_strengthened_when_had_again_and_rests_before_it_is_offered_again(self):
        self.a_week()
        with self.world.transaction() as db:
            state = read_state(db)
            found = insights(db, state, 3, 1.0)
            think(db, state, found[0], 3, at(3, NIGHT))
            write_state(db, state)
        self.assertEqual(self.thoughts(), [(3, found[0].text, "hungry_trips", 7, 1.0)])
        self.assertEqual(self.world.state()["mind"]["nudges"], {"pack": 3 + NUDGE_DAYS})
        self.assertNotIn("hungry_trips", self.keys(3 + THOUGHT_REST - 1))
        with self.world.transaction() as db:
            state = read_state(db)
            think(db, state, found[0], 9, at(9, NIGHT))
            write_state(db, state)
        self.assertEqual(self.thoughts(), [(9, found[0].text, "hungry_trips", 7, 2.0)])

    def test_jev_reflects_at_dusk_in_the_purpose_call_it_already_makes(self):
        self.a_week()
        self.edit(lambda state: mark_trigger(state, "dusk", at(3, DUSK)))
        picks = {"thought": "wary:skitter", "another_thought": "hungry_trips"}
        jev = FakeJev(lambda name, criteria: picks.get(name, "rest" if "rest" in criteria else sorted(criteria)[0]))
        Chooser(env=JEV, http=jev, executor=InlineExecutor(), rng=random.Random(1), scale=1.0).poll(
            self.registry, at(3, DUSK + 5))
        [body] = jev.bodies
        self.assertLessEqual({"purpose", "thought", "another_thought"}, set(body["questions"]))
        self.assertEqual(set(body["questions"]["thought"]["criteria"]),
                         {"none", "hungry_trips", "wary:skitter", "evenings"})
        self.assertEqual([thought[2] for thought in self.thoughts()], ["wary:skitter", "hungry_trips"])
        mind = self.world.state()["mind"]
        self.assertEqual((mind["reflected"], mind["nudges"]),
                         (3, {"wary:skitter": 3 + NUDGE_DAYS, "pack": 3 + NUDGE_DAYS}))
        self.edit(lambda state: mark_trigger(state, "hello", at(3, DUSK + 100)))  # once a game day
        ask = prepare(SurvivalWorld(self.world.path, read_only=True), at(3, DUSK + 100), 1.0, JEV)
        self.assertEqual(ask.asides, ())

    def test_jev_may_keep_nothing_or_one_thought_twice(self):
        self.a_week()
        self.edit(lambda state: mark_trigger(state, "dusk", at(3, DUSK)))
        jev = FakeJev(lambda name, criteria: "evenings" if "thought" in name else sorted(criteria)[0])
        Chooser(env=JEV, http=jev, executor=InlineExecutor(), rng=random.Random(1), scale=1.0).poll(
            self.registry, at(3, DUSK + 5))
        self.assertEqual([thought[2] for thought in self.thoughts()], ["evenings"])

    def test_a_failed_call_or_no_jev_leaves_the_day_to_the_nights_rules(self):
        self.a_week()
        self.edit(lambda state: mark_trigger(state, "dusk", at(3, DUSK)))
        with self.assertLogs("backend.survival.choosing", level="ERROR"):
            Chooser(env=JEV, http=FakeJev(error=ModelError("down")), executor=InlineExecutor(), rng=random.Random(1),
                    scale=1.0).poll(self.registry, at(3, DUSK + 5))
        self.assertEqual((self.thoughts(), mind_state(self.world.state())["reflected"]), ([], 0))

    def test_without_jev_the_night_keeps_the_top_insight_every_other_day(self):
        self.a_week()
        name = self.life["name"]
        for day in range(1, 6):
            with self.world.transaction() as db:
                log_event(db, at(day, NIGHT), "sleep", f"{name} fell asleep.")
            run_chores(self.world, at(day, NIGHT + 1), 1.0)
        self.assertEqual([(thought[0], thought[2]) for thought in self.thoughts()], [(2, "hungry_trips"),
                                                                                     (4, "wary:skitter")])
        self.assertEqual(mind_state(self.world.state())["reflected"], 5)

    def test_the_goal_choice_is_shown_the_most_relevant_thoughts_and_they_grow_stronger(self):
        for day, text, source in ((1, "I love fishing by the lake.", "likes:fish"),
                                  (1, "You visit me in the evenings.", "evenings"),
                                  (2, "I keep coming home hungry from long trips. I should pack more food.",
                                   "hungry_trips"),
                                  (2, "Home feels safe. I love my own little house.", "home")):
            self.remember(day, 500, source, text, kind="thought", importance=7)
        self.edit(lambda state: ask_for_goal(state, "no_goal", at(2, 600)))
        ask = prepare_goal(SurvivalWorld(self.world.path, read_only=True), at(2, 700), 1.0, JEV)
        self.assertEqual(len(ask.payload["thoughts"]), 3)
        self.assertEqual(len(ask.recalled), 3)
        calls = {"model": 0, "luna": 0, "reflections": 0}
        store_goal(self.world, ask, Choice(ask.options[0].name, "utility", "", calls), at(2, 710))
        with self.world.connect() as db:
            strong = [row[0] for row in db.execute("SELECT id FROM mind_memories WHERE strength = 2 ORDER BY id")]
        self.assertEqual(sorted(strong), sorted(ask.recalled))


if __name__ == "__main__":
    unittest.main()

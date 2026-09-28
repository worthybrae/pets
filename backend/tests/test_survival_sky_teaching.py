"""W2: the seven weather and season lessons: each taught in one sentence, the doubted lines doubted, and a gentle
pet granted W1's lessons granted W2's on its next tick, quietly."""

import random
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every lesson registered)
from backend.survival import minding  # noqa: F401  (the chat's "teach" question)
from backend.survival.brain import BRAIN
from backend.survival.hatch import hatch
from backend.survival.journal import LESSONS
from backend.survival.lessons import claims, named
from backend.survival.memory import know
from backend.survival.registry import LifeRegistry
from backend.survival.tick import tick_life
from backend.survival.wild import BORN_KNOWING, BY_NAME, GRANTED, SURVIVAL, survival_view, thing
from backend.survival.world import SurvivalWorld, read_state, write_state

BORN = 1_000_000.0
W2 = ("winter", "cloak", "hearth", "smoking", "rain", "storm", "fog")
# The spec's owner lines for W2's lessons (the teaching test table), and the lines doubted.
TEACHES = {"winter": "Fill a chest with food before winter.", "cloak": "Five wool make a wool cloak.",
           "hearth": "A stone hearth keeps the home warm.", "smoking": "Smoked meat keeps all winter.",
           "rain": "Rain puts out a fire under the open sky.", "storm": "In a storm stay low and inside.",
           "fog": "Stay close to home in the fog."}
DOUBTED = ("Six wool make a wool cloak.", "Lightning is harmless.", "Fog is safe.")


class TeachingTests(unittest.TestCase):
    def test_the_seven_lessons_follow_w1s_and_each_fact_says_no_negation(self):
        self.assertEqual(tuple(lesson.name for lesson in SURVIVAL[-7:]), W2)
        self.assertEqual(GRANTED, 2)
        for name in W2:
            self.assertEqual(LESSONS[thing(name)].kind, "survival")
            self.assertEqual(named(LESSONS[thing(name)]), name)
            self.assertFalse({"not", "no", "never", "don't"} & set(BY_NAME[name].fact.lower().split()))

    def test_every_owner_line_teaches_its_lesson_and_nothing_else(self):
        for name, text in TEACHES.items():
            self.assertEqual(claims(text).taught, (thing(name),), text)
            self.assertFalse(claims(text).doubtful, text)

    def test_the_doubted_lines_are_doubted(self):
        for text in DOUBTED:
            found = claims(text)
            self.assertEqual((found.taught, found.doubtful), ((), True), text)


class GrantTests(unittest.TestCase):
    def test_a_gentle_pet_granted_w1s_lessons_is_granted_w2s_on_its_next_tick_quietly(self):
        with tempfile.TemporaryDirectory() as root:
            registry = LifeRegistry(Path(root) / "data", Path(root) / "no-legacy.sqlite3")
            life = hatch(registry, random.Random(8), timestamp=BORN)
            world = SurvivalWorld(registry.world_path(life))
            with world.transaction() as db:
                state = read_state(db)
                state["wild"] = {"granted": 1}  # a world W1 granted
                for lesson in SURVIVAL[:11]:
                    know(db, thing(lesson.name), "lesson", BORN)
                    know(db, thing(lesson.name), BORN_KNOWING, BORN)
                write_state(db, state)
            tick_life(registry, BORN + 1, scale=1.0, mind=BRAIN)
            self.assertEqual(world.state()["wild"]["granted"], GRANTED)
            with world.connect() as db:
                view = {entry["name"]: entry for entry in survival_view(db)}
                memories = db.execute("SELECT COUNT(*) FROM mind_memories").fetchone()[0]
            self.assertTrue(all(view[name]["known"] and view[name]["source"] == "from_start" for name in W2))
            self.assertEqual(memories, 0)
            self.assertFalse(any(event["kind"] in ("learned", "figured") for event in world.events(100)))


if __name__ == "__main__":
    unittest.main()

import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend.survival.brain  # noqa: F401  (every creature, recipe and goal registered, for the tags)
from backend.survival import minding  # noqa: F401  (the mirror and the moments registered)
from backend.survival.clock import DAY_SECONDS
from backend.survival.episodes import AGAIN, FOLLOWERS, voice
from backend.survival.events import MIRROR_BATCH
from backend.survival.hatch import hatch
from backend.survival.once import forget_logged
from backend.survival.owner_facts import remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.talker import Talker, run_chores
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0


class MirrorTests(unittest.TestCase):
    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.life = hatch(self.registry, random.Random(8), timestamp=BORN)
        self.world = SurvivalWorld(self.registry.world_path(self.life))
        self.name = self.life["name"]

    def tearDown(self):
        self.directory.cleanup()

    def log(self, *events):
        with self.world.transaction() as db:
            for at, kind, text in events:
                log_event(db, at, kind, text)

    def memories(self):
        """What the mirror remembered, without the gists sleep writes (backend.survival.consolidation)."""
        with self.world.connect() as db:
            return [dict(row) for row in db.execute("SELECT game_day, kind, text, about, importance, feeling, source "
                                                    "FROM mind_memories WHERE kind != 'gist' ORDER BY id")]

    def edit(self, change):
        with self.world.transaction() as db:
            state = read_state(db)
            change(state)
            write_state(db, state)

    def test_notable_events_become_memories_in_mimos_own_voice(self):
        name = self.name
        self.log((BORN + 10, "found", f"{name} met its first skitter."),
                 (BORN + 20, "care", f"You gave {name} a snack."),
                 (BORN + 30, "purpose", f'{name} decided to gather wood. "Wood first."'),
                 (BORN + 40, "craft", f"{name} crafted planks."),
                 (BORN + 50, "plan", f"{name}'s plan for today: gather wood."),
                 (BORN + 60, "plan", f'{name} set a new goal: iron tools. "I want iron tools."'),
                 (BORN + 70, "grow", "A sapling grew into a tree."),
                 (BORN + DAY_SECONDS + 5, "learned", f"{name} learned that gravel sometimes hides flint."),
                 (BORN + DAY_SECONDS + 6, "built", f"{name} finished building {name}'s Snug Cabin and moved in."))
        run_chores(self.world, BORN + DAY_SECONDS + 10, 1.0)
        self.assertEqual(self.memories(), [
            {"game_day": 1, "kind": "episode", "text": "I hatched into a brand-new world.", "about": "",
             "importance": 8, "feeling": 2, "source": "birth"},
            {"game_day": 1, "kind": "episode", "text": "I met my first skitter.", "about": "skitter",
             "importance": 6, "feeling": 1, "source": "found"},
            {"game_day": 1, "kind": "episode", "text": "You gave me a snack.", "about": "owner snack",
             "importance": 5, "feeling": 2, "source": "care"},
            {"game_day": 1, "kind": "episode", "text": "I set a new goal: iron tools.",  # the quoted thought left out
             "about": "iron_tool iron tool", "importance": 4, "feeling": 1, "source": "plan"},
            {"game_day": 2, "kind": "lesson", "text": "I learned that gravel sometimes hides flint.",
             "about": "gravel hide flint", "importance": 5, "feeling": 1, "source": "learned"},
            {"game_day": 2, "kind": "episode", "text": "I finished building my Snug Cabin and moved in.",
             "about": "", "importance": 7, "feeling": 2, "source": "built"},
        ])

    def test_the_computer_that_counts_its_days_is_a_moment_it_remembers(self):
        """The Making final fix wave, M2: MOMENTS had no "computer" kind, so the headline moment never became a
        memory (only "I built Pip's computer." did, through "built")."""
        self.log((BORN + 10, "computer", f"{self.name} built a machine that remembers how long it has been alive!"))
        run_chores(self.world, BORN + 20, 1.0)
        (moment,) = [memory for memory in self.memories() if memory["source"] == "computer"]
        self.assertEqual((moment["text"], moment["importance"], moment["feeling"]),
                         ("I built a machine that remembers how long I have been alive!", 8, 2))

    def test_a_plan_is_remembered_without_its_reason_or_its_quoted_thought(self):
        # Final fix wave (I3): the bracket was voiced wrongly ("(I cannot be done now)"), and the quote
        # tagged the plan with whatever the thought named, so it came back for "the gloomling?".
        self.log((BORN + 10, "plan", f"{self.name} set a goal aside for now: map the far hills (it cannot be done "
                                     "now)."),
                 (BORN + 20, "plan", f'{self.name} set a new goal: armor up. "Next time a gloomling swings at me, '
                                     'I\'ll be ready."'),
                 (BORN + 30, "plan", f"{self.name} gave up trying to look into a cave (it was too far)."))
        run_chores(self.world, BORN + 40, 1.0)
        plans = [(memory["text"], memory["about"]) for memory in self.memories() if memory["source"] == "plan"]
        self.assertEqual(plans, [("I set a goal aside for now: map the far hills.", "far_hill hill"),
                                 ("I set a new goal: armor up.", "armor"),
                                 ("I gave up trying to look into a cave.", "cave")])

    def test_a_find_it_did_not_know_is_said_in_mimos_own_voice(self):
        self.assertEqual(voice("Pip found water it did not know.", "Pip"), "I found water I did not know.")

    def test_a_goal_reached_again_or_another_camp_is_a_smaller_moment_that_fades(self):
        # Final fix wave (I4): the first reach matters for good (7); the same goal reached again is
        # remembered at AGAIN's 4, fades after some nine game days, and both days' gists still name it.
        name = self.name
        for day in (1, 2):
            self.log((BORN + (day - 1) * DAY_SECONDS + 100, "goal", f"{name} reached a goal: look into a cave."),
                     (BORN + (day - 1) * DAY_SECONDS + 200, "camp", f"{name} dug in for the night and made a camp."),
                     (BORN + (day - 1) * DAY_SECONDS + 2500, "sleep", f"{name} fell asleep."))
            run_chores(self.world, BORN + (day - 1) * DAY_SECONDS + 2600, 1.0)
        again = [(memory["game_day"], memory["source"], memory["importance"]) for memory in self.memories()
                 if memory["source"] in AGAIN]
        self.assertEqual(again, [(1, "goal", 7), (1, "camp", 6), (2, "goal", 4), (2, "camp", 4)])
        with self.world.connect() as db:
            gists = [row[0] for row in db.execute("SELECT text FROM mind_memories WHERE kind='gist' ORDER BY id")]
        self.assertEqual(gists, ["Day 1: hatched into a brand-new world, managed to look into a cave and dug in for "
                                 "the night and made a camp.",
                                 "Day 2: managed to look into a cave and dug in for the night and made a camp."])
        for day in range(3, 14):
            self.log((BORN + (day - 1) * DAY_SECONDS + 2500, "sleep", f"{name} fell asleep."))
            run_chores(self.world, BORN + (day - 1) * DAY_SECONDS + 2600, 1.0)
            left = [memory["game_day"] for memory in self.memories() if memory["source"] == "goal"]
            self.assertEqual(left, [1, 2] if day <= 11 else [1], day)  # 4 x 1 x 3 / (3 + 10 days) < 1

    def test_the_mirror_reads_the_whole_log_a_batch_at_a_time_and_never_twice(self):
        self.log(*((BORN + number, "ate", f"{self.name} ate apple.") for number in range(1, 2 * MIRROR_BATCH + 50)))
        run_chores(self.world, BORN + 5000, 1.0)
        self.assertEqual(len(self.memories()), MIRROR_BATCH)  # the birth and 199 meals
        run_chores(self.world, BORN + 5001, 1.0)
        run_chores(self.world, BORN + 5002, 1.0)
        run_chores(self.world, BORN + 5003, 1.0)
        self.assertEqual(len(self.memories()), 2 * MIRROR_BATCH + 50)
        with self.world.connect() as db:
            newest = db.execute("SELECT MAX(id) FROM mimo_events").fetchone()[0]
        self.assertEqual(self.world.state()["mirrored"]["memory"], newest)

    def test_a_long_life_from_before_mind_is_remembered_back_to_backfill_events(self):
        # Pebble on day 55: the mirrors start Mind's memory at the newest event; it goes back BACKFILL
        # events (here 50) and catches up a batch a chore, so it starts with its past, bounded.
        self.log(*((BORN + number, "ate", f"{self.name} ate apple {number}.") for number in range(1, 120)))
        with patch("backend.survival.episodes.BACKFILL", 50):
            run_chores(self.world, BORN + 5000, 1.0)
        texts = [memory["text"] for memory in self.memories()]
        self.assertEqual((len(texts), texts[0], texts[-1]), (50, "I ate apple 70.", "I ate apple 119."))

    def test_a_writer_that_crashes_is_rolled_back_alone_and_logged_once(self):
        def broken(db, state, event, now, scale):
            db.execute("INSERT INTO mind_memories(at, game_day, kind, text, importance) "
                       "VALUES (0, 1, 'episode', 'x', 1)")
            raise RuntimeError("boom")
        self.log((BORN + 1, "found", f"{self.name} met its first cow."),
                 (BORN + 2, "found", f"{self.name} met its first sheep."))
        with patch.dict(FOLLOWERS, {"found": [broken, *FOLLOWERS["found"]]}):
            with self.assertLogs("backend.survival.episodes", level="ERROR") as logs:
                run_chores(self.world, BORN + 10, 1.0)
        self.assertEqual([memory["text"] for memory in self.memories()],
                         ["I hatched into a brand-new world.", "I met my first cow.", "I met my first sheep."])
        self.assertEqual(len(logs.records), 1)

    def test_nearly_dying_is_remembered_once_a_game_day(self):
        def hurt(state):
            state["vitals"]["health"] = 9.0
            state.update(hurt_at=BORN + 100, hurt_by="gloomling")
        self.edit(hurt)
        run_chores(self.world, BORN + 101, 1.0)
        run_chores(self.world, BORN + 200, 1.0)
        self.edit(lambda state: state.update(hurt_at=None, hurt_by=None))
        run_chores(self.world, BORN + DAY_SECONDS + 1, 1.0)
        near = [memory for memory in self.memories() if memory["source"] == "near_death"]
        self.assertEqual([(memory["game_day"], memory["text"], memory["importance"]) for memory in near],
                         [(1, "I nearly died: a gloomling almost got me.", 9), (2, "I nearly died.", 9)])

    def test_what_the_owner_tells_about_themselves_is_a_told_memory_stronger_when_heard_again(self):
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN + 10)
            remember_fact(db, "likes", "watching you explore", BORN + 11)
            remember_fact(db, "about", "I work nights", BORN + 12)
            remember_fact(db, "name", "Sam", BORN + 13)  # heard again
        with self.world.connect() as db:
            told = [tuple(row) for row in db.execute("SELECT kind, text, about, importance, strength "
                                                     "FROM mind_memories WHERE source='owner_fact' ORDER BY id")]
        self.assertEqual(told, [("told", "You told me your name is Sam.", "owner", 6, 2.0),
                                ("told", "You told me you like watching me explore.", "owner", 6, 1.0),
                                ("told", "You told me you work nights.", "owner night", 6, 1.0)])

    def test_the_workers_talker_runs_the_mirror_and_a_dead_pet_remembers_nothing_new(self):
        talker = Talker(env={}, scale=1.0)
        self.log((BORN + 1, "found", f"{self.name} met its first cow."))
        talker.poll(self.registry, BORN + 2)
        self.assertEqual(len(self.memories()), 2)
        self.log((BORN + 3, "found", f"{self.name} met its first sheep."))
        self.edit(lambda state: state.update(died_at=BORN + 4))
        talker.poll(self.registry, BORN + 20)
        self.assertEqual(len(self.memories()), 2)
        talker.close()


if __name__ == "__main__":
    unittest.main()

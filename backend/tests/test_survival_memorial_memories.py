import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api.lives import get_life, hatch_egg
from backend.api.mimo import get_mimo
from backend.services.live_mimo import MimoStore
from backend.survival import mind
from backend.survival.clock import DAY_SECONDS
from backend.survival.mind import add_memory, life_memories
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, read_state, write_state


class MemorialMemoriesTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        MimoStore(root / "mimo.sqlite3")
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "mimo.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def a_life_that_ended(self):
        born = hatch_egg()["life"]["born_at"]
        registry = LifeRegistry()
        life = registry.active_life()
        world = SurvivalWorld(registry.world_path(life))
        with world.transaction() as db:
            for day in (1, 2, 3):
                add_memory(db, born + day * DAY_SECONDS - 100, day, "gist", f"Day {day}: a good day.", (), 5)
            add_memory(db, born + 100, 1, "episode", "I met my first cow.", (), 6)
            add_memory(db, born + 2 * DAY_SECONDS, 2, "thought", "I love fishing by the lake.", (), 7)
            add_memory(db, born + DAY_SECONDS, 1, "thought", "You visit me in the evenings.", (), 7)
            state = read_state(db)
            state.update(died_at=born + 3 * DAY_SECONDS, cause="starvation", status="dead")
            write_state(db, state)
        registry.mark_dead(life["id"], born + 3 * DAY_SECONDS, "starvation")
        return life, world

    def test_the_memorial_lists_the_lifes_gists_and_thoughts_oldest_first(self):
        life, world = self.a_life_that_ended()
        memories = get_mimo()["last_life"]["memories"]
        self.assertEqual([item["text"] for item in memories["gists"]],
                         ["Day 1: a good day.", "Day 2: a good day.", "Day 3: a good day."])
        self.assertEqual([item["text"] for item in memories["thoughts"]],
                         ["You visit me in the evenings.", "I love fishing by the lake."])
        self.assertEqual(get_life(life["id"])["memories"], memories)
        self.assertEqual(get_life(1)["memories"], {"gists": [], "thoughts": []})  # the legacy life
        with patch.object(mind, "MEMORIAL_GISTS", 2):
            self.assertEqual([item["day"] for item in life_memories(world)["gists"]], [2, 3])

    def test_an_archive_from_before_mind_remembers_nothing(self):
        life, world = self.a_life_that_ended()
        raw = sqlite3.connect(world.path)
        raw.execute("DROP TABLE mind_memories")
        raw.commit()
        raw.close()
        self.assertEqual(life_memories(SurvivalWorld(world.path, read_only=True)), {"gists": [], "thoughts": []})


if __name__ == "__main__":
    unittest.main()

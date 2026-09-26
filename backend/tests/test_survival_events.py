import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.survival.choosing import InlineExecutor
from backend.survival.events import CURSORS, MIRRORS, mirror, mirror_events
from backend.survival.hatch import hatch
from backend.survival.memory import know, known
from backend.survival.once import forget_logged
from backend.survival.registry import LifeRegistry
from backend.survival.talker import CHORES, Talker
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0


class EventMirrorTests(unittest.TestCase):
    """Mind hook R7: the event log's mirrors, {kind: [writers]} with one cursor a consumer."""

    def setUp(self):
        forget_logged()
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        self.world = SurvivalWorld(self.registry.world_path(hatch(self.registry, random.Random(8), timestamp=BORN)))
        self.mirrors = patch.dict(MIRRORS, clear=True)
        self.mirrors.start()
        self.seen = []

    def tearDown(self):
        self.mirrors.stop()
        self.directory.cleanup()

    def log(self, *events):
        with self.world.transaction() as db:
            for kind, text in events:
                log_event(db, BORN + 1, kind, text)

    def run_mirrors(self):
        with self.world.transaction() as db:
            state = read_state(db)
            changed = mirror_events(db, state, BORN + 10, 1.0)
            if changed:
                write_state(db, state)
            return changed, state

    def writer(self, consumer):
        def write(db, state, event, now, scale):
            self.seen.append((consumer, event["kind"], event["text"]))
        return write

    def test_nothing_happens_while_no_one_follows_the_log(self):
        self.log(("found", "Pip met its first skitter."))
        changed, state = self.run_mirrors()
        self.assertFalse(changed)
        self.assertNotIn(CURSORS, state)

    def test_each_consumer_follows_its_kinds_from_the_newest_event_with_a_cursor_of_its_own(self):
        self.log(("found", "old news"))
        mirror("memory", "found", self.writer("memory"))
        mirror("memory", "goal", self.writer("memory"))
        mirror("inbox", "goal", self.writer("inbox"))
        self.run_mirrors()  # both start at the newest event: old news is never delivered
        self.log(("found", "Pip met its first skitter."), ("sleep", "Pip went to sleep."),
                 ("goal", "Pip reached a goal."))
        changed, state = self.run_mirrors()
        self.assertTrue(changed)
        self.assertEqual(self.seen, [("memory", "found", "Pip met its first skitter."),
                                     ("memory", "goal", "Pip reached a goal."),
                                     ("inbox", "goal", "Pip reached a goal.")])
        self.assertEqual(state[CURSORS]["memory"], state[CURSORS]["inbox"])
        self.seen.clear()
        mirror("diary", "goal", self.writer("diary"))  # a consumer that comes later starts at the newest too
        self.run_mirrors()
        self.log(("goal", "Pip set a new goal."))
        self.run_mirrors()
        self.assertEqual(sorted(self.seen), [("diary", "goal", "Pip set a new goal."),
                                             ("inbox", "goal", "Pip set a new goal."),
                                             ("memory", "goal", "Pip set a new goal.")])

    def test_registering_again_replaces_that_consumers_writer_for_the_kind(self):
        mirror("inbox", "goal", self.writer("inbox"))
        mirror("inbox", "goal", self.writer("promise"))
        mirror("memory", "goal", self.writer("memory"))
        self.assertEqual([entry.consumer for entry in MIRRORS["goal"]], ["inbox", "memory"])
        self.run_mirrors()
        self.log(("goal", "Pip reached a goal."))
        self.run_mirrors()
        self.assertEqual(self.seen, [("promise", "goal", "Pip reached a goal."),
                                     ("memory", "goal", "Pip reached a goal.")])

    def test_a_writer_that_crashes_is_rolled_back_logged_once_and_passed_over(self):
        def broken(db, state, event, now, scale):
            know(db, "half written", "test", now)
            state["half"] = True
            raise RuntimeError("boom")
        mirror("inbox", "found", broken)
        mirror("memory", "found", self.writer("memory"))
        self.run_mirrors()
        self.log(("found", "one"), ("found", "two"))
        with self.assertLogs("backend.survival.events", level="ERROR") as logs:
            changed, state = self.run_mirrors()
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(self.seen, [("memory", "found", "one"), ("memory", "found", "two")])
        self.assertNotIn("half", state)
        with self.world.connect() as db:
            self.assertEqual(known(db, "test"), [])
        self.assertEqual(state[CURSORS]["inbox"], state[CURSORS]["memory"])  # not retried: the inbox never stalls
        self.seen.clear()
        self.run_mirrors()
        self.assertEqual(self.seen, [])

    def test_a_consumer_ahead_of_another_is_never_given_an_event_twice(self):
        mirror("memory", "found", self.writer("memory"))
        self.run_mirrors()
        self.log(("found", "e1"))
        self.run_mirrors()
        del MIRRORS["found"][0]  # memory goes missing for a while (its module failed to import)...
        mirror("inbox", "found", self.writer("inbox"))  # ...while the inbox starts, at the newest event
        self.run_mirrors()
        self.log(*[("found", f"e{number}") for number in range(2, 7)])
        self.run_mirrors()  # the inbox sees e2 to e6; memory's cursor stays at e1
        mirror("memory", "found", self.writer("memory"))  # memory is back with a backlog; the inbox is ahead
        self.log(("found", "e7"))
        with patch("backend.survival.events.MIRROR_BATCH", 2):
            for _ in range(4):  # memory catches up two events a run, reading events the inbox saw already
                changed, state = self.run_mirrors()
        seen = {consumer: [text for who, _, text in self.seen if who == consumer] for consumer in ("memory", "inbox")}
        self.assertEqual(seen["memory"], [f"e{number}" for number in range(1, 8)])
        self.assertEqual(seen["inbox"], [f"e{number}" for number in range(2, 8)])  # each exactly once
        self.assertEqual(state[CURSORS]["memory"], state[CURSORS]["inbox"])

    def test_a_run_reads_at_most_a_batch_and_the_next_run_goes_on(self):
        mirror("memory", "found", self.writer("memory"))
        self.run_mirrors()
        self.log(*[("found", f"event {number}") for number in range(5)])
        with patch("backend.survival.events.MIRROR_BATCH", 2):
            self.run_mirrors()
            self.assertEqual(len(self.seen), 2)
            self.run_mirrors()
            self.run_mirrors()
        self.assertEqual([text for _, _, text in self.seen], [f"event {number}" for number in range(5)])

    def test_events_no_one_follows_are_not_delivered_and_the_cursor_catches_up_past_them(self):
        mirror("memory", "found", self.writer("memory"))
        self.run_mirrors()
        self.log(("sleep", "Pip went to sleep."), ("wake", "Pip woke up."))
        changed, state = self.run_mirrors()
        self.assertTrue(changed)  # fix round 1: the cursor still catches up, so this stretch is never rescanned
        self.assertEqual(self.seen, [])
        with self.world.connect() as db:
            self.assertEqual(state[CURSORS]["memory"], db.execute("SELECT MAX(id) FROM mimo_events").fetchone()[0])
        changed, state = self.run_mirrors()
        self.assertFalse(changed)  # already caught up: a second call with nothing new moves no cursor
        self.log(("found", "Pip met its first skitter."))
        changed, state = self.run_mirrors()
        self.assertTrue(changed)
        self.assertEqual(self.seen, [("memory", "found", "Pip met its first skitter.")])
        with self.world.connect() as db:
            self.assertEqual(state[CURSORS]["memory"], db.execute("SELECT MAX(id) FROM mimo_events").fetchone()[0])

    def test_a_long_unfollowed_stretch_is_passed_once_and_never_rescanned(self):
        """Fix round 1: `mirror_events` reads MAX(id) before its filtered SELECT, so a call that
        matches fewer than MIRROR_BATCH rows has read every followed event up to that id, and every
        consumer's cursor can catch up to it at once — a stretch nobody follows, however long, costs
        one pass, not one every chore. An index on mimo_events(kind, id) keeps that one pass cheap."""
        mirror("memory", "found", self.writer("memory"))
        self.run_mirrors()
        self.log(*[("sleep", f"tick {number}") for number in range(5000)], ("found", "Pip met its first skitter."))
        with self.world.connect() as db:
            plan = " ".join(row[3] for row in db.execute(
                "EXPLAIN QUERY PLAN SELECT id, at, kind, text FROM mimo_events WHERE id > ? AND kind IN (?) "
                "ORDER BY id LIMIT ?", (0, "found", 200)))
        self.assertIn("mimo_events_by_kind", plan)
        changed, state = self.run_mirrors()  # one call passes the whole stretch and delivers the one it follows
        self.assertTrue(changed)
        self.assertEqual(self.seen, [("memory", "found", "Pip met its first skitter.")])
        with self.world.connect() as db:
            newest = db.execute("SELECT MAX(id) FROM mimo_events").fetchone()[0]
        self.assertEqual(state[CURSORS]["memory"], newest)
        self.seen.clear()
        changed, state = self.run_mirrors()  # a second call: nothing new, so it reads nothing and moves no cursor
        self.assertFalse(changed)
        self.assertEqual(self.seen, [])
        self.assertEqual(state[CURSORS]["memory"], newest)

    def test_the_talker_runs_the_mirrors_as_its_first_chore(self):
        self.assertIs(CHORES[0], mirror_events)
        mirror("probe", "found", self.writer("probe"))  # Mind M1: not "memory", Mind's own consumer
        talker = Talker(env={}, executor_factory=InlineExecutor, scale=1.0)
        talker.poll(self.registry, BORN + 5)
        self.log(("found", "Pip met its first skitter."))
        talker.poll(self.registry, BORN + 60)
        self.assertEqual(self.seen, [("probe", "found", "Pip met its first skitter.")])


if __name__ == "__main__":
    unittest.main()

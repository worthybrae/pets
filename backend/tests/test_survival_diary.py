import json
import os
import random
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from backend.api.bond import ReadUpTo, get_diary, read_inbox
from backend.api.lives import hatch_egg
from backend.api.mimo import get_mimo
from backend.survival.bond import utc_day, visit
from backend.survival.choosing import InlineExecutor
from backend.survival.diary import (HIGHLIGHTS, STORY_LIMIT, clean_story, day_highlights, events_between,
                                    rules_story, since_then_story, story_due, story_job, story_lead, story_span)
from backend.survival.hatch import hatch
from backend.survival.inbox import post_item
from backend.survival.mind import add_memory
from backend.survival.models import ModelError
from backend.survival.once import forget_logged
from backend.survival.owner_facts import remember_fact
from backend.survival.registry import LifeRegistry
from backend.survival.snapshot import DIARY_SUMMARY, life_detail, life_summary
from backend.survival.talk import owner_says
from backend.survival.talker import Talker
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

BORN = 1_000_000.0
SCALE = 60.0  # a game day is a real minute
LUNA = {"MIMO_MODEL_API_KEY": "k", "MIMO_MODEL_URL": "https://luna.test/v1/chat/completions"}
STORY = "Day 1 was lovely. I built my hut. I found water too. I hope Sam comes back soon."
STORY_WITH_SINCE_THEN = ("I found a cave in the morning. Since then, I have explored every tunnel of it. "
                         "I hope Sam comes back.")


def sentences(text):
    return [part for part in re.split(r"(?<=[.!?])(?<!\.\.\.)\s+", text) if part]


def highlights_of(db, state, day, scale):
    """What `diary.highlights` did before fix round 1 removed it as dead code (item 8): one day's
    highlights, exactly as `story_job` still builds them, through the functions it actually calls."""
    return [text for _, text in day_highlights(events_between(db, state, day, day, scale), state)][:HIGHLIGHTS]


class FakeLuna:
    def __init__(self, story=STORY, error=None):
        self.story, self.error, self.bodies = story, error, []

    def __call__(self, url, headers, body, timeout):
        self.bodies.append(body)
        if self.error is not None:
            raise self.error
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"story": self.story})}}]}


class StoryRulesTests(unittest.TestCase):
    def test_a_story_is_due_at_the_first_dawn_after_a_visit_about_the_day_of_the_visit(self):
        state = {"born_at": BORN, "died_at": None}
        self.assertIsNone(story_due(state, BORN + 500, SCALE))  # the owner was never here
        visit(state, BORN + 10)  # game day 1
        self.assertIsNone(story_due(state, BORN + 59, SCALE))
        self.assertEqual(story_due(state, BORN + 61, SCALE), 1)
        self.assertEqual(story_due(state, BORN + 500, SCALE), 1)  # late, still about that day
        state["bond"]["storied"] = BORN + 10
        self.assertIsNone(story_due(state, BORN + 500, SCALE))  # once for that visit
        visit(state, BORN + 70)  # game day 2
        self.assertIsNone(story_due(state, BORN + 110, SCALE))
        self.assertEqual(story_due(state, BORN + 121, SCALE), 2)

    def test_the_template_covers_a_day_with_no_events_in_three_sentences(self):
        quiet = rules_story(4, [], "", "", 20.0)
        self.assertEqual(quiet, "Day 4 was a quiet one. I stayed close to home and kept safe. Maybe you'll visit tomorrow?")
        busy = rules_story(4, [], "gather wood", "Sam", 80.0)
        self.assertEqual(busy, "Day 4 was a quiet one. I spent most of it trying to gather wood. Come back soon, Sam, I missed you!")

    def test_luna_answers_are_kept_plain_and_short(self):
        self.assertEqual(clean_story("**Day 2.** I   ate. I slept."), "Day 2. I ate. I slept.")
        self.assertEqual(len(sentences(clean_story("One. Two. Three. Four. Five. Six. Seven. Eight."))), 6)
        with self.assertRaises(ModelError):
            clean_story("Just one sentence")
        with self.assertRaises(ModelError):
            clean_story(None)

    def test_since_then_only_lowercases_a_day_prefixed_highlight(self):
        """Fix round 1, item 4: "Since then, i'm ..." was a bug. Only a highlight that begins "On day"
        is lowercased to follow the comma; the goal-progress closer keeps its own capital "I"."""
        self.assertIn("Since then, on day 2, I reached",
                       since_then_story("Lead.", ["On day 2, I reached a goal: iron tools."]))
        self.assertIn("Since then, I'm 40% of the way",
                       since_then_story("Lead.", ["I'm 40% of the way to iron tools."]))


class StoryTests(unittest.TestCase):
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

    def visit(self, at):
        with self.world.transaction() as db:
            state = read_state(db)
            visit(state, at)
            write_state(db, state)

    def talker(self, env=None, http=None):
        return Talker(env=env or {}, http=http, executor_factory=InlineExecutor, scale=SCALE)

    def stories(self):
        with self.world.connect() as db:
            return [dict(row) for row in db.execute("SELECT id, text, data, read_at FROM mimo_inbox WHERE kind='story'")]

    def test_the_story_is_written_once_per_dawn_after_a_visit(self):
        talker = self.talker()
        self.visit(BORN + 10)
        talker.poll(self.registry, BORN + 30)
        self.assertEqual(self.stories(), [])
        talker.poll(self.registry, BORN + 61)
        talker.poll(self.registry, BORN + 62)
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "writer": "rules"})
        self.assertTrue(3 <= len(sentences(story["text"])) <= 6, story["text"])
        self.assertTrue(story["text"].startswith("Day 1 was"))
        self.visit(BORN + 70)
        talker.poll(self.registry, BORN + 110)
        self.assertEqual(len(self.stories()), 1)
        talker.poll(self.registry, BORN + 121)
        self.assertEqual([json.loads(story["data"])["day"] for story in self.stories()], [1, 2])

    def test_the_story_tells_the_days_highlights_in_mimos_words(self):
        with self.world.transaction() as db:
            remember_fact(db, "name", "Sam", BORN)
            for offset, kind, text in ((2, "plan", f"{self.name}'s plan for today: gather blocks for the walls and raise its walls."),
                                       (5, "built", f"{self.name} finished building a hut and moved in."),
                                       (6, "found", f"{self.name} met its first skitter."),
                                       (7, "hurt", f"{self.name} was hit by a gloomling."),
                                       (8, "hurt", f"{self.name} was hit by a gloomling."),
                                       (9, "ate", f"{self.name} ate berries."),
                                       (70, "ate", f"{self.name} ate bread.")):  # day 2: not in day 1's story
                log_event(db, BORN + offset, kind, text)
            state = read_state(db)
            found = highlights_of(db, state, 1, SCALE)
        self.assertEqual(found, ["My plan was to gather blocks for the walls and raise my walls.",
                                 "I finished building a hut and moved in.", "I met my first skitter.",
                                 "A gloomling hit me 2 times, but I made it through."])
        self.visit(BORN + 10)
        self.talker().poll(self.registry, BORN + 61)
        [story] = self.stories()
        self.assertEqual(len(sentences(story["text"])), 6)
        self.assertTrue(story["text"].startswith("Day 1 was a busy one. My plan was to gather blocks"), story["text"])
        self.assertTrue(story["text"].endswith("Maybe you'll visit tomorrow?"), story["text"])  # a shy bond

    def test_the_story_tells_how_far_along_the_goal_is(self):
        with self.world.transaction() as db:
            state = read_state(db)
            state["brain"] = {"goal": {"name": "iron_tools", "progress": 0.4, "plan": [], "picker": "utility", "since": BORN}}
            write_state(db, state)
            self.assertEqual(highlights_of(db, state, 1, SCALE), ["I'm 40% of the way to iron tools."])

    def test_luna_writes_it_once_a_utc_day_from_the_highlights_and_never_the_owners_words(self):
        luna = FakeLuna()
        owner_says(self.world, "my secret is pineapples", BORN + 5, SCALE)
        self.visit(BORN + 10)
        talker = self.talker(LUNA, luna)
        talker.poll(self.registry, BORN + 61)
        [story] = self.stories()
        self.assertEqual((story["text"], json.loads(story["data"])["writer"]), (STORY, "luna"))
        [body] = luna.bodies
        self.assertEqual(body["max_tokens"], 400)
        self.assertNotIn("pineapples", json.dumps(body))
        self.visit(BORN + 70)
        talker.poll(self.registry, BORN + 121)
        self.assertEqual(json.loads(self.stories()[-1]["data"])["writer"], "rules")  # Luna had its story today
        self.assertEqual(len(luna.bodies), 1)

    def test_a_failing_luna_falls_back_to_the_rules_and_counts_as_asked(self):
        for luna in (FakeLuna(error=ModelError("down")), FakeLuna(story="Too short")):
            forget_logged()
            with self.world.transaction() as db:
                state = read_state(db)
                state.setdefault("bond", {}).pop("story_luna_day", None)
                write_state(db, state)
            self.visit(BORN + 10 + 60 * len(self.stories()))
            with self.assertLogs("backend.survival.diary", level="ERROR"):
                self.talker(LUNA, luna).poll(self.registry, BORN + 61 + 60 * len(self.stories()))
            self.assertEqual(json.loads(self.stories()[-1]["data"])["writer"], "rules")
            self.assertIsNotNone(self.world.state()["bond"]["story_luna_day"])

    def test_a_dead_pet_writes_no_story(self):
        """Fix round 1, item 6: Luna is never even asked for a dead pet, not just never stored."""
        luna = FakeLuna()
        self.visit(BORN + 10)
        with self.world.transaction() as db:
            state = read_state(db)
            state["died_at"] = BORN + 20
            write_state(db, state)
        self.talker(LUNA, luna).poll(self.registry, BORN + 61)
        self.assertEqual(self.stories(), [])
        self.assertEqual(luna.bodies, [])

    def test_the_memorial_keeps_every_story_oldest_first(self):
        talker = self.talker()
        for day in range(3):
            self.visit(BORN + 10 + 60 * day)
            talker.poll(self.registry, BORN + 61 + 60 * day)
        detail = life_detail(self.registry, self.life, SCALE, BORN + 400)
        self.assertEqual([entry["day"] for entry in detail["diary"]], [1, 2, 3])

    def test_a_long_absence_grows_the_unread_story_to_tell_it_all(self):
        """Pre-flight 2 (the Bond ledger's ruling on Task 13): the owner visits on day 1 and stays away. The
        story written at the first dawn tells day 1; at every later dawn the same unread story grows, so
        after five game days away it tells day 2's goal too, the most notable first. Read, it stays."""
        talker = self.talker()
        self.visit(BORN + 10)
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
            log_event(db, BORN + 200, "ate", f"{self.name} ate berries.")  # day 4
        talker.poll(self.registry, BORN + 61)
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "writer": "rules"})  # as the plan has it
        self.assertNotIn("iron tools", story["text"])
        for day in range(3, 7):
            talker.poll(self.registry, BORN + 1 + 60 * (day - 1))
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 5, "writer": "rules"})
        self.assertEqual(story["text"], "Days 1 to 5 were good ones. On day 2, I reached a goal: iron tools. "
                                        "On day 4, I ate 1 time: berries. Maybe you'll visit tomorrow?")
        self.assertIsNone(story["read_at"])
        with self.world.transaction() as db:
            db.execute("UPDATE mimo_inbox SET read_at=? WHERE id=?", (BORN + 400, story["id"]))
        talker.poll(self.registry, BORN + 1 + 60 * 7)
        self.assertEqual([row["text"] for row in self.stories()], [story["text"]])  # read: it stays as it was

    def test_a_story_written_late_tells_every_day_since_the_visit(self):
        """Pre-flight 2: the worker was down after the visit; the story written at last tells every day
        since, at most MAX_STORY_DAYS, the newest."""
        self.visit(BORN + 10)
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
        self.talker().poll(self.registry, BORN + 1 + 60 * 5)  # the dawn of day 6
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 5, "writer": "rules"})
        self.assertIn("On day 2, I reached a goal: iron tools.", story["text"])
        with patch("backend.survival.diary.MAX_STORY_DAYS", 3), self.world.connect() as db:
            state = read_state(db)
            state["bond"].pop("storied")
            self.assertEqual(story_span(db, state, BORN + 1 + 60 * 5, SCALE), (3, 5, None))

    def test_luna_is_told_the_days_memories_and_writes_only_a_new_story(self):
        """Pre-flight 2: carry 7 (mind.story_memories in Luna's payload) and Luna's one call a UTC day:
        a story that grows over a long absence is the rules' work (the Bond ledger's ruling: the rules
        grow it by adding to what Luna wrote, never by asking Luna again)."""
        luna = FakeLuna()
        with self.world.transaction() as db:
            add_memory(db, BORN + 20, 1, "gist", "Day 1: met my first skitter.", (), 6)
            add_memory(db, BORN + 21, 1, "told", "You told me your name is Sam.", ("owner",), 6)
        self.visit(BORN + 10)
        talker = self.talker(LUNA, luna)
        talker.poll(self.registry, BORN + 61)
        [body] = luna.bodies
        sent = json.loads(body["messages"][1]["content"])
        self.assertEqual(sent["memories"], ["Day 1: met my first skitter."])  # never the told memory
        self.assertIn("game day 1 ", sent["instructions"])
        for day in range(3, 5):
            talker.poll(self.registry, BORN + 1 + 60 * (day - 1))
        self.assertEqual(len(luna.bodies), 1)
        # the writer stays "luna": the lead is Luna's own, per the Bond ledger's ruling on Task 13
        self.assertEqual(json.loads(self.stories()[-1]["data"]),
                          {"day": 1, "last": 3, "writer": "luna", "lead": len(STORY), "lead_last": 1})

    def test_a_long_absence_grows_a_luna_story_by_adding_a_since_then_paragraph(self):
        """The Bond ledger's ruling on Task 13: growing a story Luna wrote keeps Luna's own text as it
        is; the rules add one "Since then" paragraph after it instead of rewriting the whole thing, and
        rewrite that paragraph in place at each later dawn rather than piling another one on."""
        luna = FakeLuna()
        self.visit(BORN + 10)
        talker = self.talker(LUNA, luna)
        talker.poll(self.registry, BORN + 61)
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "writer": "luna", "lead": len(STORY), "lead_last": 1})
        self.assertEqual(story["text"], STORY)  # Luna's own words, untouched
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
        talker.poll(self.registry, BORN + 121)  # dawn of day 3: the story grows
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]),
                          {"day": 1, "last": 2, "writer": "luna", "lead": len(STORY), "lead_last": 1})
        self.assertTrue(story["text"].startswith(STORY))  # Luna's lead kept exactly
        self.assertEqual(story["text"], STORY + " Since then, on day 2, I reached a goal: iron tools.")
        self.assertEqual(story["text"].count("Since then, "), 1)
        with self.world.transaction() as db:
            log_event(db, BORN + 200, "ate", f"{self.name} ate berries.")  # day 4
        talker.poll(self.registry, BORN + 1 + 60 * 4)  # dawn of day 5: the paragraph is rewritten in place
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]),
                          {"day": 1, "last": 4, "writer": "luna", "lead": len(STORY), "lead_last": 1})
        self.assertTrue(story["text"].startswith(STORY))  # still Luna's lead, still untouched
        self.assertEqual(story["text"].count("Since then, "), 1)  # updated in place, not appended again
        self.assertIn("On day 4, I ate 1 time: berries.", story["text"])
        self.assertEqual(len(luna.bodies), 1)  # Luna was asked once, for the original story only
        self.assertFalse(story["read_at"])

    def test_a_grown_luna_story_drops_whole_highlights_to_stay_within_the_story_limit(self):
        """Fix round 1, item 5: trimming a "Since then" paragraph never cuts a sentence in half (the
        old code sliced mid-word and tacked on "..."). It drops whole highlights, the oldest first,
        until the paragraph fits, and never leaves a bare "Since then," with nothing after it. The lead
        is never touched, even when it alone leaves no room for a paragraph at all."""
        lead = "A" * 650
        found = ["On day 2, " + "B" * 100 + ".", "On day 4, " + "C" * 100 + "."]
        grown = since_then_story(lead, found)
        self.assertLessEqual(len(grown), STORY_LIMIT)
        self.assertTrue(grown.startswith(lead))
        self.assertNotIn("B" * 100, grown)  # day 2's highlight, the oldest, is dropped first
        self.assertNotIn("C" * 100, grown)  # day 4's too: neither fits even alone
        self.assertEqual(grown, lead + " Since then, it's been quiet.")  # never a bare "Since then,"
        self.assertEqual(story_lead(grown, len(lead)), lead)  # the lead is recoverable, unshortened
        # fix round 2, item 3: an over-long lead is capped at STORY_LIMIT too, never left whole and over
        over = "A" * (STORY_LIMIT + 50)
        self.assertEqual(since_then_story(over, found), over[:STORY_LIMIT])
        self.assertEqual(len(since_then_story(over, found)), STORY_LIMIT)

    def test_a_luna_story_that_says_since_then_itself_keeps_every_sentence_when_it_grows(self):
        """Fix round 1, item 1: story_lead used to split on the first " Since then, ", which Luna can
        write herself (the review's probe: Luna wrote a story with its own "Since then, ..." sentence,
        and the next dawn deleted the rest of it). The item now records the lead's own length
        (data["lead"]) when Luna writes it, so growing the story never depends on guessing where Luna's
        own text ends."""
        luna = FakeLuna(story=STORY_WITH_SINCE_THEN)
        self.visit(BORN + 10)
        talker = self.talker(LUNA, luna)
        talker.poll(self.registry, BORN + 61)
        [story] = self.stories()
        self.assertEqual(story["text"], STORY_WITH_SINCE_THEN)
        self.assertEqual(json.loads(story["data"])["lead"], len(STORY_WITH_SINCE_THEN))
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
        talker.poll(self.registry, BORN + 121)  # dawn of day 3: the story grows
        [story] = self.stories()
        # every one of Luna's own sentences is kept, including her own "Since then, ..."
        self.assertTrue(story["text"].startswith(STORY_WITH_SINCE_THEN), story["text"])
        self.assertEqual(story["text"].count("Since then, "), 2)  # Luna's own, plus the rules' growth paragraph
        self.assertIn("on day 2, I reached a goal: iron tools.", story["text"])

    def test_a_multiday_luna_story_grows_without_retelling_its_own_days(self):
        """Fix round 1, item 2: a late Luna story can already cover several days ({"day": 1, "last": 4}
        in the review's example). since_start used to be `day + 1` (the item's first day), so growing it
        re-told every day Luna already told. The item now keeps Luna's own last day in "lead_last",
        untouched as it grows, and the "Since then" paragraph starts the day after that."""
        luna = FakeLuna()
        self.visit(BORN + 10)  # day 1
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
        talker = self.talker(LUNA, luna)
        talker.poll(self.registry, BORN + 241)  # the worker's first poll: the dawn of day 5, late
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]),
                          {"day": 1, "last": 4, "lead": len(STORY), "lead_last": 4, "writer": "luna"})
        with self.world.transaction() as db:
            log_event(db, BORN + 250, "built", f"{self.name} finished building a hut and moved in.")  # day 5
        talker.poll(self.registry, BORN + 301)  # dawn of day 6: grows past Luna's own days
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]),
                          {"day": 1, "last": 5, "lead": len(STORY), "lead_last": 4, "writer": "luna"})
        self.assertTrue(story["text"].startswith(STORY))
        self.assertNotIn("iron tools", story["text"])  # day 2 is Luna's own; the paragraph never re-tells it
        self.assertIn("on day 5, I finished building a hut and moved in.", story["text"])
        self.assertEqual(len(luna.bodies), 1)

    def test_a_return_visit_before_the_talker_catches_up_keeps_the_owed_story(self):
        """Fix round 1, item 3: the viewer's visit can land before the Talker's first poll after a gap
        (the usual order after the worker's machine sleeps: the worker's catch-up tick runs before
        talker.poll, while the viewer calls /mimo/visit at once). bond.visit keeps the owed visit's time
        in "owed_from" so the story the Talker eventually writes still starts there, not at the return
        visit, losing everything in between."""
        self.visit(BORN + 10)  # day 1
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
        self.visit(BORN + 421)  # day 8: the owner is back, before the Talker has ever polled since day 1
        self.assertEqual(self.world.state()["bond"]["owed_from"], BORN + 10)
        self.talker().poll(self.registry, BORN + 481)  # the Talker's first poll since: the dawn of day 9
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 8, "writer": "rules"})
        self.assertEqual(story["text"], "Days 1 to 8 were good ones. On day 2, I reached a goal: iron tools. "
                                        "Maybe you'll visit tomorrow?")
        self.assertIsNone(self.world.state()["bond"].get("owed_from"))  # cleared once the story is written

    def test_the_owed_story_survives_the_next_dawn_unread(self):
        """Fix round 2, item 1 (a regression from round 1): growing a story must read the item's own
        first day, never re-derive it from "seen_at" or "owed_from" -- "owed_from" is cleared once the
        first dawn writes the story (store_story), so a later dawn recomputing "first" from "seen_at"
        instead would replace "Days 1 to 8 were ..." with "Day 8 was a quiet one ...", losing everything.
        The reviewer's exact probe."""
        self.visit(BORN + 10)  # day 1
        with self.world.transaction() as db:
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
        self.visit(BORN + 421)  # day 8: the owner is back, before the Talker has ever polled since day 1
        talker = self.talker()
        talker.poll(self.registry, BORN + 481)  # the Talker's first poll since: the dawn of day 9
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 8, "writer": "rules"})
        self.assertTrue(story["text"].startswith("Days 1 to 8 were"), story["text"])
        with self.world.transaction() as db:
            log_event(db, BORN + 490, "ate", f"{self.name} ate berries.")  # day 9
        talker.poll(self.registry, BORN + 541)  # the dawn of day 10: it must grow, never be replaced
        self.assertEqual(len(self.stories()), 1)  # the same item, not a second one
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 9, "writer": "rules"})
        self.assertTrue(story["text"].startswith("Days 1 to 9 were"), story["text"])
        self.assertIn("iron tools", story["text"])  # day 2's goal, still told, three dawns later

    def test_a_growing_story_absorbs_the_days_the_machine_slept_through(self):
        """Fix round 2, item 2 (still open after round 1): the story already covered days 1-2 through
        ordinary growth (no race here -- the owner never revisited while it grew). Then the machine
        slept. A goal was reached on day 4 while it caught up on waking. The owner's viewer reconnected
        on day 8, calling /mimo/visit before the Talker's first poll since the sleep. The day-4 goal
        must still be told: a new visit must never let a gap between it and the still-growing, unread
        story go untold."""
        talker = self.talker()
        self.visit(BORN + 10)  # day 1
        talker.poll(self.registry, BORN + 61)  # dawn of day 2: creates the item, day 1 only
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "writer": "rules"})
        talker.poll(self.registry, BORN + 121)  # dawn of day 3: grows to days 1-2, still no new visit
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 2, "writer": "rules"})
        with self.world.transaction() as db:
            log_event(db, BORN + 190, "goal", f"{self.name} reached a goal: iron tools.")  # day 4
        self.visit(BORN + 421)  # day 8: the owner is back, before the Talker has polled since day 3's dawn
        talker.poll(self.registry, BORN + 481)  # the Talker's first poll since: the dawn of day 9
        self.assertEqual(len(self.stories()), 1)  # the same item grew; a second was never started
        [story] = self.stories()
        self.assertEqual(json.loads(story["data"]), {"day": 1, "last": 8, "writer": "rules"})
        self.assertIn("iron tools", story["text"])  # day 4's goal: never lost to the gap

    def test_a_watching_owners_next_day_still_gets_its_own_fresh_story(self):
        """Fix round 2 guard: item 2's fix must not turn every visit into growth. A story that already
        covers through yesterday relative to today's new visit (no day skipped) still starts a fresh
        story for the new visit, exactly as round 1 has it -- the existing
        test_luna_writes_it_once_a_utc_day_... already covers this with Luna; this is the plain-rules
        case, checked directly against story_span."""
        self.visit(BORN + 10)  # day 1
        self.talker().poll(self.registry, BORN + 61)  # dawn of day 2: creates the item, day 1 only
        self.visit(BORN + 70)  # day 2: the owner is back the very next day, watching
        with self.world.connect() as db:
            state = read_state(db)
            self.assertEqual(story_span(db, state, BORN + 121, SCALE), (2, 2, None))  # a fresh story, not growth

    def test_a_grown_luna_story_returns_the_lead_alone_when_nothing_else_fits(self):
        """Fix round 2, item 3: when not even "Since then, it's been quiet." fits beside the lead, the
        rules return the lead alone rather than let the total run past STORY_LIMIT. The reviewer's
        probe: a 691-character lead plus a reached goal came to 720 characters."""
        lead = "A" * 691
        found = ["On day 2, I reached a goal: iron tools."]
        self.assertEqual(since_then_story(lead, found), lead)
        self.assertLessEqual(len(since_then_story(lead, found)), STORY_LIMIT)

    def test_growing_a_story_never_asks_luna_again_even_on_a_new_utc_day(self):
        """Fix round 1, item 6: growth never asks Luna (diary.py's `item is None` guard), regardless of
        story_luna_day's own daily cap."""
        luna = FakeLuna()
        self.visit(BORN + 10)
        talker = self.talker(LUNA, luna)
        talker.poll(self.registry, BORN + 61)
        self.assertEqual(len(luna.bodies), 1)
        with self.world.transaction() as db:
            state = read_state(db)
            state["bond"]["story_luna_day"] = "2000-01-01"  # as if the daily cap had reset
            log_event(db, BORN + 70, "goal", f"{self.name} reached a goal: iron tools.")  # day 2
            write_state(db, state)
        talker.poll(self.registry, BORN + 121)  # dawn of day 3: the story grows
        self.assertEqual(len(luna.bodies), 1)  # still just the once: growth never asks Luna
        self.assertEqual(json.loads(self.stories()[-1]["data"])["writer"], "luna")

    def test_a_restart_mid_call_does_not_cost_a_second_luna_call(self):
        """Fix round 1, item 7: the attempt is recorded when the Luna job starts (inside story_job,
        which runs synchronously in the worker's loop before the model call is dispatched), not when its
        answer is later stored, so a worker that restarts while Luna is still answering does not ask
        Luna again that day."""
        self.visit(BORN + 10)
        job = story_job(SurvivalWorld(self.world.path, read_only=True), BORN + 61, SCALE, LUNA)
        self.assertIsNotNone(job)
        self.assertTrue(job.model)  # Luna is asked
        # the attempt is already recorded, even though job.store was never called (the "restart")
        self.assertEqual(self.world.state()["bond"]["story_luna_day"], utc_day(BORN + 61))
        again = story_job(SurvivalWorld(self.world.path, read_only=True), BORN + 62, SCALE, LUNA)
        self.assertIsNotNone(again)
        self.assertFalse(again.model)  # not asked twice in the same UTC day, even though no story exists yet

    def test_life_summary_caps_the_diary_for_the_egg_screens_repeated_poll(self):
        """Fix round 1, item 8: life_summary is polled on the egg screen every few seconds; cap what it
        sends so a long-lived life's whole diary is not resent each time. life_detail (the memorial)
        still keeps every story."""
        talker = self.talker()
        for day in range(DIARY_SUMMARY + 2):
            self.visit(BORN + 10 + 60 * day)
            talker.poll(self.registry, BORN + 61 + 60 * day)
        detail = life_detail(self.registry, self.life, SCALE, BORN + 10_000)
        summary = life_summary(self.registry, self.life, SCALE, BORN + 10_000)
        self.assertEqual(len(detail["diary"]), DIARY_SUMMARY + 2)
        self.assertLessEqual(len(summary["diary"]), DIARY_SUMMARY)
        self.assertEqual([entry["day"] for entry in summary["diary"]],
                          [entry["day"] for entry in detail["diary"]][-DIARY_SUMMARY:])


class DiaryApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.env = patch.dict(os.environ, {"MIMO_DATA_DIR": str(root / "data"),
                                           "MIMO_DB_PATH": str(root / "no-legacy.sqlite3"), "MIMO_TIME_SCALE": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.directory.cleanup()

    def test_the_newest_story_shows_first_until_read_and_the_diary_lists_them(self):
        hatch_egg()
        registry = LifeRegistry()
        world = SurvivalWorld(registry.world_path(registry.active_life()))
        with world.transaction() as db:
            post_item(db, 1.0, "story", "Day 1 was a quiet one. I rested. Maybe you'll visit tomorrow?",
                      {"day": 1, "writer": "rules"})
            story = post_item(db, 2.0, "story", "Day 2 was a good one. I ate. I hope you visit again soon.",
                              {"day": 2, "writer": "rules"})
            post_item(db, 3.0, "report", "I reached a goal: iron tools.")
        shown = get_mimo()["story"]
        self.assertEqual((shown["id"], shown["day"], shown["read"]), (story, 2, False))
        self.assertEqual([entry["day"] for entry in get_diary()["entries"]], [2, 1])
        self.assertEqual(read_inbox(ReadUpTo(id=story)), {"unread": 2})  # just the story
        self.assertTrue(get_mimo()["story"]["read"])
        with self.assertRaises(HTTPException) as caught:
            read_inbox(ReadUpTo())
        self.assertEqual(caught.exception.status_code, 400)

    def test_giving_both_up_to_and_id_is_also_a_400(self):
        """Fix round 1, item 6: the exactly-one-of check refuses both fields given, not just neither."""
        with self.assertRaises(HTTPException) as caught:
            read_inbox(ReadUpTo(up_to=1, id=2))
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()

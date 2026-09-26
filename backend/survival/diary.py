"""The daily story, "While you were away" (Bond B3), and the life's diary.

At the first game dawn after the owner's last visit (bond.visit: the viewer open, care, a hello or a
chat line), Mimo writes a short diary entry about the game day the owner was last there: 3 to 6
sentences with its highlights (`day_highlights`: a goal reached or set, the day's plan, how far along its
goal is, things built, first sightings, danger, meals), from the event log of that day and the goal it
works on, or, on a day with none, what it spent the day doing. `story_span` says when one is due; the Talker's "story" lane writes it
(`story_job`). Luna writes it when MIMO_MODEL_API_KEY or OPENAI_API_KEY is set, at most once a real
UTC day (the attempt counts, so a failing Luna is not asked again that day), from the highlights and
Mimo's name, traits, mood, bond and the owner's name, never from the owner's other words; the rules'
template (`rules_story`) writes it otherwise, and whenever Luna fails, times out or answers badly.
Jev never writes it: its API answers choices only.

A story is an inbox item of kind "story" ({"day", "writer"} in its data, and "last" for one about
several days), so it counts as unread until the owner reads it and the inbox never drops it.
/api/mimo shows the newest story (`newest_story`, first when the viewer opens while it is unread);
GET /api/mimo/diary lists the newest DIARY_SHOWN; a life's memorial has all of them
(`diary_entries`). state["bond"] keeps "storied" (the visit the last story was written for), "story"
({"item", "seen", "last"}: that story and the last game day it tells) and "story_luna_day" (the UTC
day Luna was last asked).

Pre-flight 2: Luna is also given the day's gist and top memories, read only through
mind.story_memories, which never returns a told memory or one about the owner (carry 7). And a long
absence grows one story instead of a fresh one each dawn, at most MAX_STORY_DAYS (the Bond ledger's
ruling on Task 13): while the owner stays away and the visit's story is unread, every later dawn
touches it again. A story the rules wrote is rewritten whole, to tell every game day since the visit
(`story_span`, `absence_highlights`: the most notable of those days first, the most recent among
equals, told in day order). A story Luna wrote keeps Luna's own text as it is; the rules instead add
or update one "Since then, ..." paragraph after it, for the days since Luna's own (`since_then_story`,
`story_lead`; bounded by MAX_STORY_DAYS and STORY_LIMIT too). Either way Luna writes only a new story,
so its one call a UTC day is unchanged, and the item's data keeps its original "writer" (never
overwritten while it grows) so a later dawn still knows whether its lead text is Luna's. A story the
owner read is never rewritten, and an absence of a game day or less gets the story the plan wrote.

Fix round 2: growing an item always reads its own persisted "day" (`story_span`), never "seen_at" or
"owed_from", which store_story clears once a story is written -- rederiving it from either would erase
an owed story at its very next dawn. And a still-growing, unread story keeps growing across a newer
visit too, closing a gap of more than a day between what it already tells and that visit's own day
(the owner returning before the Talker's first poll since the machine slept), rather than being
abandoned for a fresh, gap-skipping one; a visit that leaves no gap (a watching owner's very next day)
still gets its own fresh story, as round 1 has it.

Bond's final fix wave: every event text is said through the one voicing (replies.in_my_voice), so the
pet's name and "it" never leak (I1); meals are told by food, never with a count the list does not show;
the plan told is the day's last, left out when a goal was reached or set after it, and the progress line
is said now and left out for a goal taken up after the last day told (I2); danger is told by what it was
(m3); a promise kept leads, a day's goals share one sentence and one day is ranked as a long absence is
(m15); an absence is told from its first day, reading the events of its newest MAX_STORY_DAYS (m16); and a
one-day story for an owner who was seen that day thanks them for the company (I4, `present`).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass

from backend.survival.bond import bond_level, bond_state, feeling, utc_day
from backend.survival.bond_tables import missing_table
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.goals import goal_view
from backend.survival.inbox import STORY, post_item
from backend.survival.mind import story_memories
from backend.survival.models import LUNA_TIMEOUT, Http, ModelError, luna_configured, luna_json
from backend.survival.once import log_once
from backend.survival.owner_facts import owner_facts, owner_name
from backend.survival.replies import CLOSE, SENTENCE_END, SHY, in_my_voice, voiced, working_on
from backend.survival.talker import LANES, Job
from backend.survival.world import SurvivalWorld, read_state, write_state

logger = logging.getLogger(__name__)

DIARY_SHOWN = 30  # entries GET /api/mimo/diary lists
HIGHLIGHTS = 4  # sentences of highlights at most
STORY_LIMIT = 700  # characters in a story
STORY_TOKENS = 400  # Luna's answer, outside gpt-6-luna's own limit
GIVE_UP_AFTER = 15.0  # seconds past Luna's timeout before the story call is given up
STORY_INSTRUCTIONS = ("Write the pet's diary entry about {days} in its own voice: 3 to 6 short sentences, "
                      "first person, plain text, only about the highlights and memories given (say it was a quiet "
                      "time if there are none), warm to its owner as its bond allows. When \"present\" is true its "
                      "owner kept it company then: never say it missed them. Answer {{\"story\": \"<entry>\"}}.")
# Game days of events one story reads at most, the newest, after a long absence (pre-flight 2). Bond's final
# fix wave (m16): the story still names every day of the absence, and the bound is some ten real days at the
# production scale, so a weekend away is told whole.
MAX_STORY_DAYS = 240
STORY_MEMORIES = 5  # memories a day Luna is told (mind.story_memories: never the owner's words)
MEMORIES_SHOWN = 12  # memories Luna is told at most, the newest days first
# How notable a highlight is, the most first, when a story tells several days (pre-flight 2).
# Bond's final fix wave (m15): a promise kept ranks first, and one day's story is ranked this way too.
RANKS = {"promise": 0, "goal": 1, "built": 2, "found": 3, "set": 4, "danger": 5, "plan": 6, "ate": 7, "progress": 8}
# Danger besides a blow, in the story's words (the final fix wave's m3), the first of these that happened
# that day told ("threat" names the creature).
DANGER_WORDS = (("trapped", "I got stuck in a pit and had to dig my way out."), ("starving", "I got very hungry."),
                ("freezing", "I got very cold."), ("fall", "I fell and got hurt."),
                ("threat", "I saw {what} coming, but I kept safe."))
COUNTS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve")
# What a meal was (m1 of the live findings): "1 raw rabbit it had no room to carry" -> "raw rabbit".
MEAL = re.compile(r"^(?:\d+ )?(.+?)(?: it had no room to carry)?$")
# Marks where the rules' growth paragraph starts in a Luna story that grew (the Bond ledger's ruling).
SINCE_THEN = "Since then, "


def day_bounds(state: dict, day: int, scale: float) -> tuple[float, float]:
    """The server times game day `day` began and ended."""
    start = state["born_at"] + (day - 1) * DAY_SECONDS / scale
    return start, start + DAY_SECONDS / scale


def story_due(state: dict, now: float, scale: float) -> int | None:
    """The game day a story is due about, or None: the owner was seen, a game dawn came since, and no
    story was written for that visit yet."""
    bond = state.get("bond") or {}
    seen = bond.get("seen_at")
    if seen is None or bond.get("storied") == seen or state.get("died_at") is not None:
        return None
    day = clock_at(state["born_at"], seen, scale)["day_number"]
    return day if clock_at(state["born_at"], now, scale)["day_number"] > day else None


def after(text: str, marker: str) -> str:
    return text.split(marker, 1)[1] if marker in text else ""


def events_between(db: sqlite3.Connection, state: dict, first: int, last: int, scale: float) -> list[dict]:
    """Every event of game days `first` to `last`, oldest first, each with its "day"; one read."""
    start, end = day_bounds(state, first, scale)[0], day_bounds(state, last, scale)[1]
    rows = db.execute("SELECT id, at, kind, text FROM mimo_events WHERE at >= ? AND at < ? ORDER BY id", (start, end))
    return [{**dict(row), "day": clock_at(state["born_at"], row["at"], scale)["day_number"]} for row in rows]


def kept_promises(db: sqlite3.Connection) -> dict[int, str]:
    """{goal event id: "You asked me to look into a cave, and I did it!"}: the promises Mimo kept, as the
    inbox told them (backend.survival.requests), for the story (the final fix wave's m15)."""
    kept = {}
    for row in db.execute("SELECT text, data FROM mimo_inbox WHERE kind='report' AND data LIKE '%\"promise\"%'"):
        data = json.loads(row["data"] or "{}")
        if data.get("promise") and data.get("event") is not None:
            kept[data["event"]] = SENTENCE_END.split(row["text"])[0]
    return kept


def counted(n: int) -> str:
    return COUNTS[n] if 0 <= n < len(COUNTS) else str(n)


def times(n: int) -> str:
    return "once" if n == 1 else "twice" if n == 2 else f"{counted(n)} times"


def listed(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def meal_line(foods: list[str]) -> str:
    """ "I ate cooked beef.", "I ate five meals: bread three times, cooked fish and raw rabbit.", or with more
    than three foods "I ate seven meals, among them bread, cooked fish and raw rabbit.": never a count the
    list does not show (the final fix wave's I1)."""
    if len(foods) == 1:
        return f"I ate {foods[0]}."
    each = Counter(foods)
    if len(each) <= 3:
        each_food = [food if n == 1 else f"{food} {times(n)}" for food, n in each.items()]
        return f"I ate {counted(len(foods))} meals: {listed(each_food)}."
    return f"I ate {counted(len(foods))} meals, among them {listed([food for food, _ in each.most_common(3)])}."


def reached_title(text: str) -> str:
    """ "Pip reached a goal: a home of its own." -> "a home of my own"."""
    return voiced(after(text, "reached a goal: ").rstrip("."))


def progress_line(goal: dict) -> str:
    """How far along the goal Mimo works on now is, said now (I2): "Now I'm working toward iron tools: 40% done."."""
    return f"Now I'm working {working_on(goal['title'])}: {round(goal['progress'] * 100)}% done."


def goal_now(state: dict, until: float | None) -> dict | None:
    """The goal Mimo works on, unless it took it up after `until` (the end of the last day a story tells,
    I2): a goal chosen at this dawn is no part of yesterday."""
    goal = goal_view(state.get("brain"))
    if goal is None or (until is not None and (goal.get("since") or 0.0) >= until):
        return None
    return goal


def day_highlights(events: list[dict], state: dict, until: float | None = None,
                   kept: dict[int, str] | None = None) -> list[tuple[str, str]]:
    """One day's highlights as (what, sentence in Mimo's voice), the most telling first (RANKS), from that
    day's events and the goal Mimo works on ("progress", only on a day it reached no goal and only for a
    goal it took up before `until`).

    Bond's final fix wave: every event text in the one voice (I1, replies.in_my_voice); the day's last plan,
    left out when a goal was reached or set after it (I2); a promise kept (`kept`, by goal event id) above
    the goals, a day's goals in one sentence, and a goal set that day left out when it was reached that day
    too (m15); danger by kind (m3); meals by food, never a count the list does not show (I1)."""
    name, kept, found = state["name"], kept or {}, []
    goals = [event for event in events if event["kind"] == "goal"]
    reached = {reached_title(event["text"]) for event in goals}
    found += [("promise", words) for words in dict.fromkeys(kept[event["id"]] for event in goals
                                                           if event.get("id") in kept)]
    titles = list(dict.fromkeys(reached_title(event["text"]) for event in goals if event.get("id") not in kept))
    if titles:
        found.append(("goal", f"I reached a goal: {titles[0]}." if len(titles) == 1
                      else f"I reached {counted(len(titles))} goals: {listed(titles)}."))
    set_titles = [after(in_my_voice(event["text"], name), "set a new goal: ").split(".")[0]
                  for event in events if event["kind"] == "plan" and "set a new goal: " in event["text"]]
    unreached = [title for title in set_titles if title and title not in reached]
    if unreached:
        found.append(("set", f"I set myself a new goal: {unreached[-1]}."))
    plans = [place for place, event in enumerate(events)
             if event["kind"] == "plan" and event["text"].startswith(f"{name}'s plan for today: ")]
    if plans and not any(event["kind"] == "goal" or (event["kind"] == "plan" and "set a new goal: " in event["text"])
                         for event in events[plans[-1] + 1:]):
        found.append(("plan", f"My plan was to {voiced(after(events[plans[-1]]['text'], 'plan for today: '))}"))
    goal = goal_now(state, until)
    if goal is not None and not goals:
        found.append(("progress", progress_line(goal)))
    found += [("built", in_my_voice(event["text"], name)) for event in events if event["kind"] == "built"]
    sights = [in_my_voice(event["text"], name).rstrip(".") for event in events  # "a cave mouth ... in its walls"
              if event["kind"] in ("found", "discovered")]
    if sights:
        found.append(("found", " and ".join(sights[:2]) + "."))
    hits = [after(event["text"], "was hit by a ").rstrip(".") for event in events if event["kind"] == "hurt"]
    if hits:
        kind, n = Counter(hits).most_common(1)[0]
        found.append(("danger", f"A {kind} hit me {times(n)}, but I made it through."))
    else:
        for kind, words in DANGER_WORDS:
            event = next((event for event in events if event["kind"] == kind), None)
            if event is not None:
                what = after(event["text"], " saw ").removesuffix(" coming.") or "something"
                found.append(("danger", words.format(what=what)))
                break
    foods = [MEAL.match(after(event["text"], " ate ").rstrip(".")).group(1) for event in events
             if event["kind"] == "ate" and after(event["text"], " ate ")]
    if foods:
        found.append(("ate", meal_line(foods)))
    return sorted(found, key=lambda item: RANKS[item[0]])


def on_day(day: int, text: str) -> str:
    """ "On day 2, I reached a goal: iron tools.", "On day 3, a gloomling hit me ..."."""
    kept = text if text.startswith(("I ", "I'")) else text[:1].lower() + text[1:]
    return f"On day {day}, {kept}"


def absence_highlights(events: list[dict], state: dict, first: int, last: int, until: float | None = None,
                       kept: dict[int, str] | None = None) -> list[str]:
    """The highlights of game days `first` to `last` (a long absence, pre-flight 2): the most notable
    first (RANKS), the most recent among equals, at most HIGHLIGHTS, told in day order with their day;
    how far along Mimo's goal is now closes them when there is room (a goal taken up before `until`)."""
    by_day: dict[int, list[dict]] = {}
    for event in events:
        by_day.setdefault(event["day"], []).append(event)
    ranked = []
    for day in sorted(by_day):
        if first <= day <= last:
            for what, text in day_highlights(by_day[day], state, kept=kept):
                if what != "progress":
                    ranked.append((RANKS[what], -day, day, text))
    chosen = sorted(sorted(ranked)[:HIGHLIGHTS], key=lambda item: (item[2], item[0]))
    found = [on_day(day, text) for _, _, day, text in chosen]
    goal = goal_now(state, until)
    if goal is not None and len(found) < HIGHLIGHTS:
        found.append(progress_line(goal))
    return found


def busiest_of(events: list[dict]) -> str:
    """What Mimo spent the time trying to do most, from its purpose events ("gather wood"), or ""."""
    phrases = [re.split(r"[.,]", after(event["text"], " decided to "))[0].strip() for event in events
               if event["kind"] == "purpose"]
    phrases = [phrase for phrase in phrases if phrase]
    return Counter(phrases).most_common(1)[0][0] if phrases else ""


def rules_story(day: int, found: list[str], doing: str, owner: str, level: float, last: int | None = None,
                present: bool = False) -> str:
    """The rules' entry: an opening, the highlights (or what the day went on), a closing: 3 to 6 sentences.
    A story of several days (pre-flight 2) opens with them all ("Days 1 to 5 were busy ones."). Bond's final
    fix wave (I4): for an owner who was there (`present`), the closing thanks them for the company, never
    "I missed you" or "Maybe you'll visit tomorrow?"."""
    if last is not None and last > day:
        kind = "busy ones" if len(found) >= 3 else "good ones" if found else "quiet ones"
        opening, spent = f"Days {day} to {last} were {kind}.", "I spent most of my time"
    else:
        kind = "a busy one" if len(found) >= 3 else "a good one" if found else "a quiet one"
        opening, spent = f"Day {day} was {kind}.", "I spent most of it"
    body = found or [f"{spent} trying to {doing}." if doing else "I stayed close to home and kept safe."]
    to = f", {owner}" if owner else ""
    if present:
        closing = f"Thanks for keeping me company{to}!"
    else:
        closing = (f"Come back soon{to}, I missed you!" if level >= CLOSE else "Maybe you'll visit tomorrow?"
                   if level < SHY else f"I hope you visit again soon{to}.")
    return " ".join([opening, *body, closing])


def clean_story(text: object) -> str:
    """Luna's entry as plain text: one paragraph, at most 6 sentences and STORY_LIMIT characters.
    Raises ModelError for anything shorter than 2 sentences."""
    if not isinstance(text, str):
        raise ModelError("Luna wrote no story")
    sentences = [part for part in SENTENCE_END.split(" ".join(text.replace("*", "").replace("#", "").split())) if part]
    if len(sentences) < 2:
        raise ModelError("Luna's story was too short")
    story = " ".join(sentences[:6])
    return story if len(story) <= STORY_LIMIT else story[:STORY_LIMIT - 3].rstrip() + "..."


def story_lead(text: str, lead: int) -> str:
    """A Luna story's own text (the Bond ledger's ruling): its first `lead` characters, exactly as
    recorded in the item's data ("lead") when Luna wrote it.

    Fix round 1, item 1: never split on a " Since then, " separator. Luna can write that phrase herself
    (the review's probe did), and splitting on it would cut her own text short."""
    return text[:lead]


def since_then_story(lead: str, found: list[str]) -> str:
    """Luna's lead followed by the rules' one "Since then" paragraph (the Bond ledger's ruling): the
    highlights of the days after Luna's own, at most HIGHLIGHTS, the most notable first, told in day
    order (`absence_highlights`).

    Fix round 1: item 4, the paragraph's first letter is lowercased to follow the comma only when it
    begins "On day" (a highlight in another shape, such as the goal-progress closer, keeps its own
    capital: "Since then, I'm 40% ..." not "i'm"). Item 5, kept within STORY_LIMIT by dropping whole
    highlights, the oldest first, until it fits, rather than cutting a sentence in half.

    Fix round 2, item 3: when nothing fits beside the lead, not even "Since then, it's been quiet."
    (the reviewer's probe: a 691-character lead plus a reached goal came to 720 characters), the lead
    is returned alone, over STORY_LIMIT only if it already was on its own (clean_story already caps
    Luna's own text at STORY_LIMIT, so this is a defensive floor, not an expected case)."""
    body = list(found)
    while body:
        sentence = " ".join(body)
        if sentence.startswith("On day"):
            sentence = sentence[:1].lower() + sentence[1:]
        text = f"{lead} {SINCE_THEN}{sentence}"
        if len(text) <= STORY_LIMIT:
            return text
        body = body[1:]  # drop the oldest highlight and try again
    quiet = f"{lead} {SINCE_THEN}it's been quiet."
    return quiet if len(quiet) <= STORY_LIMIT else lead[:STORY_LIMIT]


@dataclass(frozen=True)
class StoryAsk:
    day: int
    seen: float  # the visit the story is for
    rules: str  # the rules' entry
    payload: dict  # what Luna is told
    luna: bool  # Luna is asked
    asked_at: float
    last: int | None = None  # pre-flight 2: the last game day it tells (None: `day` alone)
    item: int | None = None  # pre-flight 2: the unread story it rewrites to tell a long absence (None: a new one)
    writer: str | None = None  # the Bond ledger's ruling: the item's own writer, when growing one (None: a new item)
    lead_len: int | None = None  # fix round 1, item 1: characters of a growing Luna item's own lead, carried as is
    lead_last: int | None = None  # fix round 1, item 2: a growing Luna item's own last day, carried as is


@dataclass(frozen=True)
class StoryAnswer:
    text: str
    writer: str  # "luna" or "rules"
    error: str | None = None


def write_story(ask: StoryAsk, env, http: Http) -> StoryAnswer:
    """Luna's entry, or the rules' when Luna is not asked or fails. Never raises."""
    if not ask.luna:
        return StoryAnswer(ask.rules, "rules")
    schema = {"type": "object", "additionalProperties": False, "properties": {"story": {"type": "string"}},
              "required": ["story"]}
    messages = [
        {"role": "system", "content": f"You are {ask.payload['pet']}, a small voxel pet surviving in a wild world. "
                                      "Write as the pet. Return valid JSON only."},
        {"role": "user", "content": json.dumps({**ask.payload, "instructions": STORY_INSTRUCTIONS.format(
            days=f"game days {ask.day} to {ask.last}" if ask.last and ask.last > ask.day else f"game day {ask.day}")})},
    ]
    try:
        return StoryAnswer(clean_story(luna_json(messages, "mimo_story", schema, env, http, STORY_TOKENS).get("story")),
                           "luna")
    except Exception as error:
        return StoryAnswer(ask.rules, "rules", f"luna: {error}")


def story_span(db: sqlite3.Connection, state: dict, now: float, scale: float) -> tuple[int, int, int | None] | None:
    """The game days a story is due to tell, first and last, and the story it rewrites (None: a new one),
    or None: from the day of the owner's last visit to the day before now, once a game dawn came since the
    visit (pre-flight 2; Bond's final fix wave, m16: every day of the absence, however long, while
    `story_job` reads the events of at most MAX_STORY_DAYS of them, the newest). A new story for a new visit; while the
    owner stays away, the visit's story, still unread, grows at every later dawn to tell the whole
    absence; one the owner read stays as it is.

    Fix round 2 (a regression from round 1's item 3, and item 2's own gap): growing an item never
    re-derives its first day from "seen_at" or "owed_from" (round 1's item 3 fix, which store_story
    clears once the story is written) -- it always reads the item's own persisted "day", so a later
    visit moving "seen_at" on can never erase what an unread, still-growing story already told. And the
    item keeps growing across a new visit, not just the one it was written for, whenever that new visit
    would otherwise leave a gap of more than one day untold between the item's own "last" and the visit's
    day -- the owner returning before the Talker's first poll since a machine's sleep must not skip the
    days in between (item 2). A watching owner's very next day, with no day skipped, still gets its own
    fresh story, exactly as round 1 has it: the gap there is never more than one day.

    Fix round 3: a story the owner reads before the Talker's next poll is skipped for growth above, so
    a fresh story is due next; that fresh story's own "first" now starts right after what the read
    story last told (bond["story"]["last"]), never at the new visit's own day, or the days in between --
    read early, before the worker ever caught up on them -- would never be told at all."""
    bond = state.get("bond") or {}
    seen = bond.get("seen_at")
    if seen is None or state.get("died_at") is not None:
        return None
    last = clock_at(state["born_at"], now, scale)["day_number"] - 1
    story = bond.get("story") or {}
    item = story.get("item")
    if item is not None:
        row = db.execute("SELECT data, read_at FROM mimo_inbox WHERE id=? AND kind=?", (item, STORY)).fetchone()
        if row is not None and row["read_at"] is None:
            seen_day = clock_at(state["born_at"], seen, scale)["day_number"]
            story_last = story.get("last", 0)
            if bond.get("storied") == seen or seen_day - story_last > 1:
                if story_last >= last:
                    return None
                story_first = json.loads(row["data"] or "{}").get("day", story_last)
                return (story_first, last, item) if story_first <= last else None
    if bond.get("storied") == seen:
        return None
    since = bond.get("owed_from") if bond.get("owed_from") is not None else seen
    first = clock_at(state["born_at"], since, scale)["day_number"]
    told = story.get("last")  # fix round 3: a story read before the Talker caught up is skipped for
    if told is not None and told + 1 < first:  # growth above, so pick up right after what it told,
        first = told + 1  # not at the visit's own day, or the days between are never told at all
    if last < first:
        return None
    return first, last, None


def story_job(world: SurvivalWorld, now: float, scale: float, env) -> Job | None:
    """The story due, as a Talker job: Luna once a UTC day when configured for a new story, else the rules
    (and always the rules to grow a waiting story over a long absence, pre-flight 2). The Bond ledger's
    ruling: growing a story the rules wrote rewrites it whole, as before; growing a story Luna wrote keeps
    Luna's own text and only adds or updates the "Since then" paragraph after it (`since_then_story`),
    starting the day after Luna's own last day (fix round 1, item 2: "lead_last", never the item's
    windowed "day", so a late, multi-day Luna story is never re-told).

    Fix round 1, item 7: when Luna is about to be asked for a new story, the attempt is recorded
    (bond["story_luna_day"]) right here, in a short write transaction of its own, before the Job is
    returned and its model call dispatched to the lane's thread -- not later, when the answer is stored.
    So a worker that restarts while that call is still in flight does not ask Luna again the same UTC
    day; the fresh `story_job` this function's caller runs after the restart already sees the attempt.

    Bond's final fix wave: the story names every day of an absence but reads the events of the newest
    MAX_STORY_DAYS (m16); its highlights know the promises Mimo kept (m15) and leave out a goal taken up
    after the last day told (I2); and a one-day story for an owner who was seen since that day began is
    for an owner who was there (I4: `present`, told to Luna too)."""
    with world.connect() as db:
        state = read_state(db)
        span = story_span(db, state, now, scale)
        if span is None:
            return None
        first, last, item = span
        owner, level = owner_name(owner_facts(db)), bond_level(state, now)
        until, kept = day_bounds(state, last, scale)[1], kept_promises(db)
        seen = (state.get("bond") or {}).get("seen_at")
        present = first == last and seen is not None and seen >= day_bounds(state, last, scale)[0]
        writer, lead_text, lead_len, lead_last, day = None, None, None, None, first
        if item is not None:
            row = db.execute("SELECT text, data FROM mimo_inbox WHERE id=?", (item,)).fetchone()
            item_data = json.loads(row["data"] or "{}") if row is not None else {}
            writer = item_data.get("writer")
            if writer == "luna":
                day = item_data.get("day", first)
                lead_len = item_data.get("lead", len(row["text"]))  # a fallback for data from before this fix
                lead_text = story_lead(row["text"], lead_len)
                lead_last = item_data.get("lead_last", day)
        if lead_text is not None:
            since_start = max(lead_last + 1, last - MAX_STORY_DAYS + 1)
            events = events_between(db, state, since_start, last, scale)
            found = absence_highlights(events, state, since_start, last, until, kept)
            rules = since_then_story(lead_text, found)
        else:
            events = events_between(db, state, max(first, last - MAX_STORY_DAYS + 1), last, scale)
            found = (absence_highlights(events, state, first, last, until, kept) if last > first
                     else [text for _, text in day_highlights(events, state, until, kept)][:HIGHLIGHTS])
            rules = rules_story(first, found, busiest_of(events), owner, level, last, present)
        remembered = []
        for told in range(last, max(first, last - MAX_STORY_DAYS + 1) - 1, -1):
            remembered += [memory.text for memory in story_memories(db, told, STORY_MEMORIES)]
            if len(remembered) >= MEMORIES_SHOWN:
                break
        remembered = remembered[:MEMORIES_SHOWN]
    luna = item is None and luna_configured(env) and (state.get("bond") or {}).get("story_luna_day") != utc_day(now)
    if luna:
        with SurvivalWorld(world.path).transaction() as write_db:
            attempt = read_state(write_db)
            bond_state(attempt)["story_luna_day"] = utc_day(now)
            write_state(write_db, attempt)
    payload = {"pet": state["name"], "day": day, "last": last, "traits": dict(state.get("traits", {})),
               "mood": round(state["vitals"]["mood"]), "bond": feeling(level), "owner": owner or None,
               "present": present, "highlights": found, "memories": remembered}
    ask = StoryAsk(day, state["bond"]["seen_at"], rules, payload, luna, now, last, item, writer, lead_len, lead_last)
    return Job("story", luna, now, LUNA_TIMEOUT + GIVE_UP_AFTER, lambda env, http: write_story(ask, env, http),
               lambda: StoryAnswer(ask.rules, "rules", "luna: no answer, gave up"),
               lambda target, answer, at: store_story(target, ask, answer, at))


def store_story(world: SurvivalWorld, ask: StoryAsk, answer: StoryAnswer, now: float) -> int | None:
    """Put the story in the inbox, unless one was written for that visit already or Mimo died; or
    (pre-flight 2, the Bond ledger's ruling) grow the visit's unread story, unless it was read or grew
    already. Growing keeps the item's own writer (`ask.writer`), never `answer.writer`'s "rules" (the
    rules always write the growth itself, whole for a rules story or one paragraph for a Luna one), so
    a later dawn still knows whether its lead text is Luna's; a growing Luna item's "lead" (its own text's
    length) and "lead_last" (its own last day) are carried the same way, never recomputed from the grown
    answer (fix round 1, items 1 and 2). Item 3: "owed_from" is cleared once a story is written, its job
    over (bond.py's `visit` sets it; diary.story_span reads it).

    Fix round 2, item 2: growth no longer requires `bond["storied"] == ask.seen` -- a job built by
    story_span to close a gap left by a newer visit is built with `ask.seen` already the newer visit's
    time, while `bond["storied"]` still lags behind it until this very write updates it (growth is
    always a rules-only job, decided and stored in the same synchronous step, so this can never race
    with another write). `story.get("item") == ask.item` and the freshly re-read "last" are still
    checked, so a stale or already-applied job still changes nothing."""
    if answer.error:
        log_once(logger, "story", ModelError(answer.error))
    with world.transaction() as db:
        state = read_state(db)
        bond = bond_state(state)
        if state["died_at"] is not None:
            return None
        last = ask.last if ask.last is not None else ask.day
        writer = ask.writer or answer.writer
        data = {"day": ask.day, "writer": writer}
        if last > ask.day:
            data["last"] = last
        if writer == "luna":
            data["lead"] = ask.lead_len if ask.lead_len is not None else len(answer.text)
            data["lead_last"] = ask.lead_last if ask.lead_last is not None else last
        if ask.item is None:
            if bond.get("storied") == ask.seen:
                return None
            item = post_item(db, now, STORY, answer.text, data)
        else:
            story = bond.get("story") or {}
            if story.get("item") != ask.item or story.get("last", last) >= last:
                return None
            item = ask.item
            if not db.execute("UPDATE mimo_inbox SET text=?, data=? WHERE id=? AND read_at IS NULL",
                              (answer.text, json.dumps(data), item)).rowcount:
                return None
        bond["storied"] = ask.seen
        bond["story"] = {"item": item, "seen": ask.seen, "last": last}
        bond.pop("owed_from", None)
        if ask.luna:
            bond["story_luna_day"] = utc_day(ask.asked_at)
        write_state(db, state)
        return item


LANES["story"].append(story_job)


def diary_entries(db: sqlite3.Connection, limit: int | None = None) -> list[dict]:
    """The stories, newest first ({id, at, day, text, writer, read}), at most `limit` (all with None).
    A world from before Bond has none."""
    try:
        rows = db.execute("SELECT id, at, text, data, read_at FROM mimo_inbox WHERE kind=? ORDER BY id DESC"
                          + (" LIMIT ?" if limit is not None else ""), (STORY, limit) if limit is not None else (STORY,)
                          ).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return []
    entries = []
    for row in rows:
        data = json.loads(row["data"] or "{}")
        entries.append({"id": row["id"], "at": row["at"], "day": data.get("day"), "last": data.get("last"),
                        "text": row["text"], "writer": data.get("writer"), "read": row["read_at"] is not None})
    return entries


def newest_story(db: sqlite3.Connection) -> dict | None:
    """The newest story for /api/mimo, or None."""
    found = diary_entries(db, 1)
    return found[0] if found else None


def life_diary(world: SurvivalWorld, limit: int | None = None) -> list[dict]:
    """Every story a life's Mimo wrote, oldest first, for its memorial; at most `limit`, the newest
    (fix round 1, item 8: life_summary caps what it sends the egg screen's repeated poll). Bond's final
    fix wave (m4): only those are read."""
    with world.connect() as db:
        return list(reversed(diary_entries(db, limit)))

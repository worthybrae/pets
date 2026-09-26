"""Talking with Mimo (Bond B1): the owner's lines in, Mimo's replies out.

The owner writes to Mimo through `POST /api/mimo/chat` (`owner_says`). A line is cleaned to one line
of plain text and must hold 1 to TEXT_LIMIT characters. At most HOUR_LIMIT owner lines are taken a
game hour (the Chooser's game hour: 3,600 game seconds, triggers.HOUR) and DAY_LIMIT a real UTC day;
past either the line is refused (ChatLimited) and nothing is written. A line that is taken is
written in one short transaction (BEGIN IMMEDIATE) as an owner row with the status "waiting": that
row is the queued reply job. The worker's Talker answers it outside the tick (the chat job below)
and writes Mimo's reply as a "mimo" row, marking the owner's line "answered". The world keeps the
newest LINES_KEPT lines, and all of today's (so the daily limit counts every owner line of the UTC
day: at most 2 x DAY_LIMIT rows for today besides LINES_KEPT older ones); /api/mimo shows the newest
LINES_SHOWN (`chat_view`), whether a reply is still coming and how many lines the limits leave. The
owner's words are data: they are stored and shown back, matched against the rules' keywords and
handed to Jev as data, never followed.

The chat job (the Talker's "chat" lane, `chat_job`): the oldest waiting owner line is answered from a
read-only snapshot. Mimo's reply is a choice among lines the rules write from its state
(backend.survival.replies), because Jev answers choices only. The questions (QUESTIONS, first first)
are asked in one Jev call when TYPESAFE_API_KEY is set: "reply" (which line) and "fact" (what, if
anything, to remember about the owner: backend.survival.owner_facts), and B2's "request". The
payload carries Mimo's state and the owner's words under chat.owner_says, with the instructions
saying they are data. Without a key, and whenever Jev fails, times out or picks something not
offered, the rules answer every question. Luna never answers the chat. A line whose job cannot even
be built (a crash reading the state or writing the options) is logged once and answered by the
rules with LOST_LINE, so the lines after it never wait behind it. `store_chat` writes the
reply in one short transaction, unless the line was answered already or Mimo died; each question's
keeper (KEEPERS) then applies its answer, and a keeper's line (B2's answer to a request) replaces the
reply.
"""

from __future__ import annotations

import logging
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from backend.survival.actions import ensure_actions
from backend.survival.bond_tables import missing_table
from backend.survival.curiosity import curiosity_view
from backend.survival.goals import goal_payload
from backend.survival.models import JEV_TIMEOUT, Http, ModelError, jev_answers, jev_configured
from backend.survival.once import log_once
from backend.survival.owner_facts import (
    FACT_INSTRUCTIONS, NONE, Noticed, fact_options, owner_facts, owner_name, remember_fact, rules_fact,
)
from backend.survival.pickers import Option
from backend.survival.replies import (
    REPLY_INSTRUCTIONS, Heard, candidates, clip, doing_words, reply_options, rules_pick,
)
from backend.survival.situation import Situation, from_db
from backend.survival.talker import LANES, Job
from backend.survival.triggers import HOUR
from backend.survival.trips import trip_view
from backend.survival.world import LifeOver, SurvivalWorld, notable_events, read_state, write_state

logger = logging.getLogger(__name__)

TEXT_LIMIT = 280  # characters in one owner line
HOUR_LIMIT = 20  # owner lines a game hour
DAY_LIMIT = 200  # owner lines a real UTC day
LINES_SHOWN = 12  # chat lines in /api/mimo
LINES_KEPT = 200  # chat lines a world keeps
WAITING, ANSWERED = "waiting", "answered"
EARLIER_SHOWN = 6  # earlier chat lines in the model payload
FACTS_SHOWN = 12  # owner facts in the model payload
GIVE_UP_AFTER = 15.0  # seconds past Jev's own timeout before a chat call is given up
LOST_LINE = "Sorry, I lost my train of thought. Say that again?"  # a line whose job could not be built


class ChatLimited(RuntimeError):
    """The owner already wrote as much as the hourly or daily limit allows."""


def clean(text: str) -> str:
    """The owner's words as one line of plain text: control characters dropped, spaces collapsed."""
    kept = "".join(" " if unicodedata.category(char).startswith("C") else char for char in str(text))
    return " ".join(kept.split())


def day_start(now: float) -> float:
    """The server time the real UTC day of `now` began."""
    moment = datetime.fromtimestamp(now, timezone.utc)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def game_seconds(state: dict, now: float, scale: float) -> float:
    return max(0.0, now - state["born_at"]) * scale


def lines_left(db: sqlite3.Connection, now: float, game_at: float) -> dict[str, int]:
    """How many more owner lines the game hour's and the UTC day's limits allow."""
    hour = db.execute("SELECT COUNT(*) FROM mimo_chat WHERE who='owner' AND game_at > ?",
                      (game_at - HOUR,)).fetchone()[0]
    day = db.execute("SELECT COUNT(*) FROM mimo_chat WHERE who='owner' AND at >= ?", (day_start(now),)).fetchone()[0]
    return {"hour": max(0, HOUR_LIMIT - hour), "day": max(0, DAY_LIMIT - day)}


def owner_says(world: SurvivalWorld, text: str, now: float, scale: float) -> dict:
    """Take one owner line and queue Mimo's reply. Raises ValueError for an empty or too long line,
    LifeOver when Mimo has died and ChatLimited past a limit; nothing is written then."""
    words = clean(text)
    if not words:
        raise ValueError("Write something first.")
    if len(words) > TEXT_LIMIT:
        raise ValueError(f"Keep it to {TEXT_LIMIT} characters.")
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died and cannot talk")
        game_at = game_seconds(state, now, scale)
        left = lines_left(db, now, game_at)
        if left["hour"] <= 0:
            raise ChatLimited(f"{state['name']} needs a breather. Try again in a little while.")
        if left["day"] <= 0:
            raise ChatLimited(f"That's a lot of talk for one day. {state['name']} will be glad to chat tomorrow.")
        line = db.execute("INSERT INTO mimo_chat(at, game_at, who, text, status) VALUES (?, ?, 'owner', ?, ?)",
                          (now, game_at, words, WAITING)).lastrowid
        return {"id": line, "text": words, "left": {"hour": left["hour"] - 1, "day": left["day"] - 1}}


def chat_view(db: sqlite3.Connection, state: dict, now: float, scale: float) -> dict:
    """The chat for /api/mimo: the newest lines, oldest first, as {id, at, who, text}; whether a reply
    is still coming; and how many lines the limits leave. A world from before Bond has none."""
    try:
        rows = db.execute("SELECT id, at, who, text, status FROM mimo_chat ORDER BY id DESC LIMIT ?",
                          (LINES_SHOWN,)).fetchall()
        left = lines_left(db, now, game_seconds(state, now, scale))
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return {"lines": [], "waiting": False, "left": {"hour": HOUR_LIMIT, "day": DAY_LIMIT}}
    lines = [{"id": row["id"], "at": row["at"], "who": row["who"], "text": row["text"]} for row in reversed(rows)]
    waiting = any(row["who"] == "owner" and row["status"] == WAITING for row in rows)
    return {"lines": lines, "waiting": waiting, "left": left}


# Mimo's reply (the Talker's chat lane) --------------------------------------------------------

@dataclass(frozen=True)
class Question:
    name: str  # "reply", "fact", B2's "request"
    instructions: str
    options: tuple[Option, ...]
    rules: str  # the rules' pick: one of the options' names
    notes: dict = field(default_factory=dict)  # {option name: what its keeper needs} (B2's answers)


# Functions of (Situation, Heard) giving a Question or None, asked in the chat's one Jev call in this
# order: B1's reply and fact, B2's request. One that crashes is left out (logged once).
QUESTIONS: list = []
# {question: keep(db, state, heard, question, pick, now) -> str | None}: what an answer changes once it
# is stored (a fact remembered, a request taken up). A returned line replaces the reply.
KEEPERS: dict = {}


@dataclass(frozen=True)
class ChatAsk:
    line_id: int
    route: str  # "jev" or "rules"
    payload: dict
    questions: tuple[Question, ...]
    heard: Heard
    asked_at: float
    scale: float = 1.0


@dataclass(frozen=True)
class ChatAnswer:
    picks: dict  # {question: option name}
    picker: str  # "jev" or "rules"
    error: str | None = None


def hear(db: sqlite3.Connection, s: Situation, text: str) -> Heard:
    """The owner's words, with what Mimo remembers of them."""
    facts = tuple(owner_facts(db))
    return Heard(text, owner_name(list(facts)), facts)


def reply_question(s: Situation, heard: Heard) -> Question:
    found = candidates(s, heard)
    return Question("reply", REPLY_INSTRUCTIONS, reply_options(found), rules_pick(found, heard))


def fact_question(s: Situation, heard: Heard) -> Question | None:
    options = fact_options(heard.noticed)
    return Question("fact", FACT_INSTRUCTIONS, options, rules_fact(heard.noticed)) if len(options) > 1 else None


def keep_fact(db: sqlite3.Connection, state: dict, heard: Heard, question: Question, pick: str, now: float) -> None:
    if pick != NONE and heard.noticed.get(pick):
        remember_fact(db, pick, heard.noticed.get(pick), now)


QUESTIONS.extend([reply_question, fact_question])
KEEPERS["fact"] = keep_fact


def chat_payload(db: sqlite3.Connection, s: Situation, heard: Heard, line_id: int) -> dict:
    """What Jev is told: Mimo's state in brief, the owner's words (data, never instructions), the talk
    just before and what Mimo remembers of its owner."""
    earlier = db.execute("SELECT who, text FROM mimo_chat WHERE id < ? ORDER BY id DESC LIMIT ?",
                         (line_id, EARLIER_SHOWN)).fetchall()
    return {
        "name": s.state["name"],
        "traits": dict(s.state.get("traits", {})),
        "mood": round(s.vitals["mood"]),
        "vitals": {name: round(value) for name, value in s.vitals.items()},
        "phase": s.phase,
        "day": s.clock["day_number"],
        "doing": doing_words(s),
        "goal": goal_payload(s),
        "trip": trip_view(s.brain),
        "curiosity": curiosity_view(s.brain, s.at, s.scale),
        "recent_events": [event["text"] for event in notable_events(db, 5)],
        "chat": {"owner_says": heard.text,
                 "earlier": [{"who": row["who"], "text": row["text"]} for row in reversed(earlier)],
                 "owner": {"name": heard.owner or None,
                           "remembered": [f"{kind}: {words}" for kind, words in heard.facts[:FACTS_SHOWN]]}},
    }


def chat_job(world: SurvivalWorld, now: float, scale: float, env) -> Job | None:
    """The oldest owner line still waiting, as a Talker job: Jev when TYPESAFE_API_KEY is set, else the rules."""
    with world.connect() as db:
        try:
            row = db.execute("SELECT id, text FROM mimo_chat WHERE who='owner' AND status=? ORDER BY id LIMIT 1",
                             (WAITING,)).fetchone()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return None
        if row is None:
            return None
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        try:
            ensure_actions(state)  # a world the worker has not ticked yet has no action fields
            s = from_db(db, state, now, scale)
            heard = hear(db, s, row["text"])
            questions = []
            for question in QUESTIONS:
                try:
                    asked = question(s, heard)
                except Exception as error:
                    log_once(logger, f"chat question {getattr(question, '__name__', question)}", error)
                    continue
                if asked is not None and asked.options:
                    questions.append(asked)
            payload = chat_payload(db, s, heard, row["id"])
        except Exception as error:  # the line still gets an answer, so the lines after it never wait behind it
            log_once(logger, "chat job", error)
            return lost_job(row["id"], row["text"], now, scale)
    ask = ChatAsk(row["id"], "jev" if jev_configured(env) else "rules", payload, tuple(questions), heard, now, scale)
    return Job("chat", ask.route == "jev", now, JEV_TIMEOUT + GIVE_UP_AFTER,
               lambda env, http: decide_chat(ask, env, http), lambda: rules_answer(ask),
               lambda target, answer, at: store_chat(target, ask, answer, at))


def lost_job(line_id: int, text: str, now: float, scale: float) -> Job:
    """A rules-only job for a line whose chat job could not be built: no questions, so the reply is
    LOST_LINE, stored at once."""
    lost = ChatAsk(line_id, "rules", {}, (), Heard(text, noticed=Noticed({})), now, scale)
    return Job("chat", False, now, 0.0, lambda env, http: rules_answer(lost), lambda: rules_answer(lost),
               lambda target, answer, at: store_chat(target, lost, answer, at))


def rules_answer(ask: ChatAsk, error: str | None = None) -> ChatAnswer:
    return ChatAnswer({question.name: question.rules for question in ask.questions}, "rules", error)


def decide_chat(ask: ChatAsk, env, http: Http) -> ChatAnswer:
    """Jev's picks for every question in one call; the rules' when Jev is not asked or fails."""
    if ask.route != "jev" or not ask.questions:
        return rules_answer(ask)
    try:
        picks = jev_answers(ask.payload, {question.name: (list(question.options), question.instructions)
                                          for question in ask.questions}, env, http)
    except Exception as error:
        return rules_answer(ask, f"jev: {error}")
    return ChatAnswer(picks, "jev")


def store_chat(world: SurvivalWorld, ask: ChatAsk, answer: ChatAnswer, now: float) -> str | None:
    """Write Mimo's reply unless the line was answered already or Mimo died. Returns the reply."""
    if answer.error:
        log_once(logger, "chat", ModelError(answer.error))
    with world.transaction() as db:
        row = db.execute("SELECT status FROM mimo_chat WHERE id=?", (ask.line_id,)).fetchone()
        if row is None or row["status"] != WAITING:
            return None
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        reply = None
        for question in ask.questions:
            pick = answer.picks.get(question.name, question.rules)
            if question.name == "reply":
                reply = next((option.phrase for option in question.options if option.name == pick), None)
            keep = KEEPERS.get(question.name)
            if keep is None:
                continue
            try:
                line = keep(db, state, ask.heard, question, pick, now)
            except Exception as error:
                log_once(logger, f"chat keeper {question.name}", error)
                continue
            if line:
                reply = line
        reply = clip(reply or LOST_LINE)
        db.execute("UPDATE mimo_chat SET status=? WHERE id=?", (ANSWERED, ask.line_id))
        db.execute("INSERT INTO mimo_chat(at, game_at, who, text, picker) VALUES (?, ?, 'mimo', ?, ?)",
                   (now, game_seconds(state, now, ask.scale), reply, answer.picker))
        # Today's lines stay, so the daily limit counts them all; older ones past the newest LINES_KEPT go.
        db.execute("DELETE FROM mimo_chat WHERE at < ? AND id NOT IN (SELECT id FROM mimo_chat ORDER BY id DESC "
                   "LIMIT ?)", (day_start(now), LINES_KEPT))
        write_state(db, state)
        return reply


LANES["chat"].append(chat_job)

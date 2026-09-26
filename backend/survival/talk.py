"""Talking with Mimo (Bond B1): the owner's lines in, Mimo's replies out.

The owner writes to Mimo through `POST /api/mimo/chat` (`owner_says`). A line is cleaned to one line
of plain text (`clean`) and must hold 1 to TEXT_LIMIT characters (a raw line past RAW_LIMIT is
refused before it is cleaned). At most HOUR_LIMIT owner lines are taken a
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
offered, the rules answer every question. A question with one option (a fact question when only a
strong name was noticed, which is kept anyway) is not asked of Jev. Luna never answers the chat. A
line whose job cannot even
be built (a crash reading the state or writing the options) is logged once and answered by the
rules with LOST_LINE, so the lines after it never wait behind it. `store_chat` writes the
reply in one short transaction, unless the line was answered already or Mimo died; each question's
keeper (KEEPERS) then applies its answer, and a keeper's line (B2's answer to a request) replaces the
reply. The reply's keeper keeps what the chosen line promised (a name, a like), so "I'll remember
that" is always true whatever the fact question's answer; the fact's keeper always keeps a strong
name and then the kind picked.

Hooks for Mind (memory and teaching), so its teaching and recall join the chat without rewriting it:
- R1: a reply line's note reaches REPLY_KEEPERS[topic] when the line is chosen (Question.notes);
- R3: HEARING hooks look at the owner's words once per job, into Heard.context;
- R4: KEEPER_PRECEDENCE decides whose keeper line is said;
- R5: a question Jev answered badly falls back to the rules alone (`decide_chat`);
- R2 and R6 are in backend.survival.replies (a line's own weight, TOLD, several lines a topic); R7,
  the event log's mirrors, is backend.survival.events.
"""

from __future__ import annotations

import copy
import logging
import sqlite3
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from types import MappingProxyType

from backend.survival.actions import ensure_actions
from backend.survival.bond import bond_level, feeling, grow_bond
from backend.survival.bond_tables import missing_table
from backend.survival.curiosity import curiosity_view
from backend.survival.goals import goal_payload
from backend.survival.models import JEV_TIMEOUT, Http, ModelError, jev_choices, jev_configured
from backend.survival.once import log_once
from backend.survival.owner_facts import (
    FACT_INSTRUCTIONS, NONE, Noticed, fact_options, owner_facts, owner_name, remember_fact, rules_fact,
)
from backend.survival.pickers import Option
from backend.survival.replies import (
    REPLY_INSTRUCTIONS, Heard, candidates, clip, doing_words, reply_notes, reply_options, rules_pick, topic_of,
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
JOINER = "\u200d"  # the zero-width joiner inside an emoji family, which cleaning keeps
RAW_LIMIT = 4 * TEXT_LIMIT  # characters a line may have before it is cleaned


class ChatLimited(RuntimeError):
    """The owner already wrote as much as the hourly or daily limit allows."""


def clean(text: str) -> str:
    """The owner's words as one line of plain text: control characters become spaces; other invisible
    characters (format marks such as a right-to-left override or a zero-width space, hidden tag
    characters, lone surrogates) are dropped, but for the joiner inside an emoji family (U+200D); spaces
    collapse. The viewer's cleanDraft (frontend/src/survival/talk.ts) cleans a draft the same way."""
    kept = []
    for char in str(text):
        category = unicodedata.category(char)
        if category == "Cc":
            kept.append(" ")
        elif category not in ("Cf", "Cs") or char == JOINER:
            kept.append(char)
    return " ".join("".join(kept).split())


def day_start(now: float) -> float:
    """The server time the real UTC day of `now` began."""
    moment = datetime.fromtimestamp(now, timezone.utc)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def game_seconds(state: dict, now: float, scale: float) -> float:
    return max(0.0, now - state["born_at"]) * scale


def add_line(db: sqlite3.Connection, state: dict, who: str, text: str, now: float, scale: float,
             picker: str) -> str:
    """Insert one chat line and prune to LINES_KEPT (today's lines all kept too, so the daily limit
    counts them all): the one write `store_chat` and Mind's teaching.say both need (fix round 1,
    Task 6 review, Important 4). Returns the clipped text."""
    text = clip(text)
    db.execute("INSERT INTO mimo_chat(at, game_at, who, text, picker) VALUES (?, ?, ?, ?, ?)",
               (now, game_seconds(state, now, scale), who, text, picker))
    db.execute("DELETE FROM mimo_chat WHERE at < ? AND id NOT IN (SELECT id FROM mimo_chat ORDER BY id DESC "
               "LIMIT ?)", (day_start(now), LINES_KEPT))
    return text


def lines_left(db: sqlite3.Connection, now: float, game_at: float) -> dict[str, int]:
    """How many more owner lines the game hour's and the UTC day's limits allow."""
    hour = db.execute("SELECT COUNT(*) FROM mimo_chat WHERE who='owner' AND game_at > ?",
                      (game_at - HOUR,)).fetchone()[0]
    day = db.execute("SELECT COUNT(*) FROM mimo_chat WHERE who='owner' AND at >= ?", (day_start(now),)).fetchone()[0]
    return {"hour": max(0, HOUR_LIMIT - hour), "day": max(0, DAY_LIMIT - day)}


def owner_says(world: SurvivalWorld, text: str, now: float, scale: float) -> dict:
    """Take one owner line and queue Mimo's reply. Raises ValueError for an empty or too long line,
    LifeOver when Mimo has died and ChatLimited past a limit; nothing is written then."""
    text = str(text)
    if len(text) > RAW_LIMIT:  # refused before the cleaning reads it all
        raise ValueError(f"Keep it to {TEXT_LIMIT} characters.")
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
        grow_bond(state, "chat", now)  # B2: talking grows the bond
        write_state(db, state)
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
    name: str  # "reply", "fact", B2's "request", Mind's "teach"
    instructions: str
    options: tuple[Option, ...]
    rules: str  # the rules' pick: one of the options' names
    # {option name: what its keeper needs}: B2's answers to a request; for "reply", each line's note
    # (Mind hook R1: the memory a recall line quotes), handed to REPLY_KEEPERS.
    notes: dict = field(default_factory=dict)


# Functions of (Situation, Heard) giving a Question or None, asked in the chat's one Jev call in this
# order: B1's reply and fact, B2's request, Mind's teach. One that crashes is left out (logged once).
QUESTIONS: list = []
# {question: keep(db, state, heard, question, pick, now) -> str | None}: what an answer changes once it
# is stored (a fact remembered, a request taken up). Every keeper runs, in the questions' order, each in
# a savepoint of its own (one that crashes is rolled back and logged once). A returned line replaces the
# reply; when several return one, KEEPER_PRECEDENCE says whose line is said (Mind hook R4).
KEEPERS: dict = {}
# Mind hook R4: whose keeper line wins, first first: B2's answer to a request, then Mind's answer to
# teaching, then a line from the reply's own keeper, then the fact's. A question not listed comes after.
KEEPER_PRECEDENCE: list = ["request", "teach", "reply", "fact"]
# Mind hook R1: {reply topic: keep(db, state, heard, note, now) -> str | None}: what saying a line of that
# topic keeps, run by the reply question's keeper with the chosen line's note ("Nice to meet you, Sam!"
# keeps the name; Mind's recall line marks its memory recalled).
REPLY_KEEPERS: dict = {}
# Mind hook R3: {name: hook(db, s, heard) -> value}: what the chat needs to know about the owner's words
# before any question is asked, found once per chat job and put in Heard.context[name] (Mind's recall
# of the words, its shortlist of teachable lessons). One that crashes is left out (logged once).
HEARING: dict = {}


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
    picker: str  # who chose the reply: "jev" or "rules"
    error: str | None = None
    by_jev: tuple = ()  # the questions Jev answered (Mind hook R5: the others fell back to the rules)


def hear(db: sqlite3.Connection, s: Situation, text: str) -> Heard:
    """The owner's words, with what Mimo remembers of them and what the HEARING hooks found (once)."""
    return listened(db, s, heard_from(db, s, text))


def heard_from(db: sqlite3.Connection, s: Situation, text: str) -> Heard:
    """The owner's words with what Mimo remembers of its owner."""
    facts = tuple(owner_facts(db))
    return Heard(text, owner_name(list(facts)), facts, bond_level(s.state, s.at))


def listened(db: sqlite3.Connection, s: Situation, heard: Heard) -> Heard:
    """The words with what each HEARING hook found in them (Heard.context), each hook run once."""
    if not HEARING:
        return heard
    context: dict = {}
    for name, hook in list(HEARING.items()):
        try:
            context[name] = hook(db, s, replace(heard, context=MappingProxyType(dict(context))))
        except Exception as error:
            log_once(logger, f"chat hearing {name}", error)
    return replace(heard, context=MappingProxyType(context))


def reply_question(s: Situation, heard: Heard) -> Question:
    found = candidates(s, heard)
    return Question("reply", REPLY_INSTRUCTIONS, reply_options(found), rules_pick(found, heard), reply_notes(found))


def fact_question(s: Situation, heard: Heard) -> Question | None:
    """What to remember, whenever the words could tell anything. With a strong name alone the only option
    is "none" (the name is kept anyway), and a question with one option is not asked of Jev."""
    if not heard.noticed.found:
        return None
    return Question("fact", FACT_INSTRUCTIONS, fact_options(heard.noticed), rules_fact(heard.noticed))


def keep_fact(db: sqlite3.Connection, state: dict, heard: Heard, question: Question, pick: str, now: float) -> None:
    """A strong name first, always ("my name is Sam"); then the kind Jev or the rules picked."""
    noticed = heard.noticed
    if noticed.strong and noticed.get("name"):
        remember_fact(db, "name", noticed.get("name"), now)
    if pick != NONE and noticed.get(pick):
        remember_fact(db, pick, noticed.get(pick), now)


def keep_reply(db: sqlite3.Connection, state: dict, heard: Heard, question: Question, pick: str,
               now: float) -> str | None:
    """What the chosen line promised, through REPLY_KEEPERS by its topic, with its note (Mind hook R1)."""
    keep = REPLY_KEEPERS.get(topic_of(pick))
    return keep(db, state, heard, question.notes.get(pick, {}), now) if keep else None


def keep_name(db: sqlite3.Connection, state: dict, heard: Heard, note: dict, now: float) -> None:
    """"Nice to meet you, Sam! I'll remember that." keeps the name, strong or weak."""
    if heard.noticed.get("name"):
        remember_fact(db, "name", heard.noticed.get("name"), now)


def keep_like(db: sqlite3.Connection, state: dict, heard: Heard, note: dict, now: float) -> None:
    """"Ooh, the lake? I'll remember that you like it." keeps the like (or the dislike it named)."""
    kind = "likes" if heard.noticed.get("likes") else "dislikes"
    if heard.noticed.get(kind):
        remember_fact(db, kind, heard.noticed.get(kind), now)


QUESTIONS.extend([reply_question, fact_question])
KEEPERS.update({"reply": keep_reply, "fact": keep_fact})
REPLY_KEEPERS.update({"name_ack": keep_name, "like_ack": keep_like})


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
        "bond": feeling(heard.bond),  # B2: how close Mimo feels to its owner
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
    """Jev's picks for every question with a choice to make, in one call; the rules' when Jev is not
    asked or the call fails. A question Jev answered with something not offered falls back to the
    rules alone, and the others keep Jev's picks (Mind hook R5). A question with one option takes it
    without asking."""
    choosing = [question for question in ask.questions if len(question.options) > 1]
    if ask.route != "jev" or not choosing:
        return rules_answer(ask)
    try:
        picks, refused = jev_choices(ask.payload, {question.name: (list(question.options), question.instructions)
                                                   for question in choosing}, env, http)
    except Exception as error:
        return rules_answer(ask, f"jev: {error}")
    error = "; ".join(f"jev {name}: {why}" for name, why in refused.items()) or None
    return ChatAnswer({**rules_answer(ask).picks, **picks}, "jev" if "reply" in picks else "rules", error,
                      tuple(picks))


def keep_answers(db: sqlite3.Connection, state: dict, ask: ChatAsk, answer: ChatAnswer, now: float) -> str | None:
    """Run every question's keeper, each in a savepoint of its own (one that crashes is rolled back,
    its state changes too, and logged once), and return the line that replaces the reply, if any: the
    line of the question that comes first in KEEPER_PRECEDENCE."""
    lines: dict[str, str] = {}
    for question in ask.questions:
        keep = KEEPERS.get(question.name)
        if keep is None:
            continue
        before = copy.deepcopy(state)
        db.execute("SAVEPOINT keeper")
        try:
            line = keep(db, state, ask.heard, question, answer.picks.get(question.name, question.rules), now)
        except Exception as error:
            db.execute("ROLLBACK TO keeper")
            state.clear()
            state.update(before)
            log_once(logger, f"chat keeper {question.name}", error)
            line = None
        db.execute("RELEASE keeper")
        if line:
            lines.setdefault(question.name, line)
    order = ([name for name in KEEPER_PRECEDENCE if name in lines]
             + [name for name in lines if name not in KEEPER_PRECEDENCE])
    return lines[order[0]] if order else None


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
        reply = next((option.phrase for question in ask.questions if question.name == "reply"
                      for option in question.options if option.name == answer.picks.get("reply", question.rules)), None)
        reply = clip(keep_answers(db, state, ask, answer, now) or reply or LOST_LINE)
        db.execute("UPDATE mimo_chat SET status=? WHERE id=?", (ANSWERED, ask.line_id))
        add_line(db, state, "mimo", reply, now, ask.scale, answer.picker)
        write_state(db, state)
        return reply


LANES["chat"].append(chat_job)

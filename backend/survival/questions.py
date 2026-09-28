"""W1: Mimo asks its owner about the wonders it met ("Mimo asks the owner" of the Wild World spec).

Posting (`ask_wonders`, a Talker chore after the mirrors, rules only): the oldest wonder a wild pet met and did
not ask yet (backend.survival.wonders), whose lessons it does not all know, becomes an inbox item of kind "ask"
with data {"ask": "wonder", "wonder", "chips" (their words, in a seeded shuffle), "order" (each shown chip's
place in the wonder's own list), "yes_no", "answer": null, "closed": null}, and the same words are Mimo's line
in the chat (teaching.say), through inbox.asking (the owner's name when Mimo knows it) and replies.in_my_voice.
An "asked" event is logged ("Pip asked you whether red berries are safe to eat."). At most OPEN_MOST (3)
questions are open at once, a new one comes ASK_GAP (5 game minutes) after the last, each wonder is asked once
a life, and a gentle pet never asks. A question whose lessons Mimo comes to know another way (alone, or taught
without being asked) closes as "figured" at the next chore; one answered in the chat closes as "taught".

Answering, always rules and always through Mind's teaching (teaching.teach_lesson: "from you", a told memory,
and "You were right" later):
1. A chip (`answer_question`, what POST /api/mimo/inbox/{id}/answer does with {"choice": n}): its lessons are
   taught at once in one short transaction, the question closes as "taught", "doubted" (a false chip: nothing
   is learned, "Hmm, I'm not sure that's right. I'll be careful.") or "noted" (a chip that teaches nothing), and
   Mimo answers in the chat. LookupError for no such question, ValueError for one closed already or a choice out
   of range, LifeOver when Mimo died (404, 400, 409). Only the chip's index is stored.
2. Yes or no in the chat: while a yes-or-no question is open, an owner line that names no lesson's subject and
   opens with a yes-word or a no-word is read as the newest open one's yes-claim or no-claim
   (teaching.REWORDS: `reworded`). The owner's own words are still stored and shown as they are.
3. Anything else is read by lessons.claims as ever: a lesson taught closes every open question it answers
   (teaching.TAUGHT_HOOKS), and a claim doubted closes as "doubted" the open questions about what it names (the
   chat's "answer" question and its keeper, `keep_answer`).
A wrong answer never teaches: Mimo goes on as if nobody answered (it hesitates, and tastes only when it must).
"""

from __future__ import annotations

import json
import logging
import sqlite3

from backend.survival.clock import clock_at
from backend.survival.inbox import asking, item_of, post_item
from backend.survival.lessons import claims, lesson_keys, tokens, warned
from backend.survival.pickers import Option
from backend.survival.replies import in_my_voice
from backend.survival.talk import KEEPERS, QUESTIONS, Question
from backend.survival.talker import CHORES
from backend.survival.nature import roll
from backend.survival.teaching import REWORDS, TAUGHT_HOOKS, say, teach_lesson
from backend.survival.wild import PREFIX, is_wild, thing, wild_state
from backend.survival.wonders import OPEN_MOST, WONDERS, open_questions
from backend.survival.world import LifeOver, SurvivalWorld, log_event, read_state, write_state

logger = logging.getLogger(__name__)

ASK_GAP = 300.0  # game seconds between two questions
SHUFFLE_CHANNEL = 220
YES = ("yes", "yeah", "yep", "yup", "sure", "of course", "ok", "okay", "fine", "safe")
NO = ("no", "nope", "nah", "don't", "dont", "never", "careful", "poison")
DOUBTED = "Hmm, I'm not sure that's right. I'll be careful."
NOTED = "Okay. Thanks for telling me."
OPEN = "kind='ask' AND json_extract(data, '$.ask')='wonder' AND json_extract(data, '$.closed') IS NULL"


def known_lessons(db: sqlite3.Connection) -> set[str]:
    return {row[0][len(PREFIX):] for row in db.execute(
        "SELECT subject FROM memory_knowledge WHERE fact='lesson' AND subject LIKE 'wild:%'")}


def open_items(db: sqlite3.Connection) -> list[dict]:
    """Mimo's open questions, newest first."""
    try:
        rows = db.execute(f"SELECT * FROM mimo_inbox WHERE {OPEN} ORDER BY id DESC").fetchall()
    except sqlite3.OperationalError:
        return []
    return [item_of(row) for row in rows]


def close(db: sqlite3.Connection, state: dict, item: dict, how: str, now: float, answer: int | None = None) -> None:
    """Close a question: "taught", "doubted", "noted" or "figured"."""
    data = {**item["data"], "closed": how}
    if answer is not None:
        data["answer"] = answer
    db.execute("UPDATE mimo_inbox SET data=?, read_at=COALESCE(read_at, ?) WHERE id=?", (json.dumps(data), now, item["id"]))
    found = wild_state(state)["wonders"].get(item["data"].get("wonder"))
    if found is not None:
        found["closed"] = how


def close_answered(db: sqlite3.Connection, state: dict, lessons: set[str], how: str, now: float) -> bool:
    """Close as `how` every open question some of these lessons answer. True when one closed."""
    closed = False
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and set(wonder.lessons) & lessons:
            close(db, state, item, how, now)
            closed = True
    return closed


def shuffled(state: dict, wonder_id: str, now: float) -> list[int]:
    """The chips' order: a seeded shuffle, so the true one is not always first."""
    count = len(WONDERS[wonder_id].chips)
    return sorted(range(count), key=lambda index: roll(state.get("world_seed", "0"), (index, 0, 0), SHUFFLE_CHANNEL,
                                                         int(now)))


def words_of(wonder_id: str, fill: str) -> str:
    wonder = WONDERS[wonder_id]
    fill = fill or wonder.fill
    return wonder.words.format(where=fill, food=fill, creature=fill)


def ask_wonders(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: close what Mimo figured out, then ask the oldest wonder it met, within the caps."""
    if not is_wild(state):
        return False
    known = known_lessons(db)
    changed = False
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and set(wonder.lessons) <= known:
            close(db, state, item, "figured", now)
            changed = True
    wild = wild_state(state)
    last = wild.get("asked_at")
    if open_questions(db) >= OPEN_MOST or (last is not None and (now - last) * scale < ASK_GAP):
        return changed
    waiting = sorted((found["met_at"], wonder_id) for wonder_id, found in wild["wonders"].items()
                     if wonder_id in WONDERS and found.get("asked_at") is None
                     and not set(WONDERS[wonder_id].lessons) <= known)
    if not waiting:
        return changed
    wonder_id = waiting[0][1]
    wonder, found = WONDERS[wonder_id], wild["wonders"][wonder_id]
    words = in_my_voice(words_of(wonder_id, found.get("fill", "")), state["name"])
    order = shuffled(state, wonder_id, now)
    data = {"ask": "wonder", "wonder": wonder_id, "chips": [wonder.chips[index].words for index in order],
            "order": order, "yes_no": bool(wonder.yes), "answer": None, "closed": None}
    text = asking(db, words)
    found.update(asked_at=now, item=post_item(db, now, "ask", text, data))
    wild["asked_at"] = now
    say(db, state, text, now, scale)
    log_event(db, now, "asked", f"{state['name']} asked you {wonder.asked}.")
    if wonder.items:
        state["last_thought"] = f"I asked about the {wonder.items[0].replace('_', ' ')}. I'll wait a bit before I try one."
    return True


CHORES.append(ask_wonders)


def teach_all(db: sqlite3.Connection, state: dict, lessons: tuple[str, ...], now: float, scale: float) -> list[str]:
    """Teach survival lessons from the owner; the ones new to Mimo."""
    day = clock_at(state["born_at"], now, scale)["day_number"]
    return [name for name in lessons if teach_lesson(db, state, thing(name), now, day)]


def answer_question(world: SurvivalWorld, item_id: int, choice: int, now: float, scale: float = 1.0) -> dict:
    """The owner picks chip `choice` of question `item_id`. Returns the item. See the module docstring."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died")
        row = db.execute("SELECT * FROM mimo_inbox WHERE id=?", (item_id,)).fetchone()
        item = item_of(row) if row is not None else None
        if item is None or item["kind"] != "ask" or item["data"].get("ask") != "wonder":
            raise LookupError("No such question from Mimo")
        if item["data"].get("closed"):
            raise ValueError("That question is answered already.")
        order = item["data"].get("order") or []
        if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < len(order):
            raise ValueError("No such answer.")
        chip = WONDERS[item["data"]["wonder"]].chips[order[choice]]
        if chip.false:
            how, line = "doubted", DOUBTED
        elif chip.teaches:
            teach_all(db, state, chip.teaches, now, scale)
            how = "taught"
            fact = next((lesson for lesson in chip.teaches), None)
            from backend.survival.journal import LESSONS
            line = f"Oh, {LESSONS[thing(fact)].fact[:1].lower()}{LESSONS[thing(fact)].fact[1:]} Thank you for teaching me!"
        else:
            how, line = "noted", NOTED
        fresh = next((found for found in open_items(db) if found["id"] == item_id), item)
        close(db, state, fresh, how, now, choice)
        say(db, state, line, now, scale)
        write_state(db, state)
        row = db.execute("SELECT * FROM mimo_inbox WHERE id=?", (item_id,)).fetchone()
        return item_of(row)


def taught(db: sqlite3.Connection, state: dict, lesson_thing: str, now: float) -> None:
    """teaching.TAUGHT_HOOKS: a survival lesson taught closes every open question it answers."""
    if lesson_thing.startswith(PREFIX):
        close_answered(db, state, {lesson_thing[len(PREFIX):]}, "taught", now)


TAUGHT_HOOKS.append(taught)


# Yes and no in the chat -------------------------------------------------------------------------

def opener(text: str) -> str | None:
    """"yes" or "no" when the words open with a yes-word or a no-word."""
    words = text.lower().strip().lstrip("¡¿\"'").replace("’", "'")
    for answer, found in (("yes", YES), ("no", NO)):
        for word in found:
            if words == word or words.startswith((f"{word} ", f"{word},", f"{word}.", f"{word}!")):
                return answer
    return None


def names_a_subject(text: str) -> bool:
    """The words name what some lesson is about."""
    keys, _, _ = lesson_keys()
    said = set(tokens(text))
    return any(subject <= said for found in keys.values() for subject in found.subjects)


def bound(db: sqlite3.Connection | None, text: str) -> tuple[dict, str] | None:
    """The newest open yes-or-no question a bare yes or no answers, and the claim it reads as."""
    if db is None:
        return None
    answer = opener(text)
    if answer is None or names_a_subject(text):
        return None
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and wonder.yes:
            return item, wonder.yes if answer == "yes" else wonder.no
    return None


def reworded(db: sqlite3.Connection, s, heard) -> str | None:
    """teaching.REWORDS: a bare yes or no, read as the open yes-or-no question's claim."""
    found = bound(db, heard.text) if is_wild(s.state) else None
    return found[1] if found else None


REWORDS.append(reworded)


def named_lessons(text: str) -> set[str]:
    """The survival lessons whose subjects the words name."""
    keys, _, _ = lesson_keys()
    said = set(tokens(warned(text)))
    return {name[len(PREFIX):] for name, found in keys.items()
            if name.startswith(PREFIX) and any(subject <= said for subject in found.subjects)}


def answer_asked(s, heard) -> Question | None:
    """The chat's "answer" question (one option, never asked of a model): the owner's words may answer Mimo's open
    questions, and its keeper closes the ones a doubted claim was about."""
    if not is_wild(s.state) or s.db is None or not open_items(s.db):
        return None
    return Question("answer", "", (Option("close", "close", "", "", 0.0),), "close")


def keep_answer(db: sqlite3.Connection, state: dict, heard, question: Question, pick: str, now: float) -> str | None:
    """The "answer" keeper: a claim doubted closes the open questions about what it names as "doubted", with Mimo's
    careful line."""
    found = bound(db, heard.text)
    text = found[1] if found else heard.text
    if not claims(text).doubtful:
        return None
    about = named_lessons(text)
    if found is not None:
        close(db, state, found[0], "doubted", now)
        return DOUBTED
    return DOUBTED if about and close_answered(db, state, about, "doubted", now) else None


QUESTIONS.append(answer_asked)
KEEPERS["answer"] = keep_answer


def questions_view(db: sqlite3.Connection) -> list[dict]:
    """Mimo's open questions for /api/mimo's inbox: {id, at, text, chips, yes_no}, oldest first."""
    return [{"id": item["id"], "at": item["at"], "text": item["text"], "chips": item["data"].get("chips", []),
             "yes_no": item["data"].get("yes_no", False)} for item in reversed(open_items(db))]

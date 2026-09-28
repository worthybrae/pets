"""W1: Mimo asks its owner about the wonders it met ("Mimo asks the owner" of the Wild World spec).

Posting (`ask_wonders`, a Talker chore after the mirrors, rules only): the oldest wonder a wild pet met and did
not ask yet (backend.survival.wonders), whose lessons it does not all know, becomes an inbox item of kind "ask"
with data {"ask": "wonder", "wonder", "chips" (their words, in a seeded shuffle), "order" (each shown chip's
place in the wonder's own list), "yes_no", "answer": null, "closed": null}, and the same words are Mimo's line
in the chat (teaching.say), through inbox.asking (the owner's name when Mimo knows it) and replies.in_my_voice.
An "asked" event is logged ("Pip asked you whether red berries are safe to eat."). At most OPEN_MOST (3)
questions are open at once, a new one comes ASK_GAP (5 game minutes) after the last, and a gentle pet never
asks. A question whose lessons Mimo comes to know another way (alone, or taught without being asked) closes as
"figured" at the next chore; one answered in the chat closes as "taught".
Set aside (the controller's ruling in W1's final fix wave: stale questions only the owner can answer were
starving every later one): while OPEN_MOST are open and a newer wonder waits, the oldest open question, once it
has been open more than STALE (a game day), closes as "set_aside" ("I stopped waiting on this one." in the
viewer) and its wonder goes back to met and not asked, so it may be asked again later; a wonder is asked at most
ASKED_MOST (2) times a life, and a set-aside wonder holds no taste back (backend.survival.wonders).

Answering, always rules and always through Mind's teaching (teaching.teach_lesson: "from you", a told memory,
and "You were right" later):
1. A chip (`answer_question`, what POST /api/mimo/inbox/{id}/answer does with {"choice": n}): its lessons are
   taught at once in one short transaction, the question closes as "taught", "doubted" (a false chip: nothing
   is learned, "Hmm, I'm not sure that's right. I'll be careful.") or "noted" (a chip that teaches nothing), and
   Mimo answers in the chat. inbox.NoSuchQuestion (a LookupError) for no such question, ValueError for one closed
   already or a choice out of range, LifeOver when Mimo died (404, 400, 409). Only the chip's index is stored.
2. Yes or no in the chat: while a yes-or-no question is open, an owner line that names no lesson's subject and
   opens with a yes-word or a no-word is read as the newest open one's yes-claim or no-claim
   (teaching.REWORDS: `reworded`). The owner's own words are still stored and shown as they are. Fix round 1
   (the controller's ruling): "ok", "okay" and "fine" are no yes-words, and a line that opens with an idiom
   ("no idea", "not sure", "never mind", "don't worry", IDIOMS) never binds. W1's final fix wave: the line is
   bound once, when it is heard (teaching's HEARING hook ANSWER records the question and its claim), and the
   chat's "answer" keeper (`keep_answer`) closes only that question, while it is still open: "doubted" when its
   claim is doubted, "taught" once what it taught is known. Bound again after the teach keeper had closed it,
   one "yes" used to answer the next open question too.
3. Anything else is read by lessons.claims as ever: a lesson taught closes the open questions it answers whose
   lessons Mimo now all knows (teaching.TAUGHT_HOOKS; W1's final fix wave: never one that needs another lesson
   too), and a claim doubted closes as "doubted" the open questions about what it names (`keep_answer`).
A wrong answer never teaches: Mimo goes on as if nobody answered (it hesitates, and tastes only when it must).
"""

from __future__ import annotations

import json
import logging
import sqlite3

from backend.survival.bond_tables import open_question_rows
from backend.survival.clock import DAY_SECONDS, clock_at
from backend.survival.goals import lower
from backend.survival.inbox import NoSuchQuestion, asking, item_of, post_item
from backend.survival.journal import LESSONS
from backend.survival.lessons import claims, lesson_keys, tokens, warned
from backend.survival.pickers import Option
from backend.survival.replies import clip, in_my_voice
from backend.survival.talk import KEEPERS, QUESTIONS, Question
from backend.survival.talker import CHORES
from backend.survival.nature import roll
from backend.survival.teaching import ANSWER, REWORDS, TAUGHT_HOOKS, Reworded, say, teach_lesson
from backend.survival.wild import BY_NAME, PREFIX, is_wild, thing, wild_state
from backend.survival.wonders import OPEN_MOST, SET_ASIDE, WONDERS, open_questions
from backend.survival.world import LifeOver, SurvivalWorld, log_event, read_state, write_state

logger = logging.getLogger(__name__)

ASK_GAP = 300.0  # game seconds between two questions
ASKED_MOST = 2  # times a wonder is asked in a life (the final fix wave's ruling: once, and once more if set aside)
STALE = DAY_SECONDS  # game seconds a question is open before a newer wonder may set it aside
SHUFFLE_CHANNEL = 220
# The controller's ruling (fix round 1): "ok", "okay" and "fine" are acknowledgements, not answers ("Ok, I'm
# back!"), and a line that opens with one of IDIOMS never binds ("No idea" answers nothing).
YES = ("yes", "yeah", "yep", "yup", "sure", "of course", "safe")
NO = ("no", "nope", "nah", "don't", "dont", "never", "careful", "poison")
IDIOMS = ("no idea", "no clue", "no problem", "no worries", "not sure", "don't know", "dont know", "never mind",
          "nevermind", "don't worry", "dont worry")
DOUBTED = "Hmm, I'm not sure that's right. I'll be careful."
NOTED = "Okay. Thanks for telling me."


def known_lessons(db: sqlite3.Connection) -> set[str]:
    return {row[0][len(PREFIX):] for row in db.execute(
        "SELECT subject FROM memory_knowledge WHERE fact='lesson' AND subject LIKE 'wild:%'")}


def open_items(db: sqlite3.Connection) -> list[dict]:
    """Mimo's open questions, newest first (a world without an inbox has none; any other error is raised)."""
    return [item_of(row) for row in open_question_rows(db)]


def close(db: sqlite3.Connection, state: dict, item: dict, how: str, now: float, answer: int | None = None) -> None:
    """Close a question: "taught", "doubted", "noted", "figured" or SET_ASIDE."""
    data = {**item["data"], "closed": how}
    if answer is not None:
        data["answer"] = answer
    db.execute("UPDATE mimo_inbox SET data=?, read_at=COALESCE(read_at, ?) WHERE id=?", (json.dumps(data), now, item["id"]))
    found = wild_state(state)["wonders"].get(item["data"].get("wonder"))
    if found is not None:
        found["closed"] = how


def close_answered(db: sqlite3.Connection, state: dict, lessons: set[str], how: str, now: float) -> bool:
    """Close as `how` every open question some of these lessons answer (a claim doubted: `keep_answer`). True when
    one closed."""
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


def asks_of(found: dict) -> int:
    """How many times a wonder was asked (a save from before the final fix wave counts an asked one once)."""
    return found.get("asks", 0 if found.get("asked_at") is None else 1)


def set_aside(db: sqlite3.Connection, state: dict, waiting: list[tuple], now: float, scale: float) -> str | None:
    """The ruling of W1's final fix wave: with OPEN_MOST questions open and a wonder newer than the oldest one's
    waiting, that oldest question, open more than STALE, closes as SET_ASIDE and its wonder goes back to met and
    not asked. The wonder set aside, or None."""
    items = open_items(db)  # newest first
    if len(items) < OPEN_MOST:
        return None
    oldest = items[-1]
    wonder_id = oldest["data"].get("wonder")
    found = wild_state(state)["wonders"].get(wonder_id)
    if found is None or (now - oldest["at"]) * scale <= STALE:
        return None
    if not any(met > found["met_at"] for _, met, _ in waiting):  # no newer wonder waits
        return None
    close(db, state, oldest, SET_ASIDE, now)
    found.update(asked_at=None, item=None)
    return wonder_id


def ask_wonders(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: close what Mimo figured out, set a stale question aside for a newer wonder, then ask the wonder
    that waits longest (one never asked before one set aside), within the caps."""
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
    if last is not None and (now - last) * scale < ASK_GAP:
        return changed
    waiting = sorted((asks_of(found), found["met_at"], wonder_id) for wonder_id, found in wild["wonders"].items()
                     if wonder_id in WONDERS and found.get("asked_at") is None and asks_of(found) < ASKED_MOST
                     and not set(WONDERS[wonder_id].lessons) <= known)
    if waiting and open_questions(db) >= OPEN_MOST:
        aside = set_aside(db, state, waiting, now, scale)
        if aside is None:
            return changed
        changed = True
        waiting = [entry for entry in waiting if entry[2] != aside]  # the newer wonder is asked, not this one again
    if not waiting:
        return changed
    wonder_id = waiting[0][2]
    wonder, found = WONDERS[wonder_id], wild["wonders"][wonder_id]
    words = in_my_voice(words_of(wonder_id, found.get("fill", "")), state["name"])
    order = shuffled(state, wonder_id, now)
    data = {"ask": "wonder", "wonder": wonder_id, "chips": [wonder.chips[index].words for index in order],
            "order": order, "yes_no": bool(wonder.yes), "answer": None, "closed": None}
    text = asking(db, words)
    found.update(asked_at=now, item=post_item(db, now, "ask", text, data), closed=None, asks=asks_of(found) + 1)
    wild["asked_at"] = now
    say(db, state, text, now, scale)
    log_event(db, now, "asked", f"{state['name']} asked you {wonder.asked}.")
    if wonder.items:  # "I asked about the red berries." (fix round 1: the lesson's own words, as the spec says)
        about = BY_NAME[wonder.lessons[0]].words
        state["last_thought"] = f"I asked about the {about}. I'll wait a bit before I try one."
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
            raise NoSuchQuestion("No such question from Mimo")
        if item["data"].get("closed"):
            raise ValueError("That question is answered already.")
        order = item["data"].get("order") or []
        if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < len(order):
            raise ValueError("No such answer.")
        chip = WONDERS[item["data"]["wonder"]].chips[order[choice]]
        if chip.false:
            how, line = "doubted", DOUBTED
        elif chip.teaches:
            # Fix round 1: the thanks name the first lesson Mimo learned; one it knew already is "I know that one!",
            # as teaching.keep_teach says it.
            learned = teach_all(db, state, chip.teaches, now, scale)
            how = "taught"
            if learned:
                line = clip(f"Oh, {lower(LESSONS[thing(learned[0])].fact)} Thank you for teaching me!")
            else:
                line = clip(f"I know that one! {LESSONS[thing(chip.teaches[0])].fact}")
        else:
            how, line = "noted", NOTED
        fresh = next((found for found in open_items(db) if found["id"] == item_id), item)
        close(db, state, fresh, how, now, choice)
        say(db, state, line, now, scale)
        write_state(db, state)
        row = db.execute("SELECT * FROM mimo_inbox WHERE id=?", (item_id,)).fetchone()
        return item_of(row)


def taught(db: sqlite3.Connection, state: dict, lesson_thing: str, now: float) -> None:
    """teaching.TAUGHT_HOOKS: a survival lesson taught closes, as "taught", every open question it answers whose
    lessons Mimo now all knows (W1's final fix wave: never one that needs another lesson too, as the figured
    close in `ask_wonders`; a chip or a bare yes or no closes the question it answered itself)."""
    if not lesson_thing.startswith(PREFIX):
        return
    name, known = lesson_thing[len(PREFIX):], known_lessons(db)
    for item in open_items(db):
        wonder = WONDERS.get(item["data"].get("wonder"))
        if wonder is not None and name in wonder.lessons and set(wonder.lessons) <= known:
            close(db, state, item, "taught", now)


TAUGHT_HOOKS.append(taught)


# Yes and no in the chat -------------------------------------------------------------------------

def opener(text: str) -> str | None:
    """"yes" or "no" when the words open with a yes-word or a no-word, and not with one of IDIOMS."""
    words = text.lower().strip().lstrip("¡¿\"'").replace("’", "'")
    if words.startswith(IDIOMS):
        return None
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


def reworded(db: sqlite3.Connection, s, heard) -> Reworded | None:
    """teaching.REWORDS: a bare yes or no, read as the open yes-or-no question's claim, with that question."""
    found = bound(db, heard.text) if is_wild(s.state) else None
    return Reworded(found[1], found[0]["id"]) if found else None


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
    """The "answer" keeper. A bare yes or no answers the question it was bound to when the line was heard
    (teaching's HEARING hook ANSWER), never one bound again here, after the teach keeper may have closed it: that
    question, while it is still open, closes as "doubted" with Mimo's careful line when its claim is doubted, or
    as "taught" once a lesson the claim teaches is known. Any other claim doubted closes the open questions about
    what it names as "doubted", with the careful line."""
    found = heard.context.get(ANSWER)
    if isinstance(found, Reworded) and found.item is not None:
        item = next((item for item in open_items(db) if item["id"] == found.item), None)
        if item is None:
            return None
        verdict = claims(found.text)
        if verdict.doubtful:
            close(db, state, item, "doubted", now)
            return DOUBTED
        if {thing(name) for name in known_lessons(db)} & set(verdict.taught):
            close(db, state, item, "taught", now)
        return None
    if not claims(heard.text).doubtful:
        return None
    about = named_lessons(heard.text)
    return DOUBTED if about and close_answered(db, state, about, "doubted", now) else None


QUESTIONS.append(answer_asked)
KEEPERS["answer"] = keep_answer


def questions_view(db: sqlite3.Connection) -> list[dict]:
    """Mimo's open questions for /api/mimo's inbox: {id, at, text, chips, yes_no}, oldest first."""
    return [{"id": item["id"], "at": item["at"], "text": item["text"], "chips": item["data"].get("chips", []),
             "yes_no": item["data"].get("yes_no", False)} for item in reversed(open_items(db))]

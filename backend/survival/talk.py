"""Talking with Mimo (Bond B1): the owner's lines in, Mimo's replies out.

The owner writes to Mimo through `POST /api/mimo/chat` (`owner_says`). A line is cleaned to one line
of plain text and must hold 1 to TEXT_LIMIT characters. At most HOUR_LIMIT owner lines are taken a
game hour (the Chooser's game hour: 3,600 game seconds, triggers.HOUR) and DAY_LIMIT a real UTC day;
past either the line is refused (ChatLimited) and nothing is written. A line that is taken is
written in one short transaction (BEGIN IMMEDIATE) as an owner row with the status "waiting": that
row is the queued reply job. The worker's Talker answers it outside the tick (the chat job below)
and writes Mimo's reply as a "mimo" row, marking the owner's line "answered". The world keeps the
newest LINES_KEPT lines; /api/mimo shows the newest LINES_SHOWN (`chat_view`), whether a reply is
still coming and how many lines the limits leave. The owner's words are data: they are stored and
shown back, matched against the rules' keywords and handed to Jev as data, never followed.
"""

from __future__ import annotations

import sqlite3
import unicodedata
from datetime import datetime, timezone

from backend.survival.bond_tables import missing_table
from backend.survival.triggers import HOUR
from backend.survival.world import LifeOver, SurvivalWorld, read_state

TEXT_LIMIT = 280  # characters in one owner line
HOUR_LIMIT = 20  # owner lines a game hour
DAY_LIMIT = 200  # owner lines a real UTC day
LINES_SHOWN = 12  # chat lines in /api/mimo
LINES_KEPT = 200  # chat lines a world keeps
WAITING, ANSWERED = "waiting", "answered"


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

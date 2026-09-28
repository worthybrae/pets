"""Bond's tables in each life's world database (docs/superpowers/specs/2026-09-25-bond-design.md).

- mimo_chat: the talk between the owner and Mimo, one row a line, oldest first: who said it
  ("owner" or "mimo"), when (server time, and game seconds since the life began, for the game-hour
  limit), the words, and for an owner line its reply's status: "waiting" until the worker's Talker
  answers it, then "answered" (backend.survival.talk). A Mimo line names who chose it ("jev" or
  "rules").
- mimo_inbox (B2): what Mimo tells the owner, one row a message: when, its kind, its words, JSON
  data and when the owner read it (null while unread) (backend.survival.inbox).

`create_bond_tables` runs inside world.create_world_tables' BEGIN IMMEDIATE, so a world from before
Bond gains the tables the first time it is opened for writing; running it again changes nothing.
A world only ever read (an archive) may lack them: every reader treats a missing table as empty.

W1: Mimo's open questions (backend.survival.questions) are the inbox items OPEN_QUESTION picks, read by one
helper (`open_question_rows`) for the questions and for wonders' hesitation; the inbox never prunes them.
"""

from __future__ import annotations

import sqlite3

# W1: one of Mimo's questions, asked and not yet closed (at most wonders.OPEN_MOST at a time).
OPEN_QUESTION = "kind = 'ask' AND json_extract(data, '$.ask') = 'wonder' AND json_extract(data, '$.closed') IS NULL"


def create_bond_tables(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS mimo_chat (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, "
               "game_at REAL NOT NULL, who TEXT NOT NULL, text TEXT NOT NULL, status TEXT NOT NULL DEFAULT '', "
               "picker TEXT NOT NULL DEFAULT '')")
    db.execute("CREATE INDEX IF NOT EXISTS mimo_chat_by_status ON mimo_chat(status, id)")
    db.execute("CREATE TABLE IF NOT EXISTS mimo_inbox (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, "
               "kind TEXT NOT NULL, text TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', read_at REAL)")
    db.execute("CREATE INDEX IF NOT EXISTS mimo_inbox_by_kind ON mimo_inbox(kind, id)")


def missing_table(error: sqlite3.OperationalError) -> bool:
    """A read of a world from before Bond (an archive, or a world not yet opened for writing)."""
    return "no such table" in str(error)


def open_question_rows(db: sqlite3.Connection) -> list:
    """W1: the inbox rows of Mimo's open questions, newest first. A world from before Bond has none; any other
    error is raised."""
    try:
        return db.execute(f"SELECT * FROM mimo_inbox WHERE {OPEN_QUESTION} ORDER BY id DESC").fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return []

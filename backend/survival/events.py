"""The event log's mirrors (survival core): what follows Mimo's event log as it grows.

Mimo's notable moments are rows in the world's mimo_events (world.log_event). Other parts of Mimo
follow that log by event kind, each at its own pace: Mind's memory stream (M1) makes memories of
events, and Bond's inbox (B2) turns a goal reached or a first sighting into a message. Each one, a
consumer, registers its writers here by kind (`mirror`), into MIRRORS: {kind: [Mirror(consumer,
write)]}, one writer a consumer and kind.

`mirror_events` runs them. For each consumer it reads the events logged since that consumer last
looked (its own cursor: state["mirrored"][consumer], the id of the last event it saw), oldest first,
at most MIRROR_BATCH a run, and only of the kinds that consumer follows (an index on
mimo_events(kind, id) keeps that search cheap even across a long stretch it does not follow). Each
consumer reads its own batch (pre-flight 2, M8), so one far behind (Mind's memory going back through
a long life after a deploy) never holds back another's news; the batches are run together, oldest
event first, each event handed to the writers of the consumers that read it. A run finds the newest
event first: when a consumer's batch holds fewer than MIRROR_BATCH events, it has read every event it
follows up to that newest id, so its cursor catches up to it at once, and a stretch it does not
follow, however long, is passed once and never rescanned. A consumer seen for the first time starts
at the newest event, so old news is never delivered. A writer that crashes is rolled back (its
database writes and state changes), logged once and passed over, so no consumer stalls on it and the
others go on. It is a rules-only chore: the worker's Talker runs it every few seconds, outside the tick
(backend.survival.talker.CHORES), in a transaction of its own. Nothing is written while nothing is
registered.
"""

from __future__ import annotations

import copy
import logging
import sqlite3
from dataclasses import dataclass
from typing import Callable

from backend.survival.once import log_once

logger = logging.getLogger(__name__)

MIRROR_BATCH = 200  # events one run reads at most
CURSORS = "mirrored"  # the state's {consumer: the id of the last event it saw}


@dataclass(frozen=True)
class Mirror:
    consumer: str  # whose cursor it follows: "memory" (Mind M1), "inbox" (Bond B2)
    write: Callable  # write(db, state, event, now, scale) -> None, event = {"id", "at", "kind", "text"}


# {event kind: [Mirror]}: who follows events of that kind, and how.
MIRRORS: dict[str, list[Mirror]] = {}


def mirror(consumer: str, kind: str, write: Callable) -> None:
    """Have `write` follow the events of `kind` for `consumer`. A consumer has one writer a kind:
    registering again replaces it (B2's requests replace the inbox's plain goal report)."""
    MIRRORS[kind] = [entry for entry in MIRRORS.get(kind, []) if entry.consumer != consumer] + [Mirror(consumer, write)]


def consumers() -> list[str]:
    return sorted({entry.consumer for entries in MIRRORS.values() for entry in entries})


def mirror_events(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: every consumer's writers over the events logged since that consumer last looked, each
    consumer from its own cursor (pre-flight 2, M8). True when it changed the state (a cursor moved,
    or a writer changed it)."""
    names = consumers()
    if not names:
        return False
    cursors = state.setdefault(CURSORS, {})
    changed = False
    newest = db.execute("SELECT COALESCE(MAX(id), 0) FROM mimo_events").fetchone()[0]
    for name in names:
        if name not in cursors:
            cursors[name] = newest
            changed = True
    batches: dict[str, list] = {}
    for name in names:
        kinds = sorted(kind for kind, entries in MIRRORS.items() if any(entry.consumer == name for entry in entries))
        marks = ",".join("?" * len(kinds))
        batches[name] = db.execute(f"SELECT id, at, kind, text FROM mimo_events WHERE id > ? AND kind IN ({marks}) "
                                   "ORDER BY id LIMIT ?", (cursors[name], *kinds, MIRROR_BATCH)).fetchall()
    events: dict[int, dict] = {}
    readers: dict[int, set[str]] = {}
    for name, rows in batches.items():
        for row in rows:
            events.setdefault(row["id"], dict(row))
            readers.setdefault(row["id"], set()).add(name)
    for number in sorted(events):
        event = events[number]
        for entry in list(MIRRORS.get(event["kind"], ())):
            if entry.consumer not in readers[number] or number <= state.get(CURSORS, {}).get(entry.consumer, 0):
                continue
            before = copy.deepcopy(state)
            db.execute("SAVEPOINT mirror")
            try:
                entry.write(db, state, event, now, scale)
            except Exception as error:
                db.execute("ROLLBACK TO mirror")
                state.clear()
                state.update(before)
                log_once(logger, f"mirror {entry.consumer} {event['kind']}", error)
            db.execute("RELEASE mirror")
        cursors = state.setdefault(CURSORS, {})
        for name in readers[number]:
            cursors[name] = max(cursors.get(name, 0), number)
        changed = True
    cursors = state.setdefault(CURSORS, {})
    for name in names:
        # Fewer than a batch matched for this consumer: every event it follows up to `newest` (read above,
        # before its query, so nothing could have been logged past it since) has been seen, so its cursor
        # catches up at once and a stretch it does not follow is never read again, however long.
        if len(batches[name]) < MIRROR_BATCH and cursors.get(name, 0) < newest:
            cursors[name] = newest
            changed = True
    return changed

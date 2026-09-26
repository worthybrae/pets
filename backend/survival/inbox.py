"""Mimo's inbox (Bond B2): what Mimo tells its owner, in the world's mimo_inbox.

An item is one message: when, its kind, its words, JSON data, and when the owner read it. Kinds:
- "ask": Mimo asks the owner for something (the chores `ask_for_care` and `ask_to_name`): a snack
  when it is really hungry (hunger under ASK_HUNGER) or a bandage when it is badly hurt (health
  under ASK_HEALTH), each at most once a real UTC day and only while today's is still there to
  give; or a name for a place it found (NAMEABLE: a cave, a lake, a grove, a pasture), found since
  the inbox started, at most one a game day. The owner answers a naming ask with a name
  (`name_place`): Mimo remembers it on the place and as an owner fact ("named"), and says thanks in
  the chat.
- "report": Mimo reports a milestone in its own words: a goal reached, a home built (`report`, from
  the event log) and (backend.survival.requests) a promise kept.
- B3 adds "found" and "danger" from the event log, and "story" (the daily story, backend.survival.diary).
Items come from rules only, never from model text, written by the Talker's chores outside the tick.
The inbox follows the event log as the consumer "inbox" (CONSUMER) of the survival core's mirrors
(backend.survival.events.mirror: one writer a kind, a cursor of its own in state["mirrored"]["inbox"],
run by the Talker's first chore); a consumer seen for the first time starts at the newest event, so
old news is never delivered. The
inbox keeps ITEMS_KEPT items besides the stories, which it keeps for the diary. /api/mimo shows how
many are unread and the newest unread few (`inbox_view`); GET /api/mimo/inbox lists the newest
ITEMS_SHOWN; the owner marks them read up to an id (`mark_read`).

Bond's final fix wave:
- I7: the inbox's limits hold at the production scale, where a game day is a real hour. At most one
  naming ask waits unanswered at a time (a newer one, about the newest place found, replaces one left
  unanswered STALE_ASK real seconds); an unanswered naming ask is never pruned, and the prune takes read
  items before unread ones; the viewer marks read only the items it listed (`mark_ids`). A repeating goal
  is reported the first time, then at most once a real UTC day (backend.survival.requests).
- m7: two places with the same words are told apart ("a lake far south of home", "another lake south of
  home"). m8: a named place is remembered in words that read well ("a lake south of home, called Echo
  Hollow"), and Mind keeps it as a told memory. m9: a name far too long is refused before it is cleaned.
- m14: a care ask is answered (its data's "done", and read) once that UTC day's care is given.
- m10, m12: marking read writes nothing when nothing listed is unread, and never for a pet that died.

Bond follow-up (N1): GET /api/mimo/inbox lists every unread item first (`inbox_listing`, at most
UNREAD_LISTED), then the newest read ones, so opening the inbox can always clear it.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3

from backend.survival.bond import REAL_DAY, bond_state, utc_day
from backend.survival.bond_tables import missing_table
from backend.survival.care import care_remaining
from backend.survival.clock import DAY_SECONDS
from backend.survival.events import mirror
from backend.survival.exploring import compass
from backend.survival.memory import places, update_place
from backend.survival.owner_facts import owner_facts, owner_name, remember_fact
from backend.survival.replies import in_my_voice
from backend.survival.talker import CHORES
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state

ITEMS_KEPT = 200  # items besides the stories
ITEMS_SHOWN = 30  # items GET /api/mimo/inbox lists
NEWEST_SHOWN = 5  # unread items in /api/mimo, for the viewer's notifications
CONSUMER = "inbox"  # the inbox's name on the event log's mirrors: its cursor is state["mirrored"]["inbox"]
ASK_HUNGER = 20.0
ASK_HEALTH = 35.0
NAMEABLE = {"cave": "a cave", "water": "a lake", "grove": "a grove", "pasture": "a pasture"}
NAME_LIMIT = 24
PLACE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 '\-]*$")
STORY = "story"
STALE_ASK = REAL_DAY  # real seconds a naming ask waits unanswered before a newer one may replace it (I7)
FAR = 64.0  # blocks from home from which a place is "far" (m7)
UNREAD_LISTED = 500  # unread items the inbox lists at most (N1): more than ITEMS_KEPT, stories and waiting asks
MARKED_AT_MOST = UNREAD_LISTED  # ids one call marks read at most
# A naming ask still waiting for its answer (I7): never pruned, and at most one at a time.
WAITING_ASK = "kind = 'ask' AND json_extract(data, '$.ask') = 'name' AND json_extract(data, '$.answer') IS NULL"
# What the prune may take: never a story (the diary keeps them) nor a naming ask still waiting.
PRUNABLE = f"kind != '{STORY}' AND NOT ({WAITING_ASK})"


def post_item(db: sqlite3.Connection, at: float, kind: str, text: str, data: dict | None = None) -> int:
    """Put a message in the inbox; past ITEMS_KEPT (stories and naming asks still waiting aside) the
    oldest go, the read ones first (I7)."""
    item = db.execute("INSERT INTO mimo_inbox(at, kind, text, data) VALUES (?, ?, ?, ?)",
                      (at, kind, text, json.dumps(data or {}))).lastrowid
    excess = db.execute(f"SELECT COUNT(*) FROM mimo_inbox WHERE {PRUNABLE}").fetchone()[0] - ITEMS_KEPT
    if excess > 0:
        db.execute(f"DELETE FROM mimo_inbox WHERE id IN (SELECT id FROM mimo_inbox WHERE {PRUNABLE} "
                   "ORDER BY read_at IS NULL, id LIMIT ?)", (excess,))
    return item


def item_of(row) -> dict:
    return {"id": row["id"], "at": row["at"], "kind": row["kind"], "text": row["text"],
            "data": json.loads(row["data"] or "{}"), "read": row["read_at"] is not None}


def inbox_items(db: sqlite3.Connection, limit: int = ITEMS_SHOWN, unread_only: bool = False) -> list[dict]:
    """The newest items, newest first. A world from before the inbox has none."""
    try:
        rows = db.execute("SELECT * FROM mimo_inbox" + (" WHERE read_at IS NULL" if unread_only else "")
                          + " ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return []
    return [item_of(row) for row in rows]


def inbox_listing(db: sqlite3.Connection) -> list[dict]:
    """What the inbox panel lists (N1): every unread item, newest first (at most UNREAD_LISTED), then the
    newest ITEMS_SHOWN read ones. A world from before the inbox has none."""
    try:
        fresh = db.execute("SELECT * FROM mimo_inbox WHERE read_at IS NULL ORDER BY id DESC LIMIT ?",
                           (UNREAD_LISTED,)).fetchall()
        seen = db.execute("SELECT * FROM mimo_inbox WHERE read_at IS NOT NULL ORDER BY id DESC LIMIT ?",
                          (ITEMS_SHOWN,)).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return []
    return [item_of(row) for row in (*fresh, *seen)]


def unread(db: sqlite3.Connection) -> int:
    try:
        return db.execute("SELECT COUNT(*) FROM mimo_inbox WHERE read_at IS NULL").fetchone()[0]
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return 0


def inbox_view(db: sqlite3.Connection) -> dict:
    """The inbox for /api/mimo: how many items are unread and the newest unread few."""
    return {"unread": unread(db), "newest": inbox_items(db, NEWEST_SHOWN, unread_only=True)}


def marking(world: SurvivalWorld, where: str, args: tuple, now: float) -> int:
    """Mark the unread items `where` says read; returns how many are still unread. Nothing is written
    when none of them is unread (m10: a stuck client's calls never take the write lock), and nothing for
    a pet that died (m12: LifeOver)."""
    with world.connect() as db:
        if read_state(db)["died_at"] is not None:
            raise LifeOver("Mimo has died")
        if not db.execute(f"SELECT 1 FROM mimo_inbox WHERE ({where}) AND read_at IS NULL LIMIT 1", args).fetchone():
            return unread(db)
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died")
        db.execute(f"UPDATE mimo_inbox SET read_at=? WHERE ({where}) AND read_at IS NULL", (now, *args))
        return unread(db)


def mark_read(world: SurvivalWorld, up_to: int, now: float) -> int:
    """Mark every item up to `up_to` read. Returns how many are still unread."""
    return marking(world, "id <= ?", (up_to,), now)


def mark_ids(world: SurvivalWorld, ids: list[int], now: float) -> int:
    """Mark the items with these ids read, the ones the viewer listed (I7), at most MARKED_AT_MOST.
    Returns how many are still unread."""
    ids = [int(item) for item in ids][:MARKED_AT_MOST]
    if not ids:
        with world.connect() as db:
            return unread(db)
    return marking(world, f"id IN ({','.join('?' * len(ids))})", tuple(ids), now)


def asking(db: sqlite3.Connection, words: str) -> str:
    """Words to the owner, by name when Mimo knows it: "Sam, I found a cave."."""
    name = owner_name(owner_facts(db))
    return f"{name}, {words}" if name else words


# The mirror: milestones from the event log ----------------------------------------------------

def report(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A milestone in Mimo's own voice (Bond's final fix wave, I1: "I finished building my Round Cottage
    and moved in.", never the pet's name)."""
    post_item(db, event["at"], "report", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


# The inbox's writers on the event log's mirrors (backend.survival.events): one a kind, each run in a
# savepoint of its own there (one that crashes is rolled back, logged once and passed over, so the
# inbox never stalls on it). B2's requests replace the goal's (a promise kept); B3's moments add theirs.
for _kind in ("goal", "built"):
    mirror(CONSUMER, _kind, report)


# Mimo's asks ----------------------------------------------------------------------------------

def ask_for_care(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: a snack when Mimo is really hungry, a bandage when it is badly hurt, each at most
    once a UTC day and only while today's is still there to give. Bond's final fix wave (m14): an ask
    of today's is answered (its data's "done", and read) once today's care of its kind is given."""
    asked = bond_state(state).setdefault("asked", {})
    today, left, changed = utc_day(now), care_remaining(state, now), False
    for kind, vital, below, words in (("snack", "hunger", ASK_HUNGER, "I'm really hungry. Could you spare a snack?"),
                                      ("bandage", "health", ASK_HEALTH, "I got badly hurt. Could you bandage me?")):
        if state["vitals"][vital] < below and left[kind] > 0 and asked.get(kind) != today:
            post_item(db, now, "ask", asking(db, words), {"care": kind, "day": today})
            asked[kind] = today
            changed = True
        if left[kind] == 0 and asked.get(kind) == today:
            for row in db.execute("SELECT id, data FROM mimo_inbox WHERE kind='ask' AND json_extract(data, '$.care')=? "
                                  "AND json_extract(data, '$.day')=? AND json_extract(data, '$.done') IS NULL",
                                  (kind, today)).fetchall():
                db.execute("UPDATE mimo_inbox SET data=?, read_at=COALESCE(read_at, ?) WHERE id=?",
                           (json.dumps({**json.loads(row["data"]), "done": True}), now, row["id"]))
                changed = True
    return changed


def place_words(db: sqlite3.Connection, place: dict) -> str:
    """ "a cave north of home", "a lake far south of home" (FAR blocks or more), and "another lake south of
    home" when an earlier ask had the same words (m7)."""
    words = NAMEABLE[place["kind"]]
    home = places(db, ("home",))
    far = math.hypot(place["x"] - home[0]["x"], place["z"] - home[0]["z"]) if home else 0.0
    if home and far >= 8:
        where = compass(place["x"] - home[0]["x"], place["z"] - home[0]["z"])
        words += f" {'far ' if far >= FAR else ''}{where} of home"
    said = {row[0] for row in db.execute("SELECT json_extract(data, '$.words') FROM mimo_inbox WHERE kind='ask' AND "
                                         "json_extract(data, '$.ask')='name'")}
    return f"another {words[2:]}" if words in said and words.startswith("a ") else words


def ask_to_name(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: ask the owner to name a place Mimo found since the inbox started, one a game day, the
    places in the order found. Bond's final fix wave (I7): never while a naming ask waits unanswered; one
    left unanswered STALE_ASK real seconds is replaced by an ask about the newest place found."""
    bond = bond_state(state)
    since = bond.get("places_seen")
    if since is None:
        bond["places_seen"] = now
        return True
    last = bond.get("named_at")
    if last is not None and (now - last) * scale < DAY_SECONDS:
        return False
    waiting = db.execute(f"SELECT id, at FROM mimo_inbox WHERE {WAITING_ASK}").fetchall()
    if waiting and now - max(row["at"] for row in waiting) < STALE_ASK:
        return False
    marks = ",".join("?" * len(NAMEABLE))
    row = db.execute(f"SELECT kind, x, y, z, found_at FROM memory_places WHERE kind IN ({marks}) AND found_at > ? "
                     f"ORDER BY found_at {'DESC' if waiting else ''}, rowid LIMIT 1", (*NAMEABLE, since)).fetchone()
    if row is None:
        return False
    for stale in waiting:  # replaced by the newer ask
        db.execute("DELETE FROM mimo_inbox WHERE id=?", (stale["id"],))
    place = dict(row)
    words = place_words(db, place)
    post_item(db, now, "ask", asking(db, f"I found {words}. What should we call it?"),
              {"ask": "name", "place": {key: place[key] for key in ("kind", "x", "y", "z")}, "words": words})
    bond.update(places_seen=place["found_at"], named_at=now)
    return True


CHORES.extend([ask_for_care, ask_to_name])  # after the mirrors, which are the Talker's first chore


def name_place(world: SurvivalWorld, item_id: int, text: str, now: float, scale: float = 1.0) -> dict:
    """The owner names the place a naming ask is about. Raises LookupError for no such ask,
    ValueError for a name that is not 1 to NAME_LIMIT letters, digits, spaces, ' or -, or an ask
    already answered, and LifeOver when Mimo died. Returns the item. Bond's final fix wave: a name far too
    long is refused before it is cleaned (m9); the fact reads "a lake south of home, called Echo Hollow"
    and Mind remembers it (m8)."""
    if len(str(text)) > 4 * NAME_LIMIT:
        raise ValueError(f"A name is 1 to {NAME_LIMIT} letters, digits, spaces, ' or -.")
    name = " ".join(str(text).split())
    if not name or len(name) > NAME_LIMIT or not PLACE_NAME.match(name):
        raise ValueError(f"A name is 1 to {NAME_LIMIT} letters, digits, spaces, ' or -.")
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died")
        row = db.execute("SELECT * FROM mimo_inbox WHERE id=?", (item_id,)).fetchone()
        item = item_of(row) if row is not None else None
        if item is None or item["kind"] != "ask" or item["data"].get("ask") != "name":
            raise LookupError("No such question from Mimo")
        if item["data"].get("answer"):
            raise ValueError("That place already has a name.")
        place = item["data"]["place"]
        update_place(db, place["kind"], (place["x"], place["y"], place["z"]), {"name": name})
        remember_fact(db, "named", f"{item['data']['words']}, called {name}", now)
        data = {**item["data"], "answer": name}
        db.execute("UPDATE mimo_inbox SET data=?, read_at=COALESCE(read_at, ?) WHERE id=?",
                   (json.dumps(data), now, item_id))
        game_at = max(0.0, now - state["born_at"]) * scale
        db.execute("INSERT INTO mimo_chat(at, game_at, who, text, picker) VALUES (?, ?, 'mimo', ?, 'rules')",
                   (now, game_at, f"{name}! I love it. I'll remember that."))
        write_state(db, state)
        return {**item, "data": data, "read": True}


def mark_one(world: SurvivalWorld, item_id: int, now: float) -> int:
    """B3: mark one item read (the story the owner just read). Returns how many are still unread."""
    return marking(world, "id = ?", (item_id,), now)

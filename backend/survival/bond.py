"""The bond between Mimo and its owner (Bond B2): a value from 0 to 100 in state["bond"].

It grows when the owner cares for Mimo (a snack or a bandage), says hello or talks with it, and when
Mimo keeps a promise (an owner's request it took up and then reached: backend.survival.requests),
by GAINS. Hellos and chat lines count at most DAILY times a real UTC day each, so pressing hello all
day does not buy a bond. It fades while the owner stays away: once GRACE real seconds have passed
since the owner was last seen (care, a hello, a chat line, or the viewer open: `visit`), by FADE
points a real day, never below 0. The fade is worked out when the bond is read (`bond_level`), so
reading never writes; the owner's next touch settles it into the stored value.

Bond changes nothing about survival. It sets the tone of Mimo's replies (backend.survival.replies)
and how readily Mimo takes up the owner's requests (backend.survival.requests).

state["bond"] = {"value", "seen_at" (when the owner was last seen, server time), "gains" ({"day",
<kind>: count} for the daily caps)}, plus what the other Bond modules keep there, including B3's
diary.py: "storied", "story", "story_luna_day" and (fix round 1, item 3) "owed_from" (`visit`).
"""

from __future__ import annotations

from datetime import datetime, timezone

START = 20.0  # a newborn's bond (and a pet's from before Bond)
TOP = 100.0
GAINS = {"snack": 4.0, "bandage": 4.0, "hello": 2.0, "chat": 1.0, "promise": 8.0}
DAILY = {"hello": 3, "chat": 10}  # how many of these count a real UTC day
GRACE = 86_400.0  # real seconds away before the bond starts to fade
FADE = 3.0  # points a real day after that
REAL_DAY = 86_400.0
FRIENDLY_FROM, CLOSE_FROM, DEVOTED_FROM = 25.0, 50.0, 75.0
# The one table of how close Mimo feels (Bond's final fix wave, m2): the HUD's words, and where the
# replies, the requests' answers and the story's closing turn shy or warm (replies.SHY, replies.CLOSE).
FEELINGS = ((DEVOTED_FROM, "devoted"), (CLOSE_FROM, "close"), (FRIENDLY_FROM, "friendly"), (0.0, "shy"))


def utc_day(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def bond_state(state: dict) -> dict:
    """state["bond"], with the fields a pet from before Bond lacks."""
    bond = state.setdefault("bond", {})
    bond.setdefault("value", START)
    bond.setdefault("seen_at", None)
    bond.setdefault("gains", {"day": None})
    return bond


def bond_level(state: dict, now: float) -> float:
    """The bond now, the fade since the owner was last seen taken off. Reads only."""
    bond = state.get("bond") or {}
    value = float(bond.get("value", START))
    seen = bond.get("seen_at")
    if seen is None:
        return min(TOP, value)
    return min(TOP, max(0.0, value - FADE * max(0.0, now - seen - GRACE) / REAL_DAY))


def visit(state: dict, now: float) -> float:
    """The owner is here: the fade so far settles into the value, and the owner was seen now.

    Fix round 1, item 3: when a story is still owed for the visit "seen_at" is about to leave behind
    (bond.get("storied") != seen_at), that visit's time is kept in "owed_from" so the Talker's story
    lane (diary.story_span) still starts the story there, even though "seen_at" moves on to `now`. This
    is the usual order after the worker's machine sleeps: its catch-up tick can run before the viewer's
    /mimo/visit call lands, or the other way around; either way the owed visit must not be lost. It is
    cleared once that story is written (diary.store_story)."""
    level = bond_level(state, now)
    bond = bond_state(state)
    bond["value"] = round(level, 3)
    owed = bond["seen_at"] is not None and now > bond["seen_at"] and bond.get("storied") != bond["seen_at"]
    if owed and bond.get("owed_from") is None:
        bond["owed_from"] = bond["seen_at"]
    bond["seen_at"] = now if bond["seen_at"] is None else max(bond["seen_at"], now)
    return level


def grow_bond(state: dict, kind: str, now: float, present: bool = True) -> float:
    """The bond grows by GAINS[kind], unless today's count of that kind is used up. `present`: the
    owner did it (care, a hello, a chat line), so it is a visit too; a promise Mimo kept is not.
    Returns the bond."""
    if present:
        visit(state, now)
    bond = bond_state(state)
    today = utc_day(now)
    if bond["gains"].get("day") != today:
        bond["gains"] = {"day": today}
    counted = bond["gains"].get(kind, 0)
    if kind not in DAILY or counted < DAILY[kind]:
        bond["gains"][kind] = counted + 1
        # Bond's final fix wave (m13): the gain is capped by the level's headroom, not the stored value's,
        # so a promise kept while a full bond has faded still counts (the fade stays unsettled: not a visit).
        bond["value"] = round(bond["value"] + min(GAINS.get(kind, 0.0), max(0.0, TOP - bond_level(state, now))), 3)
    return bond_level(state, now)


def feeling(level: float) -> str:
    return next(words for floor, words in FEELINGS if level >= floor)


def bond_view(state: dict, now: float) -> dict:
    """The bond for /api/mimo and the model: {"level" (0 to 100), "feeling"}."""
    level = bond_level(state, now)
    return {"level": round(level), "feeling": feeling(level)}

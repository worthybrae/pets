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
<kind>: count} for the daily caps)}, plus what the other Bond modules keep there.
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
FEELINGS = ((75.0, "devoted"), (50.0, "close"), (25.0, "friendly"), (0.0, "shy"))


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
        return value
    return max(0.0, value - FADE * max(0.0, now - seen - GRACE) / REAL_DAY)


def visit(state: dict, now: float) -> float:
    """The owner is here: the fade so far settles into the value, and the owner was seen now."""
    level = bond_level(state, now)
    bond = bond_state(state)
    bond["value"] = round(level, 3)
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
        bond["value"] = round(min(TOP, bond["value"] + GAINS.get(kind, 0.0)), 3)
    return bond_level(state, now)


def feeling(level: float) -> str:
    return next(words for floor, words in FEELINGS if level >= floor)


def bond_view(state: dict, now: float) -> dict:
    """The bond for /api/mimo and the model: {"level" (0 to 100), "feeling"}."""
    level = bond_level(state, now)
    return {"level": round(level), "feeling": feeling(level)}

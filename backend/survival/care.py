"""Owner care: one snack (+30 hunger) and one bandage (+25 health) per real UTC day. (Bond) Each grows
the bond between Mimo and its owner (backend.survival.bond)."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.survival.bond import grow_bond
from backend.survival.world import LifeOver, SurvivalWorld, check_not_behind, log_event, read_state, write_state

CARE_EFFECTS = {"snack": ("hunger", 30.0), "bandage": ("health", 25.0)}
DAILY_ALLOWANCE = {"snack": 1, "bandage": 1}
CARE_EVENTS = {"snack": "You gave {name} a snack.", "bandage": "You bandaged {name}."}
CARE_THOUGHTS = {"snack": "Yum! Thank you.", "bandage": "That feels much better."}


class CareRefused(RuntimeError):
    """Today's allowance of that kind of care is used up."""


def utc_day(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()


def care_remaining(state: dict, timestamp: float) -> dict[str, int]:
    used = state["care"] if state["care"].get("day") == utc_day(timestamp) else {}
    return {kind: max(0, allowance - used.get(kind, 0)) for kind, allowance in DAILY_ALLOWANCE.items()}


def give_care(world: SurvivalWorld, kind: str, timestamp: float) -> dict:
    if kind not in CARE_EFFECTS:
        raise ValueError("Care must be a snack or a bandage")
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died and cannot receive care")
        check_not_behind(state, timestamp)
        if care_remaining(state, timestamp)[kind] <= 0:
            raise CareRefused(f"No {kind} left today. The owner gets a new one each UTC day.")
        today = utc_day(timestamp)
        if state["care"].get("day") != today:
            state["care"] = {"day": today, "snack": 0, "bandage": 0}
        state["care"][kind] += 1
        grow_bond(state, kind, timestamp)
        vital, amount = CARE_EFFECTS[kind]
        state["vitals"][vital] = min(100.0, state["vitals"][vital] + amount)
        state["last_thought"] = CARE_THOUGHTS[kind]
        write_state(db, state)
        log_event(db, timestamp, "care", CARE_EVENTS[kind].format(name=state["name"]))
        return {"kind": kind, "vitals": state["vitals"], "remaining": care_remaining(state, timestamp)}

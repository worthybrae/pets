"""The brain's saved state and the triggers that ask Mimo to choose a new purpose.

Everything the brain keeps lives in state["brain"], saved as JSON with the rest of the state:

- purpose, picker, chosen_at: the current purpose (or None), who chose it ("jev", "luna" or
  "utility") and when (server time)
- batches, planned_at, replans, handled_failure: how many batches of steps the purpose finished
  well, when the last batch was planned, failures re-planned since a batch last finished well,
  and the last `state["last_failure"]` the brain already dealt with
- pending: a choice Mimo is waiting for, {"id", "reasons", "since", "urgent"}, or None; next_id
- penalties: {purpose: server time until which it scores lower, after it failed twice}
- reflex, set_aside, reflex_ends: the reflex running now (or None), the purpose's steps it set
  aside, and {reflex: server time it last ended} for cooldowns
- calls, last_call_at: today's model-call counters {"day", "model", "luna", "reflections"} and
  the server time of the last model call
- explored, escaped_at, dig_heading: explore walks so far (to vary the heading), the last
  dig-out of a pit, and the [dx, dz] heading gather_stone last dug in
- found: ore materials and "water" Mimo has discovered at least once (first sightings trigger a choice)

The tick marks triggers (backend.survival.brain); the worker's Chooser answers them
(backend.survival.choosing).
"""

from __future__ import annotations

HOUR = 3600.0  # one game hour, in game seconds
CROSSING_VITALS = ("health", "hunger", "warmth", "energy")
CROSSING_LEVELS = (50.0, 30.0, 15.0)
PHASE_TRIGGERS = ("dawn", "dusk")
REASON_LIMIT = 8


def new_brain(at: float) -> dict:
    """A brain with no purpose that waits for its first choice."""
    return {"purpose": None, "picker": None, "chosen_at": None, "batches": 0, "planned_at": None, "replans": 0,
            "handled_failure": None, "found": [],
            "pending": {"id": 1, "reasons": ["born"], "since": at, "urgent": False}, "next_id": 2,
            "penalties": {}, "reflex": None, "set_aside": [], "reflex_ends": {},
            "calls": {"day": None, "model": 0, "luna": 0, "reflections": 0}, "last_call_at": None,
            "explored": 0, "escaped_at": None, "dig_heading": None}


def ensure_brain(state: dict) -> dict:
    """The brain's state, created on first use (worlds from before M3 have none)."""
    brain = state.get("brain")
    if brain is None:
        brain = state["brain"] = new_brain(state.get("last_tick_at", 0.0))
    return brain


def mark_trigger(state: dict, reason: str, at: float, urgent: bool = False) -> None:
    """Ask for a new choice. A pending choice keeps its id and gains the reason. An urgent trigger
    (a vital crossing) gives it a new id instead, so an answer still being worked out for the old
    id is thrown away when it arrives: the state moved on."""
    brain = ensure_brain(state)
    pending = brain["pending"]
    if pending is not None and not urgent:
        if reason not in pending["reasons"]:
            pending["reasons"] = [*pending["reasons"], reason][-REASON_LIMIT:]
        return
    reasons = [] if pending is None else [known for known in pending["reasons"] if known != reason]
    brain["pending"] = {"id": brain["next_id"], "reasons": [*reasons, reason][-REASON_LIMIT:],
                        "since": at if pending is None else pending["since"],
                        "urgent": urgent or bool(pending and pending["urgent"])}
    brain["next_id"] += 1


def crossings(before: dict, after: dict) -> list[str]:
    """Vitals that fell past 50, 30 or 15 between two readings, as reasons like "hunger_30"."""
    return [f"{name}_{int(level)}" for name in CROSSING_VITALS for level in CROSSING_LEVELS
            if before[name] >= level > after[name]]


def phase_trigger(before: str, after: str) -> str | None:
    """"dawn" or "dusk" when the clock just entered that phase."""
    return after if after != before and after in PHASE_TRIGGERS else None


def hour_passed(brain: dict, at: float, scale: float) -> bool:
    """True once a game hour has passed since the last choice."""
    return brain["chosen_at"] is not None and (at - brain["chosen_at"]) * scale >= HOUR

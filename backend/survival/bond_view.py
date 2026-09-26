"""What /api/mimo shows of Bond while Mimo lives (snapshot.alive_snapshot): the chat (B1), the bond, the
request Mimo took up and the inbox (B2), and the newest story (B3). `note_visit` is the viewer telling the
world the owner is here (POST /api/mimo/visit).

Everything is read in one read-only transaction of its own, after the rest of the snapshot; a
world from before Bond shows an empty chat.
"""

from __future__ import annotations

from backend.survival.bond import bond_view, visit
from backend.survival.diary import newest_story
from backend.survival.inbox import inbox_view
from backend.survival.requests import request_view
from backend.survival.talk import chat_view
from backend.survival.world import LifeOver, SurvivalWorld, read_state, write_state

VISIT_WRITE_EVERY = 60.0  # real seconds: a visit sooner after the last one writes nothing (m10)


def bond_fields(world: SurvivalWorld, now: float, scale: float) -> dict:
    with world.connect() as db:
        db.execute("BEGIN")
        state = read_state(db)
        return {"chat": chat_view(db, state, now, scale), "bond": bond_view(state, now), "inbox": inbox_view(db),
                "request": request_view(state, now), "story": newest_story(db)}


def note_visit(world: SurvivalWorld, now: float) -> dict:
    """The owner opened the viewer: the bond stops fading from now (and, B3, a story is due at the
    next game dawn). Returns the bond. Bond's final fix wave (m10): a visit within VISIT_WRITE_EVERY real
    seconds of the last one writes nothing, so a stuck client's loop never holds the write lock."""
    with world.connect() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died")
        seen = (state.get("bond") or {}).get("seen_at")
        if seen is not None and 0 <= now - seen < VISIT_WRITE_EVERY:
            return bond_view(state, now)
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            raise LifeOver(f"{state['name']} has died")
        visit(state, now)
        write_state(db, state)
        return bond_view(state, now)

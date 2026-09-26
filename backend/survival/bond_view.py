"""What /api/mimo shows of Bond while Mimo lives (snapshot.alive_snapshot): the chat (B1).

Everything is read in one read-only transaction of its own, after the rest of the snapshot; a
world from before Bond shows an empty chat.
"""

from __future__ import annotations

from backend.survival.talk import chat_view
from backend.survival.world import SurvivalWorld, read_state


def bond_fields(world: SurvivalWorld, now: float, scale: float) -> dict:
    with world.connect() as db:
        db.execute("BEGIN")
        state = read_state(db)
        return {"chat": chat_view(db, state, now, scale)}

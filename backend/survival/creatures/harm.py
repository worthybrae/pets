"""What a creature's blow does to Mimo (spec L2, "Mimo's health" and "Armor").

A hostile creature's blow (backend.survival.creatures.hostiles) takes its kind's damage from
Mimo's health, less the share the armor Mimo carries takes off: a leather cap 8 % and a leather
tunic 12 %, 20 % together (iron armor comes in L3). Armor is worn by carrying it. No blow reaches
Mimo inside its shelter, in a room or passage cell of one it built (`sheltered`), not even from a
window gap. A blow:
- marks Mimo hurt (`state["hurt_at"]`, `state["hurt_by"]`), which the viewer flashes;
- remembers the place as a danger, noted with the creature's kind (memory kind "danger");
- asks for a new choice at once (urgent) when health falls past 50, 30 or 15, as a vital
  crossing does in the tick;
- logs a routine "hurt" event, at most one every HURT_QUIET seconds, so a fight does not flood
  the event log.
At 0 health Mimo dies of it: the tick records the death with the kind as its cause
(backend.survival.tick, "Pip was caught by a gloomling on day 3.").
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from backend.survival.creatures.table import missing_table
from backend.survival.memory import remember
from backend.survival.triggers import crossings, mark_trigger

if TYPE_CHECKING:
    from backend.survival.creatures.acts import Scene

ARMOR = {"leather_cap": 0.08, "leather_tunic": 0.12}  # the share of a blow each piece takes off
INDOORS = ("room", "passage")  # the parts of a shelter Mimo is safe in
HURT_QUIET = 10.0  # server seconds (at the normal pace) between two "hurt" events


def armor_cut(inventory: dict) -> float:
    """The share of a blow the armor Mimo carries takes off."""
    return sum(cut for piece, cut in ARMOR.items() if inventory.get(piece, 0) > 0)


def sheltered(db: sqlite3.Connection, cell: tuple[int, int, int]) -> bool:
    """`cell` is a room or passage cell of a shelter Mimo built."""
    try:
        row = db.execute("SELECT part FROM structure_cells WHERE x=? AND y=? AND z=?", cell).fetchone()
    except sqlite3.OperationalError as error:
        if not missing_table(error):  # a database without memory: unit tests of creatures alone
            raise
        return False
    return row is not None and row[0] in INDOORS


def pet_alive(state: dict) -> bool:
    return state.get("died_at") is None and state["vitals"]["health"] > 0


def hurt_pet(scene: Scene, damage: float, source: str) -> float:
    """Mimo takes a blow from a creature of kind `source`. Returns the health it lost."""
    state = scene.state
    vitals = state["vitals"]
    before = dict(vitals)
    lost = min(vitals["health"], damage * (1.0 - armor_cut(state["inventory"])))
    vitals["health"] = max(0.0, vitals["health"] - lost)
    name = source.replace("_", " ")
    last = state.get("hurt_at")
    if last is None or scene.at - last >= HURT_QUIET / scene.pace:
        scene.events.append((scene.at, "hurt", f"{state['name']} was hit by a {name}."))
    state.update(hurt_at=scene.at, hurt_by=source, last_thought=f"Ow! A {name}!")
    for reason in crossings(before, vitals):
        mark_trigger(state, reason, scene.at, urgent=True)
    try:
        remember(scene.herd.db, "danger", scene.pet, scene.at, source)
    except sqlite3.OperationalError as error:
        if not missing_table(error):  # a database without memory: unit tests of creatures alone
            raise
    return lost

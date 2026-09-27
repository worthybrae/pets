"""The notable moments that go to Mimo's inbox (Bond B3), registered with the inbox's mirror.

Besides B2's milestones (a goal reached, a home built, a promise kept) and (Making, pre-flight 2) the
computer Mimo built ("report", from its notable "computer" event), the owner hears about:
- a first sighting ("found"): a first creature of a kind, a first biome, a first ore, first water,
  and a place a trip found that is new to Mimo (the "found" and "discovered" events); L5 (pre-flight,
  carry 6): an old chest opened in a ruin ("loot"), told as a find;
- a creature seed hatching ("hatched", Bond's final fix wave m1): "My creature seed grew into a sheep!"
  (a "grow" event about a seed; a sapling growing is left out);
- danger ("danger"): a blow from a creature or one coming (the "hurt" and "threat" events), stuck in
  a pit ("trapped"), starving or freezing, at most once a game hour (DANGER_EVERY) so a fight does not
  flood the inbox;
- near death ("danger", the chore `near_death`): health under NEAR_DEATH, once a game hour too.
Every message is in Mimo's own words where the event is about it ("I met my first skitter."), from
rules only, through the one voicing (replies.in_my_voice, the final fix wave's I1). A machine whose own
notable event tells of it (SELF_TOLD: the computer) is not reported built as well. The bookkeeping is in
state["bond"]: "danger_at", when danger was last reported.
"""

from __future__ import annotations

import sqlite3

from backend.survival.bond import bond_state
from backend.survival.events import mirror
from backend.survival.inbox import CONSUMER, post_item, report
from backend.survival.machines import MACHINES, title_of
from backend.survival.replies import in_my_voice
from backend.survival.talker import CHORES
from backend.survival.triggers import HOUR

DANGER_EVERY = HOUR  # game seconds between two danger messages
NEAR_DEATH = 20.0  # health under this is near death
SEED_GREW = "A creature seed grew into"
# Danger in Mimo's words where turning the event around would read badly.
DANGER_WORDS = {"trapped": "I got stuck in a pit. I'm digging my way out."}
# Machines whose own notable event tells the owner of them ("computer": "I built a machine that remembers
# how long I have been alive!"), so their "built" event is not reported too (the final fix wave's I1).
SELF_TOLD = ("computer",)


def found(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    post_item(db, event["at"], "found", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


def hatched(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A creature seed Mimo planted grew into a creature (m1: its own kind, in Mimo's words)."""
    if event["text"].startswith(SEED_GREW):
        text = "My creature seed grew into" + event["text"][len(SEED_GREW):].rstrip(".") + "!"
        post_item(db, event["at"], "hatched", text, {"event": event["id"]})


def built(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A thing Mimo built, reported, unless it is a machine that tells of itself (SELF_TOLD)."""
    name = state["name"]
    told = {f"{name} built {title_of(MACHINES[kind], name)}." for kind in SELF_TOLD if kind in MACHINES}
    if event["text"] in told:
        return
    report(db, state, event, now, scale)


def danger_due(state: dict, at: float, scale: float) -> bool:
    """Danger was not reported in the game hour before `at`; if so, it is being reported now."""
    bond = bond_state(state)
    last = bond.get("danger_at")
    if last is not None and (at - last) * scale < DANGER_EVERY:
        return False
    bond["danger_at"] = at
    return True


def danger(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    if danger_due(state, event["at"], scale):
        text = DANGER_WORDS.get(event["kind"]) or in_my_voice(event["text"], state["name"])
        post_item(db, event["at"], "danger", text, {"event": event["id"]})


# The inbox's writers on the event log's mirrors (backend.survival.events), one a kind (pre-flight 2).
for _kind, _write in {"found": found, "discovered": found, "grow": hatched, "hurt": danger, "threat": danger,
                      "trapped": danger, "starving": danger, "freezing": danger, "computer": report,
                      "built": built, "loot": found}.items():  # L5: an old chest opened in a ruin
    mirror(CONSUMER, _kind, _write)


def near_death(db: sqlite3.Connection, state: dict, now: float, scale: float) -> bool:
    """A chore: Mimo is badly hurt (health under NEAR_DEATH), told at most once a game hour."""
    if state["vitals"]["health"] >= NEAR_DEATH or not danger_due(state, now, scale):
        return False
    post_item(db, now, "danger", "I'm badly hurt. I need to rest and heal.", {"health": round(state["vitals"]["health"])})
    return True


CHORES.append(near_death)

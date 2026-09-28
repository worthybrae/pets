"""W1: what a wild pet's new moments mean to its memory and its inbox ("Moments, news and voice").

Mind's memory (backend.survival.episodes) keeps these events as moments: "figured" 7 (+2, a lesson: Mimo worked
something out itself), "cured" 4 (+1), "wound" 4 (-2), "festering" 5 (-2), "chill" 5 (-2), "spoiled" 2 (-1, a
game day's merged as "{n} of my food went bad."), "asked" 3 (0, about the owner, so it never reaches Luna).
The inbox (Bond B2's mirror) tells the owner what Mimo worked out as a report ("I worked it out myself: ..."),
and a festering wound, a chill or a sickness as danger, each at most once a game day. Every text reads in
Mimo's own voice (replies.in_my_voice; test_survival_voice).
"""

from __future__ import annotations

import sqlite3

from backend.survival.bond import bond_state
from backend.survival.clock import DAY_SECONDS
from backend.survival.episodes import MOMENTS, Moment, followed, remember_moment
from backend.survival.events import mirror
from backend.survival.inbox import CONSUMER, post_item
from backend.survival.replies import in_my_voice

MOMENTS.update({
    "figured": Moment(7, 2, kind="lesson"),
    "cured": Moment(4, 1),
    "wound": Moment(4, -2),
    "festering": Moment(5, -2),
    "chill": Moment(5, -2),
    "spoiled": Moment(2, -1, many="{n} of my food went bad."),
    "asked": Moment(3, 0, about=("owner",)),
})
for _kind in ("figured", "cured", "wound", "festering", "chill", "spoiled", "asked"):
    followed(_kind, remember_moment)


def figured(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """What Mimo worked out, as news: "I worked it out myself: cooking makes meat safe."."""
    prefix = f"{state['name']} worked out that "
    what = event["text"][len(prefix):] if event["text"].startswith(prefix) else in_my_voice(event["text"], state["name"])
    post_item(db, event["at"], "report", f"I worked it out myself: {what}", {"event": event["id"]})


def ailment_danger(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A festering wound, a chill or a sickness, as danger, at most once a game day of each kind."""
    told = bond_state(state).setdefault("ailments_told", {})
    last = told.get(event["kind"])
    if last is not None and (event["at"] - last) * scale < DAY_SECONDS:
        return
    told[event["kind"]] = event["at"]
    post_item(db, event["at"], "danger", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


mirror(CONSUMER, "figured", figured)
for _kind in ("festering", "chill", "sick"):
    mirror(CONSUMER, _kind, ailment_danger)

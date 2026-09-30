"""W2: what the weather's and the seasons' moments mean to Mimo's memory and its inbox ("Moments, news and voice").

The events (world.log_event): "season" ("Winter has come.", routine), "spring" ("Spring! Things are growing
again.", notable), "colder" ("The nights are getting colder.", notable), "storm" ("A thunderstorm rolled in.",
routine), "struck" ("Lightning struck Pip!", notable), "fire" ("Lightning set a tree on fire near Pip.",
notable), "fire_out" ("The rain put out Pip's campfire.", routine) and "smoke" ("Pip smoked raw beef.", routine).
Mind's memory keeps "struck" 8 (-2), "fire" 5 (0), "season" 4 (+1), "spring" 6 (+1) and "colder" 4 (0) as
moments. The inbox tells the owner of a strike or a fire as danger (each kind at most once a game day) and of
winter's and spring's first days as news. Every text reads in Mimo's own voice (replies.in_my_voice;
test_survival_voice).
"""

from __future__ import annotations

import sqlite3

from backend.survival.bond import bond_state
from backend.survival.clock import DAY_SECONDS
from backend.survival.episodes import MOMENTS, Moment, followed, remember_moment
from backend.survival.events import mirror
from backend.survival.inbox import CONSUMER, post_item
from backend.survival.replies import in_my_voice
from backend.survival.sky import TURNS, UNNAMED

MOMENTS.update({
    "struck": Moment(8, -2),
    "fire": Moment(5, 0),
    "season": Moment(4, 1),
    "spring": Moment(6, 1),
    "colder": Moment(4, 0),
})
for _kind in ("struck", "fire", "season", "spring", "colder"):
    followed(_kind, remember_moment)


def sky_danger(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """A strike or a fire in the trees, as danger, at most once a game day of each kind."""
    told = bond_state(state).setdefault("sky_told", {})
    last = told.get(event["kind"])
    if last is not None and (event["at"] - last) * scale < DAY_SECONDS:
        return
    told[event["kind"]] = event["at"]
    post_item(db, event["at"], "danger", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


def season_news(db: sqlite3.Connection, state: dict, event: dict, now: float, scale: float) -> None:
    """Winter's and spring's first days, as news."""
    if event["kind"] == "spring" or event["text"] in (TURNS["winter"], UNNAMED["winter"]):
        post_item(db, event["at"], "report", in_my_voice(event["text"], state["name"]), {"event": event["id"]})


for _kind in ("struck", "fire"):
    mirror(CONSUMER, _kind, sky_danger)
for _kind in ("season", "spring"):
    mirror(CONSUMER, _kind, season_news)

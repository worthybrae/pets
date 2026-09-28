"""Wild World W2: the seasons and the sky (docs/superpowers/specs/2026-09-27-wild-world-design.md, "W2").

A year is YEAR_DAYS (40) game days: spring, summer, autumn and winter, SEASON_DAYS (10) each. The season day
(0 to 39) is `(day_number - 1 + offset) mod 40`, with the offset in state["sky"]["offset"]: a newborn's is 0
(it hatches on spring day 1 and meets its first winter on day 31), and a world from before W2 gets one on its
first tick (`settle_sky`, only in a living pet's tick) so that day is spring day 1 and its first winter comes
30 game days after the upgrade.

Seasons move the warmth Mimo drifts toward outdoors (vitals.SEASON_WARMTH: a winter night outdoors is -10, 35
sheltered). The tick tends the sky before each step (`advance`): it keeps state["sky"] up to date for
/api/mimo and for what reads it in the step (the season, and from W2's later parts the weather, the snow, the
frozen lakes, the strikes and the fires), logs the turn of a season at its first dawn ("Winter has come.", a
routine "season" event; spring's is the notable "spring": "Spring! Things are growing again.") and, on autumn
day 3 at dusk, the notable "colder" ("The nights are getting colder."). Then it runs EFFECTS, each guarded: a
crash is logged once and counts as nothing.

state["sky"] (`sky_state`; every field has a default, so a world from before W2 and an archive read as empty):
offset, season, season_day, day (the day number last tended), weather, weather_until, snow, frozen, open_cells,
strikes, fires, told ({what: day} of the season's news). A GET never writes it (`sky_view` only reads).
"""

from __future__ import annotations

import logging
from typing import Callable

from backend.survival.clock import DAY_SECONDS, PHASES, clock_at
from backend.survival.once import log_once

logger = logging.getLogger(__name__)

SEASON_DAYS = 10
SEASONS = ("spring", "summer", "autumn", "winter")
YEAR_DAYS = SEASON_DAYS * len(SEASONS)
WINTER = "winter"
COLDER_DAY = 2  # autumn day 3 (the season day's own count starts at 0)
DUSK = next(start for name, start, _ in PHASES if name == "dusk")
TURNS = {"summer": "Summer has come.", "autumn": "Autumn has come.", "winter": "Winter has come.",
         "spring": "Spring! Things are growing again."}
COLDER = "The nights are getting colder."
# W2: functions (state, context, at) run by `advance` after the season is tended, before each step (the
# weather's, the storms' and the ice's effects). One that crashes is logged once and passed over.
EFFECTS: list[Callable] = []


def sky_state(state: dict) -> dict:
    """state["sky"], with every field (a world from before W2 has none until its first tick)."""
    found = state.setdefault("sky", {})
    for key, default in (("season", "spring"), ("season_day", 0), ("day", None), ("weather", "clear"),
                         ("weather_until", None), ("snow", 0.0), ("frozen", False), ("open_cells", []),
                         ("strikes", []), ("fires", []), ("told", {})):
        found.setdefault(key, default)
    return found


def offset_of(state: dict) -> int:
    return int((state.get("sky") or {}).get("offset", 0))


def day_number(state: dict, at: float, scale: float) -> int:
    return clock_at(state["born_at"], at, scale)["day_number"]


def season_day_of(day: int, offset: int) -> int:
    """The season day (0 to 39) of the life's day number `day`."""
    return (day - 1 + offset) % YEAR_DAYS


def season_of(season_day: int) -> str:
    return SEASONS[season_day // SEASON_DAYS]


def season_at(state: dict, at: float, scale: float) -> tuple[str, int]:
    """(season, season day) at server time `at`."""
    found = season_day_of(day_number(state, at, scale), offset_of(state))
    return season_of(found), found


def season_now(state: dict) -> str:
    """The season the tick last tended ("spring" for a world from before W2)."""
    return (state.get("sky") or {}).get("season", "spring")


def winter(state: dict) -> bool:
    return season_now(state) == WINTER


def next_season_at(state: dict, at: float, scale: float, season: str) -> float:
    """Server time of the next first dawn of `season` after `at` (`at`'s own day counts when it is that dawn)."""
    day = day_number(state, at, scale)
    target = SEASONS.index(season) * SEASON_DAYS
    ahead = (target - season_day_of(day, offset_of(state))) % YEAR_DAYS
    if ahead == 0 and clock_at(state["born_at"], at, scale)["seconds_into_day"] > 0:
        ahead = YEAR_DAYS
    return state["born_at"] + (day - 1 + ahead) * DAY_SECONDS / scale


def settle_sky(state: dict, at: float, scale: float) -> None:
    """A living pet's tick: a world with no offset gets one, so the day at `at` is spring day 1."""
    sky = state.setdefault("sky", {})
    if "offset" not in sky:
        sky["offset"] = (1 - day_number(state, at, scale)) % YEAR_DAYS


def tend_season(state: dict, context, at: float) -> None:
    """Keep the season up to date and log its turns and autumn's warning (see the module docstring)."""
    sky = sky_state(state)
    clock = context.clock_at(at)
    day = clock["day_number"]
    season_day = season_day_of(day, offset_of(state))
    season = season_of(season_day)
    turned = sky["day"] is not None and day != sky["day"] and season_day % SEASON_DAYS == 0
    sky.update(season=season, season_day=season_day, day=day)
    if turned:
        kind = "spring" if season == "spring" else "season"
        context.events.append((at, kind, TURNS[season]))
        state["last_thought"] = TURNS[season]
    told = sky["told"]
    if (season == "autumn" and season_day % SEASON_DAYS == COLDER_DAY and clock["seconds_into_day"] >= DUSK
            and told.get("colder") != day):
        told["colder"] = day
        context.events.append((at, "colder", COLDER))
        state["last_thought"] = COLDER


def advance(state: dict, context, at: float) -> None:
    """Before each step of the tick: the season, then EFFECTS. A crash is logged once and changes nothing."""
    try:
        tend_season(state, context, at)
    except Exception as error:
        log_once(logger, "season", error)
    for effect in EFFECTS:
        try:
            effect(state, context, at)
        except Exception as error:
            log_once(logger, f"sky {getattr(effect, '__name__', 'effect')}", error)


def sky_view(state: dict, now: float, scale: float) -> dict:
    """For /api/mimo (read only): the season and its day (1 to 10), the days to the next season, the weather
    and until when, the snow, whether the lakes are frozen, and the latest strikes ({x, y, z, at})."""
    sky = state.get("sky") or {}
    at = state["died_at"] if state.get("died_at") is not None else now
    season, season_day = season_at(state, at, scale)
    return {"season": season, "day": season_day % SEASON_DAYS + 1, "to_next": SEASON_DAYS - season_day % SEASON_DAYS,
            "weather": sky.get("weather", "clear"), "until": sky.get("weather_until"),
            "snow": round(float(sky.get("snow", 0.0)), 3), "frozen": bool(sky.get("frozen", False)),
            "strikes": list(sky.get("strikes", []))}

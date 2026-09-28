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

Weather (`weather_at`) is a pure function of the world seed, the season and the SEGMENT (10-game-minute) of the
life: a game day has 6 segments. Each segment keeps the last one's weather with chance KEEP, else rolls its
season's TABLE, so a spell runs 20 game minutes or more on average. The look back stops after LOOK_BACK
segments (the sixth rolls fresh), and a kept weather the new season's table lacks (rain carried into winter)
rolls fresh too. The tick stores the weather of each step's start in state["sky"] (with when it next changes)
for /api/mimo and for what the step reads: a catch-up plays the weather in time order. While it snows the snow
cover rises SNOW_RISE a game minute; from the first spring dawn it melts over 20 game minutes.

state["sky"] (`sky_state`; every field has a default, so a world from before W2 and an archive read as empty):
offset, season, season_day, day (the day number last tended), weather, weather_until, snow, frozen, open_cells,
strikes, fires, told ({what: day} of the season's news). A GET never writes it (`sky_view` only reads).
"""

from __future__ import annotations

import logging
from typing import Callable

from backend.survival.clock import DAY_SECONDS, PHASES, clock_at
from backend.survival.nature import roll
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
SEGMENT = 600.0  # game seconds of one weather segment
LOOK_BACK = 6
KEEP = 0.5
TABLE = {"spring": (("clear", 0.55), ("rain", 0.30), ("storm", 0.08), ("fog", 0.07)),
         "summer": (("clear", 0.65), ("rain", 0.15), ("storm", 0.15), ("fog", 0.05)),
         "autumn": (("clear", 0.45), ("rain", 0.25), ("storm", 0.05), ("fog", 0.25)),
         "winter": (("clear", 0.45), ("fog", 0.15), ("snow", 0.40))}
RAINY = ("rain", "storm")
WEATHER_CHANNEL, KEEP_CHANNEL = 230, 231  # Wild World's roll channels are 200 to 259 (spec resolution 27)
UNTIL_AHEAD = 12  # segments looked ahead for when the weather changes
SNOW_RISE = 0.1  # snow cover a game minute while it snows
SNOW_MELT = 20 * 60.0  # game seconds a full cover takes to melt in spring
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


def segment_season(offset: int, segment: int) -> str:
    return season_of(season_day_of(int(segment * SEGMENT // DAY_SECONDS) + 1, offset))


def fresh(seed: str, offset: int, segment: int) -> str:
    """The season's table rolled for `segment`."""
    table = TABLE[segment_season(offset, segment)]
    pick = roll(seed, (segment, 0, 0), WEATHER_CHANNEL)
    for weather, share in table:
        pick -= share
        if pick < 0:
            return weather
    return table[-1][0]


def weather_at(seed: str, offset: int, segment: int) -> str:
    """The weather of the life's `segment` (see the module docstring)."""
    start = segment
    while start > 0 and segment - start < LOOK_BACK - 1 and roll(seed, (start, 0, 0), KEEP_CHANNEL) < KEEP:
        start -= 1
    weather = fresh(seed, offset, start)
    for later in range(start + 1, segment + 1):
        if all(weather != kind for kind, _ in TABLE[segment_season(offset, later)]):
            weather = fresh(seed, offset, later)
    return weather


def segment_of(state: dict, at: float, scale: float) -> int:
    return int(max(0.0, at - state["born_at"]) * scale // SEGMENT)


def weather_of(state: dict, at: float, scale: float) -> str:
    """The weather at server time `at` (pure: what the tick would store then)."""
    return weather_at(state.get("world_seed", "0"), offset_of(state), segment_of(state, at, scale))


def weather_now(state: dict) -> str:
    """The weather the tick stored at the start of the step ("clear" for a world from before W2)."""
    return (state.get("sky") or {}).get("weather", "clear")


def raining(state: dict) -> bool:
    return weather_now(state) in RAINY


def foggy(state: dict) -> bool:
    return weather_now(state) == "fog"


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


def tend_weather(state: dict, context, at: float) -> None:
    """Store the weather at `at`, when it next changes, and the snow cover."""
    sky = sky_state(state)
    scale = context.clock_at(at)["time_scale"]
    segment = segment_of(state, at, scale)
    if sky.get("segment") != segment:
        seed, offset = state.get("world_seed", "0"), offset_of(state)
        weather = weather_at(seed, offset, segment)
        ahead = next((later for later in range(segment + 1, segment + UNTIL_AHEAD + 1)
                      if weather_at(seed, offset, later) != weather), segment + UNTIL_AHEAD + 1)
        sky.update(segment=segment, weather=weather, weather_until=state["born_at"] + ahead * SEGMENT / scale)
    since = sky.get("tended_at")
    seconds = 0.0 if since is None else max(0.0, (at - since) * scale)
    sky["tended_at"] = at
    if sky["weather"] == "snow":
        sky["snow"] = min(1.0, sky["snow"] + SNOW_RISE * seconds / 60.0)
    elif sky["season"] == "spring" and sky["snow"] > 0:
        sky["snow"] = max(0.0, sky["snow"] - seconds / SNOW_MELT)


def advance(state: dict, context, at: float) -> None:
    """Before each step of the tick: the season and the weather, then EFFECTS. A crash is logged once and
    changes nothing."""
    try:
        tend_season(state, context, at)
        tend_weather(state, context, at)
    except Exception as error:
        log_once(logger, "season", error)
    for effect in EFFECTS:
        try:
            effect(state, context, at)
        except Exception as error:
            log_once(logger, f"sky {getattr(effect, '__name__', 'effect')}", error)


def sky_view(state: dict, now: float, scale: float) -> dict:
    """For /api/mimo (read only): the season and its day (1 to 10), the days to the next season, the weather
    and until when, the snow, whether the lakes are frozen, the latest strikes ({x, y, z, at}) and the cells
    burning in the trees ({x, y, z}, for the viewer's embers)."""
    sky = state.get("sky") or {}
    at = state["died_at"] if state.get("died_at") is not None else now
    season, season_day = season_at(state, at, scale)
    return {"season": season, "day": season_day % SEASON_DAYS + 1, "to_next": SEASON_DAYS - season_day % SEASON_DAYS,
            "weather": sky.get("weather", "clear"), "until": sky.get("weather_until"),
            "snow": round(float(sky.get("snow", 0.0)), 3), "frozen": bool(sky.get("frozen", False)),
            "strikes": list(sky.get("strikes", [])),
            "fires": [{"x": entry["x"], "y": entry["y"], "z": entry["z"]} for entry in sky.get("fires", [])]}

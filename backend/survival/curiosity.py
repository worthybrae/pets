"""Curiosity (L4, the owner's day-17 note: "it seems like its getting content with a small house and
a daily routine I want it to be more curious and constantly exploring and trying to undestand the
world").

Curiosity is an inner value from 0 to 100, kept in state["brain"]["curiosity"]: {"value", "at" (when
it was last tended), "new_at" (the last discovery), "noticed_at" (the last one more than new
ground), "seen" (discoveries so far), "met_at" (when Mimo last looked over the creatures near it)}.
A newborn starts at START.
- It grows while Mimo lives on ground it knows: GROWTH an hour of the day's clock (CLOCK_HOUR, a
  24th of a game day, as the HUD's clock counts), NEEDS_MET times that once its needs are met
  (`needs_met`: fed, rested, warm and healthy, with a home it built).
- Discoveries lower it (`discovered`): ground it never walked (NEW_GROUND, once a step), a biome it
  never saw (NEW_BIOME: "Pip saw the taiga for the first time."), a kind of block it never dug
  (NEW_BLOCK), a kind of creature it never met (NEW_CREATURE: "Pip met its first sheep."), and a
  place new to it (NEW_PLACE: each "found" or "discovered" event of the step, as first ores and
  water are, and each new place a trip finds, trips.FINDS; the first home is its own event, from
  brain.notice_step, outside this count). The biomes, blocks and creatures it met are remembered in
  memory_knowledge (facts "biome", "block" and "creature", with when). The biome it hatched in is
  known from the start, without a word -- and on an old save (fix round 1), so is everything else
  it already has: the biome of every patch it explored, the creature kinds in sight and the block
  kinds it carries or has built with (`old_save`, `learn_quietly`), so upgrading a life never floods
  the notable feed with false "firsts" or drops curiosity for half a day.
- High curiosity lifts every explore trip (`lift`, trips.LIFTS), never past SURVIVAL_FLOOR
  (purposes.py, fix round 1: the same ceiling a goal's own boost respects): from LIFTED on,
  LIFT_RATE a point, up to 30 more at 100, into the work band but no further. From RESTLESS on,
  exploring meets a need (goals.URGES), so goal work does not crowd it out. Curiosity is always a
  reason of its own, the "wander" trip ("look for something new": land it has never seen, a biome
  where creatures it never met live, a cave mouth it has not looked into, then new ground (spot
  likelihood 0.3, fix round 1: it is not a sure thing the way the others are), near or FAR_OUT
  blocks away, up to WANDER_REACH blocks from home, exempt from the usual cooldown between trips
  for the same reason since its targets move on their own): when nothing for its goal or a need is
  on offer, Mimo goes to see something new rather than sit and rest (the trip serves the discovery
  goals, so it is worked toward one of them meanwhile). Once its needs are met and it is curious
  (PLAN_FROM), the day plan sets time aside to wander (goals.PLAN_EXTRAS), ticked off by the next
  discovery.
- The model is told how it feels (`feeling`, `curiosity_view`): "restless; nothing new for 2 game
  days".
The tick tends it (`tend_curiosity`, from brain.notice_step; the creatures in sight are looked over
there, once a game minute) and hears about each finished step (`note_discoveries`, from
brain.observe_step). A crash is logged once and the tick goes on.
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

from backend.services.crafting import BLOCKS
from backend.services.worldgen import biome_at
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import land_kinds
from backend.survival.creatures.table import dead
from backend.survival.exploring import HEADINGS, area_novelty, home_cell, lately
from backend.survival.goals import PLAN_EXTRAS, URGES
from backend.survival.life_goals import looked_into, opening_words, openings_near
from backend.survival.memory import BUILT, PATCH, know, known, patch_of, places
from backend.survival.once import log_once
from backend.survival.situation import Situation
from backend.survival.steps import as_cell, label
from backend.survival.triggers import ensure_brain
from backend.survival.trips import FINDS, LIFTS, Find, Reason, register_reason

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

START = 40.0
CLOCK_HOUR = DAY_SECONDS / 24  # game seconds in an hour of the day's clock
GROWTH = 2.0  # points a clock hour
NEEDS_MET = 1.5  # times faster once needs are met
NEW_GROUND = 3.0
NEW_BIOME = 30.0
NEW_BLOCK = 6.0
NEW_CREATURE = 20.0
NEW_PLACE = 10.0
LIFTED = 50.0  # curiosity past this lifts explore...
LIFT_RATE = 0.6  # ...this much a point
CURIOUS = 60.0  # it feels restless from here on
WANDER_REACH = 90.0  # blocks from home a wander trip may go, as far as the discovery goals look
NEW_ENOUGH = 0.25  # ground this new (exploring.area_novelty over 9) is worth a wander
FAR_OUT = 72  # blocks away a wander also heads for new ground, past what explore's targets reach
RESTLESS = 75.0  # exploring meets a need
PLAN_FROM = 40.0  # the day plan sets time aside to wander
CREATURE_SIGHT = 24.0
MET_EVERY = 60.0  # game seconds between two looks over the creatures near
FED, RESTED, WARM, WELL = 60.0, 50.0, 50.0, 60.0
BIOME_WORDS = {"meadow": "a meadow", "forest": "a forest", "birch_forest": "a birch forest", "taiga": "the taiga",
               "swamp": "a swamp", "desert": "a desert", "alpine": "the mountains"}
OPENING_NEAR = 12
# L4 fix round 1: younger than this and there is nothing an old save's first tend could need to
# backfill -- a true newborn's first tend stays the quiet single-biome case below.
NEWBORN_WITHIN = 300.0  # game seconds (5 game minutes, as purposes.LATE_DAY counts them)


def biome_words(biome: str) -> str:
    return BIOME_WORDS.get(biome, f"the {label(biome)}")


def curiosity_state(state: dict, at: float) -> dict:
    """The brain's curiosity, started at START for a world from before it."""
    fresh = {"value": START, "at": at, "new_at": None, "noticed_at": None, "seen": 0, "met_at": None}
    return ensure_brain(state).setdefault("curiosity", fresh)


def value_of(brain: dict | None) -> float:
    return float(((brain or {}).get("curiosity") or {}).get("value", START))


def needs_met(state: dict, db) -> bool:
    """Fed, rested, warm and healthy, with a home it built."""
    vitals = state["vitals"]
    if vitals["hunger"] < FED or vitals["energy"] < RESTED or vitals["warmth"] < WARM or vitals["health"] < WELL:
        return False
    return any(place["note"] == BUILT for place in places(db, ("home",)))


def discovered(state: dict, at: float, drop: float, ground_only: bool = False) -> None:
    """A discovery: curiosity falls by `drop`, and the day's time to wander is ticked off (by more
    than new ground)."""
    curiosity = curiosity_state(state, at)
    curiosity["value"] = max(0.0, curiosity["value"] - drop)
    curiosity["new_at"] = at
    curiosity["seen"] += 1
    if ground_only:
        return
    curiosity["noticed_at"] = at
    goal = ensure_brain(state).get("goal") or {}
    for entry in goal.get("plan") or []:
        if entry.get("kind") == "wander":
            entry["done"] = True


def meet_creatures(state: dict, context: ActionContext, at: float) -> None:
    """Kinds of creatures in sight Mimo never met are met now: remembered and announced."""
    herd = context.grid.herd
    if herd is None or context.db is None:
        return
    x, _, z = as_cell(state["position"])
    kinds = {creature["kind"] for creature in herd.near(x, z, CREATURE_SIGHT) if not dead(creature)}
    for kind in sorted(kinds - set(known(context.db, "creature"))):
        know(context.db, kind, "creature", at)
        context.events.append((at, "found", f"{state['name']} met its first {label(kind)}."))
        discovered(state, at, NEW_CREATURE)


def old_save(state: dict, context: ActionContext, at: float) -> bool:
    """L4 fix round 1: this brain's first tend belongs to a life curiosity did not exist for yet --
    it has already explored ground, or it is older than a newborn's first few minutes."""
    if context.db.execute("SELECT 1 FROM memory_explored LIMIT 1").fetchone() is not None:
        return True
    scale = context.clock_at(at)["time_scale"]
    return (at - state.get("born_at", at)) * scale >= NEWBORN_WITHIN


def learn_quietly(state: dict, context: ActionContext, at: float) -> None:
    """An old save's first tend (fix round 1): everything curiosity would otherwise announce as a
    "first" is already old news to Mimo, so it is learned with no events and no drop -- the biome
    of every patch it explored, the creature kinds in sight now, and the block kinds it carries or
    has built with. Without this an upgraded world logged "met its first sheep" and "saw the taiga
    for the first time" for everything it already knew, crowding the notable feed and dropping
    curiosity to near 0 for about half a day."""
    db = context.db
    for rx, rz in db.execute("SELECT rx, rz FROM memory_explored").fetchall():
        x, z = rx * PATCH + PATCH // 2, rz * PATCH + PATCH // 2
        know(db, biome_at(x, z, state["world_seed"]), "biome", at)
    herd = context.grid.herd
    if herd is not None:
        x, _, z = as_cell(state["position"])
        for kind in {creature["kind"] for creature in herd.near(x, z, CREATURE_SIGHT) if not dead(creature)}:
            know(db, kind, "creature", at)
    for block in set(BLOCKS) & set(state["inventory"]):
        know(db, block, "block", at)
    for (block,) in db.execute("SELECT DISTINCT block FROM structure_cells").fetchall():
        if block in BLOCKS:
            know(db, block, "block", at)


def tend_curiosity(state: dict, context: ActionContext, at: float) -> None:
    """After a vitals step (brain.notice_step): curiosity grows with the game time since it was last
    tended, and the creatures in sight are looked over once a game minute."""
    if context.db is None or state.get("died_at") is not None:
        return
    try:
        fresh = "curiosity" not in ensure_brain(state)
        curiosity = curiosity_state(state, at)
        if fresh:
            if old_save(state, context, at):
                learn_quietly(state, context, at)
            else:  # a newborn: only the biome it hatched in is known, without a word
                x, _, z = as_cell(state["position"])
                know(context.db, biome_at(x, z, state["world_seed"]), "biome", at)
        scale = context.clock_at(at)["time_scale"]
        rate = GROWTH * (NEEDS_MET if needs_met(state, context.db) else 1.0)
        hours = max(0.0, at - curiosity["at"]) * scale / CLOCK_HOUR
        curiosity["value"] = min(100.0, curiosity["value"] + rate * hours)
        curiosity["at"] = at
        met = curiosity.get("met_at")
        if met is None or (at - met) * scale >= MET_EVERY:
            curiosity["met_at"] = at
            meet_creatures(state, context, at)
    except Exception as error:
        log_once(logger, "curiosity", error)


def note_discoveries(state: dict, step: dict, context: ActionContext, at: float, events: list) -> None:
    """After a finished step (brain.observe_step), before a trip looks around: new ground, a new
    biome where Mimo stands, a new kind of block dug, and the places the step's events found."""
    db = context.db
    if db is None or "curiosity" not in ensure_brain(state):
        return
    try:
        drop = NEW_PLACE * sum(1 for event in events if event[1] in ("found", "discovered"))
        ground = NEW_GROUND if ensure_brain(state).get("new_ground_at") == at else 0.0
        x, _, z = as_cell(state["position"])
        biome = biome_at(x, z, state["world_seed"])
        if biome not in known(db, "biome"):
            know(db, biome, "biome", at)
            context.events.append((at, "found", f"{state['name']} saw {biome_words(biome)} for the first time."))
            drop += NEW_BIOME
        block = step.get("block") if step["kind"] == "mine" else None
        if block and block not in known(db, "block"):
            know(db, block, "block", at)
            drop += NEW_BLOCK
        if drop or ground:
            discovered(state, at, drop + ground, ground_only=not drop)
    except Exception as error:
        log_once(logger, "curiosity discoveries", error)


def place_found(state: dict, find: Find, at: float) -> None:
    if find.new:
        discovered(state, at, NEW_PLACE)


FINDS.append(place_found)


# What curiosity does ---------------------------------------------------------------------------

def lift(s: Situation) -> float:
    """What curiosity adds to explore's score: LIFT_RATE a point past LIFTED."""
    return max(0.0, value_of(s.brain) - LIFTED) * LIFT_RATE


LIFTS.append(lift)
URGES["explore"] = lambda s: value_of(s.brain) >= RESTLESS


def since_words(seconds: float | None) -> str:
    if seconds is None:
        return "nothing new yet"
    if seconds >= DAY_SECONDS:
        days = math.floor(seconds / DAY_SECONDS)
        return f"nothing new for {days} game day{'s' if days > 1 else ''}"
    if seconds >= CLOCK_HOUR:
        hours = math.floor(seconds / CLOCK_HOUR)
        return f"nothing new for {hours} hour{'s' if hours > 1 else ''}"
    return "just saw something new"


def feeling(brain: dict | None, at: float, scale: float) -> str:
    """"restless; nothing new for 2 game days"."""
    level = value_of(brain)
    mood = "content" if level < 30 else "curious" if level < CURIOUS else "restless" if level < 90 else "very restless"
    new_at = ((brain or {}).get("curiosity") or {}).get("new_at")
    return f"{mood}; {since_words(None if new_at is None else max(0.0, at - new_at) * scale)}"


def curiosity_view(brain: dict | None, at: float, scale: float) -> dict | None:
    """Curiosity for /api/mimo and the model: {"level", "feeling"}; None before it is tended."""
    if not (brain or {}).get("curiosity"):
        return None
    return {"level": round(value_of(brain)), "feeling": feeling(brain, at, scale)}


# The wander trip -------------------------------------------------------------------------------

def seen(s: Situation, fact: str) -> set[str]:
    return s.sensed(f"known {fact}", lambda: set(known(s.db, fact)) if s.db is not None else set())


def unmet_kinds(s: Situation, biome: str) -> list[str]:
    return [kind.name for kind in land_kinds(biome) if kind.name not in seen(s, "creature")]


def wander_wanted(s: Situation) -> str | None:
    """Always, once the tick tends curiosity: why, in words."""
    if not s.brain.get("curiosity"):
        return None
    if value_of(s.brain) < CURIOUS:
        return "there is always more to see"
    return f"I feel {feeling(s.brain, s.at, s.scale)}"


def wander_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    biome = biome_at(x, z, s.seed)
    if biome not in seen(s, "biome"):
        return 1.0, f"{biome_words(biome)}, which it has never seen"
    if unmet_kinds(s, biome):
        return 0.7, f"{biome_words(biome)}, where creatures it never met live"
    for kind, ox, oz in openings_near(s.seed, x, z, OPENING_NEAR):
        if not looked_into(s, ox, oz):
            return 0.6, opening_words(kind)
    new = area_novelty(s, patch_of(x, z)) / 9
    return (0.3, "new ground") if new >= NEW_ENOUGH else (0.0, "")


def wander_spots(s: Situation) -> list[tuple[int, int, str]]:
    """New ground farther out: columns FAR_OUT blocks away at 16 headings, within WANDER_REACH of
    home, in patches Mimo did not visit lately and whose area is new enough, so a pet that walked
    all the land near it lately still finds somewhere new to go."""
    home, (x, _, z) = home_cell(s), s.here
    found = []
    for heading in range(HEADINGS):
        angle = heading * 2 * math.pi / HEADINGS
        tx, tz = x + round(math.cos(angle) * FAR_OUT), z + round(math.sin(angle) * FAR_OUT)
        if home is not None and math.hypot(tx - home[0], tz - home[2]) > WANDER_REACH:
            continue
        patch = patch_of(tx, tz)
        if not lately(s, patch) and area_novelty(s, patch) / 9 >= NEW_ENOUGH:
            found.append((tx, tz, "new ground farther out"))
    return found


def wander_look(s: Situation, context: ActionContext) -> Find | None:
    """Anything new since the trip began, more than new ground, is what it came for."""
    noticed = (s.brain.get("curiosity") or {}).get("noticed_at")
    since = (s.brain.get("trip") or {}).get("since")
    if noticed is None or since is None or noticed < since:
        return None
    return Find("something new", True, new=False)


register_reason(Reason(
    "wander", "look for something new", wander_wanted, wander_value, lambda s: 35.0,
    goals=("new_land", "new_creature", "cave", "water", "far_hills"), spots=wander_spots, look=wander_look,
    reach=WANDER_REACH, spot_likely=0.3))


def time_to_wander(s: Situation, goal) -> dict | None:
    """Once needs are met and Mimo is curious, the day plan sets time aside to wander."""
    if value_of(s.brain) < PLAN_FROM or s.db is None or not needs_met(s.state, s.db) or goal.repeat:
        return None
    return {"text": "Take time to wander and see something new", "kind": "wander"}


PLAN_EXTRAS.append(time_to_wander)

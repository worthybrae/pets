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
- Discoveries lower it (`discovered`): ground it never walked (NEW_GROUND, once a step; L4b: never
  below GROUND_FLOOR, though it still counts as a discovery), a biome it
  never saw (NEW_BIOME: "Pip saw the taiga for the first time."), a kind of block it never dug
  (NEW_BLOCK), a kind of creature it never met (NEW_CREATURE: "Pip met its first sheep."), and a
  place new to it (NEW_PLACE: each "found" or "discovered" event of the step, as first ores and
  water are, and each new place a trip finds, trips.FINDS; the first home is its own event, from
  brain.notice_step, outside this count). The biomes, blocks and creatures it met are remembered in
  memory_knowledge (facts "biome", "block" and "creature", with when). The biome it hatched in is
  known from the start, without a word -- and on an old save (fix round 1, widened in fix round 2),
  so is everything else it already has: the biome at the corners and centre of every patch it
  explored, every creature kind standing in one now (dead or alive, the creatures table, not only
  those in sight of where Mimo stands), the kinds its carried drops or past hunts and catches imply
  (`drop_kinds`, `past_creatures`: raw or cooked meat, hides, wool, feathers, string and the like,
  and the "hunted a sheep" / "caught a fish" events already logged, and, the final fix wave, "saw a
  skitter coming" / "fought off a gloomling"), and the block kinds it carries
  or has built with (`old_save`, `learn_quietly`), so upgrading a life never floods the notable feed
  with false "firsts" (fish it already ate, an animal it already hunted, a biome only a patch's edge
  touches) or drops curiosity for half a day.
- High curiosity lifts every explore trip (`lift`, trips.LIFTS): nothing at all while Mimo is hungry
  (HUNGRY_BELOW) or tired (TIRED_BELOW) enough that eating or sleeping matter more (fix round 2: the
  SURVIVAL_FLOOR cap below only stops it from outscoring a need once that need is already above 80,
  which left it beating eat and sleep just under that); otherwise LIFT_RATE a point past LIFTED, up
  to 30 more at 100, and even then never past SURVIVAL_FLOOR (purposes.py, fix round 1: the same
  ceiling a goal's own boost respects), into the work band but no further. From RESTLESS on,
  exploring meets a need (goals.URGES), so goal work does not crowd it out. Curiosity is always a
  reason of its own, the "wander" trip ("look for something new": land it has never seen, a biome
  where creatures it never met live, a cave mouth it has not looked into, then new ground, near or
  FAR_OUT blocks away, its own shorter cooldown between trips, WANDER_PENALTY_SECONDS, fix round 2:
  the trade-off ruling, since its targets move on their own and the usual TRIP_PENALTY_SECONDS paced
  it into most of a rest, but leaving it exempt let the far more frequent trips crowd out goal
  work): when nothing for its goal or a need is on offer, Mimo goes to see something new rather than
  sit and rest (the trip serves the discovery goals, so it is worked toward one of them meanwhile).
  L4a final fix wave, I4: a wander (and a discovery goal's trip, backend.survival.discovery) reaches
  `trip_reach` blocks from home, WANDER_REACH at first and RING more for each ring of land out from
  there Mimo has mostly walked (RING_WALKED of its dry patches), up to home.FARTHEST_TRIP, so a pet
  that has walked the land near home still finds new land after day 3; and it heads for ground it
  never walked (a heading counts as new ground only with NEW_PATCHES of its 9 patches unwalked, and
  `toward` gives spots on the way to the nearest unwalked land within reach, a walk at a time). Once its needs are met and it is curious (PLAN_FROM), the day plan
  sets time aside to wander (goals.PLAN_EXTRAS), ticked off by the next discovery.
- The model is told how it feels (`feeling`, `curiosity_view`): "restless; nothing new for 2 game
  days".
The tick tends it (`tend_curiosity`, from brain.notice_step; the creatures in sight are looked over
there, once a game minute) and hears about each finished step (`note_discoveries`, from
brain.observe_step). A crash is logged once and the tick goes on.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from typing import TYPE_CHECKING

from backend.services.crafting import BLOCKS
from backend.services.worldgen import biome_at
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import KINDS, land_kinds
from backend.survival.creatures.table import dead
from backend.survival.exploring import HEADINGS, area_novelty, dry_patches, home_cell, lately, visited
from backend.survival.goals import PLAN_EXTRAS, add_urge
from backend.survival.home import FARTHEST_TRIP, walked_near_home
from backend.survival.life_goals import looked_into, opening_words, openings_near
from backend.survival.memory import BUILT, PATCH, know, known, patch_of, places
from backend.survival.once import log_once
from backend.survival.purposes import HOME_RANGE, HUNGRY_BELOW, TIRED_BELOW
from backend.survival.situation import Situation
from backend.survival.steps import as_cell, label
from backend.survival.triggers import ensure_brain
from backend.survival.trips import FINDS, LIFTS, WANDER_PENALTY_SECONDS, Find, Reason, register_reason

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

START = 40.0
CLOCK_HOUR = DAY_SECONDS / 24  # game seconds in an hour of the day's clock
GROWTH = 2.0  # points a clock hour
NEEDS_MET = 1.5  # times faster once needs are met
NEW_GROUND = 1.0  # L4b (was 3): walking its own land is a small discovery, so a pet grows restless and sets out
GROUND_FLOOR = 40.0  # L4b: new ground alone never takes curiosity below this; the other discoveries still can
NEW_BIOME = 30.0
NEW_BLOCK = 6.0
NEW_CREATURE = 20.0
NEW_PLACE = 10.0
LIFTED = 50.0  # curiosity past this lifts explore...
LIFT_RATE = 0.6  # ...this much a point
CURIOUS = 60.0  # it feels restless from here on
WANDER_REACH = 90.0  # blocks from home a wander trip may go, as far as the discovery goals look...
# ...and I4 (the final fix wave): RING more for each ring of land out from there that Mimo has mostly
# walked (RING_WALKED of its dry patches), up to home.FARTHEST_TRIP; the numbers are the final fix
# wave's measure over 6-day lives (its report).
RING = 30.0
RING_WALKED = 0.6
NEW_ENOUGH = 0.25  # ground this new (exploring.area_novelty over 9) is worth a wander
NEW_PATCHES = 3  # I4: of the 9 patches round a heading's column, this many never walked make it new ground
FAR_OUT = 72  # blocks away a wander also heads for new ground, past what explore's targets reach
TOWARD = 3  # I4: spots a trip heads for on the way to land farther out, the nearest first
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


def patch_points(rx: int, rz: int) -> list[tuple[int, int]]:
    """The corners and centre of an 8x8 patch, so a patch a biome only edges into is not missed by
    sampling its centre alone (fix round 2)."""
    x0, z0 = rx * PATCH, rz * PATCH
    x1, z1 = x0 + PATCH - 1, z0 + PATCH - 1
    return [(x0, z0), (x0, z1), (x1, z0), (x1, z1), (x0 + PATCH // 2, z0 + PATCH // 2)]


def drop_kinds() -> dict[str, str]:
    """Every item a creature kind drops, and what cooking makes from it, back to the kind (fix
    round 2): raw_mutton and wool to sheep, raw_beef and leather to cow, and so on. Built fresh each
    call since KINDS keeps filling in as more of L2's hostile kinds import (gloom_dust to gloomling,
    string to skitter); this only ever runs once per life, on an old save's first tend."""
    found = {"raw_fish": "fish", "cooked_fish": "fish"}
    for kind in KINDS.values():
        for item in kind.drops:
            found.setdefault(item, kind.name)
            if item.startswith("raw_"):
                found.setdefault(f"cooked_{item[4:]}", kind.name)
    return found


# (event kind, what its text starts with, what it ends with) for the events that name a creature Mimo
# met: a hunt ("Pip hunted a sheep."), and (L4a final fix wave) a hostile it saw coming ("Pip saw a
# skitter coming.") or fought off ("Pip fought off a gloomling."), which one upgrade otherwise
# announced as a false "met its first skitter".
MET_IN_EVENTS = (("hunt", "hunted a ", "."), ("threat", "saw a ", " coming."), ("fight", "fought off a ", "."))


def past_creatures(db, name: str) -> set[str]:
    """Creature kinds this life hunted, fished, saw coming or fought off before (fix round 2, and
    the final fix wave for the last two), from the event log: a kind long gone from view and never
    carried leaves no other trace. A world read before mimo_events existed (an archive, or a light
    test fixture) has none."""
    found = set()
    kinds = ("fish", *(kind for kind, _, _ in MET_IN_EVENTS))
    try:
        rows = db.execute(f"SELECT kind, text FROM mimo_events WHERE kind IN ({','.join('?' * len(kinds))})",
                          kinds).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return found
    for kind_col, text in rows:
        if kind_col == "fish" and text == f"{name} caught a fish.":
            found.add("fish")
            continue
        for kind, start, end in MET_IN_EVENTS:
            opening = f"{name} {start}"
            if kind_col == kind and text.startswith(opening) and text.endswith(end):
                slug = text[len(opening):len(text) - len(end)].replace(" ", "_")
                if slug in KINDS:
                    found.add(slug)
    return found


def learn_quietly(state: dict, context: ActionContext, at: float) -> None:
    """An old save's first tend (fix round 1, widened in fix round 2): everything curiosity would
    otherwise announce as a "first" is already old news to Mimo, so it is learned with no events and
    no drop -- the biome at the corners and centre of every patch it explored, every creature kind
    standing in one now (dead or alive: a kind it already hunted there still counts), the kinds its
    carried drops or logged hunts and catches imply, and the block kinds it carries or has built
    with. Without this an upgraded world kept logging "met its first sheep" (one it had already
    hunted), "met its first fish" (one it had already caught 77 times) and "saw a swamp for the
    first time" (one its patches had always touched) for a game minute or two after the upgrade,
    crowding the notable feed and dropping curiosity toward 0."""
    db, seed = context.db, state["world_seed"]
    herd = context.grid.herd
    for rx, rz in db.execute("SELECT rx, rz FROM memory_explored").fetchall():
        for x, z in patch_points(rx, rz):
            know(db, biome_at(x, z, seed), "biome", at)
        if herd is not None:
            cx, cz = rx * PATCH + PATCH // 2, rz * PATCH + PATCH // 2
            for creature in herd.near(cx, cz, PATCH):
                know(db, creature["kind"], "creature", at)
    if herd is not None:
        x, _, z = as_cell(state["position"])
        for kind in {creature["kind"] for creature in herd.near(x, z, CREATURE_SIGHT) if not dead(creature)}:
            know(db, kind, "creature", at)
    for item, kind in drop_kinds().items():
        if state["inventory"].get(item):
            know(db, kind, "creature", at)
    for kind in past_creatures(db, state["name"]):
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
        walked = ensure_brain(state).get("new_ground_at") == at
        # L4b: new ground alone never takes curiosity below GROUND_FLOOR (it is still a discovery).
        ground = min(NEW_GROUND, max(0.0, value_of(state["brain"]) - GROUND_FLOOR)) if walked else 0.0
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
        if drop or walked:
            discovered(state, at, drop + ground, ground_only=not drop)
    except Exception as error:
        log_once(logger, "curiosity discoveries", error)


def place_found(state: dict, find: Find, at: float) -> None:
    if find.new:
        discovered(state, at, NEW_PLACE)


FINDS.append(place_found)


# What curiosity does ---------------------------------------------------------------------------

def lift(s: Situation) -> float:
    """What curiosity adds to explore's score: LIFT_RATE a point past LIFTED. Fix round 2: nothing
    at all while Mimo is hungry (HUNGRY_BELOW) or tired (TIRED_BELOW) enough that eat or sleep
    matter more -- the SURVIVAL_FLOOR cap (purposes.explore_score) only bites once eat or sleep
    already score above it, so a curiosity-maxed pet still edged out real needs scoring just under
    80 (hunger 20-28, energy 20-29) until this was zeroed at the source."""
    if s.vitals["hunger"] < HUNGRY_BELOW or s.vitals["energy"] < TIRED_BELOW:
        return 0.0
    return max(0.0, value_of(s.brain) - LIFTED) * LIFT_RATE


def restless(s: Situation) -> bool:
    """From RESTLESS on, exploring meets a need (goals.URGES)."""
    return value_of(s.brain) >= RESTLESS


LIFTS.append(lift)
add_urge("explore", restless)


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


def trip_reach(s: Situation) -> float:
    """How far from home a wander or discovery trip may go now (I4, the final fix wave): WANDER_REACH,
    and RING more for each ring of land out from there Mimo has mostly walked (RING_WALKED of the
    ring's dry patches; a ring with no dry land counts as walked), up to FARTHEST_TRIP. By day 3 or 4
    a pet had walked all the land within a fixed 90 blocks and settled back into resting; now the
    reach follows the land it has used up. Read once per Situation."""
    def look() -> float:
        home = home_cell(s)
        if home is None:
            return WANDER_REACH
        walked, reach = walked_near_home(s), WANDER_REACH
        while reach < FARTHEST_TRIP:
            ring = dry_patches(s.seed, home[0], home[2], reach - RING, reach)
            if ring and sum(patch in walked for patch in ring) < RING_WALKED * len(ring):
                break
            reach += RING
        return min(reach, FARTHEST_TRIP)
    return s.sensed("trip reach", look)


def toward(s: Situation, columns, short: float = 0.0) -> list[tuple[int, int, str]]:
    """Spots on the way to `columns`, (x, z, words) (I4): for the TOWARD of them nearest Mimo, the
    column itself when it lies within FAR_OUT, else the point FAR_OUT blocks along the way there (a
    trip's walks go all the way or not at all, and a walk that long is as far as one goes), so land
    farther out than one walk is reached a walk at a time. `short`: stop that many blocks before the
    column (at a lake's shore). One spot per patch."""
    x, _, z = s.here
    found, patches = [], set()
    for cx, cz, words in sorted(columns, key=lambda column: (math.hypot(column[0] - x, column[1] - z), column)):
        away = math.hypot(cx - x, cz - z)
        step = min(FAR_OUT, away - short)
        if step <= 0:
            continue
        tx, tz = x + round((cx - x) * step / away), z + round((cz - z) * step / away)
        if patch_of(tx, tz) in patches:
            continue
        patches.add(patch_of(tx, tz))
        found.append((tx, tz, words if step >= away else f"the way to {words}"))
        if len(found) >= TOWARD:
            break
    return found


def unwalked(s: Situation, beyond: float = 0.0) -> list[tuple[int, int]]:
    """The middles of the dry patches Mimo never walked farther than `beyond` and within trip_reach of
    home (I4), nearest home first ([] without a home)."""
    home = home_cell(s)
    if home is None:
        return []
    walked = walked_near_home(s)
    return [(rx * PATCH + PATCH // 2, rz * PATCH + PATCH // 2)
            for rx, rz in dry_patches(s.seed, home[0], home[2], beyond, trip_reach(s)) if (rx, rz) not in walked]


def new_patches(s: Situation, patch: tuple[int, int]) -> int:
    """How many of a patch and its 8 neighbours Mimo never walked."""
    known, (rx, rz) = visited(s), patch
    return sum((rx + dx, rz + dz) not in known for dx in (-1, 0, 1) for dz in (-1, 0, 1))


def wander_spots(s: Situation) -> list[tuple[int, int, str]]:
    """New ground farther out: columns FAR_OUT blocks away at 16 headings, within trip_reach of
    home, in patches Mimo did not visit lately and whose area holds ground it never walked
    (NEW_PATCHES of its 9; I4: "new enough" by novelty alone let a pet circle ground it walked a day
    before); and (I4) on the way to the ground it never walked within that reach (`toward`,
    `unwalked`), so once the land near home is walked a trip still heads out to new land."""
    home, (x, _, z) = home_cell(s), s.here
    reach, found = trip_reach(s), []
    for heading in range(HEADINGS):
        angle = heading * 2 * math.pi / HEADINGS
        tx, tz = x + round(math.cos(angle) * FAR_OUT), z + round(math.sin(angle) * FAR_OUT)
        if home is not None and math.hypot(tx - home[0], tz - home[2]) > reach:
            continue
        patch = patch_of(tx, tz)
        if not lately(s, patch) and area_novelty(s, patch) / 9 >= NEW_ENOUGH and new_patches(s, patch) >= NEW_PATCHES:
            found.append((tx, tz, "new ground farther out"))
    return found + toward(s, [(x, z, "land it never walked") for x, z in unwalked(s)])


def wander_look(s: Situation, context: ActionContext) -> Find | None:
    """Anything new since the trip began, more than new ground, is what it came for."""
    noticed = (s.brain.get("curiosity") or {}).get("noticed_at")
    since = (s.brain.get("trip") or {}).get("since")
    if noticed is None or since is None or noticed < since:
        return None
    return Find("something new", True, new=False)


# The discovery goals it serves are named by backend.survival.discovery (GOAL_NAMES), which
# registers it again with them.
register_reason(Reason(
    "wander", "look for something new", wander_wanted, wander_value, lambda s: 35.0,
    spots=wander_spots, look=wander_look, reach=trip_reach, cooldown=WANDER_PENALTY_SECONDS,
    roams_from=HOME_RANGE))


def time_to_wander(s: Situation, goal) -> dict | None:
    """Once needs are met and Mimo is curious, the day plan sets time aside to wander."""
    if value_of(s.brain) < PLAN_FROM or s.db is None or not needs_met(s.state, s.db) or goal.repeat:
        return None
    return {"text": "Take time to wander and see something new", "kind": "wander"}


PLAN_EXTRAS.append(time_to_wander)

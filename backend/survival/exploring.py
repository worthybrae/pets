"""Where Mimo has been, and where it explores next.

Mimo remembers the ground it walked in 8x8-block patches (memory.memory_explored). `note_ground`
hears about every finished step (brain.observe_step): a walk or swim counts a visit to each
distinct patch along its path (and to its target's, when it ended within reach of it: Mimo saw
it), any other step a visit to the patch Mimo stands in. The server
time a patch was first visited is kept as the brain's `new_ground_at`. A patch visited for the
first time more than 32 blocks from home is looked over: ripe wild food or natural water that
Mimo does not remember yet (none of its kind known within 24 blocks) is remembered and is a
discovery, which the brain announces.

explore (purposes.py) walks to `explore_target`: out of 16 headings at 32 and 48 blocks (and 64
too once all of those are well explored), the dry spot whose patch and its 8 neighbours Mimo has
seen least (few visits, long ago), with a small bonus for distance and a small seeded jitter, so
ties vary from trip to trip. A spot is never in water (natural or not: the Grid is asked), never
within 4 blocks of a step that just failed, never in the patch Mimo stands in or one it visited
less than a game day ago (so it does not pace between two spots), and with a home known never
farther than 60 blocks from it, so go_home (64 blocks) still finds its way back by dusk. With no
such spot there is nothing to explore.

`survey` sums up the land within 64 blocks: how many patches Mimo visited, and how much dry land
it has not seen yet in each of the 8 compass directions (north is -z, east is +x). explore scores
lower with little new land near, and its facts and the model payload (`exploration_payload`) say
the same in words and numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.services.worldgen import LEGACY_RADIUS, SEA_LEVEL, terrain_height
from backend.survival import nature
from backend.survival.clock import DAY_SECONDS
from backend.survival.grid import Cell, Grid
from backend.survival.memory import (
    PATCH, cell_of, explored, known, mark_explored, nearest, patch_of, places, remember, update_place,
)
from backend.survival.senses import FOOD_SIGHT, PICKABLE, WATER_SIGHT, natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain

PATH_KINDS = ("walk", "swim")
HEADINGS = 16
DISTANCES = (32, 48)
FAR = 64  # tried too once every nearer candidate is well explored
WELL_EXPLORED = 2.0  # an area (a patch and its 8 neighbours) this novel or less is well explored
FORGET = DAY_SECONDS  # game seconds after a visit until a patch feels as new as it ever will again
DISTANCE_BONUS = 0.5  # novelty points for going 64 blocks rather than none
JITTER = 0.3  # at most this many novelty points of seeded chance, so ties vary
EXPLORE_ROLL = 40  # nature.roll channel for the jitter
LEASH = 60.0  # with a home known, explore targets stay this close to it
SURVEY = 64  # blocks around Mimo that the survey looks at
SAMPLES = ((2, 2), (6, 2), (2, 6), (6, 6))  # columns sampled in a patch to guess its dry land
COMPASS = ("east", "southeast", "south", "southwest", "west", "northwest", "north", "northeast")
TOP_DIRECTIONS = 3
FOUND_KINDS = ("ore", "water", "food", "farm", "home")
AWAY = 32.0  # new ground farther than this from home may hold a discovery
SIGHT = max(FOOD_SIGHT, WATER_SIGHT)  # food or water this close to a known place of its kind is not new
FOOD_WORDS = {"berry_bush_ripe": "berries", "brown_mushroom": "mushrooms", "red_mushroom": "mushrooms"}


# Remembering the ground --------------------------------------------------------------------------

def path_patches(path: list[dict]) -> list[tuple[int, int]]:
    """The distinct patches a path crosses, in the order it enters them."""
    return list(dict.fromkeys(patch_of(int(entry["x"]), int(entry["z"])) for entry in path))


def finds_in(grid: Grid, seed: str, patch: tuple[int, int], poisons=()) -> list[tuple[str, Cell, str, int]]:
    """What a patch holds that is worth remembering, as (kind, cell, words, how many): ripe wild
    food Mimo would pick (not what it knows is poisonous), and natural water."""
    rx, rz = patch
    x0, z0 = rx * PATCH, rz * PATCH
    wanted = tuple(block for block in PICKABLE if block not in poisons)
    food = sorted(cell for cell in natural_plants(seed, x0 + PATCH / 2, z0 + PATCH / 2, PATCH, PICKABLE)
                  if x0 <= cell[0] < x0 + PATCH and z0 <= cell[2] < z0 + PATCH and grid.material(*cell) in wanted)
    found = []
    if food:
        found.append(("food", food[0], FOOD_WORDS[grid.material(*food[0])], len(food)))
    water = [(x, SEA_LEVEL, z) for x in range(x0, x0 + PATCH) for z in range(z0, z0 + PATCH)
             if terrain_height(x, z, seed) < SEA_LEVEL and grid.water((x, SEA_LEVEL, z))]
    if water:
        found.append(("water", water[0], "water", len(water)))
    return found


def discoveries(state: dict, context, patches: list[tuple[int, int]], at: float) -> list[tuple[str, str]]:
    """Remember what new patches far from home hold. Returns (kind, words) for each new place: food
    or water with none of its kind remembered within sight of it (24 blocks), since Mimo would see
    that from there anyway."""
    db = context.db
    home = places(db, ("home",))
    poisons = known(db, "poisonous")
    found = []
    for rx, rz in patches:
        middle = (rx * PATCH + PATCH / 2, rz * PATCH + PATCH / 2)
        if home and math.hypot(middle[0] - home[0]["x"], middle[1] - home[0]["z"]) <= AWAY:
            continue
        for kind, cell, words, count in finds_in(context.grid, state["world_seed"], (rx, rz), poisons):
            if nearest(places(db, (kind,), around=cell, reach=SIGHT), cell, (kind,), SIGHT) is not None:
                continue
            if remember(db, kind, cell, at):
                if kind == "food":
                    update_place(db, "food", cell, {"ripe": count, "seen_at": at})
                found.append((kind, words))
    return found


def note_ground(state: dict, step: dict, context, at: float) -> list[tuple[str, str]]:
    """Mark the ground a finished step covered as visited, and look over the patches it saw for the
    first time. Returns what was discovered there, as (kind, words)."""
    if context.db is None:
        return []
    if step["kind"] in PATH_KINDS:
        patches = path_patches(step.get("path") or [])
        target = step.get("target")
        if step.get("reached") and isinstance(target, dict):
            patches.append(patch_of(int(target["x"]), int(target["z"])))  # seen from within reach
    else:
        x, _, z = as_cell(state["position"])
        patches = [patch_of(x, z)]
    new = mark_explored(context.db, patches, at)
    if not new:
        return []
    ensure_brain(state)["new_ground_at"] = at
    return discoveries(state, context, new, at)


def visited(s: Situation) -> dict[tuple[int, int], tuple[int, float]]:
    """The patches Mimo visited within reach of anything explore or the survey looks at."""
    reach = FAR + 2 * PATCH
    return s.sensed("explored", lambda: explored(s.db, s.here, reach) if s.db is not None else {})


# Choosing where to go --------------------------------------------------------------------------

def dry_target(grid: Grid, seed: str, x: int, z: int) -> Cell | None:
    """Where Mimo would stand in the column: one above the natural ground, when that cell is
    standable and there is no water in the column from the ground up to sea level (the Grid is
    asked, so edits count). None otherwise."""
    ground = terrain_height(x, z, seed)
    if any(grid.water((x, y, z)) for y in range(ground, max(ground + 1, SEA_LEVEL) + 1)):
        return None
    cell = (x, ground + 1, z)
    return cell if grid.standable(cell) else None


def novelty(visit: tuple[int, float] | None, s: Situation) -> float:
    """1 for a patch Mimo never visited; a visited one up to 0.5, less the more often and the
    more lately it went there."""
    if visit is None:
        return 1.0
    visits, last_at = visit
    age = max(0.0, (s.at - last_at) * s.scale)
    return 0.5 * min(1.0, age / FORGET) / max(1, visits)


def area_novelty(s: Situation, patch: tuple[int, int]) -> float:
    """The novelty of a patch and its 8 neighbours, from 0 (all seen just now) to 9 (all new)."""
    known = visited(s)
    rx, rz = patch
    return sum(novelty(known.get((rx + dx, rz + dz)), s) for dx in (-1, 0, 1) for dz in (-1, 0, 1))


@dataclass(frozen=True)
class Candidate:
    cell: Cell
    distance: int
    novelty: float
    score: float


def home_cell(s: Situation) -> Cell | None:
    home = nearest(s.places, s.here, ("home",))
    return None if home is None else cell_of(home)


def leashed(s: Situation, home: Cell | None, cell: Cell) -> bool:
    """Too far from home: beyond LEASH, and no nearer to it than Mimo is now."""
    if home is None:
        return False
    away = math.hypot(cell[0] - home[0], cell[2] - home[2])
    return away > LEASH and away >= math.hypot(s.here[0] - home[0], s.here[2] - home[2])


def lately(s: Situation, patch: tuple[int, int]) -> bool:
    """Mimo visited the patch less than a game day ago."""
    visit = visited(s).get(patch)
    return visit is not None and (s.at - visit[1]) * s.scale < FORGET


def candidates(s: Situation, distances: tuple[int, ...]) -> list[Candidate]:
    """The dry spots explore may head for at these distances, scored."""
    x, _, z = s.here
    here, home, turn = patch_of(x, z), home_cell(s), s.brain["explored"]
    found = []
    for distance in distances:
        for heading in range(HEADINGS):
            angle = heading * 2 * math.pi / HEADINGS
            tx, tz = x + round(math.cos(angle) * distance), z + round(math.sin(angle) * distance)
            patch = patch_of(tx, tz)
            if patch == here or lately(s, patch):
                continue
            cell = dry_target(s.grid, s.seed, tx, tz)
            if cell is None or near_failure(s.state, cell) or leashed(s, home, cell):
                continue
            new = area_novelty(s, patch)
            jitter = JITTER * nature.roll(s.seed, (tx, 0, tz), EXPLORE_ROLL, turn)
            found.append(Candidate(cell, distance, new, new + DISTANCE_BONUS * distance / FAR + jitter))
    return found


def explore_target(s: Situation) -> Cell | None:
    """The best dry spot to explore now, or None when there is none."""
    def look() -> Cell | None:
        found = candidates(s, DISTANCES)
        if all(candidate.novelty <= WELL_EXPLORED for candidate in found):
            found += candidates(s, (FAR,))
        if not found:
            return None
        return max(found, key=lambda candidate: (candidate.score, candidate.cell)).cell
    return s.sensed("explore_target", look)


# The lay of the land ---------------------------------------------------------------------------

def compass(dx: float, dz: float) -> str:
    """The compass direction of a horizontal offset: north is -z, east is +x."""
    return COMPASS[round(math.atan2(dz, dx) / (math.pi / 4)) % 8]


def dry_blocks(seed: str, rx: int, rz: int) -> int:
    """About how many dry columns a patch has, from a few natural samples (no block reads)."""
    dry = 0
    for dx, dz in SAMPLES:
        x, z = rx * PATCH + dx, rz * PATCH + dz
        dry += terrain_height(x, z, seed) >= SEA_LEVEL or math.hypot(x, z) <= LEGACY_RADIUS
    return dry * PATCH * PATCH // len(SAMPLES)


@dataclass(frozen=True)
class Survey:
    patches: int = 0  # patches whose middle lies within SURVEY blocks
    seen: int = 0  # of those, the ones Mimo visited
    land: int = 0  # dry blocks in them, about
    new_land: int = 0  # dry blocks in the ones it never visited, about
    directions: dict = field(default_factory=dict)  # compass name -> new_land that way

    @property
    def share(self) -> float:
        """The fraction of the patches within reach Mimo visited at least once."""
        return self.seen / self.patches if self.patches else 1.0

    @property
    def new_share(self) -> float:
        """The fraction of the dry land within reach Mimo never set foot on."""
        return self.new_land / self.land if self.land else 0.0

    def unexplored(self, top: int = TOP_DIRECTIONS) -> list[tuple[str, int]]:
        """The compass directions with the most new land, most first, leaving out the ones with none."""
        ranked = sorted(self.directions.items(), key=lambda item: (-item[1], COMPASS.index(item[0])))
        return [(name, blocks) for name, blocks in ranked if blocks > 0][:top]


def survey(s: Situation) -> Survey:
    """How much of the land within 64 blocks Mimo has seen, and which way the new land lies."""
    def look() -> Survey:
        x, _, z = s.here
        known = visited(s)
        low_x, low_z = patch_of(x - SURVEY, z - SURVEY)
        high_x, high_z = patch_of(x + SURVEY, z + SURVEY)
        patches = seen = land = new_land = 0
        directions = {name: 0 for name in COMPASS}
        for rx in range(low_x, high_x + 1):
            for rz in range(low_z, high_z + 1):
                dx, dz = rx * PATCH + PATCH / 2 - x, rz * PATCH + PATCH / 2 - z
                if math.hypot(dx, dz) > SURVEY:
                    continue
                patches += 1
                dry = dry_blocks(s.seed, rx, rz)
                land += dry
                if (rx, rz) in known:
                    seen += 1
                else:
                    new_land += dry
                    directions[compass(dx, dz)] += dry
        return Survey(patches, seen, land, new_land, directions)
    return s.sensed("survey", look)


def and_list(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def survey_text(s: Situation) -> str:
    """The survey in words: "north and east are unexplored; 40% of the land within 64 blocks seen"."""
    found = survey(s)
    names = [name for name, blocks in found.unexplored() if blocks >= PATCH * PATCH]
    ways = f"{and_list(names)} {'is' if len(names) == 1 else 'are'} unexplored" if names else "no new land near"
    return f"{ways}; {round(found.share * 100)}% of the land within {SURVEY} blocks seen"


def exploration_payload(s: Situation) -> dict:
    """What a model is told about exploring: how much of the land within 64 blocks Mimo has seen,
    the 3 directions with the most new land (about how many blocks each), the places it knows by
    kind and the game seconds since it last set foot on new ground (None: never)."""
    found = survey(s)
    counts = {kind: 0 for kind in FOUND_KINDS}
    for place in s.places:
        if place["kind"] in counts:
            counts[place["kind"]] += 1
    new_ground_at = s.brain.get("new_ground_at")
    return {
        "explored_share": round(found.share, 2),
        "unexplored_directions": [{"direction": name, "blocks": blocks} for name, blocks in found.unexplored()],
        "found": counts,
        "last_new_ground_at": None if new_ground_at is None else round(max(0.0, s.at - new_ground_at) * s.scale),
    }

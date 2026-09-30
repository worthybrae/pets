"""Where animals come from (spec L1, "Spawning").

The first time Mimo comes within 48 blocks of a 16x16 chunk, the chunk's herds spawn: 0, 1 or 2
of them (a roll fixed by the world seed and the chunk), each of a kind that lives in the biome at
its spot, and a school of fish when the chunk has natural water. Spots are rolled columns in the
chunk whose cell above the ground is standable and dry, and not a cell something Mimo built
claims; a herd spreads over the spot and the cells around it. The chunk is noted in
creature_chunks, so it never spawns twice.

Numbers are capped, land animals and fish apart: a herd stops growing once 24 land animals are
within 48 blocks of Mimo, and a school once 8 fish are, or once its 16x16 water region holds 6.
Fish are never hunted, so if they counted toward the animals' cap a lakeside would fill up with
fish for good and its herds could never come back. Spawning takes at most NEW_CHUNKS chunks a
call, nearest first. A chunk whose land animals have all been gone (hunted) for 3 game days
regains one herd. (L3's creature seeds add more.) W2: in winter the animals thin out: a new chunk rolls one
herd at most, the land cap near Mimo falls to WINTER_LAND_CAP, and a hunted-out chunk waits for spring to
regain its herd. Animals already alive stay.
"""

from __future__ import annotations

import math

from backend.services.worldgen import SEA_LEVEL, biome_at, hash32, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.kinds import Kind, kind_of, land_kinds, water_kinds
from backend.survival.creatures.table import dead
from backend.survival.grid import CHUNK, Cell, Grid
from backend.survival.sky import winter

SIM_REACH = 48.0
LAND_CAP = 24  # land animals within SIM_REACH of Mimo
WINTER_LAND_CAP = 12  # W2
WINTER_HERDS = 1  # W2: the most herds a chunk first met in winter rolls
FISH_CAP = 8  # fish within SIM_REACH of Mimo
FISH_PER_REGION = 6
REGAIN_SECONDS = 3 * DAY_SECONDS  # game seconds a chunk's land animals stay gone before a herd comes back
NEW_CHUNKS = 8  # chunks whose herds spawn in one call, nearest first; the rest wait for the next
HERD_ODDS = (0.35, 0.8)  # a chunk rolls no herd below the first, one below the second, else two
SPOT_TRIES = 6
FIRST_TURN_WITHIN = 2.0  # server seconds: new creatures take their first turn within this, not all at once
SPREAD = ((0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))
# Roll channels.
HERDS, SPOT_X, SPOT_Z, KIND, SIZE, FIRST = 60, 61, 62, 63, 64, 65

Herd = tuple[Kind, list[Cell]]


def chunk_roll(seed: str, chunk: tuple[int, int], index: int, channel: int, salt: int = 0) -> float:
    """A number in [0, 1) fixed by the world seed, the chunk, which herd or try it is and the channel."""
    return hash32(chunk[0], index + salt * 64, chunk[1], seed, channel) / 4294967296


def chunks_near(x: int, z: int, reach: float) -> list[tuple[int, int]]:
    """The chunks with some column within `reach` blocks of (x, z), nearest rows first."""
    found = []
    for cx in range(math.floor((x - reach) / CHUNK), math.floor((x + reach) / CHUNK) + 1):
        for cz in range(math.floor((z - reach) / CHUNK), math.floor((z + reach) / CHUNK) + 1):
            dx = max(cx * CHUNK - x, 0, x - (cx * CHUNK + CHUNK - 1))
            dz = max(cz * CHUNK - z, 0, z - (cz * CHUNK + CHUNK - 1))
            if math.hypot(dx, dz) <= reach:
                found.append((cx, cz))
    return found


def herd_count(seed: str, chunk: tuple[int, int]) -> int:
    chance = chunk_roll(seed, chunk, 0, HERDS)
    return 0 if chance < HERD_ODDS[0] else 1 if chance < HERD_ODDS[1] else 2


def dry_ground(grid: Grid, cell: Cell) -> bool:
    return grid.standable(cell) and not grid.swimming(cell) and not grid.claimed(cell)


def plan_herd(grid: Grid, seed: str, chunk: tuple[int, int], index: int, salt: int = 0) -> Herd | None:
    """The kind and cells of a chunk's `index`-th herd, or None when no rolled spot fits."""
    cx, cz = chunk
    for attempt in range(SPOT_TRIES):
        roll_at = index * SPOT_TRIES + attempt
        x = cx * CHUNK + int(chunk_roll(seed, chunk, roll_at, SPOT_X, salt) * CHUNK)
        z = cz * CHUNK + int(chunk_roll(seed, chunk, roll_at, SPOT_Z, salt) * CHUNK)
        kinds = land_kinds(biome_at(x, z, seed))
        spot = (x, terrain_height(x, z, seed) + 1, z)
        if not kinds or not dry_ground(grid, spot):
            continue
        kind = kinds[int(chunk_roll(seed, chunk, index, KIND, salt) * len(kinds))]
        low, high = kind.herd
        size = low + int(chunk_roll(seed, chunk, index, SIZE, salt) * (high - low + 1))
        cells = []
        for dx, dz in SPREAD:
            cell = (x + dx, terrain_height(x + dx, z + dz, seed) + 1, z + dz)
            if len(cells) < size and dry_ground(grid, cell):
                cells.append(cell)
        return kind, cells
    return None


def fish_school(grid: Grid, seed: str, chunk: tuple[int, int]) -> Herd | None:
    """Fish for a rolled column of natural water in the chunk (top water layer), or None."""
    kinds = water_kinds()
    if not kinds:
        return None
    cx, cz = chunk
    for attempt in range(SPOT_TRIES):
        x = cx * CHUNK + int(chunk_roll(seed, chunk, 100 + attempt, SPOT_X) * CHUNK)
        z = cz * CHUNK + int(chunk_roll(seed, chunk, 100 + attempt, SPOT_Z) * CHUNK)
        if terrain_height(x, z, seed) >= SEA_LEVEL or not grid.water((x, SEA_LEVEL, z)):
            continue
        kind = kinds[0]
        low, high = kind.herd
        size = low + int(chunk_roll(seed, chunk, 100, SIZE) * (high - low + 1))
        cells = [(x + dx, SEA_LEVEL, z + dz) for dx, dz in SPREAD if grid.water((x + dx, SEA_LEVEL, z + dz))]
        return kind, cells[:size]
    return None


def passive(creature: dict, water: bool) -> bool:
    """A creature of a known kind that is not hostile, and a fish when `water` (else a land animal)."""
    kind = kind_of(creature["kind"])
    return kind is not None and not kind.hostile and kind.water == water


def born(scene: Scene, kind: Kind, cell: Cell, chunk: tuple[int, int], number: int) -> dict:
    """A new creature of `kind` in `cell`, at home there, taking its first turn within 2 seconds."""
    first = chunk_roll(scene.seed, chunk, number, FIRST, int(scene.at)) * FIRST_TURN_WITHIN / scene.pace
    state = {"home": list(cell), "chunk": list(chunk), "pose": "swimming" if kind.water else "idle", "turn": 0}
    return scene.herd.add(kind.name, cell, kind.health, scene.at, scene.at + first, state)


def populate(scene: Scene, loaded: list[dict], scale: float) -> list[dict]:
    """Spawn the herds of up to NEW_CHUNKS chunks Mimo came near for the first time, nearest first,
    and bring a herd back to each chunk near Mimo whose land animals have been gone for 3 game
    days. `loaded` are the creatures within 48 blocks of Mimo. Returns the creatures it added."""
    x, _, z = scene.pet
    near = sorted(chunks_near(x, z, SIM_REACH),
                  key=lambda chunk: (math.hypot(chunk[0] * CHUNK + 8 - x, chunk[1] * CHUNK + 8 - z), chunk))
    known = scene.herd.chunks((min(c[0] for c in near), min(c[1] for c in near)),
                              (max(c[0] for c in near), max(c[1] for c in near)))
    alive = [creature for creature in loaded if not dead(creature)]
    counts = {water: sum(1 for creature in alive if passive(creature, water)) for water in (False, True)}
    wintry = winter(scene.state)  # W2: the animals thin out
    land_cap = WINTER_LAND_CAP if wintry else LAND_CAP
    added: list[dict] = []

    def room(kind: Kind, cell: Cell) -> bool:
        """Whether one more of `kind` fits in `cell` under the caps."""
        if not kind.water:
            return counts[False] < land_cap
        region = (cell[0] // CHUNK, cell[2] // CHUNK)
        return counts[True] < FISH_CAP and sum(
            1 for creature in alive + added if creature["kind"] == kind.name
            and (int(creature["x"]) // CHUNK, int(creature["z"]) // CHUNK) == region) < FISH_PER_REGION

    def place(herds: list[Herd], chunk: tuple[int, int]) -> int:
        """Add the herds' creatures as far as the caps allow; returns how many land animals came."""
        came = 0
        for kind, cells in herds:
            for cell in cells:
                if not room(kind, cell):
                    break
                counts[kind.water] += 1
                came += 0 if kind.water else 1
                added.append(born(scene, kind, cell, chunk, len(added)))
        return came

    fresh = 0
    for chunk in near:
        row = known.get(chunk)
        if row is None and fresh < NEW_CHUNKS:
            fresh += 1
            rolled = min(herd_count(scene.seed, chunk), WINTER_HERDS if wintry else 2)
            planned = (plan_herd(scene.grid, scene.seed, chunk, index) for index in range(rolled))
            herds = [herd for herd in planned if herd]
            school = fish_school(scene.grid, scene.seed, chunk)
            scene.herd.note_chunk(chunk, rolled, place(herds + ([school] if school else []), chunk), scene.at)
        elif (not wintry and row is not None and row["herds"] > 0 and row["animals"] == 0 and row["empty_since"] is not None
              and (scene.at - row["empty_since"]) * scale >= REGAIN_SECONDS):
            herd = plan_herd(scene.grid, scene.seed, chunk, 0, salt=int(scene.at))
            scene.herd.regained(chunk, place([herd], chunk) if herd else 0, scene.at)
    return added

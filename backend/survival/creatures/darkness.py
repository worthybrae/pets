"""Where hostile creatures come from, and where they go (spec L2, "Light levels" and "Hostile AI").

Once every SPAWN_EVERY game seconds (at most once a creature-hook call), while fewer than
HOSTILE_CAP hostiles are alive (counted in the table, not from what one call loaded; they are all
near Mimo, see below), the dark gets one chance to bring one near it:
up to SPAWN_TRIES columns 16 to 40 blocks from Mimo (rolled from the world seed and the time) are
searched from just over the natural ground down, however deep Mimo is (L3), but no more than SPAWN_RISE
cells above or below Mimo, for a cell where a creature can stand (dry, empty, room above it, not
on leaves), that nothing Mimo built claims (so never inside its shelter) and whose light is 7 or
less (backend.survival.light): they come out near where Mimo is, on the ground or in a cave
beside its tunnel, not in every cave under the land. The first such cell gets a
gloomling when it is open to the sky (dark ground at night) and, when it is covered (a cave, a
tunnel), a skitter three times in five, else a gloomling. By day the open ground is lit, so only
covered places spawn them; torches, lanterns and fires keep their surroundings lit at night.

Hostiles go too, in one cheap delete by kind and distance each call: any farther than
DESPAWN_REACH blocks from Mimo at night, and by day any beyond the 48 blocks the creature hook
simulates, since out there it would never burn, fade or come back. At night one beyond those 48
blocks whose turn has been due for LOITER game seconds fades as well, as a loiterer near Mimo
does, so frozen ones out of reach cannot hold the cap (final fix wave). Daylight burns or fades
those near Mimo caught under the open sky (backend.survival.creatures.hostiles, sunlit).
L5: a new hostile may be shaped before it is added (BIRTHS: backend.survival.creatures.ringed makes
one born farther from home tougher), and the cap may grow (MORE_ROOM: ringed adds one a danger level).
W2: in fog the open ground by day counts as dark for spawning (its sky light as FOG_SKY), and the cap grows by
backend.survival.weather's FOG_ROOM (0 since the controller's ruling on the W2 dry run).
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3

from backend.services.blocks import CANOPY, is_replaceable
from backend.services.worldgen import terrain_height
from backend.survival.creatures import hostiles  # noqa: F401  (registers the hostile kinds and their actions)
from backend.survival.creatures.acts import Scene
from backend.survival.creatures.hostiles import LOITER
from backend.survival.creatures.kinds import KINDS, Kind, hostile_kinds
from backend.survival.creatures.moves import roll
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.creatures.table import missing_table
from backend.survival.grid import Cell, Grid
from backend.survival.light import DARK, Lights, sky_light
from backend.survival.once import log_once
from backend.survival.sky import foggy

logger = logging.getLogger(__name__)

HOSTILE_CAP = 8
SPAWN_NEAR = 16.0
SPAWN_FAR = 40.0
DESPAWN_REACH = 64.0
SPAWN_EVERY = 30.0  # game seconds between two chances of a spawn
SPAWN_TRIES = 4  # columns one chance looks at
SPAWN_RISE = 8  # cells above or below Mimo a spawn may be (L3: the only bound on how deep)
SKITTER_SHARE = 0.6  # of the hostiles spawning in covered places
FIRST_TURN = 1.0  # server seconds before a new hostile's first turn
UNDERFOOT = CANOPY  # L3: no kind of leaves is ground to come out on
FOG_SKY = 6  # W2: open ground's sky light by day in fog, for spawning
# Roll channels.
ANGLE, DISTANCE, KIND = 110, 111, 112
# L5: functions (scene, kind, cell, state, health) -> health that shape a new hostile before it is
# added (backend.survival.creatures.ringed), and functions of the Scene that add room under
# HOSTILE_CAP. One that crashes changes nothing (logged once).
BIRTHS: list = []
MORE_ROOM: list = []


def despawn_far(scene: Scene) -> None:
    """Remove every hostile farther (horizontally) from Mimo than DESPAWN_REACH blocks at night, or
    than SIM_REACH by day. Final fix wave: at night one beyond SIM_REACH whose turn has been due
    for LOITER game seconds goes too. Out there nothing runs its turns, so it never loiters and
    fades as it would near Mimo (hostiles.prowl), and frozen ones could hold HOSTILE_CAP all night;
    one that walked out of reach a moment ago, still due only lately, stays in case Mimo comes back."""
    kinds = hostile_kinds()
    reach = DESPAWN_REACH if scene.night else SIM_REACH
    x, _, z = scene.pet
    marks = ','.join('?' * len(kinds))
    distance = "(x - ?) * (x - ?) + (z - ?) * (z - ?)"
    try:
        scene.herd.db.execute(f"DELETE FROM creatures WHERE kind IN ({marks}) AND {distance} > ?",
                              (*kinds, x, x, z, z, reach * reach))
        if scene.night:
            scene.herd.db.execute(f"DELETE FROM creatures WHERE kind IN ({marks}) AND {distance} > ? AND next_at < ?",
                                  (*kinds, x, x, z, z, SIM_REACH * SIM_REACH, scene.at - LOITER / scene.scale))
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise


def hostiles_alive(scene: Scene) -> int:
    """How many hostile creatures are alive, counted in the table."""
    kinds = hostile_kinds()
    try:
        rows = scene.herd.db.execute(f"SELECT state FROM creatures WHERE kind IN ({','.join('?' * len(kinds))})",
                                     kinds).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return 0
    return sum(1 for row in rows if json.loads(row[0] or "{}").get("pose") != "dead")


def spots(grid: Grid, seed: str, x: int, z: int, level: int) -> list[Cell]:
    """Cells in the column where a hostile could stand, highest first, within SPAWN_RISE of
    `level` (Mimo's height): empty (air or a plant), dry, on anything but leaves, with room over
    it, and claimed by nothing Mimo built."""
    top = terrain_height(x, z, seed) + 2
    found = []
    for y in range(min(top, level + SPAWN_RISE), level - SPAWN_RISE - 1, -1):
        cell = (x, y, z)
        if (is_replaceable(grid.material(*cell)) and grid.standable(cell) and not grid.swimming(cell)
                and grid.passable((x, y + 1, z)) and grid.material(x, y - 1, z) not in UNDERFOOT
                and not grid.claimed(cell)):
            found.append(cell)
    return found


def born(scene: Scene, kind: Kind, cell: Cell) -> dict:
    """A new hostile of `kind` in `cell`, at home there; its first turn comes a second later. L5: the
    BIRTHS hooks may change its health and state first."""
    state = {"home": list(cell), "pose": "idle", "turn": 0}
    health = kind.health
    for shape in BIRTHS:
        try:
            health = float(shape(scene, kind, cell, state, health))
        except Exception as error:
            log_once(logger, "hostile birth", error)
    return scene.herd.add(kind.name, cell, health, scene.at, scene.at + FIRST_TURN / scene.pace, state)


def cap(scene: Scene) -> int:
    """How many hostiles may be alive: HOSTILE_CAP, plus what MORE_ROOM adds (L5)."""
    room = 0
    for more in MORE_ROOM:
        try:
            room += int(more(scene))
        except Exception as error:
            log_once(logger, "hostile cap", error)
    return HOSTILE_CAP + room


def spawn_hostiles(scene: Scene) -> list[dict]:
    """Despawn far hostiles, then maybe spawn one in the dark near Mimo (see the module docstring).
    Returns the creatures it added.

    Fix round 1: near a hostile the tick calls this every game second (backend.survival.tick,
    FIGHT_SLICE), so the window check comes first and costs nothing but a dict lookup; the sweep
    and the count (each a table scan) run only on the call that could actually spawn something,
    at most once every SPAWN_EVERY game seconds. Fix round 2: `dark_spawn_at` is set right after
    that window check, before the sweep and the count -- setting it only once a chance is not also
    capped (as it was) left it unset, and so the window open, for as long as HOSTILE_CAP hostiles
    stayed alive, and the sweep and the count ran on every call again."""
    last = scene.state.get("dark_spawn_at")
    if last is not None and (scene.at - last) * scene.scale < SPAWN_EVERY:
        return []
    scene.state["dark_spawn_at"] = scene.at
    despawn_far(scene)
    if hostiles_alive(scene) >= cap(scene):
        return []
    x, y, z = scene.pet
    # Fix round 1: salted by game seconds, not server seconds, so two chances spaced SPAWN_EVERY
    # game seconds apart never share a salt even when a high MIMO_TIME_SCALE keeps `scene.at`
    # (server time) inside the same integer second for both.
    salt, lights = int(scene.at * scene.scale), None
    for attempt in range(SPAWN_TRIES):
        angle = 2 * math.pi * roll(scene.seed, salt, attempt, ANGLE)
        reach = SPAWN_NEAR + (SPAWN_FAR - SPAWN_NEAR) * roll(scene.seed, salt, attempt, DISTANCE)
        cx, cz = round(x + math.cos(angle) * reach), round(z + math.sin(angle) * reach)
        if math.hypot(cx - x, cz - z) < SPAWN_NEAR:
            continue
        for cell in spots(scene.grid, scene.seed, cx, cz, y):
            lights = lights or Lights(scene.grid, scene.pet, SPAWN_FAR, scene.seed)
            sky = sky_light(scene.grid, scene.seed, cell, scene.night)
            if sky > FOG_SKY and foggy(scene.state):  # W2: fog hides the sun
                sky = FOG_SKY
            # Fix round 2: `lights.dark` (not `lights.at`) -- this only ever needs the dark verdict,
            # and `dark` keeps `at` exact by using a narrower reach for lava just for that verdict.
            if sky > DARK or not lights.dark(cell):
                continue
            covered = sky == 0
            name = "skitter" if covered and roll(scene.seed, salt, attempt, KIND) < SKITTER_SHARE else "gloomling"
            return [born(scene, KINDS[name], cell)]
    return []

"""W2: thunderstorms, lightning and fire in the trees ("Lightning and fire" of the Wild World spec).

In a storm (sky weather "storm": rain with lightning) a strike falls every STRIKE_EVERY game seconds near a living
Mimo, at most one a step, so a catch-up never strikes more often (`storm`, a sky effect, before each step):
- "A thunderstorm rolled in." (a "storm" event) when one starts;
- when Mimo stands under the open sky in the highest column within MIMO_REACH blocks (a hilltop, a pillar, a
  treetop: `highest`), the strike hits it with chance STRUCK_CHANCE instead: STRUCK_DAMAGE health, armor no
  help, and a death by it reads "was struck by lightning" ("Lightning struck Pip!", a "struck" event). On flat
  ground or indoors Mimo is never struck;
- else it falls on the highest of SAMPLES columns within STRIKE_REACH blocks (seeded), a tree's top counting as
  its height (`column_top`), never within HOME_CLEAR blocks of the home Mimo built nor in the legacy clearing:
  "stay inside" means the yard. The latest KEPT strikes are kept for the viewer's bolt and flash.
A strike on a tree's top leaf or log (a natural one) sets it burning: a `fire` block (light 13, not solid;
"Lightning set a tree on fire near Pip.", a "fire" event). Every SPREAD_EVERY game seconds each burning cell may
spread to one neighbouring natural log or leaf (SPREAD_CHANCE, a third of that in rain); a fire burns at most
FIRE_CELLS cells in all (`burned`, by fire) and at most FIRES burn at once. Each cell burns out BURN_SECONDS after
it caught, leaving air (renewal then lets the leaves no log holds decay, as after chopping). Fire never enters a
cell Mimo built or edited, a claimed cell, anything within FIRE_CLEAR blocks of home, or the legacy clearing
(`may_burn`: a rim tree's canopy reaches into it). Mimo in or beside a burning cell takes FIRE_DAMAGE health a
game second (a death by it reads "was caught in a fire"); the flee_fire reflex takes it away, the tick takes
short steps while a fire is that close (`fire_near`), and routes keep out of burning cells and their neighbours
like lava (Grid.hot, read by pathing.moves; a fall still goes through them). Burned trees are ordinary block
edits, synced like chopping.

Cost (the spec's criterion 10, per transaction, fix round 4): the home Mimo built is read once a transaction
(`home_now`, kept in the tick's ActionContext.memo), the strike's cheap roll on Mimo comes before the 17 x 17
height check, and the heat's cells (`heat`) are worked out again only when the burning cells change.

The state lives in state["sky"]: `strike_at` (the last strike's time), `strikes` (the latest KEPT, {x, y, z,
at}), `fires` ({x, y, z, fire, caught, until}: `caught` the time the cell caught, at most FIRES x FIRE_CELLS),
`fire_id` (the last fire's number), `burned` ({fire: cells it caught}), `fire_at` (the last spread round),
`burned_at` (the fire's last look at Mimo) and `storming`. STRIKES hears of every strike
(backend.survival.sky_wild: knocks and wonders); one that crashes is logged once.
"""

from __future__ import annotations

import logging
import math
import sqlite3

from backend.services.crafting import LOGS
from backend.services.worldgen import LEGACY_RADIUS, terrain_height
from backend.survival import sky
from backend.survival.grid import Cell, Grid
from backend.survival.light import SKY_SCAN, sky_open
from backend.survival.memory import BUILT, places
from backend.survival.nature import LEAVES, roll
from backend.survival.once import log_once
from backend.survival.triggers import crossings, mark_trigger

logger = logging.getLogger(__name__)

STRIKE_EVERY = 60.0  # game seconds between two strikes in a storm
STRIKE_REACH = 48
SAMPLES = 6
MIMO_REACH = 8
STRUCK_CHANCE = 0.05
STRUCK_DAMAGE = 25.0
HOME_CLEAR = 16.0  # no strike this close to the home Mimo built
FIRE_CLEAR = 8.0  # no fire this close to it
KEPT = 5
SPREAD_EVERY = 10.0
SPREAD_CHANCE = 0.35
RAIN_SPREAD = 1 / 3
FIRE_CELLS = 24
FIRES = 2
BURN_SECONDS = (20.0, 40.0)
FIRE_DAMAGE = 2.0  # health a game second in or beside a burning cell
FIRE = "fire"
BURNS = frozenset(LOGS) | frozenset(LEAVES)
FACES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
# Roll channels (Wild World's are 200 to 259).
SAMPLE_CHANNEL, STRUCK_CHANNEL, SPREAD_CHANNEL, BURN_CHANNEL, PICK_CHANNEL = 232, 233, 234, 235, 236
# W2: functions (state, context, cell, struck, at) run after each strike: `struck` when it hit Mimo. One that
# crashes is logged once and passed over.
STRIKES: list = []
HOME, HOT = "storms: built home", "storms: hot"  # their keys in the tick's ActionContext.memo


def built_home(db: sqlite3.Connection | None) -> tuple[float, float] | None:
    """(x, z) of the home Mimo built, or None."""
    if db is None:
        return None
    try:
        home = next((place for place in places(db, ("home",)) if place["note"] == BUILT), None)
    except sqlite3.OperationalError:
        return None
    return None if home is None else (home["x"], home["z"])


def home_now(context) -> tuple[float, float] | None:
    """`built_home`, read once a transaction: the tick's context keeps it (ActionContext.memo), and building
    clears that when Mimo moves into a shelter it built, so the next step reads the new home. A context with no
    memo (a test's) reads it each time."""
    memo = getattr(context, "memo", None)
    if memo is None:
        return built_home(context.db)
    if HOME not in memo:
        memo[HOME] = built_home(context.db)
    return memo[HOME]


def near(point: tuple[float, float] | None, x: float, z: float, reach: float) -> bool:
    return point is not None and math.hypot(x - point[0], z - point[1]) <= reach


def column_top(grid: Grid, seed: str, x: int, z: int) -> Cell:
    """The highest cell in the column that is not air (a tree's top leaf counts)."""
    ground = terrain_height(x, z, seed)
    for y in range(ground + SKY_SCAN, ground - 1, -1):
        if grid.material(x, y, z) != "air":
            return x, y, z
    return x, ground, z


def highest(grid: Grid, seed: str, cell: Cell) -> bool:
    """Mimo's column is the highest within MIMO_REACH blocks: nothing in any other stands as high as the block
    Mimo stands on (so on flat ground it never is)."""
    x, y, z = cell
    for cx in range(x - MIMO_REACH, x + MIMO_REACH + 1):
        for cz in range(z - MIMO_REACH, z + MIMO_REACH + 1):
            if (cx, cz) == (x, z):
                continue
            if terrain_height(cx, cz, seed) >= y - 1 or any(grid.material(cx, cy, cz) != "air"
                                                             for cy in (y - 1, y, y + 1)):
                return False
    return True


def pet_cell(state: dict) -> Cell:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def hurt(state: dict, damage: float, source: str, at: float, context) -> None:
    """Lightning or fire takes health, as a blow would (the tick records a death by it with `source`)."""
    vitals = state["vitals"]
    before = dict(vitals)
    vitals["health"] = max(0.0, vitals["health"] - damage)
    state.update(hurt_at=at, hurt_by=source)
    for reason in crossings(before, vitals):
        mark_trigger(state, reason, at, urgent=True)


def strike(state: dict, context, at: float, home) -> None:
    """One strike near Mimo (see the module docstring)."""
    grid, seed, name = context.grid, state.get("world_seed", "0"), state["name"]
    here = pet_cell(state)
    salt = int((at - state["born_at"]) * context.clock_at(at)["time_scale"])
    struck = False
    if (math.hypot(here[0], here[2]) > LEGACY_RADIUS and not near(home, here[0], here[2], HOME_CLEAR)
            and roll(seed, here, STRUCK_CHANNEL, salt) < STRUCK_CHANCE  # the cheap roll before the height check
            and sky_open(grid, seed, here) and highest(grid, seed, here)):
        cell, struck = here, True
    else:
        columns = []
        for sample in range(SAMPLES):
            angle = 2 * math.pi * roll(seed, (sample, 0, 0), SAMPLE_CHANNEL, salt)
            reach = STRIKE_REACH * math.sqrt(roll(seed, (sample, 1, 0), SAMPLE_CHANNEL, salt))
            x, z = round(here[0] + math.cos(angle) * reach), round(here[2] + math.sin(angle) * reach)
            if math.hypot(x, z) <= LEGACY_RADIUS or near(home, x, z, HOME_CLEAR):
                continue
            columns.append(column_top(grid, seed, x, z))
        if not columns:
            return
        cell = max(columns, key=lambda top: top[1])
    sky_state = sky.sky_state(state)
    sky_state["strikes"] = [*sky_state["strikes"], {"x": cell[0], "y": cell[1], "z": cell[2], "at": at}][-KEPT:]
    if struck:
        hurt(state, STRUCK_DAMAGE, "lightning", at, context)
        state["last_thought"] = "Ow! The lightning hit me!"
        context.events.append((at, "struck", f"Lightning struck {name}!"))
    elif grid.material(*cell) in BURNS and may_burn(grid, cell, home):
        ignite(state, context, cell, at, None)
    for hears in STRIKES:
        try:
            hears(state, context, cell, struck, at)
        except Exception as error:
            log_once(logger, "strikes", error)


def may_burn(grid: Grid, cell: Cell, home) -> bool:
    """A natural log or leaf fire may enter: never edited, nothing Mimo built claims it, not near home and not in
    the legacy clearing. Fix round 4: the edit is asked through Grid.edited, which loads the cell's chunk first; a
    read of grid.edits alone, on a grid that loads its chunks as they are read (world_grid), missed the edit in a
    chunk nothing had read yet, and a sapling renewal grew or a log Mimo placed burned."""
    return (grid.material(*cell) in BURNS and not grid.edited(cell) and not grid.claimed(cell)
            and math.hypot(cell[0], cell[2]) > LEGACY_RADIUS and not near(home, cell[0], cell[2], FIRE_CLEAR))


def fires_of(state: dict) -> list[dict]:
    return sky.sky_state(state)["fires"]


def ignite(state: dict, context, cell: Cell, at: float, fire: int | None) -> bool:
    """`cell` catches: a new fire (fire None) unless FIRES burn already, or part of `fire` unless it is full."""
    burning, sky_state = fires_of(state), sky.sky_state(state)
    burned = sky_state.setdefault("burned", {})
    if fire is None:
        if len({entry["fire"] for entry in burning}) >= FIRES:
            return False
        fire = sky_state["fire_id"] = sky_state.get("fire_id", 0) + 1
        context.events.append((at, "fire", f"Lightning set a tree on fire near {state['name']}."))
    elif burned.get(str(fire), 0) >= FIRE_CELLS:
        return False
    burned[str(fire)] = burned.get(str(fire), 0) + 1
    scale = context.clock_at(at)["time_scale"]
    low, high = BURN_SECONDS
    seconds = low + (high - low) * roll(state.get("world_seed", "0"), cell, BURN_CHANNEL, int(at * scale))
    context.grid.put(*cell, FIRE)
    burning.append({"x": cell[0], "y": cell[1], "z": cell[2], "fire": fire, "caught": at, "until": at + seconds / scale})
    return True


def spread(state: dict, context, at: float, home=None) -> None:
    """Every SPREAD_EVERY game seconds up to `at`: each burning cell may catch one neighbour; cells burn out."""
    sky_state = sky.sky_state(state)
    scale = context.clock_at(at)["time_scale"]
    every = SPREAD_EVERY / scale
    last = sky_state.get("fire_at")
    if last is None or not sky_state["fires"]:
        sky_state["fire_at"] = at
        return
    seed, grid = state.get("world_seed", "0"), context.grid
    chance = SPREAD_CHANCE * (RAIN_SPREAD if sky.raining(state) else 1.0)
    moment = last
    for _ in range(int((at - last) / every + 1e-6)):
        moment += every
        for entry in [entry for entry in sky_state["fires"] if entry["until"] <= moment]:
            sky_state["fires"].remove(entry)
            cell = (entry["x"], entry["y"], entry["z"])
            if grid.material(*cell) == FIRE:
                grid.put(*cell, "air")
        alive = {str(entry["fire"]) for entry in sky_state["fires"]}
        sky_state["burned"] = {fire: count for fire, count in sky_state.get("burned", {}).items() if fire in alive}
        salt = int(moment * scale)
        for entry in list(sky_state["fires"]):
            cell = (entry["x"], entry["y"], entry["z"])
            if roll(seed, cell, SPREAD_CHANNEL, salt) >= chance:
                continue
            ahead = [(cell[0] + dx, cell[1] + dy, cell[2] + dz) for dx, dy, dz in FACES]
            ahead = [near_cell for near_cell in ahead if may_burn(grid, near_cell, home)]
            if ahead:
                pick = ahead[int(roll(seed, cell, PICK_CHANNEL, salt) * len(ahead)) % len(ahead)]
                ignite(state, context, pick, moment, entry["fire"])
    sky_state["fire_at"] = moment


def hot_cells(state: dict) -> set[Cell]:
    """The burning cells and their face neighbours: paths keep out of them (Grid.hot)."""
    cells = set()
    for entry in (state.get("sky") or {}).get("fires", ()):
        x, y, z = entry["x"], entry["y"], entry["z"]
        cells.add((x, y, z))
        cells.update((x + dx, y + dy, z + dz) for dx, dy, dz in FACES)
    return cells


def fires_within(state: dict, reach: int) -> list[dict]:
    """The burning cells within `reach` blocks of Mimo's cell (on every axis)."""
    x, y, z = pet_cell(state)
    return [entry for entry in (state.get("sky") or {}).get("fires", ())
            if abs(entry["x"] - x) <= reach and abs(entry["z"] - z) <= reach and abs(entry["y"] - y) <= reach]


def fire_near(state: dict, reach: int = 3) -> bool:
    """A burning cell within `reach` blocks of Mimo's cell (on every axis)."""
    return bool(fires_within(state, reach))


def burn_pet(state: dict, context, at: float) -> None:
    """Mimo in or beside a burning cell takes FIRE_DAMAGE a game second since the last look (or since it caught)."""
    sky_state = sky.sky_state(state)
    last = sky_state.get("burned_at")
    sky_state["burned_at"] = at
    beside = fires_within(state, 1) if last is not None else []
    if not beside:
        return
    caught = min(entry["caught"] for entry in beside)
    seconds = (at - max(last, caught)) * context.clock_at(at)["time_scale"]
    if seconds > 0:
        hurt(state, FIRE_DAMAGE * seconds, FIRE, at, context)
        state["last_thought"] = "Hot! Hot! I have to get away from the fire!"


def storm(state: dict, context, at: float) -> None:
    """sky.EFFECTS: a storm's start and its strikes, the fires' spread and burning out, and the fire's heat on
    Mimo."""
    sky_state = sky.sky_state(state)
    storming = sky_state["weather"] == "storm"
    if storming and not sky_state.get("storming"):
        context.events.append((at, "storm", "A thunderstorm rolled in."))
        state["last_thought"] = "Thunder! A storm is coming."
    sky_state["storming"] = storming
    if not storming and not sky_state["fires"]:
        sky_state.pop("fire_at", None)
        sky_state.pop("burned_at", None)
        context.grid.hot = set()
        return
    home = home_now(context)
    if storming:
        scale = context.clock_at(at)["time_scale"]
        last = sky_state.get("strike_at")
        if last is None or (at - last) * scale >= STRIKE_EVERY:
            sky_state["strike_at"] = at
            strike(state, context, at, home)
    spread(state, context, at, home)
    burn_pet(state, context, at)
    heat(state, context)


def heat(state: dict, context) -> None:
    """Grid.hot from the burning cells, worked out again only when they changed since the last step (the tick's
    ActionContext.memo keeps the cells it was worked out from: a big fire's heat is 7 cells a burning one)."""
    fires = sky.sky_state(state)["fires"]
    memo = getattr(context, "memo", None)
    kept = None if memo is None else memo.get(HOT)
    if kept is None or kept[0] != fires or context.grid.hot is not kept[1]:
        kept = (list(fires), hot_cells(state))
        if memo is not None:
            memo[HOT] = kept
    context.grid.hot = kept[1]


sky.EFFECTS.append(storm)

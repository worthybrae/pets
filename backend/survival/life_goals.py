"""The goals Mimo sets itself (L4), registered in backend.survival.goals.

- first_shelter, "A home of its own": gather blocks, raise the walls and roof (gathering more blocks
  as they run out), put a bed inside (M5's build_shelter). Every other goal comes after it.
- iron_tools, "Iron tools": a wooden and a stone pickaxe, iron ore found, 3 iron ore mined, an
  iron pickaxe.
- better_tools, "Diamond tools", after iron tools: diamonds found, 3 mined, a diamond pickaxe
  (every milestone needs L3's diamond_pickaxe recipe). While it is the goal, mine_ore goes for any
  diamond Mimo remembers, not only once it knows of 3 (work.EAGER).
- armor_up, "Armor up", after iron tools: 5 leather, a leather cap and a leather tunic (L2's
  make_gear), and iron armor (L3's iron_cap and iron_tunic recipes). While it is the goal, iron
  armor is worth making though no creature has hurt Mimo yet (harm.ARMOR_WANTED), and while
  leather is short Mimo also hunts for hides though fed (hunting.HUNT_FOR), at most once a sixth
  of a game day.
- safe_yard, "A safe yard": torches at the corners of home (mining coal for them, and digging for
  it when none is known), a door in its doorway, and a fence round the yard once a purpose named
  build_fence exists (none yet: L3 plans no yard fence).
- herd, "A herd of its own": a pen by home and 3 animals grown in it, with L3's build_pen and
  stock_pen (their milestones need L3's fence recipe too).
- map_land, "Map the land": set foot on MAP_SHARE of the dry land within 64 blocks of home.
backend.survival.homes adds better_home and backend.survival.larder full_larder.

Explore trips these goals need (backend.survival.trips; the milestones name explore, and a trip
advances a goal when its reason serves it):
- iron, "look for iron", while mine_ore wants iron Mimo can mine and it remembers none within 48
  blocks ("my pickaxe needs it", or its armor). A cave mouth or sinkhole (worldgen's openings)
  whose ground Mimo has not looked into is sure, a rocky outcrop likely, hills and mountain rock
  less so (mouths cut into hillsides); openings within 64 blocks are spots. After each walk Mimo
  looks into any opening within 16 blocks it has not seen: it is remembered as a "cave" landmark,
  and the ore in its walls that Mimo could reach from its floor or rim as ore places. Iron among
  them is the find: mine_ore follows. Serves iron tools and armor.
- hides, "look for leather", while armor is the goal and hides are wanted (hides_wanted) with no
  animal in range: land where cows graze is sure, rabbit ground likely; pastures found before are
  spots. An animal in range is the find ("pasture" landmark), and hunt follows.
- seed, "look for a creature seed", while the herd is the goal, no seed is carried or in a chest
  and neither pen purpose is on offer: tall grass (12 within 8 blocks is sure). At each stop Mimo
  breaks up to GRASS_PER_STOP tall grass within reach (a seed drops 1 in 60); a seed carried is the
  find, and build_pen or stock_pen follows.
- map, "map the land", while mapping is the goal and not done: the least-explored ground near
  (exploring.explore_target), the one reason that heads for new land as such.

Their rules scores (goals.rules_score adds WORKABLE and STICK): first_shelter 90; iron_tools 60
plus a tenth of diligence; better_tools 50 plus a tenth of diligence; armor_up 50 plus a tenth of
caution, 15 more when a creature hurt Mimo in the last game day; safe_yard 55 plus a tenth of
caution; herd 45 plus a tenth of patience; map_land 40 plus a tenth of curiosity.
"""

from __future__ import annotations

import math

from backend.services.crafting import TOOL_RANK, can_harvest
from backend.services.worldgen import OPENING_REGION, biome_at, region_openings, rocks_in_chunk, terrain_height
from backend.survival.blueprints import bill
from backend.survival.building import NOMINAL_BILL, START_SHARE, carried_blocks
from backend.survival.clock import DAY_SECONDS
from backend.survival import work
from backend.survival.creatures import harm, hunting
from backend.survival.creatures.hunting import prey
from backend.survival.creatures.kinds import kind_of, land_kinds
from backend.survival.creatures.moves import where
from backend.survival.creatures.seeds import SEED
from backend.survival.creatures.table import dead
from backend.survival.exploring import SURVEY, dry_blocks, explore_target
from backend.survival.goals import Goal, Milestone, register_goal
from backend.survival.memory import BUILT, PATCH, cell_of, explored, patch_of, remember, structures
from backend.survival.purposes import PURPOSES, is_valid
from backend.survival.senses import ORES, grass_near, natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import REACH, label
from backend.survival.structures import blueprint_of, todo
from backend.survival.trips import Find, Reason, register_reason
from backend.survival.work import ORE_RANGE, ORE_REACH, wanted_ores, wood

WOOD_FOR_A_PICKAXE = 3.0  # logs of wood: a crafting table, planks and sticks
IRON_WANTED = 3
DIAMONDS_WANTED = 3
LEATHER_WANTED = 5  # a cap takes 2, a tunic 3
HIDE_HUNT_GAP = DAY_SECONDS / 6  # game seconds between two hunts for hides
MAP_SHARE = 0.6  # of the dry land within SURVEY blocks of home
PEN_ANIMALS = 3
CAVE = "cave"  # a landmark: a cave mouth or sinkhole Mimo looked into, the note says which
OPENING_NEAR = 12  # blocks from a spot to an opening that makes it sure for iron
OPENING_SIGHT = 64  # openings this close to Mimo are spots
CAVE_LOOK = 16  # openings this close after a walk are looked into
HILLS = 9  # ground this high is hill country, where cave mouths cut in
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))
AROUND = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
TALL_GRASS = 8  # blocks around a spot whose tall grass counts
SURE_GRASS = 12
GRASS_PER_STOP = 10


def whole(done: bool) -> float:
    return 1.0 if done else 0.0


# What Mimo built -------------------------------------------------------------------------------

def all_structures(s: Situation) -> list[dict]:
    """Everything Mimo started, oldest first, read once per Situation (the key building.py uses)."""
    return s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])


def shelters(s: Situation) -> list[dict]:
    return [found for found in all_structures(s) if found["kind"] == "shelter"]


def home_structure(s: Situation) -> dict | None:
    """The shelter Mimo lives in: the one whose inside cell is the home it built."""
    home = next((place for place in s.places if place["kind"] == "home" and place["note"] == BUILT), None)
    if home is None:
        return None
    return next((found for found in reversed(shelters(s)) if (found["x"], found["y"], found["z"]) == cell_of(home)),
                None)


def first_home(s: Situation) -> dict | None:
    """The first shelter Mimo finished."""
    return next((found for found in shelters(s) if found["status"] == "done"), None)


def built_share(s: Situation, structure: dict | None) -> float:
    """How much of a shelter's floor, walls and roof stands (1 once it is done)."""
    if structure is None:
        return 0.0
    if structure["status"] == "done":
        return 1.0
    blueprint = blueprint_of(structure)
    total = bill(blueprint)
    return 1.0 - bill(blueprint, s.grid) / total if total else 1.0


def home_parts_done(s: Situation, part: str) -> float:
    """The share of a part (torch, door) of the home's design that is in place."""
    home = home_structure(s)
    if home is None:
        return 0.0
    blueprint = blueprint_of(home)
    planned = blueprint.parts(part)
    return 1.0 - len(todo(s.grid, blueprint, (part,))) / len(planned) if planned else 1.0


# first_shelter ---------------------------------------------------------------------------------

def shelter_now(s: Situation) -> dict | None:
    """The shelter Mimo lives in, else the newest one it started."""
    found = shelters(s)
    return home_structure(s) or (found[-1] if found else None)


def shelter_blocks(s: Situation) -> float:
    if shelters(s):
        return 1.0
    return carried_blocks(s) / (START_SHARE * NOMINAL_BILL)


def bed_in(s: Situation) -> float:
    structure = shelter_now(s)
    return whole(structure is not None and structure["status"] == "done"
                 and not todo(s.grid, blueprint_of(structure), ("bed",)))


register_goal(Goal(
    "first_shelter", "A home of its own",
    "Nights are cold and dark: a shelter of its own with a bed keeps Mimo warm and safe.",
    (Milestone("Gather blocks for the walls", shelter_blocks,
               ("gather_wood", "gather_stone", "craft_tools", "explore")),
     Milestone("Raise the walls and roof", lambda s: built_share(s, shelter_now(s)),
               ("build_shelter", "gather_wood", "gather_stone", "explore")),  # its blocks run out as it builds
     Milestone("Put a bed inside", bed_in, ("build_shelter",))),
    score=lambda s: 90.0, thought="First things first: a roof of my own."))


# iron_tools and better_tools --------------------------------------------------------------------

def pickaxe_rank(s: Situation) -> int:
    return max((TOOL_RANK[tool] for tool in TOOL_RANK if s.count(tool) > 0), default=0)


def has_iron_pickaxe(s: Situation) -> bool:
    return pickaxe_rank(s) >= TOOL_RANK["iron_pickaxe"]


def wooden_pickaxe(s: Situation) -> float:
    """Done with a pickaxe; the wood for one is half the way."""
    return 1.0 if pickaxe_rank(s) >= 1 else 0.5 * min(1.0, wood(s.inventory) / WOOD_FOR_A_PICKAXE)


def iron_mined(s: Situation) -> float:
    return 1.0 if has_iron_pickaxe(s) else s.count("iron_ore", "iron_ingot") / IRON_WANTED


def remembers(s: Situation, ore: str) -> bool:
    return any(place["kind"] == "ore" and place["note"] == ore for place in s.places)


register_goal(Goal(
    "iron_tools", "Iron tools",
    "Stone only goes so far: an iron pickaxe digs anything and opens the way to better gear.",
    (Milestone("Make a wooden pickaxe", wooden_pickaxe, ("gather_wood", "craft_tools", "explore")),
     Milestone("Make a stone pickaxe", lambda s: whole(pickaxe_rank(s) >= 2), ("gather_stone", "craft_tools")),
     Milestone("Find iron ore", lambda s: whole(has_iron_pickaxe(s) or s.count("iron_ore", "iron_ingot") > 0
                                                or remembers(s, "iron_ore")), ("gather_stone", "mine_ore", "explore")),
     Milestone("Mine 3 iron ore", iron_mined, ("mine_ore", "gather_stone", "explore")),
     Milestone("Make an iron pickaxe", lambda s: whole(has_iron_pickaxe(s)), ("craft_tools",))),
    score=lambda s: 60.0 + s.trait("diligence") / 10, thought="I want iron tools. Stone only goes so far.",
    after=("first_shelter",)))


# The trip for iron: cave mouths and sinkholes ----------------------------------------------------

def opening_of(rx: int, rz: int, seed: str) -> tuple[str, int, int] | None:
    """The cave entrance of a 64x64 region as (kind, x, z of its middle column), or None."""
    kind, spans = region_openings(rx, rz, seed)
    if not kind:
        return None
    columns = sorted(spans)
    x, z = columns[len(columns) // 2]
    return kind, x, z


def openings_near(seed: str, x: int, z: int, reach: float) -> list[tuple[str, int, int]]:
    """The cave entrances whose middle lies within `reach` blocks of (x, z), nearest first."""
    found = []
    for rx in range(math.floor((x - reach) / OPENING_REGION), math.floor((x + reach) / OPENING_REGION) + 1):
        for rz in range(math.floor((z - reach) / OPENING_REGION), math.floor((z + reach) / OPENING_REGION) + 1):
            opening = opening_of(rx, rz, seed)
            if opening is not None and math.hypot(opening[1] - x, opening[2] - z) <= reach:
                found.append(opening)
    return sorted(found, key=lambda opening: (math.hypot(opening[1] - x, opening[2] - z), opening))


def looked_into(s: Situation, x: int, z: int) -> bool:
    return any(place["kind"] == CAVE and math.hypot(place["x"] - x, place["z"] - z) <= CAVE_LOOK for place in s.places)


def opening_words(kind: str) -> str:
    return "a sinkhole" if kind == "sinkhole" else "a cave mouth"


def iron_wanted(s: Situation) -> str | None:
    """mine_ore wants iron Mimo can mine, and it remembers none within reach of mine_ore."""
    if "iron_ore" not in wanted_ores(s) or not can_harvest("iron_ore", s.inventory):
        return None
    if any(place["kind"] == "ore" and place["note"] == "iron_ore" and s.distance(cell_of(place)) <= ORE_RANGE
           for place in s.places):
        return None
    return "my armor needs it" if has_iron_pickaxe(s) else "my pickaxe needs it"


def iron_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    for kind, ox, oz in openings_near(s.seed, x, z, OPENING_NEAR):
        if not looked_into(s, ox, oz):
            return 1.0, opening_words(kind)
    for rx, rz, rock, _, _ in rocks_in_chunk(x // 16, z // 16, s.seed):
        if rock == "outcrop" and math.hypot(rx - x, rz - z) <= OPENING_NEAR:
            return 0.5, "a rocky outcrop"
    if terrain_height(x, z, s.seed) >= HILLS:
        return 0.3, "bare mountain rock" if biome_at(x, z, s.seed) == "alpine" else "hills"
    return 0.0, ""


def opening_spots(s: Situation) -> list[tuple[int, int, str]]:
    x, _, z = s.here
    return [(ox, oz, opening_words(kind)) for kind, ox, oz in openings_near(s.seed, x, z, OPENING_SIGHT)
            if not looked_into(s, ox, oz)]


def exposed_ores(s: Situation, kind: str, spans) -> list[tuple[tuple[int, int, int], str]]:
    """Ore in the walls of an opening that Mimo could mine from where it can stand: the opening's
    floor (a mouth's) or the ground round its rim."""
    air = {(x, y, z) for (x, z), (low, high) in spans.items() for y in range(low, high + 1)}
    stands = [(x, low, z) for (x, z), (low, _) in spans.items()] if kind == "mouth" else []
    stands += [(x + dx, terrain_height(x + dx, z + dz, s.seed) + 1, z + dz) for (x, z) in spans for dx, dz in SIDES
               if (x + dx, z + dz) not in spans]
    found = {}
    for x, y, z in air:
        for dx, dy, dz in AROUND:
            cell = (x + dx, y + dy, z + dz)
            if cell in air or cell in found:
                continue
            material = s.grid.material(*cell)
            if material in ORES and any(math.dist(cell, stand) <= ORE_REACH for stand in stands):
                found[cell] = material
    return sorted(found.items())


def iron_look(s: Situation, context) -> Find | None:
    """Look into the openings near that Mimo has not seen: remember each as a cave landmark and the
    ore in its walls as ore places. Iron among them is what the trip was for."""
    x, _, z = s.here
    words, iron = [], False
    for kind, ox, oz in openings_near(s.seed, x, z, CAVE_LOOK):
        if looked_into(s, ox, oz):
            continue
        spans = region_openings(ox // OPENING_REGION, oz // OPENING_REGION, s.seed)[1]
        ores = exposed_ores(s, kind, spans)
        remember(s.db, CAVE, (ox, terrain_height(ox, oz, s.seed) + 1, oz), s.at, kind)
        for cell, ore in ores:
            remember(s.db, "ore", cell, s.at, ore)
        seen = sorted({ore for _, ore in ores}, key=ORES.index)
        iron = iron or "iron_ore" in seen
        words.append(opening_words(kind) + (f" with {' and '.join(label(ore) for ore in seen)} in its walls"
                                           if seen else ""))
    return Find(" and ".join(words), iron) if words else None


register_reason(Reason(
    "iron", "look for iron", iron_wanted, iron_value, lambda s: 45.0 + s.trait("curiosity") / 10,
    goals=("iron_tools", "armor_up"), spots=opening_spots, look=iron_look))


def has_diamond_pickaxe(s: Situation) -> bool:
    return s.count("diamond_pickaxe") > 0


def diamonds_wanted(s: Situation, ore: str) -> bool:
    """With diamond tools the goal, mine_ore goes for any diamond Mimo remembers (work.EAGER)."""
    return ore == "diamond_ore" and (s.brain.get("goal") or {}).get("name") == "better_tools"


work.EAGER.append(diamonds_wanted)

register_goal(Goal(
    "better_tools", "Diamond tools",
    "Diamonds lie deep: a diamond pickaxe is the best tool there is.",
    (Milestone("Find diamonds", lambda s: whole(has_diamond_pickaxe(s) or s.count("diamond") > 0
                                                or remembers(s, "diamond_ore")),
               ("gather_stone", "mine_ore"), items=("diamond_pickaxe",)),
     Milestone("Mine 3 diamonds", lambda s: 1.0 if has_diamond_pickaxe(s) else s.count("diamond") / DIAMONDS_WANTED,
               ("mine_ore",), items=("diamond_pickaxe",)),
     Milestone("Make a diamond pickaxe", lambda s: whole(has_diamond_pickaxe(s)), ("craft_tools",),
               items=("diamond_pickaxe",))),
    score=lambda s: 50.0 + s.trait("diligence") / 10, thought="Diamonds are down there somewhere.",
    after=("first_shelter", "iron_tools")))


# armor_up --------------------------------------------------------------------------------------

def wears(s: Situation, *pieces: str) -> bool:
    return any(s.count(piece) > 0 for piece in pieces)


def leather_gathered(s: Situation) -> float:
    """Leather toward a cap and a tunic, counting what the pieces Mimo has took (4 hides make 1)."""
    cap = 2 if wears(s, "leather_cap", "iron_cap") else 0
    tunic = 3 if wears(s, "leather_tunic", "iron_tunic") else 0
    return (s.count("leather") + s.count("rabbit_hide") // 4 + cap + tunic) / LEATHER_WANTED


def hurt_lately(s: Situation) -> bool:
    hurt_at = s.state.get("hurt_at")
    return hurt_at is not None and (s.at - hurt_at) * s.scale < DAY_SECONDS


def hides_wanted(s: Situation) -> bool:
    """Armor is the goal, leather is short and Mimo killed nothing for HIDE_HUNT_GAP: it hunts for
    hides though fed, a few times a day, so the land is never emptied."""
    goal = s.brain.get("goal")
    hunted_at = s.state.get("hunted_at")
    rested = hunted_at is None or (s.at - hunted_at) * s.scale >= HIDE_HUNT_GAP
    return goal is not None and goal["name"] == "armor_up" and rested and leather_gathered(s) < 1.0


hunting.HUNT_FOR.append(hides_wanted)


def armor_the_goal(state: dict) -> bool:
    """With armor the goal, iron armor is worth its ingots before any creature hurt Mimo
    (harm.ARMOR_WANTED): craft_tools makes it and mine_ore digs the iron it takes."""
    return ((state.get("brain") or {}).get("goal") or {}).get("name") == "armor_up"


harm.ARMOR_WANTED.append(armor_the_goal)

register_goal(Goal(
    "armor_up", "Armor up",
    "Gloomlings hit hard at night: armor takes the edge off every blow.",
    (Milestone("Gather 5 leather", leather_gathered, ("hunt", "explore")),
     Milestone("Make a leather cap", lambda s: whole(wears(s, "leather_cap", "iron_cap")), ("make_gear",)),
     Milestone("Make a leather tunic", lambda s: whole(wears(s, "leather_tunic", "iron_tunic")), ("make_gear",)),
     Milestone("Make iron armor", lambda s: (wears(s, "iron_cap") + wears(s, "iron_tunic")) / 2,
               ("craft_tools", "mine_ore", "explore"), items=("iron_cap", "iron_tunic"))),
    score=lambda s: 50.0 + s.trait("caution") / 10 + (15.0 if hurt_lately(s) else 0.0),
    thought="Next time a gloomling swings at me, I'll be ready.", after=("first_shelter", "iron_tools")))


def hides_trip(s: Situation) -> str | None:
    if not hides_wanted(s) or prey(s):
        return None
    return "my armor needs leather and no animal is near"


def hides_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    kinds = {kind.name for kind in land_kinds(biome_at(x, z, s.seed))}
    if "cow" in kinds:
        return 1.0, "grazing land for cows"
    return (0.4, "rabbit ground") if "rabbit" in kinds else (0.0, "")


def pasture_spots(s: Situation) -> list[tuple[int, int, str]]:
    return [(place["x"], place["z"], f"where it saw a {label(place['note'] or 'rabbit')}") for place in s.places
            if place["kind"] == "pasture"]


def hides_look(s: Situation, context) -> Find | None:
    animals = prey(s)
    if not animals:
        return None
    kind = animals[0]["kind"]
    return Find(f"a {label(kind)} to hunt", True, remember(s.db, "pasture", where(animals[0], s.at), s.at, kind))


register_reason(Reason(
    "hides", "look for leather", hides_trip, hides_value, lambda s: 40.0 + s.trait("bravery") / 10,
    goals=("armor_up",), spots=pasture_spots, look=hides_look))


# safe_yard -------------------------------------------------------------------------------------

register_goal(Goal(
    "safe_yard", "A safe yard",
    "Light and a door keep gloomlings away from home at night.",
    (Milestone("Light torches at the corners of home", lambda s: home_parts_done(s, "torch"),
               ("light_up", "mine_ore", "gather_stone")),  # digging turns up the coal torches take
     Milestone("Hang a door in the doorway", lambda s: home_parts_done(s, "door"), ("build_shelter",)),
     Milestone("Put a fence round the yard", lambda s: 0.0, ("build_fence",), items=("fence",))),
    score=lambda s: 55.0 + s.trait("caution") / 10, thought="Lights and a good door. Let them try.",
    after=("first_shelter",), valid=lambda s: home_structure(s) is not None))


# herd ------------------------------------------------------------------------------------------

def finished_pen(s: Situation) -> dict | None:
    return next((found for found in all_structures(s) if found["kind"] == "pen" and found["status"] == "done"), None)


def animals_in_pen(s: Situation) -> int:
    """Living passive animals standing inside the finished pen."""
    pen, herd = finished_pen(s), s.grid.herd
    if pen is None or herd is None:
        return 0
    blueprint = blueprint_of(pen)
    inside = {(planned.cell[0], planned.cell[2]) for planned in blueprint.parts("pen")}
    x, _, z = blueprint.anchor
    count = 0
    for creature in herd.near(x, z, 4.0):
        kind = kind_of(creature["kind"])
        if not dead(creature) and kind is not None and not kind.hostile \
                and (round(creature["x"]), round(creature["z"])) in inside:
            count += 1
    return count


register_goal(Goal(
    "herd", "A herd of its own",
    "Animals grown from creature seeds in a pen by home give meat, wool and company.",
    (Milestone("Build a pen by home", lambda s: whole(finished_pen(s) is not None), ("build_pen", "explore"),
               items=("fence",)),
     Milestone("Grow 3 animals in the pen", lambda s: animals_in_pen(s) / PEN_ANIMALS, ("stock_pen", "explore"),
               items=("fence",))),
    score=lambda s: 45.0 + s.trait("patience") / 10, thought="A few animals of my own, safe in a pen.",
    after=("first_shelter",)))


def seed_trip(s: Situation) -> str | None:
    goal = s.brain.get("goal")
    if not goal or goal["name"] != "herd" or s.count(SEED) > 0:
        return None
    if any(chest.get(SEED, 0) > 0 for chest in s.state.get("chests", {}).values()):
        return None
    if any(name in PURPOSES and is_valid(PURPOSES[name], s) for name in ("build_pen", "stock_pen")):
        return None
    return "a pen of animals grows from creature seeds"


def seed_value(s: Situation, x: int, z: int) -> tuple[float, str]:
    grass = natural_plants(s.seed, x, z, TALL_GRASS, ("tall_grass",))
    return (min(1.0, len(grass) / SURE_GRASS), "tall grass") if grass else (0.0, "")


def break_grass(s: Situation) -> list[dict]:
    """Tall grass within reach where Mimo stands, away from any step that just failed."""
    grass = [cell for cell in grass_near(s.grid, s.seed, s.here, REACH)
             if math.dist(cell, s.here) <= REACH and not near_failure(s.state, cell)]
    return [{"kind": "mine", "target": list(cell)} for cell in grass[:GRASS_PER_STOP]]


def seed_look(s: Situation, context) -> Find | None:
    return Find("a creature seed", True) if s.count(SEED) > 0 else None


register_reason(Reason(
    "seed", "look for a creature seed", seed_trip, seed_value, lambda s: 40.0 + s.trait("patience") / 10,
    goals=("herd",), look=seed_look, work=break_grass))


# map_land --------------------------------------------------------------------------------------

def home_cell(s: Situation):
    home = next((place for place in s.places if place["kind"] == "home"), None)
    return None if home is None else cell_of(home)


def land_seen(s: Situation) -> float:
    """The share of the dry 8x8 patches within 64 blocks of home that Mimo set foot on."""
    def look() -> float:
        center = home_cell(s)
        if center is None or s.db is None:
            return 0.0
        seen = explored(s.db, center, SURVEY)
        low_x, low_z = patch_of(center[0] - SURVEY, center[2] - SURVEY)
        high_x, high_z = patch_of(center[0] + SURVEY, center[2] + SURVEY)
        land = walked = 0
        for rx in range(low_x, high_x + 1):
            for rz in range(low_z, high_z + 1):
                dx, dz = rx * PATCH + PATCH / 2 - center[0], rz * PATCH + PATCH / 2 - center[2]
                if math.hypot(dx, dz) > SURVEY or dry_blocks(s.seed, rx, rz) == 0:
                    continue
                land += 1
                walked += (rx, rz) in seen
        return walked / land if land else 1.0
    return s.sensed("land seen", look)


register_goal(Goal(
    "map_land", "Map the land",
    "Knowing the land around home means knowing where the food, water and ore are.",
    (Milestone("Walk the land around home", lambda s: land_seen(s) / MAP_SHARE, ("explore",)),),
    score=lambda s: 40.0 + s.trait("curiosity") / 10, thought="I wonder what's out past the hills.",
    after=("first_shelter",), valid=lambda s: home_cell(s) is not None))


def map_trip(s: Situation) -> str | None:
    goal = s.brain.get("goal")
    if not goal or goal["name"] != "map_land" or land_seen(s) >= MAP_SHARE:
        return None
    return "I want to know the land around home"


def new_land(s: Situation) -> list[tuple[int, int, str]]:
    target = explore_target(s)
    return [] if target is None else [(target[0], target[2], "land it has not seen")]


register_reason(Reason(
    "map", "map the land", map_trip, lambda s, x, z: (0.0, ""), lambda s: 30.0 + s.trait("curiosity") / 5,
    goals=("map_land",), spots=new_land))

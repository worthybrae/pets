"""A lighter load: build_storage and drop_items (spec section 8, inventory limit).

Mimo carries at most 16 stacks (backend.survival.carrying). build_storage puts a chest in the
back corner the shelter design keeps for it, under the roof, making it from 8 planks when Mimo
carries none (and has room to carry the chest it makes), and puts away what Mimo does not need to
carry: loose blocks, materials beyond what a day's work takes (KEEP; logs and planks of every wood
count toward one keep each, L3 final fix wave), and food beyond a day's worth. With its arms full, the building blocks it keeps (cobblestone, planks) go in whole too. It
takes food back out when Mimo carries less than a meal's worth, and (the Making final fix wave, I1)
what a project needs that a chest holds (TAKES_MORE). It is offered at the built
shelter when Mimo's arms are getting full (13 stacks) or the chest holds food Mimo needs, and
scores higher the fuller Mimo is.

drop_items leaves behind what is no use at all: food Mimo knows is poisonous, pickaxes, axes and
swords a better one replaced, flowers, spare fences a finished pen left over (L3) and a spare
torch home's own dark corners no longer need (fix round 1: `kept` decides both what build_storage
puts away and what drop_items sheds outright, so a lone spare torch need not wait for a chest
visit). When its arms are full and build_storage cannot use a chest instead (none, none Mimo could
place either, or a full one), loose blocks go too, least useful first and only as far as it takes:
moss, gravel, sand and clay; with none of those, dirt; with no dirt either, cobblestone. Dirt and
cobblestone that a shelter Mimo started still needs stay, and cobblestone never drops below
gather_stone's own goal (work.STONE_GOAL), so the two do not dig up and drop the same stone
forever. It scores low while Mimo has room and high when it is full.
L4b: an expedition keeps what it packed (`KEEPS_MORE`, backend.survival.expedition): its torches
and a day and a half of food stay with Mimo, neither put away nor dropped; and while it packs, what
gives way to food is put away, to make room for the pack. While Mimo means to stay out
(purposes.AWAY), build_storage does not walk it home (the L4b final fix wave's follow-up).

When Mimo has no chest yet and the planks it would make for one need a stack of their own, a full
16 stacks leaves no room to craft it at all: no block is junk while STONE_GOAL keeps a floor under
cobblestone (fix round I2's L3 rule, resolution 21), so drop_items never offers a way out either
(follow-up fix, item 2). chest_crafting first tries the craft as it stands; when that alone would
not fit, it drops one LOW_VALUE stack -- the same order carrying.settle pushes blocks out in, moss
first and cobblestone last, never below what Mimo keeps of it (the Making final fix wave) -- to clear
room, then tries again.

The Making final fix wave: what making made and no project needs now goes in the chest too (making.MADE
joins KEEP at none: a glass pane recipe makes 16, iron bars 16), and loose blocks never drop below what
Mimo keeps of them (`kept`: the clay a project needs).

Making wave 2: when home's chest is full, what Mimo puts away goes in any other chest it built (an older
home's, which `to_take` already takes from), walking into that home first (`to_store_all`); on the gate's
route runs every home's chest was full by day 100 while the older one beside it had room.

The storage follow-up: when home's own chest is neither placed nor coming (`home_chest_coming`: no planks
and none carried to make one from), storage_valid used to return False before it looked at any other
chest, so nothing -- food included -- could be stored or taken out, and storing_cells counted the missing
chest as an empty one to store into. Now storage_valid, storing_cells and plan_storage all fall through to
the chests Mimo has instead.
"""

from __future__ import annotations

import math
import logging
from typing import TYPE_CHECKING

from backend.services.crafting import LOGS, PLANKS, TOOL_RANK
from backend.survival.blueprints import BUILDING
from backend.survival.building import current_shelter, structures_near, usable_supplies
from backend.survival.carrying import CARRY_STACKS, CHEST_STACKS, LOW_VALUE, STACK, full, room_for, stacks
from backend.survival.cooking import RAW_FOODS, made
from backend.survival import sky
from backend.survival.foraging import FOOD_WANTED, hunger_score, whole_walk
from backend.survival.goals import ADVANCES
from backend.survival.housework import chest_key
from backend.survival.once import log_once
from backend.survival.home import by_home, home_structure
from backend.survival.pathing import MAX_RANGE
from backend.survival.purposes import Purpose, away, foods, register
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import AXES, FOOD, REACH
from backend.survival.structures import blueprint_of, clearing, todo
from backend.survival.toolmaking import SWORD_LADDER
from backend.survival.wild import unlocked

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

STORE_FROM = 13  # stacks from which putting things away is worth a trip home
DROP_FROM = 10
TAKE_BELOW = 20.0  # hunger points of food carried below which Mimo takes food out
# W2: in winter the chest is where the food is (bushes and crops wait for spring, herds thin, lakes freeze), so taking
# food out while Mimo carries less than TAKE_BELOW scores as food work does, from this base (forage's is 35). On the
# gate's third run a gentle pet with 740 hunger points in its chests went foraging bare winter land 58 blocks from home
# and starved 24 game minutes.
WINTER_TAKE = 40.0
STORE_STEPS = 8
# What Mimo keeps on it of each material; the rest goes into the chest. Items not listed (tools,
# stations, food up to a day's worth) stay with Mimo.
KEEP = {"cobblestone": 16, "planks": 16, "oak_log": 8, "sticks": 8, "coal": 8, "iron_ore": 3, "iron_ingot": 3,
        "seeds": 8, "sapling": 4, "wheat": 6, "torch": 4, "dirt": 0, "gravel": 0, "sand": 0, "clay": 0, "moss": 0,
        "basalt": 0, "limestone": 0, "sandstone": 0, "brick": 0, "glass": 0, "copper_ore": 0, "copper_ingot": 0,
        # L1: what animals drop besides meat is put away, but for what L2's armor, bow and arrows
        # take (backend.survival.creatures.gear), and that only while the gear is still missing
        # (final fix wave, `kept`); gloom dust waits for L3.
        "leather": 5, "wool": 0, "feather": 4, "rabbit_hide": 8, "string": 3, "flint": 4, "gloom_dust": 0}
# L3: birch and spruce are kept like oak, stone bricks like cobblestone; fruit and desert or swamp
# plants Mimo happens to break are put away. L3 final fix wave: the woods share one keep (WOOD_POOLS,
# `kept`): 8 logs and 16 planks in all, not of each wood, so a pet with oak and birch no longer
# carries two log stacks for good.
KEEP.update({"birch_log": 8, "spruce_log": 8, "birch_planks": 16, "spruce_planks": 16, "stone_bricks": 16,
             "pumpkin": 0, "melon": 0, "cactus": 0, "sugar_cane": 0, "gold_ore": 3, "gold_ingot": 3,
             "iron_ore": 16, "iron_ingot": 16,  # iron armor takes 13 ingots: keep them on hand
             "creature_seed": 0})  # seeds wait in the chest for the pen (backend.survival.pens)
# Logs and planks of every wood are kept as one pool each, as many as KEEP gives oak's (8 logs, 16 planks).
WOOD_POOLS = (LOGS, PLANKS)
FLOWERS = ("flower_orange", "flower_pink", "flower_yellow")
LEAST_USEFUL = ("moss", "gravel", "sand", "clay")
# With full arms and no chest to use, what goes after LEAST_USEFUL, each only when nothing before it
# is left to drop.
LAST_RESORT = ("dirt", "cobblestone")
# Making wave 2: what Mimo throws out of a full chest when what it has to put away does not fit (`to_clear`),
# but for a stack of each of LEFT_IN_CHEST in all its chests; seeds and wheat (beyond that stack: the farm brings
# more than bread takes) and known poison too.
RUBBLE = ("dirt", "gravel", "moss", "basalt", "limestone", "sandstone")
HOARDED = ("seeds", "wheat")
LEFT_IN_CHEST = {"dirt": STACK, "seeds": STACK, "wheat": STACK}
CLEAR_STACKS = 4  # stacks thrown out in one visit at most


# L4b: functions of (Situation, item) giving how many more of an item Mimo keeps on it now, beyond
# what the rules below keep ("food" for hunger points of food): an expedition's torches and food.
# Fewer when negative (what a packing expedition leaves at home), but never fewer than none.
KEEPS_MORE: list = []
# The Making final fix wave (I1): functions of the Situation giving {item: count} Mimo wants back out of
# its chests now, besides food (backend.survival.making: what a project needs that a chest holds).
TAKES_MORE: list = []
# Making wave 2, fix round 1 (the re-review's I1): functions of the Situation giving {item: count} Mimo wants on
# hand now for its own gear, armor and pickaxe (backend.survival.creatures.gear: `gear_wanted`). What its chests
# hold of them comes back out (`more_taken`), and a making goal never puts them away to make room
# (making.kept_for_making), so the room a making goal makes is given back when they are needed.
WANTED_ON_HAND: list = []
# Making wave 2, fix round 1 (the re-review's Minor 6): functions of the Situation giving more (item, amount) that are
# no use to carry (`junk`): a furnace made again away from the workshop once a chest holds one.
JUNK_MORE: list = []
# And by goal name, whether build_storage works toward that goal now (goals.ADVANCES, `storage_advances`): the
# making goals' check (backend.survival.making) and armor's (gear). Toward any other goal a milestone names
# it for (a full larder's chest), always.
TOWARD: dict = {}


def in_chests(s: Situation) -> dict[str, int]:
    """What the chests Mimo built and can get to hold, added up (`reachable_chests`; read once per Situation)."""
    def look() -> dict[str, int]:
        total: dict[str, int] = {}
        for cell, _ in reachable_chests(s):
            for item, count in chest_contents(s, cell).items():
                total[item] = total.get(item, 0) + count
        return total
    return s.sensed("chests hold", look)


def on_hand_wanted(s: Situation) -> dict[str, int]:
    """What WANTED_ON_HAND want on hand, added up; one that crashes wants nothing (logged once). Read once per
    Situation."""
    def look() -> dict[str, int]:
        total: dict[str, int] = {}
        for wants in WANTED_ON_HAND:
            try:
                for item, count in wants(s).items():
                    if count > 0:
                        total[item] = total.get(item, 0) + int(count)
            except Exception as error:
                log_once(logger, "wanted on hand", error)
        return total
    return s.sensed("wanted on hand", look)


def taken_back(s: Situation) -> dict[str, int]:
    """TAKES_MORE (Making wave 2, fix round 1): what WANTED_ON_HAND want beyond what Mimo carries."""
    return {item: count - s.count(item) for item, count in on_hand_wanted(s).items() if count > s.count(item)}


TAKES_MORE.append(taken_back)


def storage_advances(s: Situation, goal) -> bool:
    """goals.ADVANCES: build_storage works toward a goal a milestone names it for when the goal's own check says
    so (TOWARD), or always with none."""
    check = TOWARD.get(goal.name)
    return True if check is None else bool(check(s))


ADVANCES["build_storage"] = storage_advances


def more_kept(s: Situation, item: str) -> float:
    """What KEEPS_MORE add for `item`; one that crashes adds nothing (logged once)."""
    total = 0.0
    for extra in KEEPS_MORE:
        try:
            total += float(extra(s, item))
        except Exception as error:
            log_once(logger, "keeps more", error)
    return total


def more_taken(s: Situation) -> dict[str, int]:
    """What TAKES_MORE want out of the chests, added up; one that crashes wants nothing (logged once)."""
    total: dict[str, int] = {}
    for wants in TAKES_MORE:
        try:
            for item, count in wants(s).items():
                if count > 0:
                    total[item] = total.get(item, 0) + int(count)
        except Exception as error:
            log_once(logger, "takes more", error)
    return total


def chest_spot(s: Situation) -> tuple[int, int, int] | None:
    """The chest corner of the shelter Mimo lives in (fix round 1: home, not `current_shelter`'s
    newest shelter, which is a second one still rising while a bigger home is under way), or None
    before it has one."""
    structure = home_structure(s)
    if structure is None or structure["status"] != "done":
        return None
    return blueprint_of(structure).one("chest")


def chests_built(s: Situation) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """(chest, stand) for every chest Mimo built and placed, home's own first (fix round 1): once
    Mimo moves into a bigger home, an older one's chest still holds what was stored there, so
    `to_take` (and pens.seeds_at_hand, the final fix wave) looks there too rather than stranding it.
    The stand is the inside cell of the chest's own shelter, where Mimo reaches it from (the final
    fix wave, I2: build_storage walks there, as it walks into home, never onto the chest block)."""
    found: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = []
    home = home_structure(s)
    shelters = [structure for structure in structures_near(s, "shelter", math.inf) if structure["status"] == "done"]
    for structure in ([home] if home is not None and home["status"] == "done" else []) + shelters:
        blueprint = blueprint_of(structure)
        cell = blueprint.one("chest")
        if cell is not None and chest_placed(s, cell) and all(cell != known for known, _ in found):
            found.append((cell, blueprint.anchor))
    return found


def built_chests(s: Situation) -> list[tuple[int, int, int]]:
    """Every chest Mimo built and placed, home's own first (`chests_built`)."""
    return [cell for cell, _ in chests_built(s)]


def chest_placed(s: Situation, cell) -> bool:
    return cell is not None and s.grid.material(*cell) == "chest"


def chest_contents(s: Situation, cell) -> dict[str, int]:
    return dict(s.state.get("chests", {}).get(chest_key(cell), {})) if cell else {}


def spare_food(s: Situation) -> list[tuple[str, int]]:
    """Food beyond a day's worth (60 hunger), the least filling first. Raw food Mimo can cook
    (cooking.RAW_FOODS) is neither: it waits for the fire, since cook only uses what Mimo carries. W1: a wild pet
    puts spare food away only once it knows `wild:keeping`."""
    if not unlocked(s, "keeping"):
        return []
    kept, spare, wanted = 0.0, [], FOOD_WANTED + more_kept(s, "food")
    for item in foods(s.inventory, s.poisons):
        if item in RAW_FOODS:
            continue
        count = s.inventory[item]
        keep = 0
        while keep < count and kept < wanted:
            keep += 1
            kept += FOOD[item]
        if count > keep:
            spare.append((item, count - keep))
    return list(reversed(spare))


def pooled(s: Situation, item: str, pool: tuple[str, ...]) -> int:
    """How many of `item` Mimo keeps from its wood pool: KEEP of the pool's first wood (oak) in all,
    shared out to the wood it holds most first (the pool's order breaks a tie: oak, birch, spruce)."""
    left = KEEP[pool[0]]
    for wood in sorted(pool, key=lambda name: (-s.count(name), pool.index(name))):
        share = min(s.count(wood), left)
        if wood == item:
            return share
        left -= share
    return 0


def kept(s: Situation, item: str) -> int:
    """How many of `item` Mimo keeps on it: KEEP, or none of a building block when its arms are
    full, only as many torches as home's own dark corners still need (fix round 1, item 1: a
    carried lantern fills a corner as well as a torch does, so it counts against the need too,
    and once every corner is lit or Mimo has no finished shelter near enough to light, that need
    is 0), or (final fix wave) of a gear material once the gear it is for is made. Logs and planks
    are kept as one pool of any wood each (L3 final fix wave, `pooled`)."""
    from backend.survival.creatures.gear import GEAR_MATERIALS, materials_wanted  # here: keeps purpose order
    from backend.survival.lighting import dark_corners  # here: lighting imports building; keeps purpose order

    more = round(more_kept(s, item))
    if item == "torch":
        return max(0, len(dark_corners(s)) - s.count("lantern")) + more
    if item in BUILDING and full(s.inventory):
        return max(0, more)
    if item in GEAR_MATERIALS and item not in materials_wanted(s.inventory):
        return max(0, more)
    pool = next((pool for pool in WOOD_POOLS if item in pool), None)
    return max(0, (pooled(s, item, pool) if pool else KEEP[item]) + more)


def spare(s: Situation) -> list[tuple[str, int]]:
    """(item, amount) Mimo would rather not carry: beyond what it keeps (`kept`), and food beyond a day's."""
    return [(item, count - kept(s, item)) for item, count in s.inventory.items()
            if item in KEEP and count > kept(s, item)] + spare_food(s)


def to_store(s: Situation, cell) -> list[tuple[str, int]]:
    """(item, amount) Mimo would put away, most first, as far as the chest has room."""
    return [(item, amount) for _, item, amount in stored_in(s, [cell])]


def stored_in(s: Situation, cells, cleared=(),
              limit: int | None = STORE_STEPS) -> list[tuple[tuple[int, int, int], str, int]]:
    """(chest, item, amount) Mimo would put away, most first, in the first of `cells` with room for it, once
    what `cleared` throws out of them is gone; the first `limit` of them."""
    chests = [(cell, chest_contents(s, cell)) for cell in cells]
    for cell, item, amount in cleared:
        for known, chest in chests:
            if known == cell:
                chest[item] -= amount
                if chest[item] <= 0:
                    del chest[item]
    found = []
    for item, amount in sorted(spare(s), key=lambda entry: (-entry[1], entry[0])):
        for cell, chest in chests:
            moved = min(amount, room_for(chest, item, CHEST_STACKS))
            if moved > 0:
                chest[item] = chest.get(item, 0) + moved
                found.append((cell, item, moved))
                amount -= moved
            if amount <= 0:
                break
    return found[:limit]


def home_chest_coming(s: Situation) -> bool:
    """The storage follow-up: home's own chest is on the way -- placed already, carried, or Mimo can
    craft one now. False, when it is neither placed nor makeable, falls storage_valid, storing_cells
    and plan_storage through to the chests Mimo has instead of getting stuck on the one it does not
    (no planks and none carried used to make storage_valid return False before it looked at any other
    chest, so nothing -- food included -- could be stored or taken out)."""
    cell = chest_spot(s)
    if cell is None:
        return False
    return chest_placed(s, cell) or s.count("chest") > 0 or chest_crafting(s) is not None


def storing_cells(s: Situation) -> list[tuple[int, int, int]]:
    """Home's chest, when it is coming, then every other chest Mimo built that it can get to."""
    home = chest_spot(s)
    homes = [home] if home_chest_coming(s) else []
    return homes + [cell for cell, _ in reachable_chests(s) if cell != home]


def to_store_all(s: Situation) -> list[tuple[tuple[int, int, int], str, int]]:
    """Making wave 2: (chest, item, amount) to put away, in home's chest first and then in any other chest
    Mimo built (an older home's, as `to_take` already takes from), once what `to_clear` throws out of a full
    one is gone. On the gate's route runs every home's chest was full (24 stacks) by day 100, while the older
    home's beside it had room, so nothing Mimo carried could be put away, and a making goal's copper and torch
    chain had no room; by day 150 both were full, with dirt, seeds and berries."""
    return stored_in(s, storing_cells(s), to_clear(s))


def to_clear(s: Situation) -> list[tuple[tuple[int, int, int], str, int]]:
    """Making wave 2: (chest, item, amount) Mimo throws out of a full chest when what it has to put away does
    not all fit: rubble (RUBBLE, but a stack of dirt, which a machine's yard is filled with), seeds and wheat
    beyond a stack (HOARDED: Juniper's chests held 160 wheat and 239 seeds), and food it knows is poisonous; up
    to CLEAR_STACKS stacks a visit, home's chest first. The stack of each of LEFT_IN_CHEST is one in all its
    chests, kept in one with room first: kept in each chest, on the gate's route Juniper's two full chests
    each held 32 dirt, 32 seeds and 32 wheat, so nothing could be put away, and its computer's last part
    waited from day 91 to 150 for the room to carry 3 cobblestone. They are taken out and left behind at once
    (a take step `away`, needing no room in Mimo's arms)."""
    cells = storing_cells(s)
    unplaced = sum(amount for _, amount in spare(s)) - sum(amount for _, _, amount in stored_in(s, cells, limit=None))
    if unplaced <= 0:
        return []
    chests = {cell: chest_contents(s, cell) for cell in cells}
    left, keep = dict(LEFT_IN_CHEST), {}
    for cell in sorted(cells, key=lambda cell: stacks(chests[cell]) >= CHEST_STACKS):  # those with room first
        for item in sorted(left):
            keep[(cell, item)] = min(chests[cell].get(item, 0), left[item])
            left[item] -= keep[(cell, item)]
    found: list[tuple[tuple[int, int, int], str, int]] = []
    for cell in cells:
        chest = chests[cell]
        if stacks(chest) < CHEST_STACKS:
            continue
        for item in sorted(chest):
            if item in RUBBLE or item in HOARDED or item in s.discards:  # W1: never the berries it only shuns
                amount = chest[item] - keep.get((cell, item), 0)
                while amount > 0 and len(found) < CLEAR_STACKS:
                    part = amount % STACK or STACK
                    found.append((cell, item, part))
                    amount -= part
    return found


def carried_food(s: Situation) -> float:
    return sum(FOOD[item] * s.inventory[item] for item in foods(s.inventory, s.poisons))


def reachable_chests(s: Situation) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """`chests_built`, leaving out one whose stand a step just failed near while Mimo would have to
    walk there (the final fix wave, I2: the same guard as storage_valid's walk home), so a chest
    with no way to it is not tried again at once."""
    return [(cell, stand) for cell, stand in chests_built(s)
            if s.here == stand or s.distance(cell) <= REACH or not near_failure(s.state, stand)]


def to_take(s: Situation) -> list[tuple[tuple[int, int, int], str, int]]:
    """(cell, item, amount) to take out of a chest: food when Mimo carries less than a meal's worth,
    best first, and (the Making final fix wave, I1) what TAKES_MORE want, as far as Mimo has room: home's
    own chest first, then (fix round 1) any other chest Mimo built, so an older home's chest is never
    stranded once a bigger one takes over (not one it just failed to reach, `reachable_chests`)."""
    hungry = carried_food(s) < TAKE_BELOW
    wanted = more_taken(s)
    if not hungry and not wanted:
        return []
    have, found, carried = carried_food(s), [], dict(s.inventory)
    for chest_cell, _ in reachable_chests(s):
        chest = chest_contents(s, chest_cell)
        for item in foods(chest, s.poisons) if hungry else ():
            amount, room = 0, room_for(carried, item, CARRY_STACKS)  # the final fix wave: only what fits
            while amount < min(chest[item], room) and have < FOOD_WANTED:
                amount += 1
                have += FOOD[item]
            if amount:
                found.append((chest_cell, item, amount))
                carried[item] = carried.get(item, 0) + amount
        for item in sorted(wanted):
            amount = min(wanted[item], chest.get(item, 0), room_for(carried, item, CARRY_STACKS))
            if amount > 0:
                found.append((chest_cell, item, amount))
                wanted[item] -= amount
                carried[item] = carried.get(item, 0) + amount
        if have >= FOOD_WANTED and not any(count > 0 for count in wanted.values()):
            break
    return found


def chest_crafting(s: Situation) -> list[dict] | None:
    """The steps that make a chest from what Mimo carries: `made` as it stands, or, when the
    planks it would need for one leave no room at full arms, the same craft after dropping one
    LOW_VALUE stack first (carrying.settle's order, moss first and cobblestone last) to clear it.
    None when neither fits."""
    steps = made(dict(s.inventory), "chest")
    if steps is not None:
        return steps
    inventory = dict(s.inventory)
    # The Making final fix wave: never below what Mimo keeps of it (`kept`: the clay a project needs was the
    # stack dropped here, on the gate's route check).
    spare = next((item for item in LOW_VALUE if inventory.get(item, 0) > 0
                  and inventory[item] - (inventory[item] % STACK or STACK) >= kept(s, item)), None)
    if spare is None:
        return None
    drop = inventory[spare] % STACK or STACK
    inventory[spare] -= drop
    if not inventory[spare]:
        del inventory[spare]
    steps = made(inventory, "chest")
    return None if steps is None else [{"kind": "drop", "item": spare, "amount": drop}, *steps]


def beyond_one_walk(s: Situation, cell) -> bool:
    """Follow-up fix, item 1: `cell` lies past what one whole walk can reach (pathing.route only
    ever hands back one segment toward a target more than MAX_RANGE blocks away on an axis, so
    whole_walk(cell) fails there at once, not just when a walk there just failed)."""
    return max(abs(s.here[0] - cell[0]), abs(s.here[2] - cell[2])) > MAX_RANGE


def storage_valid(s: Situation) -> bool:
    """Fix round 2: not while a step just failed near home and Mimo would have to walk there --
    without this, a home whose anchor has no path (an old chest a bigger home left stranded behind
    dug-out ground, or the like) kept being chosen, walking, failing and being chosen again the
    moment its 30-point penalty (pickers.options) wore off, "gave up trying to put things away (no
    way there)" every PENALTY_GAME_SECONDS / scale. near_failure is the same guard every explore
    target already gets (trips.targets); here it holds off a fresh attempt until other work has
    moved the failure out of state["recent_actions"]'s window, not just a fixed cooldown.
    L4b final fix wave, follow-up: not while Mimo means to stay out (purposes.AWAY, an expedition),
    the same gate as go_home. Out 115 blocks with full arms, it walked home to put things away, then
    dug its camp beside home, so the night out did not count and the dawn stall ended the trip.
    The storage follow-up: it returns early here only while home's own chest is coming
    (`home_chest_coming`); with none coming (no planks, none carried) it falls through to the chests
    Mimo has instead of returning False before it ever looks at them."""
    cell = chest_spot(s)
    if cell is None or s.night or away(s):
        return False
    structure = home_structure(s)
    if structure is not None:
        blueprint = blueprint_of(structure)
        walking = not (s.distance(cell) <= REACH and s.here in blueprint.stands)
        if walking and (near_failure(s.state, blueprint.anchor) or beyond_one_walk(s, blueprint.anchor)):
            return False
    if not chest_placed(s, cell) and home_chest_coming(s):
        return stacks(s.inventory) >= STORE_FROM
    return (stacks(s.inventory) >= STORE_FROM and bool(to_store_all(s))) or bool(to_take(s))


def storage_facts(s: Situation) -> str:
    cell = chest_spot(s)
    chest = chest_contents(s, cell)
    where = "a chest at home" if chest_placed(s, cell) else "no chest yet"
    return (f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; {where} holding {stacks(chest)} of "
            f"{CHEST_STACKS} stacks")


def storage_score(s: Situation) -> float:
    cell = chest_spot(s)
    if sky.winter(s.state) and carried_food(s) < TAKE_BELOW and to_take(s):  # W2
        return max(55.0, hunger_score(s, WINTER_TAKE))
    if chest_placed(s, cell) and to_take(s) and stacks(s.inventory) < STORE_FROM:
        return 55.0
    return 50.0 + 5.0 * max(0, stacks(s.inventory) - STORE_FROM) + (5.0 if s.state.get("full_at") else 0.0)


def plan_storage(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, make and place the chest if it is not there, put things away, and take food out
    -- home's own chest first, then (fix round 1) walk on to any other chest Mimo built that still
    holds some, so an older home's chest is never stranded once a bigger one takes over. The final
    fix wave, I2: that walk goes into the chest's own shelter (its stand, `chests_built`), within
    reach of the chest, as the walk home does; it used to head for the chest block itself, which no
    route ever reaches. The storage follow-up: while home's own chest is not coming
    (`home_chest_coming`), the walk home and the chest itself are skipped, straight to the chests
    Mimo has (`at` starts at None, so the first of them gets its own walk in)."""
    cell = chest_spot(s)
    if cell is None or s.brain["batches"] > 0:
        return []
    coming = home_chest_coming(s)
    if coming:
        structure = home_structure(s)
        home = blueprint_of(structure).anchor
        steps = [] if s.distance(cell) <= REACH and s.here in blueprint_of(structure).stands else [whole_walk(home)]
        if not chest_placed(s, cell):
            if s.count("chest") < 1:
                crafting = chest_crafting(s)
                if crafting is None:
                    return []
                steps.extend(crafting)
            steps.extend(clearing(s.grid, cell))
            steps.append({"kind": "place", "target": list(cell), "block": "chest"})
    else:
        steps = []
    stands, at = dict(chests_built(s)), cell if coming else None
    clears = [(chest_cell, item, amount, "away") for chest_cell, item, amount in to_clear(s)]
    stores = [(chest_cell, item, amount, "store") for chest_cell, item, amount in to_store_all(s)]
    for chest_cell, item, amount, kind in sorted(clears + stores, key=lambda entry: (entry[0] != cell, entry[0])):
        if chest_cell != at:
            steps.append(whole_walk(stands[chest_cell]))
            at = chest_cell
        if kind == "away":  # Making wave 2: out of a full chest, and left behind at once
            steps.append({"kind": "take", "target": list(chest_cell), "item": item, "amount": amount, "away": True})
        else:
            steps.append({"kind": "store", "target": list(chest_cell), "item": item, "amount": amount})
    for chest_cell, item, amount in to_take(s):
        if chest_cell != at:
            steps.append(whole_walk(stands[chest_cell]))
            at = chest_cell
        steps.append({"kind": "take", "target": list(chest_cell), "item": item, "amount": amount})
    return steps


register(Purpose(
    "build_storage", "put things away",
    "Put a chest in the shelter and store what it does not need to carry; take food back out when short.",
    valid=storage_valid, facts=storage_facts, score=storage_score, plan=plan_storage,
    thoughts=("My arms are getting full. Time to tidy up.", "A chest would keep all this safe.")))


def no_chest_to_use(s: Situation) -> bool:
    """No chest at home, or one with every stack taken and (Making wave 2, `to_store_all`) no other chest Mimo
    built with a stack free."""
    cell = chest_spot(s)
    if not chest_placed(s, cell):
        return True
    return all(stacks(chest_contents(s, chest)) >= CHEST_STACKS
               for chest in [cell] + [other for other, _ in reachable_chests(s)])


def shelter_blocks_left(s: Situation) -> int:
    """Floor, wall and roof blocks the shelter Mimo started still needs (0 with none, or a whole one)."""
    structure = current_shelter(s)
    return 0 if structure is None else len(todo(s.grid, blueprint_of(structure)))


def loose_blocks(s: Situation) -> list[tuple[str, int]]:
    """The loose blocks to drop when Mimo is full with no chest to use: LEAST_USEFUL, else dirt,
    else cobblestone, keeping the dirt and cobblestone the started shelter still needs beyond the
    other blocks Mimo carries (cobblestone is kept before dirt), and never dropping cobblestone
    below gather_stone's own goal (work.STONE_GOAL): otherwise the two would dig up and drop the
    same stone forever. The dirt and cobblestone tiers only fire when build_storage cannot use a
    chest instead (a carried, unplaced chest still means there is somewhere to put them). The Making final
    fix wave (I1): what Mimo keeps of a LEAST_USEFUL block (`kept`: the clay and sand a project needs)
    stays too, as `junk` keeps a project's flowers."""
    from backend.survival.work import STONE_GOAL  # imported here: work imports building, not storage

    found = [(item, s.count(item) - kept(s, item)) for item in LEAST_USEFUL if s.count(item) > kept(s, item)]
    if found:
        return found
    if storage_valid(s):
        return []
    need = shelter_blocks_left(s) - sum(count for item, count in usable_supplies(s.inventory).items()
                                        if item not in LAST_RESORT and item not in LEAST_USEFUL)
    # Making wave 2: nor below what Mimo keeps of it (`kept`: a machine's repeaters take 3 cobblestone each; on
    # the gate's route runs the computer's cobblestone went here while both chests were full).
    keep = {"cobblestone": min(s.count("cobblestone"), max(STONE_GOAL + max(0, need), kept(s, "cobblestone")))}
    keep["dirt"] = min(s.count("dirt"), max(0, need - keep["cobblestone"], kept(s, "dirt")))  # a machine's yard
    for item in LAST_RESORT:
        if s.count(item) > keep[item]:
            return [(item, s.count(item) - keep[item])]
    return []


def spare_fences(s: Situation) -> list[tuple[str, int]]:
    """L3: fences are made 3 at a time, so a pen leaves one or two over. Once the newest pen by home
    is done (backend.survival.pens; the final fix wave: by home, home.by_home, not near Mimo), they
    are no use to carry."""
    pens = by_home(s, "pen")
    if not s.count("fence") or not pens or pens[-1]["status"] != "done":
        return []
    return [("fence", s.count("fence"))]


def spare_torches(s: Situation) -> list[tuple[str, int]]:
    """Fix round 1: a torch beyond what home's own dark corners still need (storage.kept) is spare
    the same way an extra fence is (spare_fences): drop_items can shed it without waiting for a
    chest visit, so it does not sit in Mimo's arms until build_storage next has a reason to walk
    home."""
    excess = s.count("torch") - kept(s, "torch")
    return [("torch", excess)] if excess > 0 else []


def junk(s: Situation) -> list[tuple[str, int]]:
    """(item, amount) that is no use to carry: known poison, replaced tools and swords, flowers; and, full with
    no chest to use, loose blocks (loose_blocks)."""
    found = [(item, s.inventory[item]) for item in s.discards if s.inventory.get(item, 0) > 0]  # W1: not shunned
    best = max((TOOL_RANK[tool] for tool in TOOL_RANK if s.count(tool)), default=0)
    found += [(tool, s.count(tool)) for tool, rank in TOOL_RANK.items() if s.count(tool) and rank < best]
    axes = [axe for axe in AXES if s.count(axe)]
    found += [(axe, s.count(axe)) for axe in axes[:-1]]
    swords = [sword for sword in SWORD_LADDER if s.count(sword)]
    found += [(sword, s.count(sword)) for sword in swords[:-1]]
    found += [(piece, s.count(piece)) for piece in ("leather_cap", "leather_tunic")
              if s.count(piece) and s.count(piece.replace("leather", "iron"))]  # L3: iron replaced it
    for flower in FLOWERS:  # Making: but the flowers a project wants for its dye (KEEPS_MORE)
        spare = s.count(flower) - max(0, round(more_kept(s, flower)))
        if spare > 0:
            found.append((flower, spare))
    found += spare_fences(s)
    found += spare_torches(s)
    for extra in JUNK_MORE:  # Making wave 2, fix round 1: a second furnace (backend.survival.workshop)
        try:
            found += [(item, amount) for item, amount in extra(s) if amount > 0]
        except Exception as error:
            log_once(logger, "junk more", error)
    if stacks(s.inventory) >= CARRY_STACKS and no_chest_to_use(s):
        found += loose_blocks(s)
    return found


def plan_drop(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return [{"kind": "drop", "item": item, "amount": amount} for item, amount in junk(s)]


register(Purpose(
    "drop_items", "drop what it cannot use",
    "Leave behind food it knows is poisonous, tools a better one replaced and other things of no use.",
    valid=lambda s: stacks(s.inventory) >= DROP_FROM and bool(junk(s)),
    facts=lambda s: f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; no use for "
                    + ", ".join(item.replace("_", " ") for item, _ in junk(s)),
    score=lambda s: 30.0 + 8.0 * max(0, stacks(s.inventory) - DROP_FROM),
    plan=plan_drop,
    thoughts=("I don't need all of this.", "Lighter is better.")))

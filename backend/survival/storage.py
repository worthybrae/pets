"""A lighter load: build_storage and drop_items (spec section 8, inventory limit).

Mimo carries at most 16 stacks (backend.survival.carrying). build_storage puts a chest in the
back corner the shelter design keeps for it, under the roof, making it from 8 planks when Mimo
carries none (and has room to carry the chest it makes), and puts away what Mimo does not need to
carry: loose blocks, materials beyond what a day's work takes (KEEP; logs and planks of every wood
count toward one keep each, L3 final fix wave), and food beyond a day's worth. With its arms full, the building blocks it keeps (cobblestone, planks) go in whole too. It
takes food back out when Mimo carries less than a meal's worth. It is offered at the built
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
first and cobblestone last -- to clear room, then tries again.
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
from backend.survival.foraging import FOOD_WANTED, whole_walk
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

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

STORE_FROM = 13  # stacks from which putting things away is worth a trip home
DROP_FROM = 10
TAKE_BELOW = 20.0  # hunger points of food carried below which Mimo takes food out
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


# L4b: functions of (Situation, item) giving how many more of an item Mimo keeps on it now, beyond
# what the rules below keep ("food" for hunger points of food): an expedition's torches and food.
# Fewer when negative (what a packing expedition leaves at home), but never fewer than none.
KEEPS_MORE: list = []


def more_kept(s: Situation, item: str) -> float:
    """What KEEPS_MORE add for `item`; one that crashes adds nothing (logged once)."""
    total = 0.0
    for extra in KEEPS_MORE:
        try:
            total += float(extra(s, item))
        except Exception as error:
            log_once(logger, "keeps more", error)
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
    (cooking.RAW_FOODS) is neither: it waits for the fire, since cook only uses what Mimo carries."""
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


def to_store(s: Situation, cell) -> list[tuple[str, int]]:
    """(item, amount) Mimo would put away, most first, as far as the chest has room."""
    chest = chest_contents(s, cell)
    wanted = [(item, count - kept(s, item)) for item, count in s.inventory.items()
              if item in KEEP and count > kept(s, item)] + spare_food(s)
    found = []
    for item, amount in sorted(wanted, key=lambda entry: (-entry[1], entry[0])):
        amount = min(amount, room_for(chest, item, CHEST_STACKS))
        if amount > 0:
            chest[item] = chest.get(item, 0) + amount
            found.append((item, amount))
    return found[:STORE_STEPS]


def carried_food(s: Situation) -> float:
    return sum(FOOD[item] * s.inventory[item] for item in foods(s.inventory, s.poisons))


def reachable_chests(s: Situation) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """`chests_built`, leaving out one whose stand a step just failed near while Mimo would have to
    walk there (the final fix wave, I2: the same guard as storage_valid's walk home), so a chest
    with no way to it is not tried again at once."""
    return [(cell, stand) for cell, stand in chests_built(s)
            if s.here == stand or s.distance(cell) <= REACH or not near_failure(s.state, stand)]


def to_take(s: Situation) -> list[tuple[tuple[int, int, int], str, int]]:
    """(cell, item, amount) to take out of a chest when Mimo carries less than a meal's worth, best
    first: home's own chest first, then (fix round 1) any other chest Mimo built, so an older
    home's chest is never stranded once a bigger one takes over (not one it just failed to reach,
    `reachable_chests`)."""
    if carried_food(s) >= TAKE_BELOW:
        return []
    have, found = carried_food(s), []
    for chest_cell, _ in reachable_chests(s):
        chest = chest_contents(s, chest_cell)
        for item in foods(chest, s.poisons):
            amount = 0
            while amount < chest[item] and have < FOOD_WANTED:
                amount += 1
                have += FOOD[item]
            if amount:
                found.append((chest_cell, item, amount))
        if have >= FOOD_WANTED:
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
    spare = next((item for item in LOW_VALUE if inventory.get(item, 0) > 0), None)
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
    dug its camp beside home, so the night out did not count and the dawn stall ended the trip."""
    cell = chest_spot(s)
    if cell is None or s.night or away(s):
        return False
    structure = home_structure(s)
    if structure is not None:
        blueprint = blueprint_of(structure)
        walking = not (s.distance(cell) <= REACH and s.here in blueprint.stands)
        if walking and (near_failure(s.state, blueprint.anchor) or beyond_one_walk(s, blueprint.anchor)):
            return False
    if not chest_placed(s, cell):
        can_have = s.count("chest") > 0 or chest_crafting(s) is not None
        return can_have and stacks(s.inventory) >= STORE_FROM
    return (stacks(s.inventory) >= STORE_FROM and bool(to_store(s, cell))) or bool(to_take(s))


def storage_facts(s: Situation) -> str:
    cell = chest_spot(s)
    chest = chest_contents(s, cell)
    where = "a chest at home" if chest_placed(s, cell) else "no chest yet"
    return (f"carrying {stacks(s.inventory)} of {CARRY_STACKS} stacks; {where} holding {stacks(chest)} of "
            f"{CHEST_STACKS} stacks")


def storage_score(s: Situation) -> float:
    cell = chest_spot(s)
    if chest_placed(s, cell) and to_take(s) and stacks(s.inventory) < STORE_FROM:
        return 55.0
    return 50.0 + 5.0 * max(0, stacks(s.inventory) - STORE_FROM) + (5.0 if s.state.get("full_at") else 0.0)


def plan_storage(s: Situation, context: ActionContext) -> list[dict]:
    """Walk home, make and place the chest if it is not there, put things away, and take food out
    -- home's own chest first, then (fix round 1) walk on to any other chest Mimo built that still
    holds some, so an older home's chest is never stranded once a bigger one takes over. The final
    fix wave, I2: that walk goes into the chest's own shelter (its stand, `chests_built`), within
    reach of the chest, as the walk home does; it used to head for the chest block itself, which no
    route ever reaches."""
    cell = chest_spot(s)
    if cell is None or s.brain["batches"] > 0:
        return []
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
    steps.extend({"kind": "store", "target": list(cell), "item": item, "amount": amount}
                 for item, amount in to_store(s, cell))
    stands, at = dict(chests_built(s)), cell
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
    """No chest at home, or one with every stack taken."""
    cell = chest_spot(s)
    return not chest_placed(s, cell) or stacks(chest_contents(s, cell)) >= CHEST_STACKS


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
    chest instead (a carried, unplaced chest still means there is somewhere to put them)."""
    from backend.survival.work import STONE_GOAL  # imported here: work imports building, not storage

    found = [(item, s.count(item)) for item in LEAST_USEFUL if s.count(item)]
    if found:
        return found
    if storage_valid(s):
        return []
    need = shelter_blocks_left(s) - sum(count for item, count in usable_supplies(s.inventory).items()
                                        if item not in LAST_RESORT and item not in LEAST_USEFUL)
    keep = {"cobblestone": min(s.count("cobblestone"), STONE_GOAL + max(0, need))}
    keep["dirt"] = min(s.count("dirt"), max(0, need - keep["cobblestone"]))
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
    found = [(item, s.inventory[item]) for item in s.poisons if s.inventory.get(item, 0) > 0]
    best = max((TOOL_RANK[tool] for tool in TOOL_RANK if s.count(tool)), default=0)
    found += [(tool, s.count(tool)) for tool, rank in TOOL_RANK.items() if s.count(tool) and rank < best]
    axes = [axe for axe in AXES if s.count(axe)]
    found += [(axe, s.count(axe)) for axe in axes[:-1]]
    swords = [sword for sword in SWORD_LADDER if s.count(sword)]
    found += [(sword, s.count(sword)) for sword in swords[:-1]]
    found += [(piece, s.count(piece)) for piece in ("leather_cap", "leather_tunic")
              if s.count(piece) and s.count(piece.replace("leather", "iron"))]  # L3: iron replaced it
    found += [(flower, s.count(flower)) for flower in FLOWERS if s.count(flower)]
    found += spare_fences(s)
    found += spare_torches(s)
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

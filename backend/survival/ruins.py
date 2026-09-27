"""Frontier ruins in the brain (L5): seeing them, opening their old chests and taking the loot.

Worldgen stands a small ruin in some regions, with an old chest in its middle
(backend.services.worldgen.region_ruin). Here Mimo meets them:
- Seeing one: after every walk or swim (`notice_ruins`, one of steps.OBSERVERS, which the brain
  calls), a ruin whose chest is within RUIN_SIGHT blocks and that Mimo does not remember yet is
  remembered as a "ruin" place (at its chest) and is a notable "found" event ("Pip found an old ruin
  in the far wilds."), a new place for curiosity and a discovery that asks for a new choice.
- The open_chest step (0.6 s, the chest within reach): the first time Mimo opens a ruin's chest the
  server rolls what is inside by the ruin's danger ring (`ruin_loot`, from the world seed, the chest's
  cell and the ring, so the same chest in the same ring always holds the same) and puts it in the
  chest (state["chests"], where every chest's contents live). Nearer ruins hold food, arrows and iron;
  farther ones gold, amber and diamonds. A notable "loot" event names what was inside. A chest once
  opened stays open; the place is noted opened. Opened before Mimo knows that copper carries a spark, one
  chest in RUIN_MANUAL_ODDS holds an old manual that teaches it (`find_manual`; Making's tinker.py waited
  for L5's ruins to carry them).
- The loot event is a memory (Mind's episodes.MOMENTS) and news in the owner's inbox (Bond's moments),
  like the "found" events of a ruin seen, a first thornback and the first steps into the far wilds.
- The loot_ruin purpose ("loot an old ruin"): by day, not late, a remembered ruin within LOOT_RANGE
  whose chest still stands and holds something (or was never opened), in a ring Mimo is ready for
  (rings.ready_ring: home ground and the near wilds always), the nearest first. It walks up, opens the
  chest, then takes what it has room for below LOOT_ROOM stacks, the rarest first (housework's take
  step); the rest waits in the chest until Mimo has room again. Riches it makes room for (the L5 final fix
  wave, I2: `room_for_riches` leaves stacks of blocks there first), and a chest that still holds riches is
  worth going back to (backend.survival.frontier). A first version took all that fit in
  its 16 stacks: four new stacks early in a life pushed a pet near home past the point where putting
  things away and dropping loose blocks are worth doing, and it swung between digging stone, dropping
  and putting away (94 changes of purpose in its busiest hour, over the sims' 90; seed 5, the fake
  Jev, slow mode). Work band: 58 plus a tenth of bravery. A chest in sight (within URGE_REACH) is an
  urge (goals.URGES): Mimo opens it though its goal is something else. The frontier goal
  (backend.survival.frontier) names it too.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import RUIN_REGION, region_ruin
from backend.survival import nature
from backend.survival import storage
from backend.survival.carrying import CARRY_STACKS, LOW_VALUE, STACK, room_for
from backend.survival.foraging import STAND, whole_walk
from backend.survival.goals import add_urge
from backend.survival.grid import Cell, Grid
from backend.survival.housework import chest_key
from backend.survival.journal import journal_ready, learn_lesson, taught
from backend.survival.memory import remember, update_place
from backend.survival.purposes import Purpose, late_day, late_penalty, register
from backend.survival.rings import DEEPEST, ready_ring, ring_at, ring_name
from backend.survival.senses import near_failure
from backend.survival.situation import Situation
from backend.survival.steps import (
    OBSERVERS, REACH, StepFailed, StepKind, as_cell, as_point, in_reach, label, register_step, seed_of,
)
from backend.survival.triggers import mark_trigger
from backend.survival.trips import fenced

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

RUIN = "ruin"  # the memory place kind, at the ruin's chest
RUIN_SIGHT = 24.0  # a ruin's chest this close after a walk is seen
LOOT_RANGE = 64.0  # loot_ruin goes to remembered ruins this close
URGE_REACH = 32.0  # an unopened chest this close is an urge
OPEN_SECONDS = 0.6
LOOT_BATCHES = 3
LOOT_ROOM = storage.STORE_FROM - 1  # stacks Mimo fills with loot at most: below where putting things away is worth a trip
# The order loot is taken in when there is not room for all of it: the rarest first.
RAREST_FIRST = ("diamond", "amber", "gold_ingot", "gold_nugget", "iron_ingot", "bread", "coal", "arrow", "torch")
# Pre-flight (carry 5): the far rings' riches may fill Mimo's arms; the rest stops at LOOT_ROOM. Task 6
# review, M3: capped one stack short of CARRY_STACKS, not at it -- riches filling the very last stack
# left no room at all, so the next bit of food pushed out flint or leather instead of riding along free.
RICHES_ROOM = CARRY_STACKS - 1
RICHES = ("diamond", "amber", "gold_ingot", "gold_nugget")
# What an old chest holds by the ring its ruin stands in: (item, least, most, chance).
LOOT = {
    0: (("bread", 1, 3, 1.0), ("arrow", 4, 8, 0.8), ("iron_ingot", 1, 2, 0.7), ("torch", 2, 4, 0.5)),
    1: (("bread", 2, 4, 1.0), ("arrow", 4, 8, 0.9), ("iron_ingot", 1, 3, 0.8), ("coal", 2, 4, 0.6)),
    2: (("bread", 2, 4, 0.8), ("arrow", 6, 12, 1.0), ("iron_ingot", 2, 4, 0.8), ("gold_nugget", 2, 6, 0.8),
        ("amber", 1, 2, 0.6)),
    3: (("arrow", 8, 16, 1.0), ("gold_ingot", 1, 3, 0.8), ("gold_nugget", 3, 8, 0.8), ("amber", 1, 3, 0.8),
        ("diamond", 1, 1, 0.5)),
    4: (("arrow", 8, 16, 1.0), ("gold_ingot", 2, 4, 1.0), ("amber", 2, 4, 1.0), ("diamond", 1, 3, 0.8)),
}
LOOT_ROLL, COUNT_ROLL = 130, 140  # nature.roll channels (and the next few after each)
UNCOUNTED = ("bread", "coal", "amber")  # said as they are, whatever the count: "4 bread"
# Making's hook (pre-flight, carry 4): an old chest opened before Mimo knows that copper carries a spark holds
# an old manual one time in RUIN_MANUAL_ODDS (a roll on the world seed and the chest's cell), which teaches it.
RUIN_MANUAL_ODDS = 3
MANUAL_ROLL = 150


# Where ruins are -------------------------------------------------------------------------------

def ruin_chest(seed: str, rx: int, rz: int) -> Cell | None:
    """The cell of the chest of region (rx, rz)'s ruin, or None."""
    ruin = region_ruin(rx, rz, seed)
    return None if ruin is None else (ruin[0], ruin[2] + 1, ruin[1])


def ruins_near(seed: str, x: float, z: float, reach: float) -> list[Cell]:
    """The chests of the ruins within `reach` blocks (across) of (x, z), nearest first."""
    found = []
    for rx in range(math.floor((x - reach) / RUIN_REGION), math.floor((x + reach) / RUIN_REGION) + 1):
        for rz in range(math.floor((z - reach) / RUIN_REGION), math.floor((z + reach) / RUIN_REGION) + 1):
            chest = ruin_chest(seed, rx, rz)
            if chest is not None and math.hypot(chest[0] - x, chest[2] - z) <= reach:
                found.append(chest)
    return sorted(found, key=lambda cell: (math.hypot(cell[0] - x, cell[2] - z), cell))


def is_ruin_chest(seed: str, cell: Cell) -> bool:
    return ruin_chest(seed, cell[0] // RUIN_REGION, cell[2] // RUIN_REGION) == tuple(cell)


def ruin_chest_key(seed: str, key: str) -> bool:
    """Whether a state["chests"] key (housework.chest_key) is an old ruin's chest, not one Mimo built."""
    x, y, z = (int(part) for part in key.split(","))
    return is_ruin_chest(seed, (x, y, z))


def ruin_loot(seed: str, cell: Cell, ring: int) -> dict[str, int]:
    """What the old chest at `cell` holds when first opened in `ring` (see the module docstring)."""
    level = max(0, min(DEEPEST, ring))
    found = {}
    for index, (item, least, most, chance) in enumerate(LOOT[level]):
        if nature.roll(seed, cell, LOOT_ROLL + index, level) < chance:
            found[item] = least + int(nature.roll(seed, cell, COUNT_ROLL + index, level) * (most - least + 1))
    return found


def plural(item: str, count: int) -> str:
    """ "arrows", "torches", "bread" (pre-flight: the loot's words are said in the inbox and Mind's memory)."""
    words = label(item)
    if count == 1 or item in UNCOUNTED:
        return words
    return f"{words}es" if words.endswith(("ch", "sh")) else f"{words}s"


def loot_words(loot: dict[str, int]) -> str:
    parts = [f"{count} {plural(item, count)}" for item, count in sorted(loot.items(), key=lambda entry: (-entry[1], entry[0]))]
    if not parts:
        return "nothing at all"
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


# Seeing ruins ----------------------------------------------------------------------------------

def notice_ruins(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a walk or swim: remember a ruin whose chest Mimo can see now (see the module docstring)."""
    if step["kind"] not in ("walk", "swim") or context.db is None:
        return
    position = state["position"]
    for chest in ruins_near(seed_of(state), position["x"], position["z"], RUIN_SIGHT):
        if context.grid.material(*chest) != "chest":
            continue
        ring = min(DEEPEST, ring_at(state, chest[0], chest[2]))
        if remember(context.db, RUIN, chest, at, ring_name(ring).lower()):
            context.events.append((at, "found", f"{state['name']} found an old ruin in the {ring_name(ring).lower()}."))
            mark_trigger(state, "discovery", at)


def holds_manual(seed: str, chest: Cell) -> bool:
    """Whether the old chest at `chest` holds an old manual (RUIN_MANUAL_ODDS)."""
    return nature.roll(seed, chest, MANUAL_ROLL) < 1 / RUIN_MANUAL_ODDS


def find_manual(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After an open_chest step (steps.OBSERVERS): the chest's old manual, if it holds one and Mimo does not
    know that copper carries a spark yet, teaches it (pre-flight, carry 4: Making's "L5's ruins carry them")."""
    from backend.survival.tinker import SPARK  # here: importing tinker at the top would move making's registrations

    if step["kind"] != "open_chest" or not journal_ready(state, context.db) or taught(context.db, SPARK):
        return
    if holds_manual(seed_of(state), as_cell(step["target"])):
        context.events.append((at, "found", f"{state['name']} found an old manual in the ruin's chest."))
        learn_lesson(state, context, at, SPARK)


def note_opened(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After an open_chest step: the ruin's place is noted opened (steps.OBSERVERS). The L5 final fix wave (I2):
    after a take of riches from an old chest, it is noted looted, which the frontier goal counts like an opening
    (a riches trip goes back to a chest opened before that still holds riches)."""
    if context.db is None:
        return
    if step["kind"] == "open_chest":
        update_place(context.db, RUIN, as_cell(step["target"]), {"opened": at})
    elif step["kind"] == "take" and step.get("item") in RICHES and not step.get("away"):
        cell = as_cell(step["target"])
        if is_ruin_chest(seed_of(state), cell):
            update_place(context.db, RUIN, cell, {"looted": at})


# The open_chest step ---------------------------------------------------------------------------

def closed_ruin_chest(spec: dict, state: dict, grid: Grid) -> Cell:
    target = as_cell(spec["target"])
    if not in_reach(as_cell(state["position"]), target):
        raise StepFailed("out of reach", "out_of_reach")
    if grid.material(*target) != "chest" or not is_ruin_chest(seed_of(state), target):
        raise StepFailed("there is no old chest there", "gone")
    if chest_key(target) in state.get("chests", {}):
        raise StepFailed("it is open already", "blocked")
    return target


def start_open(spec: dict, state: dict, grid: Grid, at: float, scale: float) -> dict:
    target = closed_ruin_chest(spec, state, grid)
    return {"kind": "open_chest", "started_at": at, "ends_at": round(at + OPEN_SECONDS / scale, 3),
            "target": as_point(target)}


def finish_open(step: dict, state: dict, grid: Grid, at: float) -> tuple[str, str]:
    target = closed_ruin_chest(step, state, grid)
    ring = min(DEEPEST, ring_at(state, target[0], target[2]))
    loot = ruin_loot(seed_of(state), target, ring)
    state.setdefault("chests", {})[chest_key(target)] = dict(loot)
    state["last_thought"] = "Treasure!" if loot else "Empty... someone got here first."
    return "loot", f"{state['name']} opened an old chest in a ruin: {loot_words(loot)}."


register_step(StepKind("open_chest", start_open, finish_open, "opening", cell_field="target"))


# loot_ruin -------------------------------------------------------------------------------------

def opened(s: Situation, chest: Cell) -> bool:
    return chest_key(chest) in s.state.get("chests", {})


def inside_of(s: Situation, chest: Cell) -> dict[str, int]:
    return s.state.get("chests", {}).get(chest_key(chest), {})


def rarest_first(items) -> list[str]:
    rank = {item: index for index, item in enumerate(RAREST_FIRST)}
    return sorted(items, key=lambda item: (rank.get(item, len(rank)), item))


def takeable(s: Situation, chest: Cell, carried: dict[str, int] | None = None) -> dict[str, int]:
    """What Mimo takes out of an opened chest now (with `carried` in its arms: what it carries): the rarest first,
    as much as it has room for below LOOT_ROOM stacks (RICHES: RICHES_ROOM), all of it together."""
    inside = inside_of(s, chest)
    carried, found = dict(s.inventory if carried is None else carried), {}
    for item in rarest_first(inside):
        amount = min(inside[item], room_for(carried, item, RICHES_ROOM if item in RICHES else LOOT_ROOM))
        if amount > 0:
            found[item] = amount
            carried[item] = carried.get(item, 0) + amount
    return found


def holds_riches(s: Situation, chest: Cell) -> bool:
    """An opened old chest that still holds riches (the L5 final fix wave, I2: a target again)."""
    return opened(s, chest) and any(inside_of(s, chest).get(item, 0) > 0 for item in RICHES)


def riches_left(s: Situation, chest: Cell, carried: dict[str, int]) -> int:
    """How many of the chest's riches would stay in it with `carried` in Mimo's arms (RICHES_ROOM)."""
    inside = inside_of(s, chest)
    trial, left = dict(carried), 0
    for item in rarest_first(item for item in inside if item in RICHES):
        fit = min(inside[item], room_for(trial, item, RICHES_ROOM))
        trial[item] = trial.get(item, 0) + fit
        left += inside[item] - fit
    return left


def room_for_riches(s: Situation, chest: Cell) -> tuple[list[dict], dict[str, int]]:
    """(drop steps, Mimo's arms after them): the stacks Mimo leaves at an old chest so the riches in it fit (the L5
    final fix wave, I2), the same trade carrying.settle makes when a treasure drops into full arms: whole stacks
    of carrying.LOW_VALUE blocks first (the least useful first, none below what Mimo keeps: storage.kept), then
    what is no use to carry (storage.junk: a replaced tool, a replaced iron piece), then the blocks it keeps too.
    None when the riches fit already, or when nothing it drops would let more of them fit. On the final review's
    gate pets carried 15 or more stacks for 60 to 103 of their 150 days, and 42 % of the far chests' gold and
    amber stayed in them."""
    carried = dict(s.inventory)
    before = riches_left(s, chest, carried)
    if not before:
        return [], carried
    junk = [(item, max(0, s.count(item) - amount)) for item, amount in storage.junk(s) if item not in LOW_VALUE]
    tiers = [(item, storage.kept(s, item)) for item in LOW_VALUE] + junk + [(item, 0) for item in LOW_VALUE]
    dropped: dict[str, int] = {}
    for item, keep in tiers:
        while riches_left(s, chest, carried) and carried.get(item, 0) > 0:
            part = carried[item] % STACK or STACK
            if carried[item] - part < keep:
                break
            carried[item] -= part
            dropped[item] = dropped.get(item, 0) + part
            if not carried[item]:
                del carried[item]
    if riches_left(s, chest, carried) >= before:
        return [], dict(s.inventory)
    return [{"kind": "drop", "item": item, "amount": amount} for item, amount in dropped.items()], carried


def worth_a_visit(s: Situation, chest: Cell) -> bool:
    """The chest still stands, and was never opened or holds something Mimo can carry (the L5 final fix wave, I2:
    or riches it can make room for)."""
    if s.grid.material(*chest) != "chest":
        return False
    return not opened(s, chest) or bool(takeable(s, chest)) or bool(room_for_riches(s, chest)[0])


def ruin_targets(s: Situation) -> list[Cell]:
    """Remembered ruins within LOOT_RANGE worth a visit, in a ring Mimo is ready for and inside the limit every
    walk keeps to (trips.fenced; the L5 final fix wave, I4), nearest first.
    Task 6 review, M2: a chest a step just failed to reach is left alone for a while too (the same
    guard storage.reachable_chests already has), so it is not retried at once."""
    def look() -> list[Cell]:
        ready = ready_ring(s)
        found = [(place["x"], place["y"], place["z"]) for place in s.places if place["kind"] == RUIN]
        found = [chest for chest in found if s.distance(chest) <= LOOT_RANGE
                 and ring_at(s.state, chest[0], chest[2]) <= ready and not fenced(s, chest) and worth_a_visit(s, chest)
                 and (s.distance(chest) <= REACH or not near_failure(s.state, chest))]
        return sorted(found, key=lambda chest: (s.distance(chest), chest))
    return s.sensed("ruin targets", look)


def loot_valid(s: Situation) -> bool:
    return not s.night and not late_day(s) and bool(ruin_targets(s))


def loot_facts(s: Situation) -> str:
    chest = ruin_targets(s)[0]
    ring = ring_name(ring_at(s.state, chest[0], chest[2])).lower()
    inside = "its chest never opened" if not opened(s, chest) else \
        f"its chest holds {loot_words(s.state['chests'][chest_key(chest)])}"
    return f"an old ruin {round(s.distance(chest))} blocks away in the {ring}, {inside}"


def plan_loot(s: Situation, context: ActionContext) -> list[dict]:
    """Walk up to the nearest ruin worth a visit, open its chest, then take what fits."""
    targets = ruin_targets(s)
    if not targets or s.brain["batches"] >= LOOT_BATCHES:
        return []
    chest = targets[0]
    steps = [whole_walk(chest, STAND)] if s.distance(chest) > REACH else []
    if not opened(s, chest):
        return steps + [{"kind": "open_chest", "target": list(chest)}]
    drops, carried = room_for_riches(s, chest)
    takes = [{"kind": "take", "target": list(chest), "item": item, "amount": count}
             for item, count in takeable(s, chest, carried).items()]
    return steps + drops + takes if takes else []


def chest_in_sight(s: Situation) -> bool:
    """An unopened ruin chest within URGE_REACH, or (the L5 final fix wave, I2) one still holding riches it can
    carry: Mimo wants to open it or empty it, whatever its goal."""
    return any((not opened(s, chest) or holds_riches(s, chest)) and s.distance(chest) <= URGE_REACH
               for chest in ruin_targets(s))


register(Purpose(
    "loot_ruin", "loot an old ruin",
    "Walk to an old ruin Mimo found, open its chest and take what it holds (food, arrows and iron near home; "
    "gold, amber and diamonds farther out).",
    valid=loot_valid, facts=loot_facts,
    score=lambda s: 58.0 + s.trait("bravery") / 10 - late_penalty(s), plan=plan_loot,
    thoughts=("An old ruin! I wonder what's in that chest.", "Somebody left something here long ago.")))

add_urge("loot_ruin", chest_in_sight)
# Task 6 review, M6: find_manual is not one of OBSERVERS (called before note_discoveries costs curiosity
# for the step's "found"/"discovered" events) -- brain.observe_step calls it after note_discoveries,
# the same place observe_tinker's copper manual is called, so a manual costs the same curiosity either way.
OBSERVERS.extend((notice_ruins, note_opened))

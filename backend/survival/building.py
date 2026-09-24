"""build_shelter: a home Mimo builds itself, one block at a time.

With no shelter of its own within 64 blocks, Mimo designs one (backend.survival.blueprints) on
flat ground near its home (a mine staircase or overhang it found), or near where it stands, and
starts once it carries at least half the blocks it needs. The design and the cells it claims are
remembered (backend.survival.structures), so every later batch goes on with the same design:
walk inside, then place up to 12 blocks a batch in the design's order, floor, walls, roof, making
planks from logs when the planks run short and letting any building block stand in for another.
With arms too full to carry the planks a log makes, logs do not count as blocks and the batch
places only what Mimo carries.
When the blocks run out the purpose pauses (its plan is done) and the gathering purposes aim for
what is still missing (`building_need`); it goes on once Mimo carries 8 blocks again, or what is
left. When the last floor, wall or roof block is down the shelter is done: home moves into it
(memory.set_home, noted "built"), a notable "built" event is logged and Mimo is pleased.

A finished shelter is furnished by the same purpose: a bed (carried, or made from 6 planks) in
its back corner and a campfire (carried, or made from 2 logs and 3 sticks) beside the door. A
shelter with a floor, wall or roof block gone is damaged and build_shelter repairs it; a door gap
or passage something solid was put in is cleared. build_storage puts a chest in the other back
corner and light_up the torches at the outside corners (backend.survival.storage, lighting).

Scores sit in the needs band: 60 to 70 by caution, 10 more from the afternoon on so the roof is
up before night, 75 for repairs, 45 to 55 for furnishing. Building is day work next to home, so
it takes no late-day penalty; at night Mimo sleeps.

`note_building` hears about every finished step (brain.observe_step): it finishes structures,
remembers the saplings Mimo planted (so gather_wood knows the trees that grow there are its own
to chop), lifts Mimo's mood for each torch and asks for a new choice when Mimo's arms get full.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.worldgen import terrain_height
from backend.survival.blueprints import Blueprint, Planned, bill, design_shelter, pick_block, supplies
from backend.survival.carrying import crafts_fit
from backend.survival.cooking import made
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, finish_structure, nearest, remember, set_home, structures
from backend.survival.purposes import HOME_RANGE, Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import REACH, as_cell
from backend.survival.structures import blocked, blueprint_of, start, structure_at, todo
from backend.survival.triggers import mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

PLACES_PER_BATCH = 12
SHELTER_BATCHES = 8
START_SHARE = 0.5  # start a shelter once Mimo carries half the blocks it needs
RESUME_BLOCKS = 8  # go on with one once it carries this many blocks (or all that is left)
FEWEST_BLOCKS = 12  # below this no shelter design is even looked for
NOMINAL_BILL = 38  # about what the smallest shelter takes, before a design says exactly
AFTERNOON = 1200.0  # game seconds into the day from which building gets more urgent
BUILT_MOOD = 10.0
TORCH_MOOD = 2.0
FURNISHINGS = ("bed", "campfire")
SHELTER_RANGE = 2 * HOME_RANGE  # a shelter Mimo built this close is still its own: it starts no other


def structures_near(s: Situation, kind: str, reach: float = HOME_RANGE) -> list[dict]:
    """Structures of `kind` Mimo started, oldest first, whose anchor is within `reach` blocks."""
    known = s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])
    x, _, z = s.here
    return [found for found in known if found["kind"] == kind and math.hypot(found["x"] - x, found["z"] - z) <= reach]


def current_shelter(s: Situation) -> dict | None:
    """The newest shelter Mimo started within 64 blocks, being built or done."""
    near = structures_near(s, "shelter")
    return near[-1] if near else None


def shelter_elsewhere(s: Situation) -> bool:
    """Mimo has a shelter of its own farther than 64 but within 128 blocks: it goes back to that
    one instead of starting another."""
    return current_shelter(s) is None and bool(structures_near(s, "shelter", SHELTER_RANGE))


def site_center(s: Situation) -> Cell:
    """Where to look for a site: home (on the surface above it, when home is a staircase or cave),
    else where Mimo stands."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
    x, y, z = cell_of(home) if home is not None else s.here
    return x, max(y, terrain_height(x, z, s.seed) + 1), z


def without_logs(inventory: dict) -> dict:
    return {item: count for item, count in inventory.items() if item != "oak_log"}


def usable_supplies(inventory: dict) -> dict[str, int]:
    """The building blocks Mimo can use now (blueprints.supplies): its logs count as planks only
    while it has room to carry the planks a log makes (carrying.crafts_fit)."""
    if crafts_fit(inventory, [{"kind": "craft", "recipe": "planks"}]):
        return supplies(inventory)
    return supplies(without_logs(inventory))


def carried_blocks(s: Situation) -> int:
    return sum(usable_supplies(s.inventory).values())


def shelter_design(s: Situation) -> Blueprint | None:
    """A new shelter's design (looked for once per Situation)."""
    def look() -> Blueprint | None:
        if carried_blocks(s) < FEWEST_BLOCKS:
            return None
        known = s.sensed("structures", lambda: structures(s.db) if s.db is not None else [])
        return design_shelter(s.grid, s.seed, site_center(s), s.state.get("traits", {}), s.inventory,
                              s.state["name"], len(known))
    return s.sensed("shelter_design", look)


def fittings_due(s: Situation, blueprint: Blueprint) -> list[Planned]:
    """A bed and a campfire still missing that Mimo carries or can make now."""
    due, trial = [], dict(s.inventory)
    for planned in todo(s.grid, blueprint, FURNISHINGS):
        if trial.get(planned.block, 0) > 0:
            trial[planned.block] -= 1
            due.append(planned)
        elif made(trial, planned.block) is not None:
            trial[planned.block] -= 1
            due.append(planned)
    return due


def enough_to_resume(s: Situation, remaining: int) -> bool:
    return carried_blocks(s) >= min(RESUME_BLOCKS, remaining)


def shelter_valid(s: Situation) -> bool:
    if s.night:
        return False
    structure = current_shelter(s)
    if structure is None:
        design = None if shelter_elsewhere(s) else shelter_design(s)
        return design is not None and carried_blocks(s) >= START_SHARE * bill(design, s.grid)
    blueprint = blueprint_of(structure)
    remaining = todo(s.grid, blueprint)
    if remaining:
        return enough_to_resume(s, len(remaining))
    return bool(blocked(s.grid, blueprint)) or bool(fittings_due(s, blueprint))


def shelter_facts(s: Situation) -> str:
    carried = carried_blocks(s)
    structure = current_shelter(s)
    if structure is None:
        design = shelter_design(s)
        need = bill(design, s.grid) if design else NOMINAL_BILL
        return (f"no shelter of its own yet; {design.name if design else 'a small shelter'} would need {need} "
                f"blocks, carrying {carried} (short {max(0, need - carried)})")
    blueprint = blueprint_of(structure)
    remaining = len(todo(s.grid, blueprint))
    if remaining and structure["status"] == "done":
        return f"{structure['name']} is damaged: {remaining} blocks missing, carrying {carried}"
    if remaining:
        return (f"building {structure['name']}: {remaining} blocks to go, carrying {carried} "
                f"(short {max(0, remaining - carried)})")
    furnishing = [planned.part for planned in fittings_due(s, blueprint)]
    return f"{structure['name']} is built; it could still use a {' and a '.join(furnishing) or 'clear door'}"


def shelter_score(s: Situation) -> float:
    structure = current_shelter(s)
    if structure is not None and structure["status"] == "done":
        blueprint = blueprint_of(structure)
        if todo(s.grid, blueprint) or blocked(s.grid, blueprint):
            return 75.0
        return 45.0 + s.trait("creativity") / 10
    urgent = 10.0 if s.clock["seconds_into_day"] >= AFTERNOON else 0.0
    return 60.0 + s.trait("caution") / 10 + urgent


def stand_for(blueprint: Blueprint, at: Cell, cell: Cell) -> Cell | None:
    """Where to stand to reach `cell`: where Mimo will be if it reaches, else the nearest stand that does."""
    if math.dist(at, cell) <= REACH:
        return at
    reaching = [stand for stand in blueprint.stands if math.dist(stand, cell) <= REACH]
    return min(reaching, key=lambda stand: (math.dist(stand, at), stand)) if reaching else None


def planks_first(inventory: dict, blocks: list[str]) -> list[dict]:
    """Craft steps turning logs into the planks `blocks` use beyond the planks carried."""
    short = sum(1 for block in blocks if block == "planks") - inventory.get("planks", 0)
    crafts = min(math.ceil(max(0, short) / 4), inventory.get("oak_log", 0))
    return [{"kind": "craft", "recipe": "planks"} for _ in range(crafts)]


def reach_all(blueprint: Blueprint, stand: Cell, jobs: list[tuple[Cell, dict]]) -> list[dict]:
    """Each job's step, walking to another stand inside first when its cell is out of reach."""
    steps, at = [], stand
    for cell, step in jobs:
        spot = stand_for(blueprint, at, cell)
        if spot is None:
            continue
        if spot != at:
            steps.append(whole_walk(spot))
            at = spot
        steps.append(step)
    return steps


def next_blocks(s: Situation, blueprint: Blueprint, inventory: dict) -> tuple[list[str], list[tuple[Cell, dict]]]:
    """The blocks the next cells in the design's order take from `inventory`'s supplies, and their
    place jobs."""
    have = supplies(inventory)
    jobs: list[tuple[Cell, dict]] = []
    blocks = []
    for planned in todo(s.grid, blueprint):
        block = pick_block(planned.block, have)
        if block is None or len(blocks) >= PLACES_PER_BATCH:
            break
        have[block] -= 1
        blocks.append(block)
        jobs.append((planned.cell, {"kind": "place", "target": list(planned.cell), "block": block}))
    return blocks, jobs


def structural_batch(s: Situation, blueprint: Blueprint, stand: Cell) -> list[dict]:
    """The next blocks in the design's order, making planks from logs when they run short, but
    only when Mimo has room to carry the planks: otherwise it places what it carries."""
    blocks, jobs = next_blocks(s, blueprint, s.inventory)
    crafting = planks_first(s.inventory, blocks)
    if not crafts_fit(s.inventory, crafting):
        blocks, jobs = next_blocks(s, blueprint, without_logs(s.inventory))
        crafting = []
    return crafting + reach_all(blueprint, stand, jobs)


def furnishing_batch(s: Situation, blueprint: Blueprint, stand: Cell) -> list[dict]:
    """Make and place the bed and the campfire Mimo can."""
    inventory, crafting, jobs = dict(s.inventory), [], []
    for planned in fittings_due(s, blueprint):
        if inventory.get(planned.block, 0) < 1:
            steps = made(inventory, planned.block)
            if steps is None:
                continue
            crafting.extend(steps)
        inventory[planned.block] -= 1
        jobs.append((planned.cell, {"kind": "place", "target": list(planned.cell), "block": planned.block}))
    return crafting + reach_all(blueprint, stand, jobs) if jobs else []


def build_batch(s: Situation, blueprint: Blueprint) -> list[dict]:
    """Clear a blocked door or way in (from outside when Mimo is out), walk inside if Mimo is not
    there, then place the next blocks, or furnish the shelter once it is built."""
    clear = reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)}]) for cell in blocked(s.grid, blueprint)])
    walk: list[dict] = []
    stand = s.here
    if stand not in blueprint.stands:
        stand = blueprint.stands[0]
        walk = [whole_walk(stand)]
    if todo(s.grid, blueprint):
        work = structural_batch(s, blueprint, stand)
    else:
        work = furnishing_batch(s, blueprint, stand)
    return clear + walk + work if clear or work else []


def plan_shelter(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= SHELTER_BATCHES or s.db is None:
        return []
    structure = current_shelter(s)
    if structure is not None:
        return build_batch(s, blueprint_of(structure))
    design = None if shelter_elsewhere(s) else shelter_design(s)
    if design is None or carried_blocks(s) < START_SHARE * bill(design, s.grid):
        return []
    start(s.db, s.grid, design, s.at)
    return build_batch(s, design)


register(Purpose(
    "build_shelter", "build a shelter",
    "Build a shelter of its own near home, block by block, and furnish it with a bed and a campfire.",
    valid=shelter_valid, facts=shelter_facts, score=shelter_score, plan=plan_shelter,
    thoughts=("A roof of my own would be so cozy.", "One block at a time, a home.")))


def building_need(s: Situation) -> int:
    """Blocks the shelter Mimo started still needs beyond what it carries (0 with none started):
    while it waits for them, gather_wood and gather_stone aim that much higher (backend.survival.work)."""
    structure = current_shelter(s)
    if structure is None:
        return 0
    return max(0, len(todo(s.grid, blueprint_of(structure))) - carried_blocks(s))


# What finished steps teach ---------------------------------------------------------------------

def finish_if_built(state: dict, context, number: int, at: float) -> None:
    """Mark a structure done once nothing is left to place or till; a finished shelter becomes home."""
    structure = next((found for found in structures(context.db) if found["id"] == number), None)
    if structure is None or structure["status"] != "building":
        return
    blueprint = blueprint_of(structure)
    parts = ("plot",) if structure["kind"] == "farm" else ("floor", "wall", "roof")
    if todo(context.grid, blueprint, parts):
        return
    finish_structure(context.db, number, at)
    name = state["name"]
    if structure["kind"] == "shelter":
        set_home(context.db, blueprint.anchor, at)
        text = f"{name} finished building {structure['name']} and moved in."
        state["last_thought"] = "I built this myself. Home sweet home."
    else:
        text = f"{name} laid out {structure['name']}."
    context.events.append((at, "built", text))
    state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + BUILT_MOOD)
    mark_trigger(state, "built", at)


def note_building(state: dict, step: dict, context, at: float) -> None:
    """What a finished step teaches (see the module docstring)."""
    db = context.db
    if db is None:
        return
    if state.get("full_at") == at:
        mark_trigger(state, "full", at)
    kind = step["kind"]
    if kind == "plant" and step.get("item") == "sapling":
        remember(db, "tree", as_cell(step["target"]), at)
    elif kind in ("place", "till"):
        cell = as_cell(step["target"])
        number = structure_at(db, cell)
        if number is not None:
            finish_if_built(state, context, number, at)
        if kind == "place" and step.get("block") == "torch":
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + TORCH_MOOD)


def building_payload(s: Situation) -> dict:
    """What a model is told about building: home, what Mimo built and what it could build now."""
    home = nearest(s.places, s.here, ("home",), HOME_RANGE)
    built = [{"kind": found["kind"], "name": found["name"], "status": found["status"]}
             for found in structures_near(s, "shelter") + structures_near(s, "farm")]
    return {"home": None if home is None else (home["note"] or "found"), "built": built,
            "shelter": shelter_facts(s), "blocks_short": building_need(s)}

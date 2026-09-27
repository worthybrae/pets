"""Loot put to use (L5, "Frontier"): the warding lantern and amber-studded armor.

- The warding lantern: a lantern and 4 gloom dust (what gloomlings drop), anywhere. It is a block
  (shared/blocks.json, the last one) that gives light 15 like a lantern (light.BLOCK_LIGHT), and no
  hostile steps within WARD_REACH (6) blocks of one: a step that would bring a hostile that close,
  and closer than it is, is barred (acts.BARRIERS, used by wandering and chasing). Its light already
  keeps hostiles from coming out near it. Mimo keeps the cells of the ones it hung in its state
  (state["wards"], noted after each place or mine step: steps.OBSERVERS), so a creature's step never
  has to look for them. craft_tools makes up to WARDS_WANTED once Mimo carries 4 gloom dust and a
  lantern, or the iron and a torch for one (toolmaking.MORE_ORDERS); build_storage keeps 4 gloom dust
  on Mimo for it (storage.KEEP). The
  ward_home purpose hangs one on a corner of home (a torch corner, taking the torch or lantern that
  is there back into Mimo's arms; structures.STANDS_IN), so the yard stays clear: by day or in the
  evening, near home, while Mimo carries one and fewer than WARDS_WANTED hang there. Work band, 62;
  carrying one is an urge (goals.URGES), so it goes up whatever the goal.
- Amber-studded armor: an amber cap (2 iron ingots and 2 amber) and an amber tunic (3 iron ingots and
  3 amber), at a crafting table, a step past iron: they take 24 % and 36 % off a blow (60 % together;
  harm.ARMOR, harm.SLOTS). craft_tools makes a piece once Mimo wears iron on that slot and carries the
  amber (toolmaking.MORE_ORDERS). The iron piece stays with Mimo: only the best piece on a slot counts.
All of it registers into the registries of the modules it touches.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.survival import carrying, storage
from backend.survival.creatures.acts import BARRIERS, Scene
from backend.survival.creatures.harm import ARMOR, SLOTS
from backend.survival.creatures.kinds import Kind
from backend.survival.foraging import reach_steps
from backend.survival.goals import URGES
from backend.survival.grid import Cell
from backend.survival.journal import Lesson, teach
from backend.survival.light import BLOCK_LIGHT
from backend.survival.lighting import home_blueprint
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import STANDS_IN
from backend.survival.steps import OBSERVERS, as_cell
from backend.survival.toolmaking import MORE_ORDERS, STATIONS

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WARD = "warding_lantern"
WARD_REACH = 6.0
WARD_LIGHT = 15
WARD_DUST = 4  # gloom dust a warding lantern takes
WARDS_WANTED = 2
AMBER_PIECES = {"amber_tunic": ("iron_tunic", 3), "amber_cap": ("iron_cap", 2)}  # piece: (iron it tops, amber)
AMBER_CUTS = {"amber_cap": 0.24, "amber_tunic": 0.36}
LIGHTS = ("torch", "lantern")  # what a ward takes the place of on a home corner

BLOCK_LIGHT[WARD] = WARD_LIGHT
ARMOR.update(AMBER_CUTS)
SLOTS.update({"amber_cap": "head", "amber_tunic": "body"})
STATIONS.update({WARD: (), "amber_cap": ("crafting_table",), "amber_tunic": ("crafting_table",)})
STANDS_IN["torch"] = (*STANDS_IN["torch"], WARD)
storage.KEEP["gloom_dust"] = WARD_DUST
carrying.TREASURES += (WARD, "amber_cap", "amber_tunic")
# Pre-flight (carry 6): what the owner can teach of the new loot (Mind's lessons.py makes the amber pieces'
# own recipe lessons, as armor); written from the recipes, so they are true.
teach(Lesson("recipe:warding_lantern", "recipe", "a warding lantern", "A warding lantern takes a lantern and four gloom dust."),
      Lesson("recipe:gold_nuggets", "recipe", "gold nuggets", "Four gold nuggets make a gold ingot."))


# Hostiles keep away ----------------------------------------------------------------------------

def note_wards(state: dict, step: dict, context, at: float) -> None:
    """Keep state["wards"], the cells of the warding lanterns Mimo hung, after a place or mine step."""
    if step["kind"] not in ("place", "mine") or step.get("block") != WARD:
        return
    cell = list(as_cell(step["target"]))
    wards = [ward for ward in state.get("wards", []) if ward != cell]
    state["wards"] = wards + [cell] if step["kind"] == "place" else wards


def warded(scene: Scene, kind: Kind, cell: Cell, step: Cell) -> bool:
    """A hostile may not step within WARD_REACH of a warding lantern, closer than it stands now."""
    if not kind.hostile:
        return False
    for ward in scene.state.get("wards", ()):
        if math.dist(step, ward) <= WARD_REACH and math.dist(step, ward) < math.dist(cell, ward):
            return True
    return False


BARRIERS.append(warded)
OBSERVERS.append(note_wards)


# What craft_tools makes ------------------------------------------------------------------------

def wards_at_home(s: Situation) -> int:
    blueprint = home_blueprint(s)
    if blueprint is None:
        return 0
    return sum(1 for planned in blueprint.parts("torch") if s.grid.material(*planned.cell) == WARD)


def frontier_orders(inventory: dict) -> list[tuple[str, ...]]:
    """Amber armor on a slot Mimo wears iron on, with the amber carried; then a warding lantern."""
    orders = []
    for piece, (iron, amber) in AMBER_PIECES.items():
        if inventory.get(piece, 0) < 1 and inventory.get(iron, 0) > 0 and inventory.get("amber", 0) >= amber:
            orders.append((piece,))
    if inventory.get("gloom_dust", 0) >= WARD_DUST and inventory.get(WARD, 0) < WARDS_WANTED:
        orders.append((WARD,))
    return orders


MORE_ORDERS.append(frontier_orders)


# ward_home -------------------------------------------------------------------------------------

def ward_corners(s: Situation) -> list[Cell]:
    """Home's torch corners holding a torch or lantern a ward could take the place of, while fewer than
    WARDS_WANTED wards hang there."""
    blueprint = home_blueprint(s)
    if blueprint is None or wards_at_home(s) >= WARDS_WANTED:
        return []
    return [planned.cell for planned in blueprint.parts("torch") if s.grid.material(*planned.cell) in LIGHTS]


def ward_valid(s: Situation) -> bool:
    return not s.night and s.count(WARD) > 0 and bool(ward_corners(s))


def plan_ward(s: Situation, context: ActionContext) -> list[dict]:
    corners = ward_corners(s)
    if not corners or s.brain["batches"] > 0 or s.count(WARD) < 1:
        return []
    cell = corners[0]
    return reach_steps(s, [(cell, [{"kind": "mine", "target": list(cell)},
                                   {"kind": "place", "target": list(cell), "block": WARD}])])


register(Purpose(
    "ward_home", "hang a warding lantern",
    "Hang a warding lantern on a corner of home: its light and its gloom keep hostiles six blocks away.",
    valid=ward_valid,
    facts=lambda s: f"carrying {s.count(WARD)} warding lanterns, {wards_at_home(s)} hanging at home",
    score=lambda s: 62.0, plan=plan_ward,
    thoughts=("Let them keep their distance tonight.", "This glow will keep the yard clear.")))

URGES["ward_home"] = lambda s: s.count(WARD) > 0

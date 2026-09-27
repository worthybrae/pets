"""Loot put to use (L5, "Frontier"): the warding lantern and amber-studded armor.

- The warding lantern: a lantern and 2 gloom dust (what gloomlings drop), anywhere. It is a block
  (shared/blocks.json, the last one) that gives light 15 like a lantern (light.BLOCK_LIGHT), and no
  hostile steps within WARD_REACH (6) blocks of one: a step that would bring a hostile that close,
  and closer than it is, is barred (acts.BARRIERS, used by wandering and chasing). Its light already
  keeps hostiles from coming out near it. Mimo keeps the cells of the ones it hung in its state
  (state["wards"], noted after each place or mine step: steps.OBSERVERS), so a creature's step never
  has to look for them. craft_tools makes up to WARDS_WANTED once Mimo carries 2 gloom dust and a
  lantern, or the iron and a torch for one (toolmaking.MORE_ORDERS; the L5 final fix wave, M2: it took 4,
  and no pet on the final review's gate ever made one). Gloom dust waits in the chest until a warding
  lantern can be made, then 2 come back out (`loot_plan`). The
  ward_home purpose hangs one on a corner of home (a torch corner, taking the torch or lantern that
  is there back into Mimo's arms; structures.STANDS_IN), so the yard stays clear: by day or in the
  evening, near home, while Mimo carries one and fewer than WARDS_WANTED hang there. Work band, 62;
  carrying one is an urge (goals.add_urge), so it goes up whatever the goal.
- Amber-studded armor: an amber cap (2 iron ingots and 2 amber) and an amber tunic (3 iron ingots and
  3 amber), at a crafting table, a step past iron: they take 24 % and 36 % off a blow (60 % together;
  harm.ARMOR, harm.SLOTS). craft_tools makes a piece once Mimo wears iron on that slot and carries the
  amber (toolmaking.MORE_ORDERS); the plan brings a furnace when the iron is smelted from ore (toolmaking
  .tool_steps). The L5 final fix wave (I3): once the amber piece is made the iron piece is no use to carry
  (storage.JUNK_MORE), and an amber piece stands for its iron one wherever that is asked for (harm.worn),
  so no order asks for it again.
- What storage does with the loot (the L5 final fix wave, I3; `loot_plan`): amber, gold nuggets, diamonds
  and gloom dust go in the chest like other goods but for what a craft in reach takes, and come back out
  for it (storage.KEEPS_MORE and storage.WANTED_ON_HAND). On the final review's gate they were never put
  away, and every pet that stalled on the way to its computer carried them.
All of it registers into the registries of the modules it touches.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from backend.services.crafting import RECIPES, TOOL_RANK
from backend.survival import carrying, storage
from backend.survival.creatures.acts import BARRIERS, Scene
from backend.survival.creatures.harm import ARMOR, SLOTS
from backend.survival.creatures.kinds import Kind
from backend.survival.foraging import reach_steps
from backend.survival.goals import add_urge
from backend.survival.grid import Cell
from backend.survival.journal import Lesson, teach
from backend.survival.light import BLOCK_LIGHT
from backend.survival.lighting import home_blueprint
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import STANDS_IN
from backend.survival.steps import OBSERVERS, as_cell
from backend.survival.toolmaking import MORE_ORDERS, STATIONS
from backend.survival.work import ladder_ores, pickaxe_rank

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WARD = "warding_lantern"
WARD_REACH = 6.0
WARD_LIGHT = 15
WARD_DUST = 2  # gloom dust a warding lantern takes (the L5 final fix wave, M2: it was 4, and none was ever made)
WARDS_WANTED = 2
AMBER_PIECES = {"amber_tunic": ("iron_tunic", 3), "amber_cap": ("iron_cap", 2)}  # piece: (iron it tops, amber)
AMBER_CUTS = {"amber_cap": 0.24, "amber_tunic": 0.36}
LIGHTS = ("torch", "lantern")  # what a ward takes the place of on a home corner

BLOCK_LIGHT[WARD] = WARD_LIGHT
ARMOR.update(AMBER_CUTS)
SLOTS.update({"amber_cap": "head", "amber_tunic": "body"})
STATIONS.update({WARD: (), "amber_cap": ("crafting_table",), "amber_tunic": ("crafting_table",)})
STANDS_IN["torch"] = (*STANDS_IN["torch"], WARD)
carrying.TREASURES += (WARD, "amber_cap", "amber_tunic")
# Pre-flight (carry 6): what the owner can teach of the new loot (Mind's lessons.py makes the amber pieces'
# own recipe lessons, as armor); written from the recipes, so they are true.
teach(Lesson("recipe:warding_lantern", "recipe", "a warding lantern", "A warding lantern takes a lantern and two gloom dust."),
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


# What goes in the chest, and what comes back out (the L5 final fix wave, I3) ---------------------------------

LOOT_KEPT = ("amber", "gold_nugget", "diamond", "gloom_dust")  # put away but for what a craft in reach takes
storage.KEEP.update({item: 0 for item in LOOT_KEPT})
NUGGETS_PER_INGOT = RECIPES["gold_nuggets"]["ingredients"]["gold_nugget"]
GOLD_PICKAXE_INGOTS = RECIPES["gold_pickaxe"]["ingredients"]["gold_ingot"]


def loot_plan(s: Situation) -> tuple[dict[str, int], dict[str, int]]:
    """(kept, wanted): what of LOOT_KEPT Mimo keeps on hand (storage.KEEPS_MORE) and what it wants on hand
    (storage.WANTED_ON_HAND: what its chests hold of it comes back out), from what its arms and chests hold
    together; read once per Situation. On the final review's gate amber, gold nuggets and diamonds were never
    put away (they had no KEEP), and every pet that stalled on the way to its computer carried them:
    - amber: what the amber pieces take on the slots Mimo wears iron on without one, once there is amber
      enough for a piece and the iron ingots (or ore) it takes, which come out of the chest with it;
    - gloom dust: WARD_DUST for a warding lantern while fewer than WARDS_WANTED are carried or hung, once
      there is that much and a lantern (or a torch and iron) in hand;
    - gold nuggets: while the pickaxe ladder counts gold (work.ladder_ores), what makes up the gold pickaxe's
      ingots, once there are nuggets enough for them;
    - diamonds: what the next diamond tool takes (the pickaxe over an iron one, then the sword), kept on hand
      however few (life_goals' diamond goal counts the ones carried), wanted back once there are enough.
    Everything else of them waits in the chest."""
    def look() -> tuple[dict[str, int], dict[str, int]]:
        inventory, stored = s.inventory, storage.in_chests(s)

        def have(*items: str) -> int:
            return sum(inventory.get(item, 0) + stored.get(item, 0) for item in items)

        kept: dict[str, int] = {}
        wanted: dict[str, int] = {}
        amber = iron = 0
        for piece, (under, count) in AMBER_PIECES.items():
            ingots = RECIPES[piece]["ingredients"]["iron_ingot"]
            if (inventory.get(piece, 0) < 1 and inventory.get(under, 0) > 0 and have("amber") >= amber + count
                    and have("iron_ingot", "iron_ore") >= iron + ingots):
                amber, iron = amber + count, iron + ingots
        if amber:
            kept["amber"] = wanted["amber"] = amber
            ingots = min(iron, have("iron_ingot"))
            wanted.update({item: count for item, count in (("iron_ingot", ingots), ("iron_ore", iron - ingots)) if count})
        wards = inventory.get(WARD, 0) + len(s.state.get("wards", []))
        lit = inventory.get("lantern", 0) > 0 or (inventory.get("torch", 0) > 0 and have("iron_ingot", "iron_ore") > 0)
        if wards < WARDS_WANTED and lit and have("gloom_dust") >= WARD_DUST:
            kept["gloom_dust"] = wanted["gloom_dust"] = WARD_DUST
        if ladder_ores(inventory):
            short = max(0, GOLD_PICKAXE_INGOTS - have("gold_ingot", "gold_ore"))
            if short and have("gold_nugget") >= short * NUGGETS_PER_INGOT:
                kept["gold_nugget"] = wanted["gold_nugget"] = short * NUGGETS_PER_INGOT
        rank = pickaxe_rank(inventory)
        tool = "diamond_pickaxe" if TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["diamond_pickaxe"] else \
            "diamond_sword" if rank >= TOOL_RANK["diamond_pickaxe"] and inventory.get("diamond_sword", 0) < 1 else None
        if tool is not None:
            kept["diamond"] = RECIPES[tool]["ingredients"]["diamond"]
            if have("diamond") >= kept["diamond"]:
                wanted["diamond"] = kept["diamond"]
        return kept, wanted
    return s.sensed("frontier loot kept", look)


def loot_kept(s: Situation, item: str) -> float:
    """storage.KEEPS_MORE: what of an item in LOOT_KEPT a craft in reach takes (`loot_plan`)."""
    return float(loot_plan(s)[0].get(item, 0)) if item in LOOT_KEPT else 0.0


def loot_wanted(s: Situation) -> dict[str, int]:
    """storage.WANTED_ON_HAND: the loot (and the iron for an amber piece) a craft in reach takes (`loot_plan`)."""
    return dict(loot_plan(s)[1])


def replaced_pieces(s: Situation) -> list[tuple[str, int]]:
    """storage.JUNK_MORE: the iron piece an amber piece replaced (harm.worn lets the amber stand for it, so no
    order asks for it again), and a leather piece under an amber one that storage.junk does not list already (it
    lists leather under iron). On the final review's gate an iron cap stayed in the arms of both pets that made
    an amber cap."""
    found = []
    for piece, (under, _) in AMBER_PIECES.items():
        if s.count(piece) < 1:
            continue
        leather = under.replace("iron", "leather")
        if s.count(under):
            found.append((under, s.count(under)))
        elif s.count(leather):
            found.append((leather, s.count(leather)))
    return found


storage.KEEPS_MORE.append(loot_kept)
storage.WANTED_ON_HAND.append(loot_wanted)
storage.JUNK_MORE.append(replaced_pieces)


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

add_urge("ward_home", lambda s: s.count(WARD) > 0)  # the L5 final fix wave, M3: added to, never replaced

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
from backend.services.worldgen import WORLD_MAX_Y
from backend.survival import carrying, storage
from backend.survival.carrying import STACK
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
from backend.survival.toolmaking import MORE_ORDERS, STATIONS, chain_steps
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

LOOT_KEPT = ("amber", "gold_nugget", "diamond", "gloom_dust", "arrow")  # put away but for what a craft in reach takes
storage.KEEP.update({item: 0 for item in LOOT_KEPT})
NUGGETS_PER_INGOT = RECIPES["gold_nuggets"]["ingredients"]["gold_nugget"]
GOLD_PICKAXE_INGOTS = RECIPES["gold_pickaxe"]["ingredients"]["gold_ingot"]
ANYWHERE = (((0, WORLD_MAX_Y, 0), False), ((1, WORLD_MAX_Y, 0), False))  # stand-in station spots for `makeable`


def makeable(inventory: dict, item: str) -> bool:
    """craft_tools could make `item` from `inventory` wherever there is room for its stations: the chain its
    recipe takes, the stations carried or made (a furnace when it smelts), and room in Mimo's arms for every
    step of it (toolmaking.chain_steps)."""
    return chain_steps(inventory, (item,), set(), list(ANYWHERE)) is not None


def loot_plan(s: Situation) -> tuple[dict[str, int], dict[str, int]]:
    """(kept, wanted): what of LOOT_KEPT Mimo keeps on hand (storage.KEEPS_MORE) and what it wants on hand
    (storage.WANTED_ON_HAND: what its chests hold of it comes back out), read once per Situation. The rule: the
    frontier's loot stays on hand only for a craft Mimo could make with it now, the loot its chests hold added
    to its arms (`makeable`); everything else of it waits in the chest. On the final review's gate amber, gold
    nuggets and diamonds were never put away (they had no KEEP), and every pet that stalled on the way to its
    computer carried them; a first version of this fix kept them for any craft they were short of, and a pet
    stood 58 game days at full arms with 3 amber for a tunic it had no furnace for, and 2 diamonds for a sword
    it had no room to make.
    - amber: an amber piece on a slot Mimo wears iron on, with the iron ingots (or ore) it takes, which come out
      of the chest with it;
    - gloom dust: WARD_DUST for a warding lantern while fewer than WARDS_WANTED are carried or hung, with the
      iron its lantern takes when Mimo carries no lantern;
    - gold nuggets: while the pickaxe ladder counts gold (work.ladder_ores), what makes up the gold pickaxe;
    - diamonds: the next diamond tool, the sword once the pickaxe is made. Toward the diamond pickaxe (over an
      iron one) they stay on hand however few, since the diamond goal counts the ones carried
      (life_goals.better_tools), as the ladder's gold does (work.ladder_ores);
    - arrows: all of them while Mimo carries a bow (old chests hold arrows, and a pet with no bow carried a
      stack of them for good)."""
    def look() -> tuple[dict[str, int], dict[str, int]]:
        inventory, stored = s.inventory, storage.in_chests(s)

        def have(*items: str) -> int:
            return sum(inventory.get(item, 0) + stored.get(item, 0) for item in items)

        def with_stored(**wanted: int) -> dict[str, int]:
            """Mimo's arms with what its chests hold of `wanted` added, up to that many of each."""
            trial = dict(inventory)
            for item, count in wanted.items():
                trial[item] = max(inventory.get(item, 0), min(count, have(item)))
            return trial

        kept: dict[str, int] = {}
        wanted: dict[str, int] = {}
        for piece, (under, count) in AMBER_PIECES.items():
            ingots = RECIPES[piece]["ingredients"]["iron_ingot"]
            if inventory.get(piece, 0) > 0 or inventory.get(under, 0) < 1 or have("amber") < count:
                continue
            ore = max(0, ingots - have("iron_ingot"))
            if makeable(with_stored(amber=count, iron_ingot=ingots, iron_ore=ore), piece):
                kept["amber"] = wanted["amber"] = count
                wanted.update({item: n for item, n in (("iron_ingot", min(ingots, have("iron_ingot"))),
                                                         ("iron_ore", ore)) if n})
                break
        wards = inventory.get(WARD, 0) + len(s.state.get("wards", []))
        if wards < WARDS_WANTED and have("gloom_dust") >= WARD_DUST:
            iron = {} if inventory.get("lantern", 0) > 0 or inventory.get("iron_ingot", 0) > 0 else \
                {"iron_ingot": 1} if have("iron_ingot") else {"iron_ore": 1} if have("iron_ore") else {}
            if makeable(with_stored(gloom_dust=WARD_DUST, **iron), WARD):  # its lantern's iron comes out too
                kept["gloom_dust"] = wanted["gloom_dust"] = WARD_DUST
                for item, count in iron.items():
                    wanted[item] = wanted.get(item, 0) + count
        short = max(0, GOLD_PICKAXE_INGOTS - have("gold_ingot", "gold_ore"))
        nuggets = short * NUGGETS_PER_INGOT
        if (ladder_ores(inventory) and short and have("gold_nugget") >= nuggets
                and makeable(with_stored(gold_nugget=nuggets, gold_ingot=GOLD_PICKAXE_INGOTS, gold_ore=GOLD_PICKAXE_INGOTS),
                             "gold_pickaxe")):
            kept["gold_nugget"] = wanted["gold_nugget"] = nuggets
        rank = pickaxe_rank(inventory)
        if TOOL_RANK["iron_pickaxe"] <= rank < TOOL_RANK["diamond_pickaxe"]:
            need = RECIPES["diamond_pickaxe"]["ingredients"]["diamond"]
            kept["diamond"] = need
            if have("diamond") >= need and makeable(with_stored(diamond=need), "diamond_pickaxe"):
                wanted["diamond"] = need
        elif rank >= TOOL_RANK["diamond_pickaxe"] and inventory.get("diamond_sword", 0) < 1:
            need = RECIPES["diamond_sword"]["ingredients"]["diamond"]
            if have("diamond") >= need and makeable(with_stored(diamond=need), "diamond_sword"):
                kept["diamond"] = wanted["diamond"] = need
        if inventory.get("bow", 0) > 0 and have("arrow"):
            kept["arrow"] = wanted["arrow"] = min(STACK, have("arrow"))
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

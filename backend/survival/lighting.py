"""light_up: torches and lanterns around home for the night.

From 5 game minutes before dusk until nightfall, at the shelter it built, Mimo puts a light on
each outside corner the design marked (up to four) that is still dark: a lantern it carries first
(L3: an iron ingot and a torch, light 15), then torches, making torches from coal and sticks (1
coal and 1 stick make 4) when it carries none. A lantern left over takes the place of a torch on a
corner that has one (the torch is mined and goes back in Mimo's arms), so light_up is also
offered to swap them. Lights glow at night in the viewer and each one lifts Mimo's mood a little
(building.note_building); their light (a torch 14, a lantern 15, one less a block) keeps hostile
creatures from spawning around home (L2, backend.survival.light). A mushroom or sapling on a
corner is mined first (structures.clearing). The walks to the corners go all the way or not at
all, and head_home leaves light_up alone, since it keeps Mimo at home. Its facts tell the chooser
how many corners are dark, what lights Mimo carries and (L3 final fix wave) how many torch corners
a spare lantern can take.

W2 (the controller's ruling on W2's final review): relight_fire. The rain puts out the campfire the home's design
puts by its door (backend.survival.rain), and it stood for the door's campfire still (structures.STANDS_IN), so
nothing lit it again: every home's fire was out from its first rain. Once it no longer rains, Mimo at home (as
light_up, within HOME_REACH) with a stick walks to it and relights it (rain's `relight` step), at RELIGHT_SCORE. A
wild pet does so once it knows fire, as it puts a campfire down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.survival import sky
from backend.survival.carrying import crafts_fit
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.grid import Cell
from backend.survival.life_goals import home_structure
from backend.survival.purposes import LATE_DAY, Purpose, register
from backend.survival.rain import DOUSED_BLOCK
from backend.survival.situation import NIGHTFALL, Situation
from backend.survival.structures import blueprint_of, clearing, todo
from backend.survival.toolmaking import Short, make
from backend.survival.wild import unlocked

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

HOME_REACH = 16.0  # light_up is offered this close to the shelter
RELIGHT_SCORE = 72.0  # W2: as light_up


def home_blueprint(s: Situation):
    """The design of the shelter Mimo lives in, when Mimo stands near it, or None (fix round 1:
    home, not `current_shelter`'s newest shelter, which is a second one still rising while a
    bigger home is under way)."""
    structure = home_structure(s)
    if structure is None or structure["status"] != "done":
        return None
    blueprint = blueprint_of(structure)
    return None if s.distance(blueprint.anchor) > HOME_REACH else blueprint


def dark_corners(s: Situation) -> list[Cell]:
    """The shelter's torch cells without a torch or lantern that one can stand in now (open, on solid ground)."""
    blueprint = home_blueprint(s)
    if blueprint is None:
        return []
    return [planned.cell for planned in todo(s.grid, blueprint, ("torch",))
            if s.grid.standable(planned.cell)]


def torch_corners(s: Situation) -> list[Cell]:
    """The shelter's corners that hold a torch: a carried lantern lights them better (L3)."""
    blueprint = home_blueprint(s)
    if blueprint is None:
        return []
    return [planned.cell for planned in blueprint.parts("torch") if s.grid.material(*planned.cell) == "torch"]


def evening(s: Situation) -> bool:
    return not s.night and LATE_DAY <= s.clock["seconds_into_day"] < NIGHTFALL


def torch_supply(s: Situation, wanted: int) -> tuple[list[dict], int]:
    """Craft steps making torches (4 at a time) until Mimo has `wanted`, or as many as it can with
    room to carry them (carrying.crafts_fit), and how many it will then carry."""
    inventory, steps = dict(s.inventory), []
    while inventory.get("torch", 0) < wanted:
        trial, more = dict(inventory), []
        try:
            make(trial, "torch", inventory.get("torch", 0) + 1, more)
        except Short:
            break
        if not crafts_fit(s.inventory, steps + more):
            break
        inventory, steps = trial, steps + more
    return steps, inventory.get("torch", 0)


def light_valid(s: Situation) -> bool:
    if not evening(s):
        return False
    lanterns = s.count("lantern")
    return (bool(dark_corners(s)) and (lanterns > 0 or torch_supply(s, 1)[1] > 0)) or (lanterns > 0 and bool(torch_corners(s)))


def swaps(s: Situation) -> int:
    """Torch corners a carried lantern can take: those left over once the dark corners have one."""
    return min(max(0, s.count("lantern") - len(dark_corners(s))), len(torch_corners(s)))


def plural(count: int, word: str) -> str:
    """`count` and `word`, `word` pluralised (an "es" for one ending in ch, sh, s, x or z, an s for
    any other, none for 1): "1 torch", "3 torches", "2 lanterns", "1 torch corner"."""
    if count == 1:
        return f"{count} {word}"
    return f"{count} {word}{'es' if word.endswith(('ch', 'sh', 's', 'x', 'z')) else 's'}"


def light_facts(s: Situation) -> str:
    """Dark corners and torches carried, and (L3 final fix wave) with lanterns carried, how many
    and how many torch corners a spare one can take."""
    facts = f"{len(dark_corners(s))} dark corners around home, carrying {plural(s.count('torch'), 'torch')}"
    lanterns = s.count("lantern")
    if lanterns:
        facts += f" and {plural(lanterns, 'lantern')}; {plural(swaps(s), 'torch corner')} a spare lantern can take"
    return facts


def plan_light(s: Situation, context: ActionContext) -> list[dict]:
    if not evening(s) or s.brain["batches"] > 0:
        return []
    corners, lanterns = dark_corners(s), s.count("lantern")
    crafting, have = torch_supply(s, max(0, len(corners) - lanterns))
    lights = ["lantern"] * min(lanterns, len(corners)) + ["torch"] * have
    jobs = [(cell, [*clearing(s.grid, cell), {"kind": "place", "target": list(cell), "block": block}])
            for cell, block in zip(corners, lights)]
    # L3: carried lanterns left over take the place of torches (the torch goes back in Mimo's arms).
    spare = lanterns - lights.count("lantern")
    jobs += [(cell, [{"kind": "mine", "target": list(cell)}, {"kind": "place", "target": list(cell), "block": "lantern"}])
             for cell in torch_corners(s)[:spare]]
    if not jobs:
        return []
    home = blueprint_of(home_structure(s)).anchor
    return crafting + reach_steps(s, jobs) + [whole_walk(home)]  # and back inside for the night


register(Purpose(
    "light_up", "light torches", "Put torches around home before night; they glow in the dark.",
    valid=light_valid,
    facts=light_facts,
    score=lambda s: 72.0, plan=plan_light,
    thoughts=("A little light for the night.", "Torches make home feel safe.")))


# relight_fire (W2) -------------------------------------------------------------------------------

def doused_home_fire(s: Situation) -> Cell | None:
    """The campfire by the home's door, when the rain put it out, it no longer rains and Mimo, at home, carries a
    stick to light it with (and, a wild pet, knows fire); None otherwise."""
    if sky.raining(s.state) or s.count("sticks") < 1 or not unlocked(s, "fire"):
        return None
    blueprint = home_blueprint(s)
    cell = None if blueprint is None else blueprint.one("campfire")
    return cell if cell is not None and s.grid.material(*cell) == DOUSED_BLOCK else None


def plan_relight(s: Situation, context: ActionContext) -> list[dict]:
    cell = doused_home_fire(s)
    return [] if cell is None else reach_steps(s, [(cell, [{"kind": "relight", "target": list(cell)}])])


register(Purpose(
    "relight_fire", "light the fire by the door again",
    "The rain put out the campfire by home's door; light it again with a stick now the rain has stopped.",
    valid=lambda s: doused_home_fire(s) is not None,
    facts=lambda s: f"the fire by the door is out; carrying {plural(s.count('sticks'), 'stick')}",
    score=lambda s: RELIGHT_SCORE, plan=plan_relight,
    thoughts=("The rain's stopped. Time to light the fire again.", "Home's fire should be burning.")))

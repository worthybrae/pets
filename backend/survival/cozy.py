"""A cozy home (Making, T1): glass in the windows, a bookshelf, a rug in its favourite colour, a flower
pot, a candle, a sign with its name, and a composter by the farm.

The spec: "Blueprints use the new blocks: windows, bookshelves ..."; "a home with bookshelves makes Mimo
content"; "Mimo decorates its home in its favourite colour, a trait". The touches go on the home Mimo
lives in (home.home_structure, finished), placed where its design leaves room (`touches`, worked out
from the home's own design: its size, its door side and its anchor):
- a glass pane in the window high in the middle of each side wall; a home built without windows gets
  them by taking that wall block out first (a pane is solid, so the wall stays whole);
- a bookshelf in the middle of the back wall, in place of its lower block;
- a rug of Mimo's favourite colour (making.favourite_colour) on each passage cell from the second in
  (the final fix wave's I4: the first, just inside the door, is the automatic door's pressure plate);
- a flower pot in the front right corner inside and a candle (light 12) in the front left;
- a sign outside by the door, on the side the campfire is not;
- a composter at the corner of the farm by home, when there is one: crops within COMPOST_REACH of a
  composter grow a quarter faster (backend.survival.renewal).

decorate_home ("make home cozy") is offered while the cozy home is Mimo's goal, by day, at a home it
built, near it, when it can make a touch now: it makes up to TOUCHES_PER_BATCH where it stands
(making.craft_plan; outside, where there is room for a table and a furnace), walks in and puts them
in, taking a wall block out first where a touch replaces one. Work band: 50 plus a tenth of
creativity. While the cozy home is the goal, its touches are what making wants (making.NEEDS), so
gather_materials brings the sugar cane, flowers, clay and sand, and Mimo hunts though fed while it
lacks the leather, wool or tallow a touch takes (hunting.HUNT_FOR). The Making final fix wave (I3): such
a hunt waits HIDE_HUNT_GAP after the last kill, as L4's hunt for hides does, and counts only while an
animal that drops what is missing is in sight (GOODS_FROM: sheep for wool and tallow, cows for leather),
which the hunt then goes after first (hunting.PREY_WANTED); only such a hunt works toward the cozy home
(goals.ADVANCES), so a hunt for food is no longer boosted and labelled as one. A candle is tallow and a
stick (the final fix wave's ruling: string only came from skitters). The flower pot waits while the
workshop still wants its kiln (`waiting`: both are fired from the rare clay, and the kiln is on the way to
the computer); what the touches will take is kept meanwhile (making.LATER).

Waking at dawn in a home with a bookshelf, Mimo is content: BOOKSHELF_MOOD more mood (`tend_comfort`,
from brain.notice_step).

The cozy home goal ("A cozy home", after a home of its own): the windows, the bookshelf, the rug, the
pot, candle and sign, and the composter (whole when there is no farm). Rules score 35 plus a fifth of
creativity.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from backend.services.blocks import is_replaceable
from backend.survival.blueprints import Blueprint, local_to_world
from backend.survival.creatures import hunting
from backend.survival.foraging import reach_steps
from backend.survival.goals import ADVANCES, Goal, Milestone, active, reached, register_goal
from backend.survival.grid import Cell
from backend.survival.home import by_home, home_structure
from backend.survival.life_goals import HIDE_HUNT_GAP
from backend.survival.making import (
    LATER, NEEDS, craft_plan, favourite_colour, in_chests, ingredients, needs, place_steps,
)
from backend.survival.once import log_once
from backend.survival.pens import near_home
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.structures import blueprint_of
from backend.survival.workshop import kiln_wanted

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

GOAL = "cozy_home"
TOUCHES_PER_BATCH = 4
DECORATE_BATCHES = 3
BOOKSHELF_MOOD = 5.0
ANIMAL_GOODS = ("leather", "wool", "tallow")
GOODS_FROM = {"leather": ("cow",), "wool": ("sheep",), "tallow": ("sheep",)}  # I3: who drops each


@dataclass(frozen=True)
class Touch:
    kind: str  # "window", "bookshelf", "rug", "pot", "candle", "sign", "composter"
    cell: Cell
    block: str
    inside: bool = True  # put in from inside the home
    replaces: bool = False  # a wall block comes out first


def frame(blueprint: Blueprint):
    """World cells of a shelter's local (i, j) and height y: i across the door side, j from the front
    wall (-1) to the back, as blueprints.local_to_world, the origin found from the anchor."""
    style = blueprint.style
    side, (width, depth) = style.get("door", "north"), tuple(style.get("size") or (3, 3))
    door, middle = (width - 1) // 2, (depth - 1) // 2
    ax, _, az = blueprint.anchor
    dx, dz = local_to_world(side, (0, 0), (width, depth), door, middle)
    origin = (ax - dx, az - dz)

    def world(i: int, j: int, y: int) -> Cell:
        x, z = local_to_world(side, origin, (width, depth), i, j)
        return x, y, z
    return world, width, depth, door, middle


def open_spot(s: Situation, cell: Cell) -> bool:
    x, y, z = cell
    material = s.grid.material(*cell)
    return material != "water" and is_replaceable(material) and s.grid.solid((x, y - 1, z)) and not s.grid.claimed(cell)


def touches(s: Situation) -> list[Touch]:
    """Every touch the home Mimo lives in takes (read once per Situation); [] without a finished home."""
    def look() -> list[Touch]:
        home = home_structure(s)
        if home is None or home["status"] != "done":
            return []
        blueprint = blueprint_of(home)
        world, width, depth, door, middle = frame(blueprint)
        floor = blueprint.anchor[1] - 1
        found = [Touch("window", world(i, middle, floor + 2), "glass_pane",
                       replaces=s.grid.solid(world(i, middle, floor + 2))) for i in (-1, width)]
        found.append(Touch("bookshelf", world(door, depth, floor + 1), "bookshelf", replaces=True))
        found += [Touch("rug", world(door, j, floor + 1), f"rug_{favourite_colour(s.state)}")
                  for j in range(1, middle + 1)]  # I4: the cell inside the door is the automatic door's plate
        found.append(Touch("pot", world(width - 1, 0, floor + 1), "flower_pot"))
        found.append(Touch("candle", world(0, 0, floor + 1), "candle"))
        for i in (door + 1, door - 1):
            spot = world(i, -2, floor + 1)
            if s.grid.material(*spot) == "sign" or open_spot(s, spot):
                found.append(Touch("sign", spot, "sign", inside=False))
                break
        farms = [farm for farm in by_home(s, "farm") if farm["status"] == "done"]
        if farms:
            plots = [planned.cell for planned in blueprint_of(farms[-1]).parts("plot")]
            corner = (min(x for x, _, _ in plots) - 1, plots[0][1] + 1, min(z for _, _, z in plots) - 1)
            if s.grid.material(*corner) == "composter" or open_spot(s, corner):
                found.append(Touch("composter", corner, "composter", inside=False))
        return found
    return s.sensed("cozy touches", look)


def touches_left(s: Situation) -> list[Touch]:
    return [touch for touch in touches(s) if s.grid.material(*touch.cell) != touch.block]


def cozying(s: Situation) -> bool:
    goal = active(s)
    return goal is not None and goal.name == GOAL


def waiting(s: Situation, touch: Touch) -> bool:
    """The Making final fix wave: the flower pot waits while the workshop still wants its kiln (workshop.
    kiln_wanted): both are fired from clay, which is rare (3 to 12 columns within 96 blocks of the gate's six
    homes), and the kiln is on the way to the computer."""
    return touch.kind == "pot" and kiln_wanted(s)


def touches_wanted(s: Situation) -> dict[str, int]:
    """The blocks of the touches still missing that can be made now (not `waiting`)."""
    wanted: dict[str, int] = {}
    for touch in touches_left(s):
        if not waiting(s, touch):
            wanted[touch.block] = wanted.get(touch.block, 0) + 1
    return wanted


def cozy_needs(s: Situation) -> dict[str, int]:
    """making.NEEDS: the touches still missing, while the cozy home is Mimo's goal."""
    return touches_wanted(s) if cozying(s) else {}


def cozy_later(s: Situation) -> dict[str, int]:
    """making.LATER: the same, while the cozy home is not Mimo's goal and not reached yet."""
    return {} if cozying(s) or GOAL in reached(s) else touches_wanted(s)


def goods_missing(s: Situation) -> list[str]:
    """The leather, wool or tallow the cozy home's touches take that Mimo neither carries nor keeps in a
    chest (build_storage takes that out)."""
    if not cozying(s):
        return []
    chain = ingredients(needs(s))
    return [item for item in ANIMAL_GOODS if item in chain and s.count(item) == 0 and not in_chests(s).get(item)]


def prey_for_goods(s: Situation) -> tuple[str, ...]:
    """hunting.PREY_WANTED (I3): the kinds that drop what the cozy home lacks."""
    return tuple(sorted({kind for item in goods_missing(s) for kind in GOODS_FROM[item]}))


def hunt_for_goods(s: Situation) -> bool:
    """hunting.HUNT_FOR: the cozy home wants leather, wool or tallow Mimo does not have, an animal that
    drops it is in sight, and (I3) Mimo killed nothing for HIDE_HUNT_GAP, as L4's hunt for hides waits."""
    kinds = prey_for_goods(s)
    if not kinds:
        return False
    hunted_at = s.state.get("hunted_at")
    if hunted_at is not None and (s.at - hunted_at) * s.scale < HIDE_HUNT_GAP:
        return False
    return any(creature["kind"] in kinds for creature in hunting.prey(s))


def hunt_advances(s: Situation, goal: Goal) -> bool:
    """goals.ADVANCES (I3): a hunt works toward the cozy home only as a hunt for its goods; toward any other
    goal whose milestone names it (armor's leather), as before."""
    return goal.name != GOAL or hunt_for_goods(s)


NEEDS.append(cozy_needs)
LATER.append(cozy_later)
hunting.HUNT_FOR.append(hunt_for_goods)
hunting.PREY_WANTED.append(prey_for_goods)
ADVANCES["hunt"] = hunt_advances


# decorate_home -----------------------------------------------------------------------------------

def chosen_touches(s: Situation) -> list[Touch]:
    """The next touches Mimo can make now, together, up to TOUCHES_PER_BATCH (read once per Situation)."""
    def look() -> list[Touch]:
        chosen: list[Touch] = []
        for touch in touches_left(s):
            if waiting(s, touch):
                continue
            trial: dict[str, int] = {}
            for block in [entry.block for entry in chosen] + [touch.block]:
                trial[block] = trial.get(block, 0) + 1
            if craft_plan(s, trial) is not None:
                chosen.append(touch)
            if len(chosen) >= TOUCHES_PER_BATCH:
                break
        return chosen
    return s.sensed("cozy chosen", look)


def decorate_valid(s: Situation) -> bool:
    return not s.night and cozying(s) and near_home(s) and bool(chosen_touches(s))


def job(touch: Touch) -> tuple[Cell, list[dict]]:
    out = [{"kind": "mine", "target": list(touch.cell)}] if touch.replaces else []
    return touch.cell, [*out, {"kind": "place", "target": list(touch.cell), "block": touch.block}]


def plan_decorate(s: Situation, context: ActionContext) -> list[dict]:
    if s.night or s.brain["batches"] >= DECORATE_BATCHES or not decorate_valid(s):
        return []
    chosen = chosen_touches(s)
    wanted: dict[str, int] = {}
    for touch in chosen:
        wanted[touch.block] = wanted.get(touch.block, 0) + 1
    steps = list(craft_plan(s, wanted) or [])
    stands = blueprint_of(home_structure(s)).stands
    steps += place_steps(s, stands, [job(touch) for touch in chosen if touch.inside])
    outside = [job(touch) for touch in chosen if not touch.inside]
    if outside:
        steps += reach_steps(s, outside) if not steps else _from_last(steps, s, outside)
    return steps


def _from_last(steps: list[dict], s: Situation, jobs: list[tuple[Cell, list[dict]]]) -> list[dict]:
    """reach_steps for `jobs` from where the steps before leave Mimo (the last walk's end)."""
    walks = [step for step in steps if step["kind"] == "walk"]
    here = tuple(walks[-1]["target"]) if walks else s.here
    return reach_steps(replace(s, state={**s.state, "position": dict(zip("xyz", map(float, here)))}, memo={}), jobs)


def decorate_facts(s: Situation) -> str:
    left = [touch.block.replace("_", " ") for touch in touches_left(s)]
    return f"home still wants {', '.join(left)}; can make {len(chosen_touches(s))} of them now"


register(Purpose(
    "decorate_home", "make home cozy",
    "Put glass in the windows, a bookshelf, a rug, a flower pot, a candle and a sign in and by its home.",
    valid=decorate_valid, facts=decorate_facts, score=lambda s: 50.0 + s.trait("creativity") / 10,
    plan=plan_decorate,
    thoughts=("A few touches and home will be so cozy.", "A rug in my favourite colour!")))


# Content at home ---------------------------------------------------------------------------------

def tend_comfort(state: dict, context, at: float, phase: str | None) -> None:
    """At dawn, in a home with a bookshelf, Mimo is content: BOOKSHELF_MOOD more mood. A crash is logged
    once and the tick goes on."""
    if phase != "dawn" or context.db is None:
        return
    try:
        from backend.survival.situation import in_tick

        s = in_tick(state, context, at)
        home = home_structure(s)
        shelf = next((touch for touch in touches(s) if touch.kind == "bookshelf"), None)
        if home is None or shelf is None or s.grid.material(*shelf.cell) != "bookshelf":
            return
        if s.distance(blueprint_of(home).anchor) <= 4.0:
            state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + BOOKSHELF_MOOD)
            state["last_thought"] = "Waking up among my books. So cozy."
    except Exception as error:
        log_once(logger, "comfort", error)


# The cozy home goal ------------------------------------------------------------------------------

def share(s: Situation, *kinds: str) -> float:
    wanted = [touch for touch in touches(s) if touch.kind in kinds]
    if not wanted:
        return 1.0 if home_structure(s) is not None else 0.0
    return 1.0 - len([touch for touch in touches_left(s) if touch.kind in kinds]) / len(wanted)


register_goal(Goal(
    GOAL, "A cozy home",
    "A home is more than walls: glass in the windows, books on a shelf and a rug in its favourite colour.",
    (Milestone("Put glass in the windows", lambda s: share(s, "window"),
               ("decorate_home", "gather_materials", "build_storage"), ("glass_pane",)),
     Milestone("Build a bookshelf into the wall", lambda s: share(s, "bookshelf"),
               ("decorate_home", "gather_materials", "hunt", "build_storage"), ("bookshelf",)),
     Milestone("Lay a rug in its favourite colour", lambda s: share(s, "rug"),
               ("decorate_home", "gather_materials", "hunt", "build_storage"), ("rug_pink",)),
     Milestone("Set a flower pot, a candle and a sign by the door", lambda s: share(s, "pot", "candle", "sign"),
               ("decorate_home", "gather_materials", "hunt", "build_storage"), ("flower_pot", "candle", "sign")),
     Milestone("Put a composter by the farm", lambda s: share(s, "composter"), ("decorate_home",), ("composter",))),
    score=lambda s: 35.0 + s.trait("creativity") / 5, thought="Home should feel like home. Time to make it cozy.",
    after=("first_shelter",), reward=20.0))

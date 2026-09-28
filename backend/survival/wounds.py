"""W1: wounds that fester ("Hazards" 4 of the Wild World spec), for a wild pet only.

A creature's blow that takes 2 health or more after armor (WOUND_FROM; leather armor keeps a skitter's blow
under it) opens a wound with chance WOUND_CHANCE (a seeded roll), unless Mimo has one: "A skitter cut Pip."
(a "wound" event; harm.BLOWS: `cut`). A blow at night is counted for the night's summary too (the shelter and
light lessons' knocks: backend.survival.ailments.DAWN). What a wound does and how it heals is
backend.survival.ailments'.

Dressing (the `dress` step, 2 game seconds, with a bandage or a sunleaf it carries) stops a wound festering at
once. A pet that knows `wild:bandage` makes bandages (1 wool makes 2, anywhere: crafting's "bandage") and
dresses with one; one that knows `wild:sunleaf` presses a sunleaf on it: "Pip wrapped its wound in a bandage."
or "Pip pressed sunleaf on its wound." (a "dressed" event). `dress_wound` (76, a need) does it. The owner's
care bandage dresses a wound too, besides its 25 health (care.CARED).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.services.crafting import take_items
from backend.survival.ailments import HERB, dress, open_wound, wound_of
from backend.survival.care import CARED
from backend.survival.cooking import made
from backend.survival.creatures.harm import BLOWS
from backend.survival.goals import add_urge
from backend.survival.nature import roll
from backend.survival.purposes import Purpose, register
from backend.survival.situation import Situation
from backend.survival.steps import StepFailed, StepKind, register_step
from backend.survival.wild import is_wild, knows, wild_state

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

WOUND_FROM = 2.0
WOUND_CHANCE = 0.35
WOUND_CHANNEL = 204
DRESS_SECONDS = 2.0
BANDAGE = "bandage"
DRESSINGS = (BANDAGE, HERB)
WORDS = {BANDAGE: "{name} wrapped its wound in a bandage.", HERB: "{name} pressed sunleaf on its wound."}


def cut(scene, lost: float, source: str) -> None:
    """harm.BLOWS: a wild pet's blow may open a wound; one at night counts for the night."""
    state = scene.state
    if not is_wild(state):
        return
    if scene.night:
        found = wild_state(state)
        found["night_blows"] = found.get("night_blows", 0) + 1
    if lost < WOUND_FROM or wound_of(state) is not None:
        return
    if roll(scene.seed, scene.pet, WOUND_CHANNEL, int(scene.at)) < WOUND_CHANCE and open_wound(state, scene.at):
        scene.events.append((scene.at, "wound", f"A {source.replace('_', ' ')} cut {state['name']}."))


BLOWS.append(cut)


def cared(state: dict, kind: str, timestamp: float) -> None:
    """care.CARED: the owner's bandage dresses a wound."""
    if kind == BANDAGE and dress(state):
        state["last_thought"] = "You wrapped my wound. Thank you!"


CARED.append(cared)


# The dress step --------------------------------------------------------------------------------

def start_dress(spec: dict, state: dict, grid, at: float, scale: float) -> dict:
    item = spec["item"]
    if item not in DRESSINGS:
        raise StepFailed(f"{item.replace('_', ' ')} cannot dress a wound")
    if state["inventory"].get(item, 0) < 1:
        raise StepFailed(f"no {item.replace('_', ' ')} to dress a wound with", "missing_item")
    found = wound_of(state)
    if found is None or found["dressed_age"] is not None:
        raise StepFailed("no wound to dress", "gone")
    return {"kind": "dress", "started_at": at, "ends_at": round(at + DRESS_SECONDS / scale, 3), "item": item}


def finish_dress(step: dict, state: dict, grid, at: float) -> tuple[str, str] | None:
    if state["inventory"].get(step["item"], 0) < 1 or not dress(state):
        raise StepFailed("no wound to dress", "gone")
    state["inventory"] = take_items(state["inventory"], {step["item"]: 1})
    return "dressed", WORDS[step["item"]].format(name=state["name"])


register_step(StepKind("dress", start_dress, finish_dress, "dressing", string_field="item"))


# dress_wound -----------------------------------------------------------------------------------

def dressing(s: Situation) -> tuple[str, list[dict]] | None:
    """What Mimo dresses its wound with, and the craft steps that make it: a bandage it carries or makes (it
    knows bandages), else a sunleaf it carries (it knows sunleaf)."""
    if knows(s, "bandage"):
        if s.inventory.get(BANDAGE, 0) > 0:
            return BANDAGE, []
        trial = dict(s.inventory)
        steps = made(trial, BANDAGE)
        if steps is not None:
            return BANDAGE, steps
    if knows(s, "sunleaf") and s.inventory.get(HERB, 0) > 0:
        return HERB, []
    return None


def dress_valid(s: Situation) -> bool:
    found = wound_of(s.state)
    return is_wild(s.state) and found is not None and found["dressed_age"] is None and dressing(s) is not None


def plan_dress(s: Situation, context: ActionContext) -> list[dict]:
    found = dressing(s) if dress_valid(s) and s.brain["batches"] == 0 else None
    if found is None:
        return []
    item, crafting = found
    return [*crafting, {"kind": "dress", "item": item}]


add_urge("dress_wound", dress_valid)
register(Purpose(
    "dress_wound", "dress its wound", "Wrap the wound in a bandage, or press sunleaf on it, before it festers.",
    valid=dress_valid, facts=lambda s: f"a wound {'festering' if wound_of(s.state)['festering'] else 'open'}; "
                                       f"dressing it with {dressing(s)[0]}",
    score=lambda s: 76.0, plan=plan_dress,
    thoughts=("Let me look after this wound.", "A clean wrap, and it will heal.")))

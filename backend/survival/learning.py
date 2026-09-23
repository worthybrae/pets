"""What Mimo learns from the M4 steps it finished, kept in its memory (backend.survival.memory).

- Eating food that made it sick teaches it the food is poisonous; foods() and meal() leave it out
  from then on, so neither the eat purpose nor the eat-now reflex eats it again. The eat steps for
  it still queued (or set aside by a reflex) are dropped at once.
- Picking wild food remembers the patch (one per 8 blocks) with how many ripe plants it still
  had and when (data {"ripe", "seen_at"}), so forage can come back once it grew again. A forage
  walk that ends at a patch where Mimo sees nothing it will pick (only known poison counts as
  nothing) remembers it as picked clean then, so forage does not keep walking back to it.
- Placing a campfire or furnace remembers a fire (a warm spot and a place to cook); mining it
  back forgets it.
- Tilling remembers the farm, where the farm purpose keeps its plots.
backend.survival.brain's observe_step calls `learn_from_step` for every step that finished well.
"""

from __future__ import annotations

import math

from backend.services.crafting import FIRES
from backend.survival.memory import cell_of, forget, know, known, nearest, places, remember, update_place
from backend.survival.senses import food_near, near_failure
from backend.survival.steps import FOOD_HEALTH, as_cell

PATCH_REACH = 8.0


def note_food_patch(db, grid, state: dict, picked, at: float) -> None:
    """Remember the patch around a picked plant and how much ripe food it still has."""
    patch = nearest(places(db, ("food",), around=picked, reach=PATCH_REACH), picked, ("food",), PATCH_REACH)
    spot = picked if patch is None else cell_of(patch)
    if patch is None:
        remember(db, "food", spot, at)
    ripe = food_near(grid, state["world_seed"], spot, PATCH_REACH, known(db, "poisonous"))
    update_place(db, "food", spot, {"ripe": len(ripe), "seen_at": at})


def note_empty_patches(db, grid, state: dict, at: float) -> None:
    """Forage walked to a remembered patch: one where it sees nothing it will pick (nothing ripe,
    only food it knows is poisonous, or only food beside a failed step) is remembered as picked
    clean now, so forage leaves it alone until it could have grown again."""
    position = state["position"]
    here = (round(position["x"]), round(position["y"]), round(position["z"]))
    poisons = known(db, "poisonous")
    for patch in places(db, ("food",), around=here, reach=PATCH_REACH):
        spot = cell_of(patch)
        if math.dist(spot, here) > PATCH_REACH:
            continue
        ripe = [cell for cell in food_near(grid, state["world_seed"], spot, PATCH_REACH, poisons)
                if not near_failure(state, cell)]
        if not ripe:
            update_place(db, "food", spot, {"ripe": 0, "seen_at": at})


def drop_eats(state: dict, item: str) -> None:
    """Drop the eat steps for `item` still queued, or set aside by a reflex: it just made Mimo sick."""
    def keep(spec: dict) -> bool:
        return not (spec.get("kind") == "eat" and spec.get("item") == item)

    if "queue" in state:
        state["queue"] = [spec for spec in state["queue"] if keep(spec)]
    brain = state.get("brain")
    if brain and brain.get("set_aside"):
        brain["set_aside"] = [spec for spec in brain["set_aside"] if keep(spec)]


def learn_from_step(state: dict, step: dict, context, at: float) -> None:
    db = context.db
    if db is None:
        return
    kind = step["kind"]
    if kind == "eat" and FOOD_HEALTH.get(step["item"], 0.0) < 0:
        know(db, step["item"], "poisonous", at)
        drop_eats(state, step["item"])
    elif kind == "pick":
        note_food_patch(db, context.grid, state, as_cell(step["target"]), at)
    elif kind == "walk" and step.get("purpose") == "forage":
        note_empty_patches(db, context.grid, state, at)
    elif kind == "place" and step["block"] in FIRES:
        remember(db, "fire", as_cell(step["target"]), at, step["block"])
    elif kind == "mine" and step["block"] in FIRES:
        forget(db, "fire", as_cell(step["target"]))
    elif kind == "till":
        remember(db, "farm", as_cell(step["target"]), at)

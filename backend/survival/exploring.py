"""Where Mimo has been, and where it explores next.

Mimo remembers the ground it walked in 8x8-block patches (memory.memory_explored). `note_ground`
hears about every finished step (brain.observe_step): a walk or swim counts a visit to each
distinct patch along its path, any other step a visit to the patch Mimo stands in. The server
time a patch was first visited is kept as the brain's `new_ground_at`.
"""

from __future__ import annotations

from backend.survival.memory import mark_explored, patch_of
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain

PATH_KINDS = ("walk", "swim")


def path_patches(path: list[dict]) -> list[tuple[int, int]]:
    """The distinct patches a path crosses, in the order it enters them."""
    return list(dict.fromkeys(patch_of(int(entry["x"]), int(entry["z"])) for entry in path))


def note_ground(state: dict, step: dict, context, at: float) -> list[tuple[int, int]]:
    """Mark the ground a finished step covered as visited. Returns the patches visited for the
    first time."""
    if context.db is None:
        return []
    if step["kind"] in PATH_KINDS:
        patches = path_patches(step.get("path") or [])
    else:
        x, _, z = as_cell(state["position"])
        patches = [patch_of(x, z)]
    new = mark_explored(context.db, patches, at)
    if new:
        ensure_brain(state)["new_ground_at"] = at
    return new

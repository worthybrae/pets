"""W2: the hard winter's ice ("Winter" and "Snow and ice: overlays, not blocks" of the Wild World spec).

From the first winter dawn to the first spring dawn the lakes are frozen (`freeze`, a sky effect before each
step): state["sky"]["frozen"], which every grid of the world reads (Grid.overlay: a natural surface water cell
reads as ice, solid and walkable, and is never mined, so no block is ever written). When the freeze comes, the
water cells Mimo stands or swims in stay open (`open_cells`) until the next dawn, by which time it has left, and
each fish near Mimo in a surface cell that freezes swims a cell down, or fades when there is no water under it.
Fish can't be caught through ice (a fishing spot is water), cave lakes lie lower and stay open, and no fish
comes back in winter (renewal: nature.recover_fish).

The rest of the winter lives beside what it changes: growth that falls due in winter waits for the first
spring dawn (renewal.WINTER_WAITS), herds thin (creatures.spawning: one herd a new chunk at most, the land cap
near Mimo 12, no herd back in a hunted-out chunk until spring), spoilage runs a third as fast
(spoilage.WINTER_RATE), the snow cover builds while it snows (sky.tend_weather), and the cold is vitals'.
"""

from __future__ import annotations

from backend.services.worldgen import SEA_LEVEL
from backend.survival import sky
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.kinds import water_kinds
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.grid import Cell, Grid


def surface_water(grid: Grid, cell: Cell) -> bool:
    """A natural water cell at SEA_LEVEL never edited: what freezes. W2 fix round 4: the edit is asked through
    Grid.edited, which loads the cell's chunk first (a fish's chunk may be one nothing in the tick has read yet)."""
    return cell[1] == SEA_LEVEL and grid.natural_material(*cell) == "water" and not grid.edited(cell)


def kept_open(grid: Grid, state: dict) -> list[list[int]]:
    """The water cells Mimo stands or swims in: its own cell and the one under it."""
    position = state["position"]
    x, y, z = round(position["x"]), round(position["y"]), round(position["z"])
    return [[x, cy, z] for cy in (y, y - 1) if surface_water(grid, (x, cy, z))]


def fish_under_ice(state: dict, grid: Grid, at: float) -> None:
    """Each fish near Mimo in a surface cell that froze swims a cell down, or fades with no water there."""
    herd = grid.herd
    if herd is None:
        return
    position = state["position"]
    kinds = [kind.name for kind in water_kinds()]
    for fish in herd.near(position["x"], position["z"], SIM_REACH, kinds=kinds):
        cell = (int(round(fish["x"])), int(round(fish["y"])), int(round(fish["z"])))
        if not surface_water(grid, cell) or list(cell) in state["sky"]["open_cells"]:
            continue
        below = (cell[0], cell[1] - 1, cell[2])
        if grid.material(*below) == "water":
            fish["y"] = float(below[1])
            fish["state"] = {**fish["state"], "home": list(below), "path": None}
            herd.save(fish)
        else:
            herd.remove(fish["id"])


def freeze(state: dict, context, at: float) -> None:
    """sky.EFFECTS: the lakes freeze at the first winter dawn and thaw at the first spring dawn."""
    found = sky.sky_state(state)
    frozen = found["season"] == sky.WINTER
    grid = context.grid
    if frozen and not found["frozen"]:
        found["open_cells"] = kept_open(grid, state)
        scale = context.clock_at(at)["time_scale"]
        found["open_until"] = at + (DAY_SECONDS - context.clock_at(at)["seconds_into_day"]) / scale
        fish_under_ice(state, grid, at)
    elif not frozen:
        found["open_cells"] = []
    if found.get("open_until") is not None and at >= found["open_until"]:
        found["open_cells"] = []
        found.pop("open_until", None)
    found["frozen"] = frozen
    grid.overlay(found)


sky.EFFECTS.append(freeze)

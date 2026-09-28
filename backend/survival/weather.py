"""W2: what the weather does ("Weather" of the Wild World spec). The weather itself is backend.survival.sky's.

- Rain (and a thunderstorm, which is rain with lightning): a walk that starts under the open sky takes
  RAIN_PACE times as long (steps.WALK_PACE), and so does a creature's walk, flight or chase from a cell under the
  open sky (creatures.acts.SLOWS: the controller's ruling on the W2 dry run; slowed alone, an unarmed pet fleeing
  a gloomling and a skitter at 60 times took 37 blows in the rain against at most 6), and a crop stage that starts while it rains grows at the watered
  rate (backend.survival.renewal). What rain does to a campfire and to a fire in the trees is
  backend.survival.storms'.
- Snow (winter only): a walk under the open sky, Mimo's or a creature's, takes SNOW_PACE times as long, it is 10 colder outdoors
  (vitals.SNOW_CHILL, through the tick's Surroundings) and the snow cover builds (sky.tend_weather).
- Fog: the hostiles treat the open ground by day as dark (creatures.darkness.FOG_SKY), the sun does not burn or
  fade them (creatures.hostiles.sunlit), and their cap rises by FOG_ROOM (darkness.MORE_ROOM): 0, tuned down from
  the spec's 2 by the controller's ruling on the W2 dry run (1; the plan's resolution 21). Torches and lanterns
  keep their light.
Everything reads the weather the tick stored at the step's start (sky.weather_now).
"""

from __future__ import annotations

from backend.survival import sky, steps
from backend.survival.creatures import acts, darkness
from backend.survival.creatures.moves import where
from backend.survival.grid import Cell, Grid
from backend.survival.light import sky_open

RAIN_PACE = 1.15
SNOW_PACE = 1.3
FOG_ROOM = 0  # was 2: the ruling on the W2 dry run (1)


def walk_pace(state: dict, grid: Grid, here: Cell) -> float:
    """steps.WALK_PACE: rain and snow slow a walk that starts under the open sky."""
    weather = sky.weather_now(state)
    pace = SNOW_PACE if weather == "snow" else RAIN_PACE if weather in sky.RAINY else 1.0
    if pace == 1.0 or not sky_open(grid, state.get("world_seed", "0"), here):
        return 1.0
    return pace


def creature_pace(scene, creature: dict) -> float:
    """creatures.acts.SLOWS: rain and snow slow a creature's move that starts under the open sky, as they slow
    Mimo's walk."""
    if sky.weather_now(scene.state) not in (*sky.RAINY, "snow"):
        return 1.0
    return walk_pace(scene.state, scene.grid, where(creature, scene.at))


def fog_room(scene) -> int:
    """darkness.MORE_ROOM: FOG_ROOM more hostiles may be about in fog."""
    return FOG_ROOM if sky.foggy(scene.state) else 0


steps.WALK_PACE.append(walk_pace)
acts.SLOWS.append(creature_pace)
darkness.MORE_ROOM.append(fog_room)

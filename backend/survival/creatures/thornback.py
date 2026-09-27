"""The thornback (L5, "Frontier"): a slow, heavily armoured crawler of the far wilds and beyond.

- thornback: 24 health, slow (1.2 s a block, a quarter of Mimo's pace), a blow of 4 every 1.8 s from
  1.6 blocks. Its shell of thorny plates takes SHELL (60 %) off every sword or fist blow, but an arrow
  finds the gaps between them, so arrows are its weakness (creatures.combat: the shell only stops
  a melee blow). It walks by day as well as by night (`daylight`: the sun neither burns nor fades
  it) and drops 1 or 2 flint (its thorns make arrowheads) and sometimes a leather hide. Born in a
  ring, it is tougher like any hostile (backend.survival.creatures.ringed): 41 health in the far wilds.
- Where it comes from: only from the far wilds (danger 2) on, measured where Mimo stands. Once every
  SPAWN_EVERY game seconds, by day or night, it gets a chance of CHANCE (by the ring) to come out on
  open ground 20 to 40 blocks from Mimo, while fewer than MOST_NEAR thornbacks are near it and the
  hostile cap has room (darkness.cap). Light does not keep it away; like any hostile it fades after
  loitering (hostiles.prowl) and goes when Mimo leaves it far behind (darkness.despawn_far).
- Mimo meets it with a bow: a thornback is in defense.BOW_ONLY, so Mimo shoots it even in sword
  reach, never swings at it, and runs from it when it has no bow and arrows. It is too slow to catch
  a pet that runs.
The spawner registers into the creature hook's SPAWNERS (backend.survival.creatures.simulate).
"""

from __future__ import annotations

import math

from backend.survival.creatures.acts import Scene
from backend.survival.creatures.darkness import SPAWN_FAR, born, cap, hostiles_alive, spots
from backend.survival.creatures.defense import BOW_ONLY
from backend.survival.creatures.kinds import Kind, register_kind
from backend.survival.creatures.moves import roll
from backend.survival.creatures.simulate import SPAWNERS
from backend.survival.creatures.spawning import SIM_REACH
from backend.survival.creatures.table import dead
from backend.survival.light import sky_open
from backend.survival.rings import DEEPEST, ring_here

SHELL = 0.6
THORNBACK = register_kind(Kind("thornback", health=24.0, speed=1.2, size=0.9, hostile=True, damage=4.0, reach=1.6,
                               drops={"flint": (1, 2), "leather": 0.3}, flee_when_hurt=False, cooldown=1.8,
                               shell=SHELL, daylight=True))
FROM_RING = 2
SPAWN_EVERY = 90.0  # game seconds between two chances
# Fix (carried from Task 3's review): its own near bound, not darkness.SPAWN_NEAR (16.0, for ordinary
# hostiles). Resolution 7 says a thornback comes out 20 to 40 blocks from Mimo.
SPAWN_NEAR = 20.0
CHANCE = {2: 0.35, 3: 0.5, 4: 0.65}
MOST_NEAR = 2
TRIES = 4
# Roll channels.
CHANCE_ROLL, ANGLE, DISTANCE = 115, 116, 117


def thornbacks_near(scene: Scene) -> int:
    x, _, z = scene.pet
    return sum(1 for creature in scene.herd.near(x, z, SIM_REACH, kinds=[THORNBACK.name]) if not dead(creature))


def spawn_thornbacks(scene: Scene) -> list[dict]:
    """Maybe bring a thornback out near Mimo, from the far wilds on (see the module docstring)."""
    level = min(DEEPEST, ring_here(scene.state))
    if level < FROM_RING:
        return []
    last = scene.state.get("thornback_at")
    if last is not None and (scene.at - last) * scene.scale < SPAWN_EVERY:
        return []
    scene.state["thornback_at"] = scene.at
    salt = int(scene.at * scene.scale)
    if roll(scene.seed, salt, 0, CHANCE_ROLL) >= CHANCE[level] or thornbacks_near(scene) >= MOST_NEAR:
        return []
    if hostiles_alive(scene) >= cap(scene):
        return []
    x, y, z = scene.pet
    for attempt in range(TRIES):
        angle = 2 * math.pi * roll(scene.seed, salt, attempt, ANGLE)
        reach = SPAWN_NEAR + (SPAWN_FAR - SPAWN_NEAR) * roll(scene.seed, salt, attempt, DISTANCE)
        cx, cz = round(x + math.cos(angle) * reach), round(z + math.sin(angle) * reach)
        if math.hypot(cx - x, cz - z) < SPAWN_NEAR:
            continue
        for cell in spots(scene.grid, scene.seed, cx, cz, y)[:1]:
            if sky_open(scene.grid, scene.seed, cell):
                return [born(scene, THORNBACK, cell)]
    return []


SPAWNERS.append(spawn_thornbacks)
BOW_ONLY.add(THORNBACK.name)

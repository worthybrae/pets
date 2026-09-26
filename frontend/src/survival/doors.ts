import type { Point } from './types'

/**
 * Doors (L2). A door block (shared/blocks.json, layer "none") is not meshed: the viewer draws a
 * plank door in its cell itself (SurvivalDoors.tsx), two blocks tall to fill the shelter's door gap,
 * hinged at one side, that swings open while the drawn pet passes through and shuts behind it.
 */

/** Blocks (across) from the door's cell within which the pet holds it wide open. */
export const HELD_OPEN = 0.6
/** Blocks (across) from which the door starts to open as the pet comes. */
export const OPEN_REACH = 1.6
/** Blocks up or down the pet may be and still open it. */
const LEVEL = 1.5

/** How far a door stands open, 0 (shut) to 1 (wide), for the pet drawn at `pet` (cell coordinates). */
export function doorSwing(door: Point, pet: Point | null): number {
  if (!pet || Math.abs(pet.y - door.y) > LEVEL) return 0
  const distance = Math.hypot(pet.x - door.x, pet.z - door.z)
  if (distance >= OPEN_REACH) return 0
  if (distance <= HELD_OPEN) return 1
  return (OPEN_REACH - distance) / (OPEN_REACH - HELD_OPEN)
}

/** Making: whether a machine holds this door open (its cells, [x, y, z], from the workshop view). */
export function heldOpen(door: Point, held: readonly number[][] | null | undefined): boolean {
  return (held ?? []).some(([x, y, z]) => x === door.x && y === door.y && z === door.z)
}

/** The axis a door's panel lies along: x when a wall stands east or west of it, else z. */
export function doorAxis(solidAt: (x: number, y: number, z: number) => boolean, door: Point): 'x' | 'z' {
  return solidAt(door.x - 1, door.y, door.z) || solidAt(door.x + 1, door.y, door.z) ? 'x' : 'z'
}

import { AIR, blockDef } from '../engine/blocks'
import type { Cutaway } from '../engine/columnRenderer'
import type { Point } from './types'

/**
 * Seeing Mimo underground. When rock (or a roof) covers Mimo, the terrain materials discard
 * their fragments above Mimo's head (the cut height, 1.5 blocks over its feet) in two places:
 * within CUTAWAY_RADIUS blocks of Mimo horizontally, and inside a cone from the camera to Mimo
 * that is CUTAWAY_RADIUS wide at Mimo, so the follow camera (about 27 degrees up) sees down a
 * tunnel ten blocks deep. One uniform carries the cut; it changes every frame without remeshing.
 * The shader in columnRenderer.ts mirrors `cutsAway`.
 */

export const CUTAWAY_RADIUS = 8
/** How far over Mimo's feet the cut starts: its own cell stays, the cell over its head goes. */
export const CUT_CLEARANCE = 1.5
/** How far up the column over Mimo's head to look for cover. */
export const COVER_SEARCH = 12
/** A tree's canopy and trunk, and a placed station or fixture, are not ground: Mimo under one of
 * these stays drawn with it instead of having the terrain around it cut away. */
const NOT_COVER = new Set(['leaves', 'oak_log', 'crafting_table', 'furnace', 'lantern', 'glass'])

export interface BlockReader {
  getBlock(x: number, y: number, z: number): number
}

/** Whether a solid block (not a tree) covers the cell within COVER_SEARCH blocks over Mimo's head. */
export function underground(store: BlockReader, cell: Point): boolean {
  for (let dy = 1; dy <= COVER_SEARCH; dy++) {
    const id = store.getBlock(cell.x, cell.y + dy, cell.z)
    if (id === AIR) continue
    const block = blockDef(id)
    if (block.solid && !NOT_COVER.has(block.name)) return true
  }
  return false
}

/** The cut for Mimo drawn at `pose` (cell coordinates, fractional while it moves), or null in the open. */
export function cutawayFor(store: BlockReader, pose: Point): Cutaway | null {
  const cell = { x: Math.round(pose.x), y: Math.round(pose.y), z: Math.round(pose.z) }
  if (!underground(store, cell)) return null
  return { x: pose.x + 0.5, y: pose.y + CUT_CLEARANCE, z: pose.z + 0.5, radius: CUTAWAY_RADIUS }
}

/** Whether the shader discards a terrain fragment at world point `at`, seen from `camera`. */
export function cutsAway(at: Point, cut: Cutaway, camera: Point): boolean {
  if (cut.radius <= 0 || at.y <= cut.y) return false
  if (Math.hypot(at.x - cut.x, at.z - cut.z) < cut.radius) return true
  // The cone from the camera to Mimo's middle, CUTAWAY_RADIUS wide at Mimo.
  const pet = { x: cut.x, y: cut.y - 1, z: cut.z }
  const axis = { x: pet.x - camera.x, y: pet.y - camera.y, z: pet.z - camera.z }
  const length2 = axis.x ** 2 + axis.y ** 2 + axis.z ** 2
  if (length2 === 0) return false
  const t = ((at.x - camera.x) * axis.x + (at.y - camera.y) * axis.y + (at.z - camera.z) * axis.z) / length2
  if (t <= 0 || t >= 1) return false
  const off = Math.hypot(at.x - camera.x - axis.x * t, at.y - camera.y - axis.y * t, at.z - camera.z - axis.z * t)
  return off < cut.radius * t
}

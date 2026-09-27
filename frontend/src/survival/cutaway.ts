import { AIR, blockDef } from '../engine/blocks'
import type { Cutaway } from '../engine/columnRenderer'
import type { Built, Point } from './types'

/**
 * Seeing Mimo underground or at home. When rock or a roof covers Mimo, or a wall or roof of a
 * shelter it built stands between it and the camera, the terrain materials discard their fragments
 * above Mimo's head (the cut height, 1.5 blocks over its feet) in two places: within CUTAWAY_RADIUS
 * blocks of Mimo horizontally, and inside a cone from the camera to Mimo that is CUTAWAY_RADIUS
 * wide at Mimo, so the follow camera (about 27 degrees up) sees down a tunnel ten blocks deep, and
 * into a shelter over its walls. One uniform carries the cut; it changes every frame without
 * remeshing. The shader in columnRenderer.ts mirrors `cutsAway`.
 *
 * Only a shelter's own blocks count as walls (`shelterBlocks`: building blocks the server says were
 * placed around a shelter in the structures list), so a natural hill beside Mimo never cuts the
 * view open. The wall cut goes on at once and stays on for WALL_HOLD_SECONDS after the walls last
 * hid Mimo (`holdWallCut`), so it doesn't flicker as Mimo walks along a wall or the owner orbits.
 */

export const CUTAWAY_RADIUS = 8
/** How far over Mimo's feet the cut starts: its own cell stays, the cell over its head goes. */
export const CUT_CLEARANCE = 1.5
/** How far up the column over Mimo's head to look for cover. */
export const COVER_SEARCH = 12
/** How far from Mimo, toward the camera, a wall or roof that hides it is looked for. */
export const HIDE_REACH = 6
const HIDE_STEP = 0.5
/** A tree's canopy and trunk, and a placed station or fixture, are not ground: Mimo under one of
 * these stays drawn with it instead of having the terrain around it cut away. */
const NOT_COVER = new Set([
  'leaves', 'oak_log', 'crafting_table', 'furnace', 'lantern', 'glass', 'campfire', 'torch', 'bed', 'chest',
  'birch_leaves', 'spruce_leaves', 'birch_log', 'spruce_log', 'fence',  // L3
  'warding_lantern',  // L5
])

export interface BlockReader {
  getBlock(x: number, y: number, z: number): number
}

/** A BlockReader that also knows which blocks the server says were placed (engine/worldStore.ts). */
export interface PlacedReader extends BlockReader {
  placedAt(x: number, y: number, z: number): boolean
}

/** Whether the block at a cell counts, for `hidden`. */
export type CellTest = (x: number, y: number, z: number) => boolean

/** A shelter's floor, walls and roof lie within SHELTER_REACH blocks across of its home cell, from
 * one below it (the floor) to four above (the highest roof): backend/survival/blueprints.py shelter. */
export const SHELTER_REACH = 3
const SHELTER_BELOW = 1
const SHELTER_ABOVE = 4
/** The blocks a shelter is built from (backend/survival/blueprints.py BUILDING). */
const BUILDING = new Set([
  'cobblestone', 'planks', 'brick', 'limestone', 'sandstone', 'basalt', 'moss', 'clay', 'sand', 'gravel', 'dirt',
  'birch_planks', 'spruce_planks', 'stone_bricks',  // L3
])
/** How long the wall cut stays on after the walls last hid Mimo. */
export const WALL_HOLD_SECONDS = 0.75

function isCover(store: BlockReader, x: number, y: number, z: number): boolean {
  const id = store.getBlock(x, y, z)
  if (id === AIR) return false
  const block = blockDef(id)
  return block.solid && !NOT_COVER.has(block.name)
}

/** Whether a solid block (not a tree) covers the cell within COVER_SEARCH blocks over Mimo's head. */
export function underground(store: BlockReader, cell: Point): boolean {
  for (let dy = 1; dy <= COVER_SEARCH; dy++) {
    if (isCover(store, cell.x, cell.y + dy, cell.z)) return true
  }
  return false
}

/**
 * The blocks of the shelters Mimo built: building blocks the server placed within a shelter's
 * reach of its home cell (`structures`, the snapshot's list). Natural ground, a placed station and
 * anything away from every shelter don't count.
 */
export function shelterBlocks(store: PlacedReader, structures: readonly Built[]): CellTest {
  const shelters = structures.filter((built) => built.kind === 'shelter')
  return (x, y, z) => shelters.some((home) => Math.abs(x - home.x) <= SHELTER_REACH
    && Math.abs(z - home.z) <= SHELTER_REACH && y >= home.y - SHELTER_BELOW && y <= home.y + SHELTER_ABOVE)
    && store.placedAt(x, y, z) && BUILDING.has(blockDef(store.getBlock(x, y, z)).name)
}

/**
 * Whether a wall or roof Mimo built hides it, drawn at `pose`, from `camera`: a solid block that
 * `built` counts (shelterBlocks), reaching above the cut height on the line from Mimo's middle
 * toward the camera, within HIDE_REACH blocks. A wall lower than that stays, since the cut would
 * not take it away.
 */
export function hidden(store: BlockReader, pose: Point, camera: Point, built: CellTest): boolean {
  const from = { x: pose.x + 0.5, y: pose.y + 0.5, z: pose.z + 0.5 }
  const toward = { x: camera.x - from.x, y: camera.y - from.y, z: camera.z - from.z }
  const length = Math.hypot(toward.x, toward.y, toward.z)
  if (length === 0) return false
  const lowest = Math.floor(pose.y + CUT_CLEARANCE)
  const home = { x: Math.round(pose.x), y: Math.round(pose.y), z: Math.round(pose.z) }
  for (let along = HIDE_STEP; along <= Math.min(HIDE_REACH, length); along += HIDE_STEP) {
    const x = Math.floor(from.x + (toward.x * along) / length)
    const y = Math.floor(from.y + (toward.y * along) / length)
    const z = Math.floor(from.z + (toward.z * along) / length)
    if (y < lowest || (x === home.x && y === home.y && z === home.z)) continue
    if (isCover(store, x, y, z) && built(x, y, z)) return true
  }
  return false
}

/**
 * The wall cut with its hold: on at once while the walls hide Mimo (`hiddenNow`), and on until
 * WALL_HOLD_SECONDS after they last did. `lastHidden` is when that was (seconds, same clock as
 * `now`), or null; the result carries it forward for the next frame.
 */
export function holdWallCut(hiddenNow: boolean, lastHidden: number | null, now: number):
  { on: boolean; lastHidden: number | null } {
  const last = hiddenNow ? now : lastHidden
  return { on: last !== null && now - last < WALL_HOLD_SECONDS, lastHidden: last }
}

/** The cut for Mimo drawn at `pose` (cell coordinates, fractional while it moves), or null in the
 * open. `walled` says a wall or roof it built hides it from the camera (hidden, held by holdWallCut). */
export function cutawayFor(store: BlockReader, pose: Point, walled = false): Cutaway | null {
  const cell = { x: Math.round(pose.x), y: Math.round(pose.y), z: Math.round(pose.z) }
  if (!underground(store, cell) && !walled) return null
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

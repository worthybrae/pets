import { AIR, blockDef, blockId, LAYER_BY_ID, LAYER_CUTOUT, TILES, type Rgb } from '../engine/blocks'
import {
  blockAt, canopyTop, CHUNK_SIZE, LEGACY_RADIUS, plantStack, SEA_LEVEL, surfaceMaterial, swampPool, terrainBlock,
  terrainHeight, WORLD_MIN_Y,
} from '../engine/worldgen'
import type { WorldStore } from '../engine/worldStore'
import { typingIn, type KeyPress } from './cameraModes'
import type { Built, ExploredPatch, Landmark, MimoAction, Point } from './types'

/**
 * The minimap's maths, kept out of the component so it can be tested (Minimap.tsx draws it).
 *
 * The map is a top-down picture of the land 96 blocks each way around Mimo, north (-z) up and
 * east (+x) right, one pixel per block. Each column is coloured by the block seen from above, as
 * the 3D world has it: worldgen's terrain, water and tree tops (`naturalTop`), with the blocks
 * Mimo placed or dug from the WorldStore (`topBlock`). Pixels are worked out per 8x8 patch, the
 * same patches the server remembers Mimo visiting, and cached, so a redraw only works out the
 * patches it has not drawn before, a budget at a time. Patches Mimo never visited are greyed out.
 */

export const PATCH = 8
export const MAP_RADIUS = 96
export const MAP_BLOCKS = 2 * MAP_RADIUS
/** Canvas pixels per block, so the marks stay crisp. */
export const MAP_SCALE = 2
/** New patches worked out per redraw at most (about 6,000 columns, some 20 ms on a laptop): a new
 * map fills in from the middle over a few polls instead of stalling one frame. */
export const PATCHES_PER_DRAW = 96
export const MAP_OPEN_KEY = 'mimo.minimap'
/** A patch not worked out yet. */
export const UNKNOWN: Rgb = [176, 190, 186]
const FOG_GREY: Rgb = [112, 122, 124]
const FOG = 0.7
/** How much a column higher (lower) than the one north of it is lightened (darkened). */
const RELIEF = 0.06
const WATER = blockId('water')
const LEAVES = new Set(['leaves', 'birch_leaves', 'spruce_leaves'].map((name) => blockId(name)))
const PATH_KINDS = new Set(['walk', 'swim', 'fall'])

/** The block seen from above in a column, how high it is and, for water, how deep. */
export interface Top {
  id: number
  y: number
  depth: number
}

export interface MapOrigin {
  x: number
  z: number
}

export interface MapMark {
  kind: 'home' | 'farm'
  /** Still being built. */
  building: boolean
  px: number
  py: number
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value))
}

function visible(id: number): boolean {
  return id !== AIR && LAYER_BY_ID[id] !== LAYER_CUTOUT
}

/** The first block from above that the map shows, found by reading `at` down from `from`. */
function scanTop(at: (y: number) => number, from: number): Top {
  for (let y = from; y >= WORLD_MIN_Y; y--) {
    const id = at(y)
    if (visible(id)) return { id, y, depth: id === WATER ? 1 : 0 }
  }
  return { id: AIR, y: WORLD_MIN_Y, depth: 0 }
}

/** The block worldgen shows from above at (x, z): a tree top (oak, birch or spruce), water or a frozen
 * lake, a swamp pool, a pumpkin or melon, or the ground. Small plants (grass, flowers, bushes, cacti,
 * cane) are too small to see. */
export function naturalTop(x: number, z: number, seed: string): Top {
  const height = terrainHeight(x, z, seed)
  if (Math.hypot(x, z) <= LEGACY_RADIUS + CHUNK_SIZE) {
    // The retired home island: its hand-placed house and trees are only found by looking.
    return scanTop((y) => blockId(blockAt(x, y, z, seed)), Math.max(height, SEA_LEVEL) + 8)
  }
  const leaves = canopyTop(x, z, seed)
  if (leaves !== null && leaves[1] > Math.max(height, SEA_LEVEL)) return { id: blockId(leaves[0]), y: leaves[1], depth: 0 }
  if (height < SEA_LEVEL) return { id: blockId(terrainBlock(x, SEA_LEVEL, z, seed)), y: SEA_LEVEL, depth: SEA_LEVEL - height }
  if (swampPool(x, z, seed)) return { id: WATER, y: height, depth: 1 }
  const plant = plantStack(x, z, seed)
  if (plant && LAYER_BY_ID[blockId(plant[0])] !== LAYER_CUTOUT) return { id: blockId(plant[0]), y: height + plant[1], depth: 0 }
  return { id: blockId(surfaceMaterial(x, z, seed)), y: height, depth: 0 }
}

/** The block seen from above at (x, z) with Mimo's edits: placed blocks (crops and saplings too)
 * show, dug cells show what is under them. `edits` are the store's edited columns of the chunk. */
export function topBlock(store: WorldStore, x: number, z: number,
  edits = store.editedColumns(Math.floor(x / CHUNK_SIZE), Math.floor(z / CHUNK_SIZE))): Top {
  const natural = naturalTop(x, z, store.seed)
  const edited = edits.get(`${x},${z}`)
  if (edited === undefined) return natural
  for (let y = Math.max(edited, natural.y); y >= WORLD_MIN_Y; y--) {
    const id = store.getBlock(x, y, z)
    if (id === AIR || (LAYER_BY_ID[id] === LAYER_CUTOUT && !store.placedAt(x, y, z))) continue
    return { id, y, depth: id === WATER ? Math.max(1, SEA_LEVEL - terrainHeight(x, z, store.seed)) : 0 }
  }
  return natural
}

/** A column's colour: its block's top face in the soft-pixel palette, lighter the higher it is,
 * water darker the deeper, tree tops a little darker than grass. */
export function topColor(top: Top): Rgb {
  const def = blockDef(top.id)
  const base = TILES[def.textures.top]?.color ?? def.color
  let shade = top.id === WATER
    ? 1.06 - 0.1 * Math.min(4, top.depth)
    : 0.86 + 0.28 * clamp((top.y - SEA_LEVEL) / 14, 0, 1)
  if (LEAVES.has(top.id)) shade *= 0.86
  return [0, 1, 2].map((i) => clamp(Math.round(base[i] * shade), 0, 255)) as Rgb
}

/** Land Mimo never visited: mostly grey, darker, with a faint trace of its colour. */
export function fogColor(rgb: readonly number[]): Rgb {
  return [0, 1, 2].map((i) => Math.round(rgb[i] * (1 - FOG) + FOG_GREY[i] * FOG)) as Rgb
}

/** The pixels (RGBA, north row first) of one 8x8 patch. A column higher than the one north of it
 * is lightened a little and a lower one darkened, so hills show. */
export function patchPixels(store: WorldStore, rx: number, rz: number): Uint8ClampedArray {
  const x0 = rx * PATCH, z0 = rz * PATCH
  const cx = Math.floor(x0 / CHUNK_SIZE)
  const inside = store.editedColumns(cx, Math.floor(z0 / CHUNK_SIZE))
  const north = store.editedColumns(cx, Math.floor((z0 - 1) / CHUNK_SIZE))
  const pixels = new Uint8ClampedArray(PATCH * PATCH * 4)
  let above = Array.from({ length: PATCH }, (_, lx) => topBlock(store, x0 + lx, z0 - 1, north).y)
  for (let lz = 0; lz < PATCH; lz++) {
    const row: number[] = []
    for (let lx = 0; lx < PATCH; lx++) {
      const top = topBlock(store, x0 + lx, z0 + lz, inside)
      const color = topColor(top)
      const relief = top.id === WATER ? 1 : top.y > above[lx] ? 1 + RELIEF : top.y < above[lx] ? 1 - RELIEF : 1
      const at = (lz * PATCH + lx) * 4
      for (let i = 0; i < 3; i++) pixels[at + i] = Math.round(color[i] * relief)
      pixels[at + 3] = 255
      row.push(top.y)
    }
    above = row
  }
  return pixels
}

function patchKey(rx: number, rz: number): string {
  return `${rx},${rz}`
}

/** Patch pixels worked out once each. `invalidate` (fed the store's dirty columns) drops the
 * patches in those chunks, and the row south of them, whose relief looks north into them. */
export class PatchCache {
  private readonly patches = new Map<string, Uint8ClampedArray>()
  private readonly compute: (rx: number, rz: number) => Uint8ClampedArray

  constructor(store: WorldStore, compute?: (rx: number, rz: number) => Uint8ClampedArray) {
    this.compute = compute ?? ((rx, rz) => patchPixels(store, rx, rz))
  }

  get(rx: number, rz: number): Uint8ClampedArray | null {
    return this.patches.get(patchKey(rx, rz)) ?? null
  }

  /** Work out the `wanted` patches not cached yet, in order, at most `budget` of them. Returns how
   * many it worked out. */
  fill(wanted: readonly (readonly [number, number])[], budget: number): number {
    let done = 0
    for (const [rx, rz] of wanted) {
      if (done >= budget) break
      const key = patchKey(rx, rz)
      if (this.patches.has(key)) continue
      this.patches.set(key, this.compute(rx, rz))
      done += 1
    }
    return done
  }

  invalidate(columns: readonly string[]): void {
    const per = CHUNK_SIZE / PATCH
    for (const column of columns) {
      const [cx, cz] = column.split(',').map(Number)
      for (let rx = cx * per; rx < (cx + 1) * per; rx++) {
        for (let rz = cz * per; rz <= (cz + 1) * per; rz++) this.patches.delete(patchKey(rx, rz))
      }
    }
  }

  /** Forget the patches far from the map, so a long walk does not keep them all. */
  prune(keep: (rx: number, rz: number) => boolean): void {
    for (const key of this.patches.keys()) {
      const [rx, rz] = key.split(',').map(Number)
      if (!keep(rx, rz)) this.patches.delete(key)
    }
  }
}

/** The world block at the map's top-left corner: Mimo's block is at the middle of the map. */
export function mapOrigin(position: Point): MapOrigin {
  return { x: Math.round(position.x) - MAP_RADIUS, z: Math.round(position.z) - MAP_RADIUS }
}

/** Where a world column's middle is on the map, in blocks from its top-left corner. */
export function toMap(x: number, z: number, origin: MapOrigin): { px: number; py: number } {
  return { px: x - origin.x + 0.5, py: z - origin.z + 0.5 }
}

/** The patches the map covers, nearest to its middle first, so those are worked out first. */
export function mapPatches(origin: MapOrigin): [number, number][] {
  const found: [number, number][] = []
  const low = [Math.floor(origin.x / PATCH), Math.floor(origin.z / PATCH)]
  const high = [Math.floor((origin.x + MAP_BLOCKS - 1) / PATCH), Math.floor((origin.z + MAP_BLOCKS - 1) / PATCH)]
  for (let rx = low[0]; rx <= high[0]; rx++) for (let rz = low[1]; rz <= high[1]; rz++) found.push([rx, rz])
  const middle = [origin.x + MAP_RADIUS, origin.z + MAP_RADIUS]
  const away = ([rx, rz]: [number, number]) => Math.hypot(rx * PATCH + PATCH / 2 - middle[0], rz * PATCH + PATCH / 2 - middle[1])
  return found.sort((a, b) => away(a) - away(b))
}

/** The patches drawn in colour: the ones the server says Mimo visited, and the one it stands in. */
export function seenPatches(explored: readonly ExploredPatch[] | null | undefined, position: Point): Set<string> {
  const seen = new Set((explored ?? []).map(([rx, rz]) => patchKey(rx, rz)))
  seen.add(patchKey(Math.floor(Math.round(position.x) / PATCH), Math.floor(Math.round(position.z) / PATCH)))
  return seen
}

/** Fill `out` (RGBA, `size` x `size` blocks from `origin`) from the patches: seen ones in colour,
 * the others greyed, and ones not worked out yet (null) as UNKNOWN. */
export function composeMap(out: Uint8ClampedArray, size: number, origin: MapOrigin,
  pixelsOf: (rx: number, rz: number) => Uint8ClampedArray | null, seen: (rx: number, rz: number) => boolean): void {
  const fogged = fogColor(UNKNOWN)
  for (let rz = Math.floor(origin.z / PATCH); rz * PATCH < origin.z + size; rz++) {
    for (let rx = Math.floor(origin.x / PATCH); rx * PATCH < origin.x + size; rx++) {
      const pixels = pixelsOf(rx, rz)
      const lit = seen(rx, rz)
      for (let lz = 0; lz < PATCH; lz++) {
        const row = rz * PATCH + lz - origin.z
        if (row < 0 || row >= size) continue
        for (let lx = 0; lx < PATCH; lx++) {
          const column = rx * PATCH + lx - origin.x
          if (column < 0 || column >= size) continue
          const to = (row * size + column) * 4
          if (pixels === null) {
            const color = lit ? UNKNOWN : fogged
            out[to] = color[0]
            out[to + 1] = color[1]
            out[to + 2] = color[2]
          } else {
            const from = (lz * PATCH + lx) * 4
            for (let i = 0; i < 3; i++) out[to + i] = lit ? pixels[from + i] : pixels[from + i] * (1 - FOG) + FOG_GREY[i] * FOG
          }
          out[to + 3] = 255
        }
      }
    }
  }
}

/** The way Mimo is walking, swimming or falling (radians on the map: 0 east, -π/2 north), or null. */
export function travelHeading(action: MimoAction | null, position: Point): number | null {
  const path = action && PATH_KINDS.has(action.kind) ? action.path ?? [] : []
  if (path.length < 2) return null
  let nearest = 0
  for (let i = 1; i < path.length; i++) {
    const distance = Math.hypot(path[i].x - position.x, path[i].z - position.z)
    if (distance < Math.hypot(path[nearest].x - position.x, path[nearest].z - position.z)) nearest = i
  }
  const from = path[Math.min(nearest, path.length - 2)]
  const to = path[Math.min(nearest, path.length - 2) + 1]
  if (from.x === to.x && from.z === to.z) return null
  return Math.atan2(to.z - from.z, to.x - from.x)
}

/** Home and the farm on the map: what Mimo built, and what it remembers where it built nothing
 * (a sheltered spot it made home, the plot it first tilled). Marks off the map are left out. */
export function mapMarks(structures: readonly Built[] | null | undefined, landmarks: readonly Landmark[] | null | undefined,
  origin: MapOrigin): MapMark[] {
  const built = structures ?? []
  const marks: { kind: 'home' | 'farm'; building: boolean; x: number; z: number }[] = []
  for (const kind of ['home', 'farm'] as const) {
    const structureKind = kind === 'home' ? 'shelter' : 'farm'
    const same = kind === 'home' ? 4 : 16
    const own = built.filter((found) => found.kind === structureKind)
    for (const found of own) marks.push({ kind, building: found.status !== 'done', x: found.x, z: found.z })
    for (const place of landmarks ?? []) {
      if (place.kind === kind && !own.some((found) => Math.hypot(found.x - place.x, found.z - place.z) <= same)) {
        marks.push({ kind, building: false, x: place.x, z: place.z })
      }
    }
  }
  return marks
    .map(({ kind, building, x, z }) => ({ kind, building, ...toMap(x, z, origin) }))
    .filter(({ px, py }) => px >= 0 && py >= 0 && px < MAP_BLOCKS && py < MAP_BLOCKS)
}

/** The marks with each farm moved straight away from any house closer than `gap` (map blocks), so
 * the glyphs do not cover each other: a farm right on a house goes west. */
export function spreadMarks(marks: readonly MapMark[], gap: number): MapMark[] {
  const homes = marks.filter((mark) => mark.kind === 'home')
  return marks.map((mark) => {
    if (mark.kind !== 'farm') return mark
    let { px, py } = mark
    for (const home of homes) {
      const dx = px - home.px, dy = py - home.py
      const away = Math.hypot(dx, dy)
      if (away >= gap) continue
      const [ux, uy] = away > 0 ? [dx / away, dy / away] : [-1, 0]
      px = home.px + ux * gap
      py = home.py + uy * gap
    }
    return px === mark.px && py === mark.py ? mark : { ...mark, px, py }
  })
}

/** Whether a key press shows or hides the map: M, without Ctrl, Cmd or Alt, and not while typing. */
export function isMapKey(event: KeyPress): boolean {
  if (event.key !== 'm' && event.key !== 'M') return false
  return !event.ctrlKey && !event.metaKey && !event.altKey && !typingIn(event.target)
}

/** Whether the map starts shown when nothing was saved: not where it would cover the vitals. On
 * phones (narrower than 640 px, where the HUD stacks) it needs 640 px of height; wider, where it
 * sits in the right-hand column under the vitals and over the recent events, 580. */
export function mapShownByDefault(width: number, height: number): boolean {
  return height >= (width < 640 ? 640 : 580)
}

/** Whether the map was left open, or `fallback` when nothing was saved (mapShownByDefault).
 * `storage` may throw, and so may reading it. */
export function loadMapOpen(storage: () => Pick<Storage, 'getItem'>, fallback: boolean): boolean {
  try {
    const saved = storage().getItem(MAP_OPEN_KEY)
    return saved === 'shown' ? true : saved === 'hidden' ? false : fallback
  } catch {
    return fallback
  }
}

export function saveMapOpen(storage: () => Pick<Storage, 'setItem'>, open: boolean): void {
  try {
    storage().setItem(MAP_OPEN_KEY, open ? 'shown' : 'hidden')
  } catch {
    // Blocked or full storage: the choice lasts for this visit only.
  }
}

import type { Voxel } from '../types/world'
import { MAP_BLOCKS, toMap, type MapOrigin } from './overheadMap'
import type { Creature, Point } from './types'

/**
 * Blocky voxel models of the creatures, in the soft pixel style of the pet (PetVoxels): a white
 * rabbit with long ears, a woolly sheep, a spotted cow with horns, a small chicken with a comb and
 * a fish, and (L2) the hostile gloomling, tall and dark with glowing eyes and its arms held out,
 * and the skitter, low and wide on eight legs with red eyes. Each model is two voxel lists, the
 * body and the head, so the head can dip to graze.
 * Voxel units: x across, y up from the feet, z forward (the way the creature faces). Every kind is
 * drawn on the same grid of VOXEL blocks, coarse enough that eyes, ears and horns still read from
 * the camera next to the pet, and each model is as many voxels tall as its kind's size in blocks
 * (backend/survival/creatures/kinds.py) takes, so `scale` works out to VOXEL for all of them.
 */
export interface CreatureModel {
  body: Voxel[]
  head: Voxel[]
  /** Where the head turns to graze, in voxel units. */
  neck: Point
  /** Blocks per voxel. */
  scale: number
  /** How high a walk hops, in blocks. */
  hop: number
}

type Color = readonly [number, number, number]

/** Blocks per voxel, the same for every kind. */
export const VOXEL = 0.1

const WHITE: Color = [240, 238, 232]
const PINK: Color = [236, 168, 176]
const EYE: Color = [44, 42, 52]
const WOOL: Color = [236, 229, 212]
const FACE: Color = [168, 142, 122]
const SPOT: Color = [52, 48, 50]
const NOSE: Color = [226, 158, 150]
const HORN: Color = [226, 214, 180]
const COMB: Color = [214, 72, 64]
const BEAK: Color = [240, 184, 72]
const WING: Color = [224, 220, 210]
const SCALES: Color = [242, 150, 76]
const FIN: Color = [250, 196, 120]
const GLOOM: Color = [66, 58, 88]
const GLOOM_DARK: Color = [44, 38, 60]
const GLOW: Color = [170, 238, 255]
const SHELL: Color = [78, 64, 54]
const SHELL_DARK: Color = [54, 44, 38]
const RED_EYE: Color = [226, 70, 62]

/** Blocks tall, as in the kinds registry. Each model is this divided by VOXEL voxels tall. */
const SIZES: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1.0, cow: 1.3, fish: 0.3, gloomling: 1.7,
  skitter: 0.6 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0, gloomling: 0.03,
  skitter: 0.02 }

class Builder {
  voxels: Voxel[] = []

  box(x: [number, number], y: [number, number], z: [number, number], color: Color | ((x: number, y: number, z: number) => Color)) {
    for (let i = x[0]; i <= x[1]; i++) {
      for (let j = y[0]; j <= y[1]; j++) {
        for (let k = z[0]; k <= z[1]; k++) {
          const [r, g, b] = typeof color === 'function' ? color(i, j, k) : color
          this.voxels = this.voxels.filter((voxel) => voxel.x !== i || voxel.y !== j || voxel.z !== k)
          this.voxels.push({ x: i, y: j, z: k, r, g, b, a: 255 })
        }
      }
    }
    return this
  }

  /** The same box on both sides: at x and at -x. */
  pair(x: number, y: [number, number], z: [number, number], color: Color) {
    return this.box([x, x], y, z, color).box([-x, -x], y, z, color)
  }
}

/** Black patches on a cow, two voxels across so they read from afar, fixed by the voxel's place. */
function spotted(x: number, y: number, z: number): Color {
  const patch = Math.floor(x / 2) * 7 + Math.floor(y / 2) * 13 + Math.floor(z / 2) * 5
  return ((patch % 11) + 11) % 11 < 3 ? SPOT : WHITE
}

/** 5 voxels tall: a round body, a head with ears 2 voxels long above it. */
function rabbit(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-1, 1], [0, 1], [-2, 1], WHITE).box([-1, 1], [2, 2], [-2, 0], WHITE)
    .box([0, 0], [2, 2], [-3, -3], WHITE).pair(1, [0, 0], [2, 2], WHITE)
  const head = new Builder().box([-1, 1], [1, 2], [2, 3], WHITE).pair(1, [2, 2], [3, 3], EYE)
    .box([0, 0], [1, 1], [3, 3], PINK).pair(1, [3, 4], [2, 2], WHITE)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 1, z: 2 } }
}

/** 6 voxels tall: legs, a plump body with wings and a tail, a head with eyes, a beak, a comb and a wattle. */
function chicken(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().pair(1, [0, 0], [0, 0], BEAK).box([-1, 1], [1, 3], [-2, 0], WHITE)
    .box([-1, 1], [1, 2], [1, 1], WHITE).pair(2, [2, 3], [-1, 0], WING).box([0, 0], [2, 4], [-3, -3], WHITE)
  const head = new Builder().box([-1, 1], [3, 4], [1, 2], WHITE).pair(1, [4, 4], [2, 2], EYE)
    .box([0, 0], [3, 3], [3, 3], BEAK).box([0, 0], [5, 5], [1, 2], COMB).box([0, 0], [2, 2], [2, 2], COMB)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 3, z: 1 } }
}

/** 10 voxels tall: four legs under a thick fleece, a face with eyes, ears and a woolly crown. */
function sheep(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [4, 8], [-3, 3], WOOL)
  for (const z of [-2, 2]) body.pair(1, [0, 3], [z, z], FACE)
  const head = new Builder().box([-1, 1], [5, 8], [4, 5], FACE).pair(1, [7, 7], [5, 5], EYE)
    .box([-1, 1], [9, 9], [4, 5], WOOL).pair(2, [8, 8], [4, 4], FACE)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 6, z: 4 } }
}

/** 13 voxels tall: sturdy legs, a long spotted body with a tail and udder, a head with a muzzle,
 * ears and horns that grow out of its sides. */
function cow(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-3, 3], [5, 10], [-5, 4], spotted)
  for (const z of [-5, 3]) {
    body.box([-3, -2], [1, 4], [z, z + 1], WHITE).box([2, 3], [1, 4], [z, z + 1], WHITE)
      .box([-3, -2], [0, 0], [z, z + 1], SPOT).box([2, 3], [0, 0], [z, z + 1], SPOT)
  }
  body.box([0, 0], [7, 9], [-6, -6], WHITE).box([0, 0], [6, 6], [-6, -6], SPOT).box([0, 0], [4, 4], [-3, -2], NOSE)
  const head = new Builder().box([-2, 2], [8, 11], [5, 7], spotted).box([-1, 1], [8, 9], [8, 8], NOSE)
    .pair(2, [10, 10], [7, 7], EYE).pair(3, [10, 10], [5, 5], WHITE).pair(3, [11, 12], [6, 6], HORN)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 8, z: 5 } }
}

/** 3 voxels tall: a tapered body with eyes, a back fin and a tail. */
function fish(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([0, 0], [0, 1], [-2, 1], SCALES).box([-1, 1], [0, 1], [-1, 0], SCALES)
    .pair(1, [1, 1], [0, 0], EYE).box([0, 0], [2, 2], [-1, 0], FIN).box([0, 0], [0, 2], [-3, -3], FIN)
  return { body: body.voxels, head: [], neck: { x: 0, y: 1, z: 1 } }
}

/** L2, 17 voxels tall: long legs, a thin dark body with its arms held out in front, a head with two glowing eyes. */
function gloomling(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().pair(1, [0, 6], [0, 0], GLOOM_DARK).box([-2, 2], [7, 12], [-1, 1], GLOOM)
    .pair(3, [9, 12], [0, 0], GLOOM).pair(3, [9, 9], [1, 4], GLOOM_DARK)
  const head = new Builder().box([-2, 2], [13, 16], [-1, 2], GLOOM).pair(1, [15, 15], [2, 2], GLOW)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 13, z: 0 } }
}

/** L2, 6 voxels tall: a low, wide shell on eight splayed legs, a head with red eyes and fangs. */
function skitter(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [2, 4], [-3, 1], SHELL).box([-1, 1], [5, 5], [-2, 0], SHELL_DARK)
  for (const z of [-2, -1, 0, 1]) body.pair(3, [2, 2], [z, z], SHELL_DARK).pair(4, [0, 1], [z, z], SHELL_DARK)
  const head = new Builder().box([-1, 1], [2, 4], [2, 3], SHELL).pair(1, [4, 4], [3, 3], RED_EYE)
    .pair(1, [1, 1], [3, 3], SHELL_DARK)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 3, z: 2 } }
}

/** A plain grey block for a kind this viewer does not know yet. */
function unknown(): Omit<CreatureModel, 'scale' | 'hop'> {
  return { body: new Builder().box([-2, 2], [0, 5], [-2, 2], [150, 150, 150]).voxels, head: [], neck: { x: 0, y: 5, z: 2 } }
}

const MODELS: Record<string, () => Omit<CreatureModel, 'scale' | 'hop'>> = {
  rabbit, chicken, sheep, cow, fish, gloomling, skitter,
}
const cache = new Map<string, CreatureModel>()

/** The voxel model of a kind of creature (the same object every time). */
export function creatureModel(kind: string): CreatureModel {
  const known = cache.get(kind)
  if (known) return known
  const parts = (MODELS[kind] ?? unknown)()
  const all = [...parts.body, ...parts.head]
  const low = Math.min(...all.map((voxel) => voxel.y))
  const high = Math.max(...all.map((voxel) => voxel.y))
  const model = { ...parts, scale: (SIZES[kind] ?? 0.6) / (high - low + 1), hop: HOPS[kind] ?? 0.05 }
  cache.set(kind, model)
  return model
}

/** The color of a dropped item as it pops out of a creature's puff. */
export function dropColor(item: string): Color {
  if (item.startsWith('raw_')) return [214, 112, 108]
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124],
    gloom_dust: [132, 120, 176], string: [236, 236, 230] } as Record<string, Color>)[item] ?? [180, 180, 180]
}

/** A creature as a small dot on the minimap, in blocks from the map's top-left corner. */
export interface CreatureDot {
  px: number
  py: number
  fish: boolean
  /** L2: a hostile creature, drawn red. */
  hostile: boolean
}

/** The living creatures on the minimap (overheadMap.ts): dead ones and ones off the map are left out. */
export function creatureDots(creatures: readonly Creature[] | null | undefined, origin: MapOrigin): CreatureDot[] {
  return (creatures ?? [])
    .filter((creature) => creature.state !== 'dead')
    .map((creature) => ({ ...toMap(creature.x, creature.z, origin), fish: creature.kind === 'fish',
      hostile: Boolean(creature.hostile) }))
    .filter(({ px, py }) => px >= 0 && py >= 0 && px < MAP_BLOCKS && py < MAP_BLOCKS)
}

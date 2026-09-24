import type { Voxel } from '../types/world'
import { MAP_BLOCKS, toMap, type MapOrigin } from './overheadMap'
import type { Creature, Point } from './types'

/**
 * Blocky voxel models of the creatures, in the soft pixel style of the pet (PetVoxels): a white
 * rabbit with long ears, a woolly sheep, a spotted cow, a small chicken and a fish. Each model is
 * two voxel lists, the body and the head, so the head can dip to graze. Voxel units: x across,
 * y up from the feet, z forward (the way the creature faces). `scale` makes the model as tall as
 * the kind's size in blocks (backend/survival/creatures/kinds.py).
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

const WHITE: Color = [240, 238, 232]
const PINK: Color = [236, 168, 176]
const EYE: Color = [44, 42, 52]
const WOOL: Color = [236, 229, 212]
const FACE: Color = [96, 90, 88]
const SPOT: Color = [52, 48, 50]
const NOSE: Color = [226, 158, 150]
const HORN: Color = [226, 214, 180]
const COMB: Color = [214, 72, 64]
const BEAK: Color = [240, 184, 72]
const SCALES: Color = [242, 150, 76]
const FIN: Color = [250, 196, 120]

/** Blocks tall, as in the kinds registry. */
const SIZES: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1.0, cow: 1.3, fish: 0.3 }
const HOPS: Record<string, number> = { rabbit: 0.25, chicken: 0.08, sheep: 0.06, cow: 0.04, fish: 0 }

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
}

/** Black patches on a cow, fixed by the voxel's place. */
function spotted(x: number, y: number, z: number): Color {
  return ((x * 7 + y * 13 + z * 5) % 11 + 11) % 11 < 3 ? SPOT : WHITE
}

function rabbit(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-1, 1], [0, 2], [-3, 1], WHITE).box([0, 0], [2, 2], [-4, -4], WHITE)
  const head = new Builder().box([-1, 1], [2, 4], [2, 4], WHITE)
    .box([-1, -1], [3, 3], [4, 4], EYE).box([1, 1], [3, 3], [4, 4], EYE).box([0, 0], [2, 2], [4, 4], PINK)
    .box([-1, -1], [5, 8], [2, 2], WHITE).box([1, 1], [5, 8], [2, 2], WHITE)
    .box([-1, -1], [5, 7], [3, 3], PINK).box([1, 1], [5, 7], [3, 3], PINK)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 2.5, z: 1.5 } }
}

function chicken(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-1, 1], [1, 3], [-2, 1], WHITE).box([0, 0], [3, 4], [-3, -3], WHITE)
    .box([-2, -2], [2, 2], [-1, 0], WHITE).box([2, 2], [2, 2], [-1, 0], WHITE)
    .box([-1, -1], [0, 0], [0, 0], BEAK).box([1, 1], [0, 0], [0, 0], BEAK)
  const head = new Builder().box([0, 0], [4, 5], [1, 2], WHITE).box([0, 0], [6, 6], [1, 2], COMB)
    .box([0, 0], [4, 4], [3, 3], BEAK).box([0, 0], [3, 3], [2, 2], COMB)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 3.5, z: 1 } }
}

function sheep(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [2, 5], [-3, 3], WOOL)
  for (const [x, z] of [[-1, -2], [1, -2], [-1, 2], [1, 2]]) body.box([x, x], [0, 1], [z, z], FACE)
  const head = new Builder().box([-1, 1], [4, 6], [4, 5], FACE).box([-1, 1], [7, 7], [4, 5], WOOL)
    .box([-1, -1], [6, 6], [6, 6], EYE).box([1, 1], [6, 6], [6, 6], EYE).box([-1, 1], [4, 5], [6, 6], FACE)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 4.5, z: 3.5 } }
}

function cow(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([-2, 2], [3, 6], [-4, 3], spotted)
  for (const [x, z] of [[-2, -3], [2, -3], [-2, 2], [2, 2]]) body.box([x, x], [0, 2], [z, z], WHITE)
  const head = new Builder().box([-1, 1], [5, 7], [4, 6], spotted).box([-1, 1], [5, 5], [7, 7], NOSE)
    .box([-1, -1], [7, 7], [7, 7], EYE).box([1, 1], [7, 7], [7, 7], EYE)
    .box([-2, -2], [8, 8], [5, 5], HORN).box([2, 2], [8, 8], [5, 5], HORN)
  return { body: body.voxels, head: head.voxels, neck: { x: 0, y: 5.5, z: 3.5 } }
}

function fish(): Omit<CreatureModel, 'scale' | 'hop'> {
  const body = new Builder().box([0, 0], [0, 1], [-2, 1], SCALES).box([0, 0], [2, 2], [-1, 0], FIN)
    .box([0, 0], [-1, 2], [-3, -3], FIN).box([0, 0], [1, 1], [1, 1], EYE)
  return { body: body.voxels, head: [], neck: { x: 0, y: 1, z: 1 } }
}

/** A plain grey block for a kind this viewer does not know yet. */
function unknown(): Omit<CreatureModel, 'scale' | 'hop'> {
  return { body: new Builder().box([-1, 1], [0, 2], [-1, 1], [150, 150, 150]).voxels, head: [], neck: { x: 0, y: 2, z: 1 } }
}

const MODELS: Record<string, () => Omit<CreatureModel, 'scale' | 'hop'>> = { rabbit, chicken, sheep, cow, fish }
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
  return ({ leather: [150, 96, 62], wool: WOOL, feather: [250, 250, 246], rabbit_hide: [196, 164, 124] } as Record<string, Color>)[item]
    ?? [180, 180, 180]
}

/** A creature as a small dot on the minimap, in blocks from the map's top-left corner. */
export interface CreatureDot {
  px: number
  py: number
  fish: boolean
}

/** The living creatures on the minimap (overheadMap.ts): dead ones and ones off the map are left out. */
export function creatureDots(creatures: readonly Creature[] | null | undefined, origin: MapOrigin): CreatureDot[] {
  return (creatures ?? [])
    .filter((creature) => creature.state !== 'dead')
    .map((creature) => ({ ...toMap(creature.x, creature.z, origin), fish: creature.kind === 'fish' }))
    .filter(({ px, py }) => px >= 0 && py >= 0 && px < MAP_BLOCKS && py < MAP_BLOCKS)
}

import { describe, expect, it } from 'vitest'
import { VOXEL, creatureDots, creatureModel, dropColor } from './creatures'
import { mapOrigin } from './overheadMap'
import type { Creature } from './types'

const KINDS = ['rabbit', 'chicken', 'sheep', 'cow', 'fish']

function height(kind: string): number {
  const model = creatureModel(kind)
  const ys = [...model.body, ...model.head].map((voxel) => voxel.y)
  return (Math.max(...ys) - Math.min(...ys) + 1) * model.scale
}

type Cell = { x: number; y: number; z: number }
const key = ({ x, y, z }: Cell) => `${x},${y},${z}`
const SIDES = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]

/** Whether every voxel of `part` touches `whole` (or another voxel of `part`) face to face. */
function attached(part: readonly Cell[], whole: readonly Cell[]): boolean {
  const cells = new Set(whole.map(key))
  return part.every(({ x, y, z }) => SIDES.some(([dx, dy, dz]) => cells.has(key({ x: x + dx, y: y + dy, z: z + dz }))))
}

describe('creatureModel', () => {
  it('builds every kind from voxels of one shared size, as tall as the kind is', () => {
    const sizes: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1, cow: 1.3, fish: 0.3 }
    expect(VOXEL).toBeGreaterThanOrEqual(0.1)
    for (const kind of KINDS) {
      const model = creatureModel(kind)
      expect(model.scale).toBeCloseTo(VOXEL)
      expect(model.body.length).toBeGreaterThan(5)
      expect(height(kind)).toBeCloseTo(sizes[kind])
      const cells = [...model.body, ...model.head].map(key)
      expect(new Set(cells).size).toBe(cells.length)
      expect(attached(model.head, [...model.body, ...model.head])).toBe(true)
    }
    expect(creatureModel('cow')).toBe(creatureModel('cow'))
  })

  it('knows how tall it stands once, so a frame loop need not measure its voxels', () => {
    for (const kind of [...KINDS, 'gloomling', 'skitter', 'unknown']) expect(creatureModel(kind).height).toBeCloseTo(height(kind))
  })

  it('gives the rabbit long ears, the cow its spots and the sheep its wool', () => {
    const rabbit = creatureModel('rabbit')
    const top = Math.max(...rabbit.head.map((voxel) => voxel.y))
    expect(top - Math.max(...rabbit.body.map((voxel) => voxel.y))).toBeGreaterThanOrEqual(2)
    const cow = creatureModel('cow').body.map((voxel) => voxel.r)
    expect(cow.some((red) => red < 80)).toBe(true)
    expect(cow.some((red) => red > 200)).toBe(true)
    const sheep = creatureModel('sheep').body
    expect(sheep.filter((voxel) => voxel.r > 220).length).toBeGreaterThan(sheep.length / 2)
    expect(creatureModel('fish').head).toEqual([])
  })

  it('gives the chicken a head with eyes, a beak and a comb', () => {
    const { head } = creatureModel('chicken')
    const colors = new Set(head.map((voxel) => `${voxel.r},${voxel.g},${voxel.b}`))
    expect(colors.size).toBeGreaterThanOrEqual(4)  // feathers, eyes, beak, comb
    expect(head.filter((voxel) => voxel.r < 80).length).toBe(2)  // two eyes
    expect(new Set(head.map((voxel) => voxel.x)).size).toBeGreaterThanOrEqual(3)  // a head, not a sliver
  })

  it('grows the cow\'s horns out of its head, so they turn with it', () => {
    const { head } = creatureModel('cow')
    const horns = head.filter((voxel) => voxel.r === 226 && voxel.g === 214)
    expect(horns.length).toBeGreaterThanOrEqual(2)
    expect(new Set(horns.map((voxel) => Math.sign(voxel.x)))).toEqual(new Set([-1, 1]))
    const skull = head.filter((voxel) => !horns.includes(voxel))
    expect(attached(horns, [...skull, ...horns])).toBe(true)
    const touching = new Set(skull.map(key))
    expect(horns.some(({ x, y, z }) => SIDES.some(([dx, dy, dz]) => touching.has(key({ x: x + dx, y: y + dy, z: z + dz })))))
      .toBe(true)
  })

  it('hops rabbits highest and draws a kind it does not know as a plain block', () => {
    expect(creatureModel('rabbit').hop).toBeGreaterThan(creatureModel('cow').hop)
    const unknown = creatureModel('dragon')
    expect(unknown.body.length).toBe(150)
    expect(unknown.scale).toBeCloseTo(VOXEL)
  })
})

describe('hostile models', () => {
  it('draws the gloomling tall with glowing eyes and the skitter low on eight legs, on the shared grid', () => {
    const sizes: Record<string, number> = { gloomling: 1.7, skitter: 0.6 }
    for (const kind of ['gloomling', 'skitter']) {
      const model = creatureModel(kind)
      expect(model.scale).toBeCloseTo(VOXEL)
      expect(height(kind)).toBeCloseTo(sizes[kind])
      expect(attached(model.head, [...model.body, ...model.head])).toBe(true)
      const cells = [...model.body, ...model.head].map(key)
      expect(new Set(cells).size).toBe(cells.length)
    }
    const eyes = creatureModel('gloomling').head.filter((voxel) => voxel.g > 200)
    expect(eyes.length).toBe(2)
    const feet = creatureModel('skitter').body.filter((voxel) => voxel.y === 0)
    expect(new Set(feet.map((voxel) => `${Math.sign(voxel.x)},${voxel.z}`)).size).toBe(8)
    const width = (kind: string) => Math.max(...creatureModel(kind).body.map((voxel) => voxel.x)) - Math.min(...creatureModel(kind).body.map((voxel) => voxel.x))
    expect(width('skitter')).toBeGreaterThan(height('skitter') / VOXEL)
  })
})

describe('dropColor', () => {
  it('colors meat, leather, wool and feathers', () => {
    expect(dropColor('raw_beef')).toEqual(dropColor('raw_rabbit'))
    expect(new Set(['raw_beef', 'leather', 'wool', 'feather', 'rabbit_hide'].map((item) => dropColor(item).join()))
      .size).toBe(5)
    expect(dropColor('mystery')).toEqual([180, 180, 180])
  })
})

describe('creatureDots', () => {
  it('puts the living creatures on the minimap, fish apart, and leaves out the dead and the far', () => {
    const origin = mapOrigin({ x: 100, y: 5, z: 100 })
    const cow: Creature = { id: 1, kind: 'cow', x: 110, y: 5, z: 90, heading: 0, health: 1, state: 'grazing' }
    const dots = creatureDots([cow, { ...cow, id: 2, kind: 'fish', x: 100, z: 100 },
      { ...cow, id: 3, state: 'dead', dead_at: 5 }, { ...cow, id: 4, x: 400 }], origin)
    expect(dots).toEqual([{ px: 106.5, py: 86.5, fish: false, hostile: false }, { px: 96.5, py: 96.5, fish: true, hostile: false }])
    expect(creatureDots(undefined, origin)).toEqual([])
  })
})

import { describe, expect, it } from 'vitest'
import { creatureModel, dropColor } from './creatures'

const KINDS = ['rabbit', 'chicken', 'sheep', 'cow', 'fish']

function height(kind: string): number {
  const model = creatureModel(kind)
  const ys = [...model.body, ...model.head].map((voxel) => voxel.y)
  return (Math.max(...ys) - Math.min(...ys) + 1) * model.scale
}

describe('creatureModel', () => {
  it('builds every kind from voxels, as tall as the kind is', () => {
    const sizes: Record<string, number> = { rabbit: 0.5, chicken: 0.6, sheep: 1, cow: 1.3, fish: 0.3 }
    for (const kind of KINDS) {
      const model = creatureModel(kind)
      expect(model.body.length).toBeGreaterThan(5)
      expect(height(kind)).toBeCloseTo(sizes[kind])
      const cells = [...model.body, ...model.head].map((voxel) => `${voxel.x},${voxel.y},${voxel.z}`)
      expect(new Set(cells).size).toBe(cells.length)
    }
    expect(creatureModel('cow')).toBe(creatureModel('cow'))
  })

  it('gives the rabbit long ears, the cow its spots and the sheep its wool', () => {
    const rabbit = creatureModel('rabbit')
    const top = Math.max(...rabbit.head.map((voxel) => voxel.y))
    expect(top - Math.max(...rabbit.body.map((voxel) => voxel.y))).toBeGreaterThanOrEqual(5)
    const cow = creatureModel('cow').body.map((voxel) => voxel.r)
    expect(cow.some((red) => red < 80)).toBe(true)
    expect(cow.some((red) => red > 200)).toBe(true)
    const sheep = creatureModel('sheep').body
    expect(sheep.filter((voxel) => voxel.r > 220).length).toBeGreaterThan(sheep.length / 2)
    expect(creatureModel('fish').head).toEqual([])
  })

  it('hops rabbits highest and draws a kind it does not know as a plain block', () => {
    expect(creatureModel('rabbit').hop).toBeGreaterThan(creatureModel('cow').hop)
    expect(creatureModel('gloomling').body.length).toBe(27)
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

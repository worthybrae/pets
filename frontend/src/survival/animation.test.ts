import { describe, expect, it } from 'vitest'
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import type { MimoAction } from './types'

const mine: MimoAction = { kind: 'mine', started_at: 10, ends_at: 12, target: { x: 1, y: 1, z: 0 }, block: 'dirt' }

describe('moveFor', () => {
  it('maps each step to an animation', () => {
    expect(moveFor(null, 0)).toBe('idle')
    expect(moveFor(mine, 11)).toBe('mine')
    expect(moveFor({ ...mine, kind: 'craft', recipe: 'planks' }, 11)).toBe('work')
    expect(moveFor({ kind: 'sleep', started_at: 0, ends_at: null }, 5000)).toBe('sleep')
    expect(moveFor({ kind: 'walk', started_at: 0, ends_at: 3, path: [] }, 1, true)).toBe('swim')
    expect(moveFor({ kind: 'fish', started_at: 0, ends_at: 40 }, 10)).toBe('fish')
    expect(moveFor({ kind: 'pick', started_at: 0, ends_at: 1 }, 0.5)).toBe('place')
    expect(moveFor({ kind: 'till', started_at: 0, ends_at: 1 }, 0.5)).toBe('mine')
    expect(moveFor({ kind: 'cook', started_at: 0, ends_at: 5 }, 1)).toBe('work')
  })

  it('leans over the water while fishing', () => {
    const leans = [0, 1, 2, 3, 4].map((seconds) => bodyPose('fish', seconds, 0, 0).pitch)
    expect(Math.min(...leans)).toBeGreaterThanOrEqual(0.28)
    expect(Math.max(...leans)).toBeLessThanOrEqual(0.32)
  })

  it('goes idle when a step has ended and the next has not arrived yet', () => {
    expect(moveFor(mine, 12.5)).toBe('idle')
    expect(moveFor(mine, 12.5, true)).toBe('swim')
  })
})

describe('bodyPose', () => {
  it('hops once per block while walking', () => {
    expect(bodyPose('walk', 0, 2, 0).lift).toBeCloseTo(0)
    expect(bodyPose('walk', 0, 2.5, 0).lift).toBeCloseTo(0.22)
  })

  it('swings while mining, bobs low while swimming, stretches when falling and lies down to sleep', () => {
    const swings = [0, 0.05, 0.1, 0.2, 0.3, 0.4].map((seconds) => bodyPose('mine', seconds, 0, 0).pitch)
    expect(Math.max(...swings)).toBeGreaterThan(0.3)
    expect(Math.min(...swings)).toBeGreaterThanOrEqual(0)
    expect(bodyPose('swim', 0, 0, 1).lift).toBeLessThan(-0.25)
    expect(bodyPose('fall', 0, 0, 0).stretch).toBeGreaterThan(1)
    expect(bodyPose('sleep', 0.3, 0, 0).roll).toBeCloseTo(Math.PI / 4)
    expect(bodyPose('sleep', 5, 0, 0)).toMatchObject({ roll: Math.PI / 2, lift: 0.45 })
  })
})

describe('sleep and eating details', () => {
  it('floats three z\'s one after another once the pet lies down', () => {
    expect(zPuffs(0.3).every((puff) => puff.opacity === 0)).toBe(true)
    const first = zPuffs(0.6)
    expect(first[0]).toMatchObject({ y: 0, opacity: 1 })
    expect(first[1].opacity).toBe(0)
    expect(zPuffs(20).every((puff) => puff.y >= 0 && puff.y <= 1.2)).toBe(true)
    expect(zPuffs(0.6 + 2.39)[0].opacity).toBeLessThan(0.05)
  })

  it('drops crumbs below the mouth', () => {
    const bits = crumbs(0.2)
    expect(bits).toHaveLength(3)
    expect(bits.every((bit) => bit.y <= 0 && bit.y >= -0.4)).toBe(true)
  })
})

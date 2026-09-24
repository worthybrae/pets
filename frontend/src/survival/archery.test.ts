import { describe, expect, it } from 'vitest'
import { MISS_PAST, RELEASE, arrowAt } from './archery'
import type { MimoAction } from './types'

const shot: MimoAction = { kind: 'shoot', started_at: 10, ends_at: 11, target: { x: 8, y: 1, z: 0 }, hit: true }
const pet = { x: 0, y: 1, z: 0 }
const release = 10 + RELEASE

describe('arrowAt', () => {
  it('shows no arrow while the bow is drawn, after it lands, or for any other step', () => {
    expect(arrowAt(shot, pet, 10.3)).toBeNull()
    expect(arrowAt(shot, pet, 11)).toBeNull()
    expect(arrowAt({ ...shot, kind: 'attack' }, pet, 10.8)).toBeNull()
    expect(arrowAt(null, pet, 10.8)).toBeNull()
  })

  it('flies from the pet to its target in a low arc, pointing the way it goes', () => {
    expect(arrowAt(shot, pet, release)).toMatchObject({ x: 0.5, y: 1.8, z: 0.5 })
    const middle = arrowAt(shot, pet, (release + 11) / 2)!
    expect(middle.x).toBeCloseTo(4.5)
    expect(middle.y).toBeGreaterThan(1.7)  // above the straight line from 1.8 to 1.6
    expect(middle.yaw).toBeCloseTo(Math.PI / 2)
    const early = arrowAt(shot, pet, release + 0.01)!
    const late = arrowAt(shot, pet, 10.99)!
    expect(early.pitch).toBeGreaterThan(0)
    expect(late.pitch).toBeLessThan(0)
    expect(late.x).toBeCloseTo(8.5, 0)
  })

  it('flies on past the target and drops when it misses', () => {
    const miss = arrowAt({ ...shot, hit: false }, pet, 10.99)!
    expect(miss.x).toBeGreaterThan(8.5 + MISS_PAST - 0.5)
    expect(miss.y).toBeLessThan(1.3)
  })
})

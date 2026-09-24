import { describe, expect, it } from 'vitest'
import type { Look } from './creatureMotion'
import { BURN_SECONDS, FLAME_BITS, STRIKE_SECONDS, flames, hostileLook } from './hostileMotion'
import type { Creature } from './types'

const still: Look = { lift: 0, pitch: 0, roll: 0, headPitch: 0, flash: 0, knock: 0, size: 1 }
const gloom: Creature = { id: 5, kind: 'gloomling', x: 3, y: 1, z: 0, heading: 0, health: 1, state: 'idle', hostile: true }

describe('hostileLook', () => {
  it('lunges once each time it strikes Mimo and hunches forward while it chases', () => {
    const struck = { ...gloom, state: 'attacking' as const, struck_at: 20 }
    expect(hostileLook(struck, still, 19.9, 0).pitch).toBe(0)
    expect(hostileLook(struck, still, 20 + STRIKE_SECONDS / 2, 0).pitch).toBeCloseTo(0.6)
    expect(hostileLook(struck, still, 20 + STRIKE_SECONDS, 0).pitch).toBeCloseTo(0)
    expect(hostileLook({ ...gloom, state: 'chasing' }, still, 0, 0).pitch).toBeCloseTo(0.15)
  })

  it('makes a skitter scuttle as it goes', () => {
    const skitter: Creature = { ...gloom, kind: 'skitter', state: 'chasing' }
    const rolls = [0, 0.02, 0.04, 0.06].map((clock) => hostileLook(skitter, still, 0, clock).roll)
    expect(Math.max(...rolls.map(Math.abs))).toBeGreaterThan(0.05)
    expect(hostileLook({ ...skitter, state: 'idle' }, still, 0, 0.02).roll).toBe(0)
  })

  it('flickers and shrinks while it burns', () => {
    const burning = { ...gloom, state: 'burning' as const, burning_at: 30 }
    const look = hostileLook(burning, still, 30 + BURN_SECONDS / 2, 1)
    expect(look.flash).toBeGreaterThanOrEqual(0.1)
    expect(look.size).toBeCloseTo(0.7)
    expect(hostileLook(burning, still, 30 + BURN_SECONDS, 1).size).toBeCloseTo(0.4)
  })

  it('leaves animals as they are', () => {
    const cow: Creature = { ...gloom, kind: 'cow', hostile: undefined, state: 'walking', struck_at: 20 }
    expect(hostileLook(cow, still, 20.2, 0)).toBe(still)
  })
})

describe('flames', () => {
  it('rise over a burning creature and nothing else', () => {
    const burning = { ...gloom, state: 'burning' as const, burning_at: 30 }
    const bits = flames(burning, 30.2, 1.7)
    expect(bits.length).toBe(FLAME_BITS)
    expect(bits.every((bit) => bit.y > 0.4 && bit.y < 1.7 * 1.1 && bit.scale > 0 && bit.scale <= 1)).toBe(true)
    expect(flames(gloom, 30.2, 1.7)).toEqual([])
    expect(flames(burning, 29, 1.7)).toEqual([])
  })
})

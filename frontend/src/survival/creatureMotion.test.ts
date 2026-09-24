import { describe, expect, it } from 'vitest'
import {
  BAR_SECONDS, FLASH_SECONDS, KNOCK_SECONDS, LEAP_SECONDS, PUFF_AFTER, PUFF_LENGTH, dropPops, drawn, healthBar,
  lookAt, movesById, placeAt, puffAge,
} from './creatureMotion'
import type { Creature, CreatureMove } from './types'

const cow: Creature = { id: 3, kind: 'cow', x: 12, y: 5, z: 2, heading: 1.2, health: 0.6, state: 'idle' }
const walk: CreatureMove = { id: 3, from: { x: 10, y: 5, z: 2 }, to: { x: 12, y: 5, z: 2 }, started: 100, ends: 102,
  cells: [[10, 5, 2], [11, 5, 2], [12, 5, 2]] }
const step: CreatureMove = { id: 3, from: { x: 11, y: 5, z: 2 }, to: { x: 12, y: 5, z: 2 }, started: 100, ends: 101 }

describe('placeAt', () => {
  it('replays a move cell by cell, facing the way it goes, then stands where it ended', () => {
    expect(placeAt(cow, walk, 99)).toMatchObject({ x: 10, z: 2, moving: false, travelled: 0 })
    expect(placeAt(cow, walk, 100.5)).toMatchObject({ x: 10.5, y: 5, z: 2, facing: Math.PI / 2, moving: true, travelled: 0.5 })
    expect(placeAt(cow, walk, 101.5)).toMatchObject({ x: 11.5, travelled: 1.5 })
    expect(placeAt(cow, walk, 102)).toEqual({ x: 12, y: 5, z: 2, facing: 1.2, moving: false, travelled: 0 })
    expect(placeAt(cow, step, 100.25).x).toBeCloseTo(11.25)
    expect(placeAt(cow, undefined, 100)).toMatchObject({ x: 12, facing: 1.2, moving: false })
  })

  it('finds each creature\'s move by id, and none from an API without moves', () => {
    expect(movesById([walk]).get(3)).toBe(walk)
    expect(movesById(undefined).size).toBe(0)
  })
})

describe('lookAt', () => {
  const still = placeAt(cow, undefined, 0)

  it('hops as it walks and dips its head to graze', () => {
    const halfway = lookAt(cow, { ...still, moving: true, travelled: 0.5 }, 0, 0, 0.2)
    expect(halfway.lift).toBeCloseTo(0.2)
    expect(lookAt(cow, { ...still, moving: true, travelled: 1 }, 0, 0, 0.2).lift).toBeCloseTo(0)
    expect(lookAt({ ...cow, state: 'grazing' }, still, 0, 0, 0.2).headPitch).toBeGreaterThan(0.6)
    expect(lookAt(cow, still, 0, 0, 0.2).headPitch).toBe(0)
  })

  it('flashes and is knocked back when hit, then settles', () => {
    const hit = { ...cow, hurt_at: 50 }
    expect(lookAt(hit, still, 49, 0, 0).flash).toBe(0)
    expect(lookAt(hit, still, 50, 0, 0).flash).toBe(1)
    expect(lookAt(hit, still, 50 + KNOCK_SECONDS / 2, 0, 0).knock).toBeCloseTo(0.35)
    expect(lookAt(hit, still, 50 + FLASH_SECONDS, 0, 0)).toMatchObject({ flash: 0, knock: 0 })
  })

  it('tips over when it dies and shrinks away in its puff', () => {
    const body = { ...cow, state: 'dead' as const, health: 0, dead_at: 60, drops: ['raw_beef', 'leather'] }
    expect(lookAt(body, still, 59, 0, 0)).toMatchObject({ roll: 0, size: 1 })
    expect(lookAt(body, still, 60.3, 0, 0).roll).toBeCloseTo(Math.PI / 2)
    expect(lookAt(body, still, 60 + PUFF_AFTER + PUFF_LENGTH / 2, 0, 0).size).toBeCloseTo(0.5)
    expect(drawn(body, 60 + PUFF_AFTER + PUFF_LENGTH - 0.05)).toBe(true)
    expect(drawn(body, 60 + PUFF_AFTER + PUFF_LENGTH + 0.05)).toBe(false)
    expect(drawn(cow, 1e9)).toBe(true)
  })

  it('makes a fish wiggle, and leap once when it takes the hook', () => {
    const fish: Creature = { id: 4, kind: 'fish', x: 0, y: 2, z: 0, heading: 0, health: 1, state: 'swimming', caught_at: 70 }
    const swimming = [0, 0.5, 1, 1.5].map((clock) => lookAt(fish, still, 0, clock, 0).roll)
    expect(Math.max(...swimming.map(Math.abs))).toBeGreaterThan(0.05)
    expect(lookAt(fish, still, 70 + LEAP_SECONDS / 2, 0, 0).lift).toBeGreaterThan(1)
    expect(lookAt(fish, still, 70 + LEAP_SECONDS, 0, 0).lift).toBeLessThan(0.1)
  })
})

describe('health bar, puff and drops', () => {
  it('shows the health left for a few seconds after a hit it lived through', () => {
    const hit = { ...cow, hurt_at: 50 }
    expect(healthBar(cow, 50)).toEqual({ shown: false, fraction: 0.6 })
    expect(healthBar(hit, 49)).toMatchObject({ shown: false })
    expect(healthBar(hit, 51)).toEqual({ shown: true, fraction: 0.6 })
    expect(healthBar(hit, 50 + BAR_SECONDS).shown).toBe(false)
    expect(healthBar({ ...hit, state: 'dead', dead_at: 50.5 }, 51).shown).toBe(false)
  })

  it('puffs once the body has tipped over and pops the drops out of it', () => {
    const body = { ...cow, state: 'dead' as const, dead_at: 60, drops: ['raw_beef', 'leather'] }
    expect(puffAge(body, 60.2)).toBeNull()
    expect(puffAge(body, 60 + PUFF_AFTER + 0.1)).toBeCloseTo(0.1)
    expect(puffAge(cow, 60)).toBeNull()
    const pops = dropPops(body.drops, PUFF_LENGTH)
    expect(pops.map((pop) => pop.item)).toEqual(['raw_beef', 'leather'])
    expect(pops[0].offset.x).toBeLessThan(0)
    expect(pops[1].offset.x).toBeGreaterThan(0)
    expect(pops[0].offset.y).toBeCloseTo(1.5)
    expect(dropPops(undefined, 0.3)).toEqual([])
  })
})

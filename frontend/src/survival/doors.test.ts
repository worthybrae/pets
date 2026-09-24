import { describe, expect, it } from 'vitest'
import { HELD_OPEN, OPEN_REACH, doorAxis, doorSwing } from './doors'

const door = { x: 4, y: 1, z: 7 }

describe('doors', () => {
  it('opens wide as the pet passes through and shuts behind it', () => {
    expect(doorSwing(door, { x: 4, y: 1, z: 7 })).toBe(1)
    expect(doorSwing(door, { x: 4, y: 1, z: 7 - HELD_OPEN })).toBe(1)
    expect(doorSwing(door, { x: 4, y: 1, z: 8.1 })).toBeCloseTo(0.5)
    expect(doorSwing(door, { x: 4, y: 1, z: 7 + OPEN_REACH })).toBeCloseTo(0)
    expect(doorSwing(door, { x: 4, y: 4, z: 7 })).toBe(0)
    expect(doorSwing(door, null)).toBe(0)
  })

  it('lies along the wall it stands in', () => {
    const wallAlongX = (x: number, _y: number, z: number) => z === 7 && x !== 4
    const wallAlongZ = (x: number, _y: number, z: number) => x === 4 && z !== 7
    expect(doorAxis(wallAlongX, door)).toBe('x')
    expect(doorAxis(wallAlongZ, door)).toBe('z')
  })
})

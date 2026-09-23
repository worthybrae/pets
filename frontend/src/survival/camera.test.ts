import { describe, expect, it } from 'vitest'
import { easeOffset, type Vec3 } from './camera'

/** The follow camera's normal direction (not yet normalized or scaled to a distance). */
const NORMAL: Vec3 = [18, 13, 18]
const DISTANCE = Math.hypot(...NORMAL)

function elevationDegrees([x, y, z]: Vec3): number {
  return Math.atan2(y, Math.hypot(x, z)) * (180 / Math.PI)
}

describe('easeOffset', () => {
  it('eases a steep arrival offset down to the normal elevation over a few seconds', () => {
    let offset: Vec3 = [18, 80, 18]
    for (let frame = 0; frame < 180; frame++) offset = easeOffset(offset, NORMAL, DISTANCE, 1 / 60)
    const elevation = elevationDegrees(offset)
    const normalElevation = elevationDegrees(NORMAL)
    expect(Math.abs(elevation - normalElevation)).toBeLessThan(5)
  })

  it('keeps the normal offset as a fixed point', () => {
    const result = easeOffset(NORMAL, NORMAL, DISTANCE, 1 / 30)
    expect(result[0]).toBeCloseTo(NORMAL[0])
    expect(result[1]).toBeCloseTo(NORMAL[1])
    expect(result[2]).toBeCloseTo(NORMAL[2])
  })

  it('scales the eased offset to the requested distance, not the target vector\'s own length', () => {
    const result = easeOffset(NORMAL, NORMAL, DISTANCE * 2, 5)
    expect(Math.hypot(...result)).toBeCloseTo(DISTANCE * 2, 1)
  })
})

import { describe, expect, it } from 'vitest'
import { fogRange } from './fog'

describe('fogRange', () => {
  it('starts past the camera target and hides the edge of the loaded terrain at view distance 4', () => {
    const [near, far] = fogRange(4, 26)
    expect(near).toBeCloseTo(51.6)
    expect(far).toBeCloseTo(90)
  })

  it('starts past the camera target and hides the edge of the loaded terrain at view distance 6', () => {
    const [near, far] = fogRange(6, 84)
    expect(near).toBeCloseTo(122.4)
    expect(far).toBeCloseTo(180)
  })

  it('always keeps far greater than near and greater than the camera distance', () => {
    for (const viewDistance of [4, 6]) {
      for (const cameraDistance of [26, 30, 52, 84]) {
        const [near, far] = fogRange(viewDistance, cameraDistance)
        expect(far).toBeGreaterThan(near)
        expect(far).toBeGreaterThan(cameraDistance)
      }
    }
  })
})

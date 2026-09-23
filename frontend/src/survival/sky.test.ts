import { describe, expect, it } from 'vitest'
import { DAY_SKY, daylightFactor, mixRgb, NIGHT_SKY, rgbToHex, skyColor } from './sky'

describe('daylightFactor', () => {
  it('is 1.0 by day and 0.35 at night', () => {
    expect(daylightFactor(180)).toBe(1)
    expect(daylightFactor(1500)).toBe(1)
    expect(daylightFactor(2400)).toBeCloseTo(0.35)
    expect(daylightFactor(3000)).toBeCloseTo(0.35)
  })

  it('eases down through dusk', () => {
    expect(daylightFactor(2310)).toBeCloseTo(0.675)
    let previous = daylightFactor(2220)
    for (let s = 2230; s <= 2400; s += 10) {
      const next = daylightFactor(s)
      expect(next).toBeLessThanOrEqual(previous)
      previous = next
    }
  })

  it('eases up through pre-dawn and dawn without a jump at midnight of the game day', () => {
    expect(daylightFactor(3420)).toBeCloseTo(0.35)
    expect(daylightFactor(0)).toBeCloseTo(0.675)
    expect(daylightFactor(3599.99)).toBeCloseTo(daylightFactor(0), 3)
    const samples = [3420, 3480, 3540, 3599, 0, 60, 120, 179].map(daylightFactor)
    for (let i = 1; i < samples.length; i++) expect(samples[i]).toBeGreaterThanOrEqual(samples[i - 1])
  })
})

describe('skyColor', () => {
  it('is the day sky by day and the night sky at night', () => {
    expect(skyColor(1000)).toEqual(DAY_SKY)
    expect(skyColor(3000)).toEqual(NIGHT_SKY)
  })

  it('warms up in the middle of dusk', () => {
    expect(skyColor(2310)[0]).toBeGreaterThan(mixRgb(NIGHT_SKY, DAY_SKY, 0.5)[0])
  })

  it('formats colors as hex', () => {
    expect(rgbToHex(DAY_SKY)).toBe('#dce9eb')
    expect(rgbToHex([0, 15, 255])).toBe('#000fff')
  })
})

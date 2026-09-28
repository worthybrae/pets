import { describe, expect, it } from 'vitest'
import {
  desaturate, FLASH_LIFT, FLASH_SECONDS, FOG_NEAR, flashAt, flashLevel, particleCount, RAIN_STREAKS, SNOW_FLAKES,
  weatherFog, weatherLine, weatherSky,
} from './weather'

const DAY: [number, number, number] = [0xdc, 0xe9, 0xeb]

describe('the sky in each weather', () => {
  it('greys and darkens in rain and storm, pales in fog and whitens in snow; clear keeps it', () => {
    expect(weatherSky(DAY, 'clear')).toEqual(DAY)
    expect(weatherSky(DAY, null)).toEqual(DAY)
    const sum = (rgb: number[]) => rgb[0] + rgb[1] + rgb[2]
    expect(sum(weatherSky(DAY, 'storm'))).toBeLessThan(sum(weatherSky(DAY, 'rain')))
    expect(sum(weatherSky(DAY, 'rain'))).toBeLessThan(sum(DAY))
    const fog = weatherSky(DAY, 'fog')
    expect(Math.max(...fog) - Math.min(...fog)).toBeLessThan(Math.max(...DAY) - Math.min(...DAY))
    expect(desaturate([200, 100, 0], 1)).toEqual([119, 119, 119])
  })

  it('names the weather on the HUD', () => {
    expect(weatherLine('storm')).toBe('ϟ Storm')
    expect(weatherLine('snow')).toBe('❄ Snow')
    expect(weatherLine(undefined)).toBeNull()
  })
})

describe('particles and fog', () => {
  it('draws rain streaks and snowflakes, half on a phone, none in dry weather', () => {
    expect(particleCount('rain', false)).toBe(RAIN_STREAKS)
    expect(particleCount('storm', true)).toBe(RAIN_STREAKS / 2)
    expect(particleCount('snow', false)).toBe(SNOW_FLAKES)
    expect(particleCount('fog', false)).toBe(0)
    expect(particleCount('clear', false)).toBe(0)
  })

  it('closes the fog in to a share of the view in fog', () => {
    expect(weatherFog(100, 200, 'fog')).toEqual([100 * FOG_NEAR, 200 * FOG_NEAR])
    expect(weatherFog(100, 200, 'rain')).toEqual([100, 200])
  })
})

describe('the lightning flash', () => {
  it('lifts the light three times at the strike and fades within 0.15 s', () => {
    expect(flashLevel(0)).toBe(FLASH_LIFT)
    expect(flashLevel(FLASH_SECONDS / 2)).toBeCloseTo(2)
    expect(flashLevel(FLASH_SECONDS)).toBe(1)
    expect(flashLevel(-0.01)).toBe(1)
    expect(flashAt([{ x: 0, y: 0, z: 0, at: 10 }, { x: 1, y: 0, z: 0, at: 20 }], 20.05)).toBeCloseTo(1 + 2 * (1 - 0.05 / 0.15))
    expect(flashAt([], 5)).toBe(1)
    expect(flashAt(undefined, 5)).toBe(1)
  })
})

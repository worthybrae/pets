import { mixRgb, type Rgb } from './sky'
import type { Strike, Weather } from './types'

/**
 * Wild World W2 in the viewer: how each weather tints the sky, the word and mark the HUD shows, how many rain
 * streaks and snowflakes fall, how close the fog comes, and the lightning flash. The weather is the server's
 * (backend/survival/sky.py); the viewer only draws it.
 */

export const RAIN_STREAKS = 1500
export const SNOW_FLAKES = 800
/** A lightning flash lifts the ambient and sky light this many times... */
export const FLASH_LIFT = 3
/** ...for this many seconds. */
export const FLASH_SECONDS = 0.15
/** In fog the fog closes to this share of the view distance. */
export const FOG_NEAR = 0.35
const TINTS: Partial<Record<Weather, { color: Rgb; share: number; grey: number }>> = {
  rain: { color: [0x8d, 0x9c, 0xae], share: 0.5, grey: 0.4 },
  storm: { color: [0x5c, 0x68, 0x78], share: 0.65, grey: 0.4 },
  fog: { color: [0xcc, 0xd0, 0xd2], share: 0.75, grey: 0 },
  snow: { color: [0xe2, 0xe6, 0xea], share: 0.55, grey: 0.2 },
}
const WORDS: Record<Weather, string> = { clear: 'Clear', rain: 'Rain', storm: 'Storm', fog: 'Fog', snow: 'Snow' }
const MARKS: Record<Weather, string> = { clear: '☀', rain: '☂', storm: 'ϟ', fog: '≋', snow: '❄' }

/** `rgb` with `amount` (0..1) of its color taken out toward its own grey. */
export function desaturate(rgb: Rgb, amount: number): Rgb {
  const grey = Math.round(0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2])
  return mixRgb(rgb, [grey, grey, grey], amount)
}

/** The sky's (and the fog's) color in this weather: grey-blue in rain and storm, pale grey in fog, white-grey in snow. */
export function weatherSky(base: Rgb, weather: Weather | null | undefined): Rgb {
  const tint = weather ? TINTS[weather] : undefined
  return tint ? mixRgb(desaturate(base, tint.grey), tint.color, tint.share) : base
}

/** "☂ Rain" for the HUD; null for an older API that sends no weather. */
export function weatherLine(weather: Weather | null | undefined): string | null {
  return weather ? `${MARKS[weather]} ${WORDS[weather]}` : null
}

/** Rain streaks or snowflakes to draw: half on a phone-sized screen, none in dry weather. */
export function particleCount(weather: Weather | null | undefined, small: boolean): number {
  const count = weather === 'rain' || weather === 'storm' ? RAIN_STREAKS : weather === 'snow' ? SNOW_FLAKES : 0
  return small ? Math.round(count / 2) : count
}

/** The fog's near and far in this weather: in fog both close to FOG_NEAR of what they are. */
export function weatherFog(near: number, far: number, weather: Weather | null | undefined): [number, number] {
  return weather === 'fog' ? [near * FOG_NEAR, far * FOG_NEAR] : [near, far]
}

/** How many times brighter the light is `since` seconds after a strike: FLASH_LIFT for FLASH_SECONDS, fading. */
export function flashLevel(since: number): number {
  if (since < 0 || since >= FLASH_SECONDS) return 1
  return 1 + (FLASH_LIFT - 1) * (1 - since / FLASH_SECONDS)
}

/** The brightest flash of any strike at replay time `now`. */
export function flashAt(strikes: readonly Strike[] | null | undefined, now: number): number {
  return Math.max(1, ...(strikes ?? []).map((strike) => flashLevel(now - strike.at)))
}

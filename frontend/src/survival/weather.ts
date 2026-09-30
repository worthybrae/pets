import type { CameraMode } from './cameraModes'
import { mixRgb, type Rgb } from './sky'
import type { Point, Strike, Weather } from './types'

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

/** Rain and snow fall in a box this wide and tall that follows the camera. */
export const FALL_BOX = { width: 44, height: 30 }
const FALL_SPEED: Partial<Record<Weather, number>> = { rain: 24, storm: 30, snow: 2.4 }
/** A bolt is drawn this long after its strike. */
export const BOLT_SECONDS = 0.25
const BOLT_HEIGHT = 60
export const BOLT_SEGMENTS = 9
/** Embers over a burning cell, and how long a burned-out tree smokes (game seconds). */
export const EMBERS_PER_FIRE = 3
export const SMOKE_GAME_SECONDS = 60

function hashUnit(a: number, b: number): number {
  let h = Math.imul(a | 0, 374761393) ^ Math.imul(b | 0, 668265263)
  h = Math.imul(h ^ (h >>> 13), 1274126177)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}

/** Where rain streak or snowflake `index` is at `t` seconds, in a box round `center`: it falls and wraps round,
 * and a flake drifts. */
export function fallAt(index: number, t: number, weather: Weather, center: Point): Point {
  const speed = FALL_SPEED[weather] ?? 0
  const x = (hashUnit(index, 1) - 0.5) * FALL_BOX.width, z = (hashUnit(index, 2) - 0.5) * FALL_BOX.width
  const drop = (hashUnit(index, 3) * FALL_BOX.height + t * speed) % FALL_BOX.height
  const drift = weather === 'snow' ? Math.sin(t * 0.8 + index) * 0.6 : 0
  return { x: center.x + x + drift, y: center.y + FALL_BOX.height / 2 - drop, z: center.z + z }
}

/** Rain and snow are left out under a roof when the camera is close to or in the pet. */
export function fallShown(weather: Weather | null | undefined, mode: CameraMode, sheltered: boolean): boolean {
  if (particleCount(weather, false) === 0) return false
  return !(sheltered && (mode === 'close' || mode === 'eyes'))
}

/** A jagged bolt from the sky down to the strike: BOLT_SEGMENTS + 1 points, the same for the same strike. */
export function boltPoints(strike: Strike): Point[] {
  const salt = Math.round(strike.at * 1000)
  return Array.from({ length: BOLT_SEGMENTS + 1 }, (_, k) => {
    const share = k / BOLT_SEGMENTS
    const jitter = k === BOLT_SEGMENTS ? 0 : 2.2
    return {
      x: strike.x + 0.5 + (hashUnit(salt, k * 2) - 0.5) * jitter,
      y: strike.y + 1 + BOLT_HEIGHT * (1 - share),
      z: strike.z + 0.5 + (hashUnit(salt, k * 2 + 1) - 0.5) * jitter,
    }
  })
}

/** The strikes whose bolt shows at replay time `now`. */
export function boltsAt(strikes: readonly Strike[] | null | undefined, now: number): Strike[] {
  return (strikes ?? []).filter((strike) => now >= strike.at && now < strike.at + BOLT_SECONDS)
}

/** Ember `index` of a burning cell, rising and fading over a second and a half, at `t` seconds. */
export function emberAt(cell: Point, index: number, t: number): { position: Point; scale: number } {
  const age = (t * 0.66 + hashUnit(index, cell.x * 31 + cell.z)) % 1
  return {
    position: {
      x: cell.x + 0.5 + (hashUnit(index, cell.y) - 0.5) * 0.8,
      y: cell.y + 0.6 + age * 1.6,
      z: cell.z + 0.5 + (hashUnit(cell.z, index) - 0.5) * 0.8,
    },
    scale: 1 - age,
  }
}

/** The cells burning a moment ago that are not now: a tree burned out there, and smokes. */
export function burnedOut(before: readonly Point[], now: readonly Point[]): Point[] {
  const burning = new Set(now.map((cell) => `${cell.x},${cell.y},${cell.z}`))
  return before.filter((cell) => !burning.has(`${cell.x},${cell.y},${cell.z}`))
}

/** How far toward white the sky goes in a flash that lifts the light `flash` times: none at 1, all the way at
 * FLASH_LIFT. */
export function flashWhite(flash: number): number {
  return Math.min(1, Math.max(0, (flash - 1) / (FLASH_LIFT - 1)))
}

/** The sky's color `tinted` in a flash of `flash` times the light, taken toward white by flashWhite. */
export function flashSky(tinted: Rgb, flash: number): Rgb {
  const white = flashWhite(flash)
  return white > 0 ? mixRgb(tinted, [255, 255, 255], white) : tinted
}

/** A burned-out tree's smoke: where, and when it began (replay time). */
export interface Puff { cell: Point; at: number }

/**
 * The smoke still rising at `t`, in place: a puff for each cell of `fresh` joins `smoking`, those older than `lasts`
 * seconds go, and the oldest go past `most`. The list is kept from frame to frame, not made anew in each.
 */
export function keepSmoke(smoking: Puff[], fresh: readonly Point[], t: number, lasts: number, most: number): Puff[] {
  for (const cell of fresh) smoking.push({ cell, at: t })
  let kept = 0
  for (const puff of smoking) if (t - puff.at < lasts) smoking[kept++] = puff
  smoking.length = kept
  if (kept > most) smoking.splice(0, kept - most)
  return smoking
}

/** The brightest flash of any strike at replay time `now`. */
export function flashAt(strikes: readonly Strike[] | null | undefined, now: number): number {
  return Math.max(1, ...(strikes ?? []).map((strike) => flashLevel(now - strike.at)))
}

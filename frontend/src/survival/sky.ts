import { DAY_SECONDS, wrapDay } from './clock'

export type Rgb = [number, number, number]

export const DAY_LIGHT = 1
export const NIGHT_LIGHT = 0.35
/** Today's preview sky, a deep night blue, and a warm glow for dusk and dawn. */
export const DAY_SKY: Rgb = [0xdc, 0xe9, 0xeb]
export const NIGHT_SKY: Rgb = [0x1d, 0x26, 0x3b]
export const TWILIGHT_SKY: Rgb = [0xe8, 0xa8, 0x8c]
const DAY_START = 180
const DUSK_START = 2220
const NIGHT_START = 2400
const PRE_DAWN_START = 3420
/** Pre-dawn and dawn together make one 360-second sunrise. */
const SUNRISE_SECONDS = DAY_SECONDS - PRE_DAWN_START + DAY_START

function smoothstep(t: number): number {
  const c = Math.min(1, Math.max(0, t))
  return c * c * (3 - 2 * c)
}

/** 1 in full day, 0 in full night, easing through dusk and through the sunrise. */
export function dayness(secondsIntoDay: number): number {
  const s = wrapDay(secondsIntoDay)
  if (s >= DAY_START && s < DUSK_START) return 1
  if (s >= DUSK_START && s < NIGHT_START) return 1 - smoothstep((s - DUSK_START) / (NIGHT_START - DUSK_START))
  if (s >= NIGHT_START && s < PRE_DAWN_START) return 0
  const sinceSunriseStart = s >= PRE_DAWN_START ? s - PRE_DAWN_START : s + DAY_SECONDS - PRE_DAWN_START
  return smoothstep(sinceSunriseStart / SUNRISE_SECONDS)
}

/** Terrain brightness multiplier: 1.0 by day, 0.35 at night. */
export function daylightFactor(secondsIntoDay: number): number {
  return NIGHT_LIGHT + (DAY_LIGHT - NIGHT_LIGHT) * dayness(secondsIntoDay)
}

export function mixRgb(a: Rgb, b: Rgb, t: number): Rgb {
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * t)) as Rgb
}

/** Sky and fog color: blue-grey by day, deep blue at night, warm in the middle of dusk and sunrise. */
export function skyColor(secondsIntoDay: number): Rgb {
  const light = dayness(secondsIntoDay)
  const twilight = 1 - Math.abs(light - 0.5) * 2
  return mixRgb(mixRgb(NIGHT_SKY, DAY_SKY, light), TWILIGHT_SKY, twilight * 0.45)
}

export function rgbToHex(rgb: Rgb): string {
  return `#${rgb.map((value) => value.toString(16).padStart(2, '0')).join('')}`
}

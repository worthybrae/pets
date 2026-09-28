import { mixRgb, type Rgb } from './sky'
import type { Season, SkyView } from './types'

/**
 * Wild World W2 in the viewer: the season on the HUD, a colder sky by day in winter, and how the snow cover and
 * the ice ease in and out on the terrain (the uSnow and uFrozen uniforms). The seasons are the server's
 * (backend/survival/sky.py): four of SEASON_DAYS game days each.
 */

export const SEASON_DAYS = 10
/** Seconds the drawn snow cover takes to catch up with the server's. */
export const SNOW_EASE_SECONDS = 10
/** Game seconds the ice takes to come and go at the freeze and the thaw. */
export const FREEZE_GAME_SECONDS = 60
/** A colder day sky, mixed in by day in winter. */
export const WINTER_DAY_SKY: Rgb = [0xcf, 0xdb, 0xe8]
const WINTER_SKY_SHARE = 0.55
const NAMES: Record<Season, string> = { spring: 'Spring', summer: 'Summer', autumn: 'Autumn', winter: 'Winter' }
const NEXT: Record<Season, Season> = { spring: 'summer', summer: 'autumn', autumn: 'winter', winter: 'spring' }

/** "Winter · day 34 · 6 days to spring" (the life's day number), or null for an older API that sends no sky. */
export function seasonBadge(sky: SkyView | null | undefined, dayNumber: number): string | null {
  if (!sky) return null
  const days = sky.to_next === 1 ? '1 day' : `${sky.to_next} days`
  return `${NAMES[sky.season]} · day ${dayNumber} · ${days} to ${NEXT[sky.season]}`
}

/** A value `seconds` long to go from 0 to 1, moved toward `target` for a frame of `delta` seconds. */
export function easeToward(current: number, target: number, delta: number, seconds: number): number {
  const step = seconds > 0 ? delta / seconds : 1
  return current + Math.max(-step, Math.min(step, target - current))
}

/** Real seconds the ice takes at the freeze and the thaw, at the clock's pace (game seconds a second). */
export function freezeSeconds(timeScale: number): number {
  return FREEZE_GAME_SECONDS / Math.max(timeScale, 1e-6)
}

/** The sky's color in the season: in winter a colder blue by day (`dayness` 1 by day, 0 at night). */
export function seasonSky(color: Rgb, season: Season | null | undefined, dayness: number): Rgb {
  return season === 'winter' ? mixRgb(color, WINTER_DAY_SKY, WINTER_SKY_SHARE * dayness) : color
}

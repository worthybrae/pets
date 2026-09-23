import type { Clock, ClockPhase } from './types'

/** The game clock, matching backend/survival/clock.py. */
export const DAY_SECONDS = 3600
export const PHASES: readonly { name: ClockPhase; start: number; end: number }[] = [
  { name: 'dawn', start: 0, end: 180 },
  { name: 'day', start: 180, end: 2220 },
  { name: 'dusk', start: 2220, end: 2400 },
  { name: 'night', start: 2400, end: 3420 },
  { name: 'pre_dawn', start: 3420, end: 3600 },
]
/** The sun is up from dawn to the end of dusk; the moon from night to the end of pre-dawn. */
const SUNSET = 2400

export function wrapDay(seconds: number): number {
  return ((seconds % DAY_SECONDS) + DAY_SECONDS) % DAY_SECONDS
}

export function phaseAt(secondsIntoDay: number): ClockPhase {
  const seconds = wrapDay(secondsIntoDay)
  return PHASES.find((phase) => seconds >= phase.start && seconds < phase.end)?.name ?? 'pre_dawn'
}

export interface LiveClock {
  dayNumber: number
  secondsIntoDay: number
  phase: ClockPhase
}

/** The game clock now, moved forward from the last server clock by the real time since it arrived. */
export function liveClock(clock: Clock, receivedAt: number, now: number): LiveClock {
  const total = clock.seconds_into_day + Math.max(0, now - receivedAt) * clock.time_scale
  const secondsIntoDay = wrapDay(total)
  return { dayNumber: clock.day_number + Math.floor(total / DAY_SECONDS), secondsIntoDay, phase: phaseAt(secondsIntoDay) }
}

/** Where the sun (by day) or the moon (by night) sits on the HUD dial: 0 rising on the left, 1 setting on the right. */
export function dialPosition(secondsIntoDay: number): { body: 'sun' | 'moon'; progress: number } {
  const seconds = wrapDay(secondsIntoDay)
  if (seconds < SUNSET) return { body: 'sun', progress: seconds / SUNSET }
  return { body: 'moon', progress: (seconds - SUNSET) / (DAY_SECONDS - SUNSET) }
}

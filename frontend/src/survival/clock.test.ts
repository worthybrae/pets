import { describe, expect, it } from 'vitest'
import { dialPosition, liveClock, phaseAt } from './clock'
import type { Clock } from './types'

const clock = (seconds: number, day = 1, scale = 1): Clock => ({
  day_number: day, seconds_into_day: seconds, time_of_day: seconds / 3600, phase: phaseAt(seconds),
  day_seconds: 3600, time_scale: scale,
})

describe('phaseAt', () => {
  it('matches the server phases at every boundary', () => {
    const expected: [number, string][] = [[0, 'dawn'], [179.9, 'dawn'], [180, 'day'], [2219.9, 'day'], [2220, 'dusk'],
      [2400, 'night'], [3419.9, 'night'], [3420, 'pre_dawn'], [3599.9, 'pre_dawn'], [3600, 'dawn'], [-10, 'pre_dawn']]
    for (const [seconds, phase] of expected) expect(phaseAt(seconds), String(seconds)).toBe(phase)
  })
})

describe('liveClock', () => {
  it('moves the server clock forward by the real time since it arrived', () => {
    expect(liveClock(clock(1000), 50, 60)).toEqual({ dayNumber: 1, secondsIntoDay: 1010, phase: 'day' })
  })

  it('applies the time scale and rolls into the next day', () => {
    const next = liveClock(clock(3500, 2, 60), 100, 102)
    expect(next.dayNumber).toBe(3)
    expect(next.secondsIntoDay).toBeCloseTo(20)
    expect(next.phase).toBe('dawn')
  })

  it('never runs backwards when the local clock is behind', () => {
    expect(liveClock(clock(1000), 50, 40).secondsIntoDay).toBe(1000)
  })
})

describe('dialPosition', () => {
  it('shows the sun from dawn to the end of dusk and the moon through the night', () => {
    expect(dialPosition(0)).toEqual({ body: 'sun', progress: 0 })
    expect(dialPosition(1200)).toEqual({ body: 'sun', progress: 0.5 })
    expect(dialPosition(2400)).toEqual({ body: 'moon', progress: 0 })
    expect(dialPosition(3000)).toEqual({ body: 'moon', progress: 0.5 })
  })
})

import { describe, expect, it } from 'vitest'
import { easeToward, FREEZE_GAME_SECONDS, freezeSeconds, seasonBadge, seasonSky, WINTER_DAY_SKY } from './seasons'
import type { SkyView } from './types'

const SKY: SkyView = {
  season: 'winter', day: 4, to_next: 6, weather: 'snow', until: null, snow: 0.4, frozen: true, strikes: [], fires: [],
}

describe('seasonBadge', () => {
  it('names the season, the day and the days to the next one', () => {
    expect(seasonBadge(SKY, 34)).toBe('Winter · day 34 · 6 days to spring')
    expect(seasonBadge({ ...SKY, season: 'autumn', to_next: 1 }, 30)).toBe('Autumn · day 30 · 1 day to winter')
    expect(seasonBadge(null, 3)).toBeNull()
  })
})

describe('easing the snow and the ice', () => {
  it('moves toward the target at a full swing per `seconds`, never past it', () => {
    expect(easeToward(0, 1, 1, 10)).toBeCloseTo(0.1)
    expect(easeToward(0.95, 1, 1, 10)).toBe(1)
    expect(easeToward(0.5, 0, 2, 10)).toBeCloseTo(0.3)
    expect(easeToward(0.2, 0.2, 1, 10)).toBe(0.2)
  })

  it('takes a game minute to freeze and thaw at the clock\'s pace', () => {
    expect(freezeSeconds(1)).toBe(FREEZE_GAME_SECONDS)
    expect(freezeSeconds(60)).toBe(1)
  })
})

describe('seasonSky', () => {
  it('is colder by day in winter and as it was otherwise', () => {
    const base: [number, number, number] = [0xdc, 0xe9, 0xeb]
    expect(seasonSky(base, 'summer', 1)).toEqual(base)
    expect(seasonSky(base, 'winter', 0)).toEqual(base)
    const cold = seasonSky(base, 'winter', 1)
    expect(cold[2]).toBeGreaterThanOrEqual(WINTER_DAY_SKY[2])
    expect(cold[0]).toBeLessThan(base[0])
  })
})

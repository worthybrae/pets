import { describe, expect, it } from 'vitest'
import { careLabel, causeText, clockTime, dayLabel, lifeLine, statusText, vitalBars, workerOnline } from './hud'

const vitals = { health: 100, hunger: 14.6, warmth: 34, energy: 62.4, air: 100, mood: 70 }

describe('vitalBars', () => {
  it('lists the five HUD vitals, rounded, with a warning level', () => {
    expect(vitalBars(vitals)).toEqual([
      { key: 'health', label: 'Health', value: 100, level: 'ok' },
      { key: 'hunger', label: 'Hunger', value: 15, level: 'low' },
      { key: 'warmth', label: 'Warmth', value: 34, level: 'low' },
      { key: 'energy', label: 'Energy', value: 62, level: 'ok' },
      { key: 'air', label: 'Air', value: 100, level: 'ok' },
    ])
  })

  it('marks vitals past their danger line as critical and clamps to 0..100', () => {
    const bars = vitalBars({ ...vitals, hunger: 0, warmth: 19, health: -3 })
    expect(bars.find((bar) => bar.key === 'hunger')?.level).toBe('critical')
    expect(bars.find((bar) => bar.key === 'warmth')?.level).toBe('critical')
    expect(bars.find((bar) => bar.key === 'health')).toMatchObject({ value: 0, level: 'critical' })
  })
})

describe('HUD text', () => {
  it('names the day and phase', () => {
    expect(dayLabel(3, 'pre_dawn')).toBe('Day 3 · Before dawn')
    expect(dayLabel(1, 'day')).toBe('Day 1 · Day')
  })

  it('shows game time with dawn at 06:00', () => {
    expect(clockTime(0)).toBe('06:00')
    expect(clockTime(2400)).toBe('22:00')
    expect(clockTime(3450)).toBe('05:00')
  })

  it('describes status, care, causes and whether the worker is running', () => {
    expect(statusText('sleeping')).toBe('Sleeping')
    expect(statusText('waiting_for_food')).toBe('waiting for food')
    expect(careLabel('snack', 1)).toBe('Give snack · 1 left today')
    expect(careLabel('bandage', 0)).toBe('Bandage · 0 left today')
    expect(causeText('cold')).toBe('the cold')
    expect(causeText(null)).toBe('unknown causes')
    expect(workerOnline(1005, 1000)).toBe(true)
    expect(workerOnline(1030, 1000)).toBe(false)
  })

  it('sums up a life in one line', () => {
    expect(lifeLine({ kind: 'legacy', alive: false, days: 48, cause: 'retired' })).toBe('Retired after 48 days')
    expect(lifeLine({ kind: 'survival', alive: true, days: 2, cause: null })).toBe('Alive · day 2')
    expect(lifeLine({ kind: 'survival', alive: false, days: 1, cause: 'starvation' }))
      .toBe('Survived 1 day · died of starvation')
  })
})

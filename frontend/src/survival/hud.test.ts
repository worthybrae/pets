import { describe, expect, it } from 'vitest'
import {
  actionText, careLabel, causeText, clockTime, dayLabel, lifeLine, purposeText, statusText, thingName, vitalBars,
  workerOnline,
} from './hud'

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

describe('actionText', () => {
  it('names the current step in plain words and falls back to the status', () => {
    expect(actionText({ kind: 'mine', started_at: 0, ends_at: 2, block: 'oak_log' }, 'mining')).toBe('Mining oak log')
    expect(actionText({ kind: 'craft', started_at: 0, ends_at: 1, recipe: 'planks' }, 'crafting')).toBe('Crafting planks')
    expect(actionText({ kind: 'walk', started_at: 0, ends_at: 1, path: [] }, 'walking')).toBe('Walking')
    expect(actionText({ kind: 'wait', started_at: 0, ends_at: 5 }, 'idle')).toBe('Standing still')
    expect(actionText(null, 'sleeping')).toBe('Sleeping')
  })

  it('names food and farm work without ripeness or crop stages', () => {
    expect(actionText({ kind: 'pick', started_at: 0, ends_at: 1, block: 'berry_bush_ripe' }, 'picking')).toBe('Picking berry bush')
    expect(actionText({ kind: 'harvest', started_at: 0, ends_at: 1, block: 'wheat_3' }, 'harvesting')).toBe('Harvesting wheat')
    expect(actionText({ kind: 'plant', started_at: 0, ends_at: 1, item: 'seeds', block: 'wheat_0' }, 'planting'))
      .toBe('Planting wheat')
    expect(actionText({ kind: 'fish', started_at: 0, ends_at: 40, target: { x: 1, y: 2, z: 3 } }, 'fishing')).toBe('Fishing')
    expect(actionText({ kind: 'cook', started_at: 0, ends_at: 5, item: 'raw_fish' }, 'cooking')).toBe('Cooking raw fish')
    expect(thingName('red_mushroom')).toBe('red mushroom')
  })
})

describe('purposeText', () => {
  it('names a reflex first, then the purpose, then whether Mimo is choosing', () => {
    expect(purposeText({ purpose: 'gather_wood', reflex: 'head_home', choosing: false })).toBe('Hurrying home before dark')
    expect(purposeText({ purpose: 'gather_wood', reflex: null, choosing: true })).toBe('Gathering wood')
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Build shelter')
    expect(purposeText({ purpose: 'forage', reflex: null, choosing: false })).toBe('Foraging for food')
    expect(purposeText({ purpose: 'farm', reflex: null, choosing: false })).toBe('Tending the farm')
    expect(purposeText({ purpose: null, reflex: null, choosing: true })).toBe('Deciding what to do')
    expect(purposeText({ purpose: null, reflex: null, choosing: false })).toBe('Taking it easy')
  })
})

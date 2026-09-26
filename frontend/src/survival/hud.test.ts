import { describe, expect, it } from 'vitest'
import {
  DANGER_REACH, DANGER_RISE, actionText, careLabel, causeText, chestText, clockTime, dangerText, dayLabel, homeText, hurtFlashDelay,
  lifeLine, purposeText, statusText, thingName, vitalBars, workerOnline,
} from './hud'
import { REPLAY_DELAY } from './replay'
import type { Built, Chests, Creature } from './types'

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
    expect(lifeLine({ kind: 'survival', alive: false, days: 3, cause: 'gloomling' }))
      .toBe('Survived 3 days · caught by a gloomling')
  })
})

describe('danger', () => {
  const gloom: Creature = { id: 1, kind: 'gloomling', x: 5, y: 1, z: 0, heading: 0, health: 1, state: 'chasing', hostile: true }
  const here = { x: 0, y: 1, z: 0 }

  it('warns of the hostile creatures close to Mimo', () => {
    expect(dangerText([gloom], here)).toBe('A gloomling is close!')
    expect(dangerText([gloom, { ...gloom, id: 2, x: -3 }], here)).toBe('2 gloomlings are close!')
    expect(dangerText([gloom, { ...gloom, id: 3, kind: 'skitter' }], here)).toBe('2 creatures are close!')
    const cow: Creature = { ...gloom, id: 4, kind: 'cow', hostile: undefined }
    expect(dangerText([cow, { ...gloom, x: DANGER_REACH + 1 }, { ...gloom, state: 'burning' }, { ...gloom, state: 'dead' }], here))
      .toBeNull()
    expect(dangerText(undefined, here)).toBeNull()
  })

  it('leaves out what is far above or below Mimo, as the server does', () => {
    expect(dangerText([{ ...gloom, y: here.y - DANGER_RISE - 1 }], here)).toBeNull() // a cave under its feet
    expect(dangerText([{ ...gloom, y: here.y + DANGER_RISE + 1 }], here)).toBeNull()
    expect(dangerText([{ ...gloom, y: here.y - DANGER_RISE }], here)).toBe('A gloomling is close!')
  })

  it('keeps quiet while Mimo is safe inside the shelter it built', () => {
    const outside = [gloom, { ...gloom, id: 2, x: -3 }, { ...gloom, id: 3, z: 4 }, { ...gloom, id: 4, z: -4 }]
    expect(dangerText(outside, here, true)).toBeNull()
    expect(dangerText(outside, here, false)).toBe('4 gloomlings are close!')
  })

  it('flashes for a blow when the pet drawn behind the server takes it', () => {
    expect(hurtFlashDelay(100, 100.5)).toBeCloseTo(REPLAY_DELAY - 0.5)
    expect(hurtFlashDelay(100, 102)).toBe(0)
    expect(hurtFlashDelay(100, 104)).toBeNull()
    expect(hurtFlashDelay(null, 100)).toBeNull()
    expect(hurtFlashDelay(undefined, 100)).toBeNull()
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
    expect(actionText({ kind: 'attack', started_at: 0, ends_at: 0.6, target: { x: 1, y: 2, z: 3 } }, 'attacking'))
      .toBe('Attacking')
    expect(actionText({ kind: 'shoot', started_at: 0, ends_at: 1, target: { x: 1, y: 2, z: 3 }, hit: true }, 'shooting'))
      .toBe('Shooting')
    expect(thingName('red_mushroom')).toBe('red mushroom')
  })
})

describe('purposeText', () => {
  it('names a reflex first, then the purpose, then whether Mimo is choosing', () => {
    expect(purposeText({ purpose: 'gather_wood', reflex: 'head_home', choosing: false })).toBe('Hurrying home before dark')
    expect(purposeText({ purpose: 'gather_wood', reflex: null, choosing: true })).toBe('Gathering wood')
    expect(purposeText({ purpose: 'build_shelter', reflex: null, choosing: false })).toBe('Building a shelter')
    expect(purposeText({ purpose: 'light_up', reflex: null, choosing: false })).toBe('Lighting torches')
    expect(purposeText({ purpose: 'mend_fences', reflex: null, choosing: false })).toBe('Mend fences')
    expect(purposeText({ purpose: 'forage', reflex: null, choosing: false })).toBe('Foraging for food')
    expect(purposeText({ purpose: 'farm', reflex: null, choosing: false })).toBe('Tending the farm')
    expect(purposeText({ purpose: 'hunt', reflex: null, choosing: false })).toBe('Hunting')
    expect(purposeText({ purpose: 'make_gear', reflex: null, choosing: false })).toBe('Making gear')
    expect(purposeText({ purpose: 'gather_flint', reflex: null, choosing: false })).toBe('Digging for flint')
    expect(purposeText({ purpose: 'build_pen', reflex: null, choosing: false })).toBe('Building a pen')
    expect(purposeText({ purpose: 'stock_pen', reflex: null, choosing: false })).toBe('Planting creature seeds')
    expect(purposeText({ purpose: 'sleep', reflex: 'fight', choosing: false })).toBe('Fighting back!')
    expect(purposeText({ purpose: 'sleep', reflex: 'flee', choosing: false })).toBe('Running away!')
    expect(purposeText({ purpose: null, reflex: null, choosing: true })).toBe('Deciding what to do')
    expect(purposeText({ purpose: null, reflex: null, choosing: false })).toBe('Taking it easy')
  })

  it('names what Mimo does when it makes things', () => {
    expect(purposeText({ purpose: 'gather_materials', reflex: null, choosing: false })).toBe('Gathering materials')
    expect(purposeText({ purpose: 'build_workshop', reflex: null, choosing: false })).toBe('Building the workshop')
    expect(purposeText({ purpose: 'decorate_home', reflex: null, choosing: false })).toBe('Making home cozy')
  })
})

describe('building', () => {
  const hut = { id: 1, kind: 'shelter' as const, name: "Pip's Snug Cottage", status: 'building' as const, x: 1, y: 2, z: 3 }

  it('names the chest and hand work', () => {
    expect(actionText({ kind: 'store', started_at: 0, ends_at: 0.3, item: 'dirt' }, 'storing')).toBe('Putting away dirt')
    expect(actionText({ kind: 'take', started_at: 0, ends_at: 0.3, item: 'bread' }, 'taking')).toBe('Taking out bread')
    expect(actionText({ kind: 'drop', started_at: 0, ends_at: 0.3, item: 'red_mushroom' }, 'dropping'))
      .toBe('Dropping red mushroom')
    expect(actionText({ kind: 'place', started_at: 0, ends_at: 0.3, block: 'cobblestone' }, 'building'))
      .toBe('Placing cobblestone')
  })

  it('says where home is: the shelter Mimo built, or the one it is building', () => {
    expect(homeText([])).toBeNull()
    expect(homeText([hut])).toBe("Building Pip's Snug Cottage")
    expect(homeText([{ ...hut, status: 'done' }, { ...hut, id: 2, kind: 'farm', name: "Pip's farm" }]))
      .toBe("Home: Pip's Snug Cottage")
  })

  it('sums up what the chests hold, most first', () => {
    expect(chestText({})).toBeNull()
    expect(chestText({ '1,2,3': { dirt: 40, red_mushroom: 2 }, '5,2,3': { dirt: 2, gravel: 5, sand: 0 } }))
      .toBe('42 dirt, 5 gravel, 2 red mushroom')
  })

  it('reads a snapshot from an older API with no structures or chests', () => {
    // Fix wave minor 4: an API from before M5 sends neither field.
    const older = JSON.parse('{}') as { structures: Built[]; chests: Chests }
    expect(homeText(older.structures)).toBeNull()
    expect(chestText(older.chests)).toBeNull()
    expect(homeText(null)).toBeNull()
    expect(chestText(null)).toBeNull()
  })
})

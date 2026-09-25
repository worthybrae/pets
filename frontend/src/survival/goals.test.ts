import { describe, expect, it } from 'vitest'
import { curiosityBar, goalHint, goalLine, otherEvents, planSteps, reachedLine, tripLines } from './goals'
import { purposeText } from './hud'
import type { Goal, Trip } from './types'

const goal: Goal = {
  name: 'iron_tools', title: 'Iron tools', why: 'Stone only goes so far.', progress: 0.404, picker: 'jev', since: 10,
  plan: [
    { text: 'Find iron ore', done: true }, { text: 'Mine 3 iron ore', done: false },
    { text: 'Make an iron pickaxe', done: false }, { text: 'Take time to wander and see something new', done: false },
    { text: 'A fifth step', done: false },
  ],
}

describe('the goal line', () => {
  it('names the goal and its progress in whole percent', () => {
    expect(goalLine(goal)).toEqual({ label: 'Goal: Iron tools', percent: 40 })
    expect(goalLine({ ...goal, progress: 1.3 })?.percent).toBe(100)
    expect(goalLine({ ...goal, progress: -0.2 })?.percent).toBe(0)
  })

  it('is left out without a goal, or with an API from before goals', () => {
    expect(goalLine(null)).toBeNull()
    expect(goalLine(undefined)).toBeNull()
    expect(planSteps(undefined)).toEqual([])
    expect(goalHint(null)).toBeUndefined()
  })

  it('says why and who chose it', () => {
    expect(goalHint(goal)).toBe('Stone only goes so far. Jev chose it.')
    expect(goalHint({ ...goal, picker: 'utility' })).toBe('Stone only goes so far. The rules chose it.')
  })

  it("shows the first four steps of today's plan, the time to wander among them", () => {
    expect(planSteps(goal).map((step) => step.text))
      .toEqual(['Find iron ore', 'Mine 3 iron ore', 'Make an iron pickaxe', 'Take time to wander and see something new'])
  })

  it('names the purposes goals add', () => {
    expect(purposeText({ purpose: 'improve_home', reflex: null, choosing: false })).toBe('Building a bigger home')
    expect(purposeText({ purpose: 'stock_larder', reflex: null, choosing: false })).toBe('Stocking the larder')
  })
})

describe('goals reached', () => {
  it('lists each with the day it was reached', () => {
    expect(reachedLine({ name: 'first_shelter', title: 'A home of its own', day: 2 })).toBe('A home of its own · day 2')
  })

  it('leaves the goal events out of the notable ones, since the goals have a list of their own', () => {
    const events = [
      { id: 3, at: 30, kind: 'death', text: 'Pip died of the cold on day 4.' },
      { id: 2, at: 20, kind: 'goal', text: 'Pip reached a goal: iron tools.' },
      { id: 1, at: 10, kind: 'built', text: "Pip finished building Pip's Snug Cabin and moved in." },
    ]
    expect(otherEvents(events).map((event) => event.id)).toEqual([3, 1])
  })
})

describe('the explore trip', () => {
  const trip: Trip = { reason: 'iron', words: 'look for iron', why: 'my pickaxe needs it', direction: 'north', found: null }

  it('says what Mimo looks for, which way and why', () => {
    expect(tripLines(trip)).toEqual({ label: 'Exploring to look for iron', detail: 'Heading north: my pickaxe needs it' })
  })

  it('says what it found', () => {
    expect(tripLines({ ...trip, found: 'a cave mouth' })?.detail).toBe('Found a cave mouth')
  })

  it('is left out when Mimo is not exploring, or with an API from before trips', () => {
    expect(tripLines(null)).toBeNull()
    expect(tripLines(undefined)).toBeNull()
  })
})

describe('the curiosity bar', () => {
  it('shows the level in whole percent and how Mimo feels', () => {
    expect(curiosityBar({ level: 72.6, feeling: 'restless; nothing new for 2 game days' }))
      .toEqual({ percent: 73, hint: 'Restless; nothing new for 2 game days' })
    expect(curiosityBar({ level: 130, feeling: 'very restless; nothing new yet' })?.percent).toBe(100)
  })

  it('is left out before curiosity is tended, or with an API from before it', () => {
    expect(curiosityBar(null)).toBeNull()
    expect(curiosityBar(undefined)).toBeNull()
  })
})

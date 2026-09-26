import { describe, expect, it } from 'vitest'
import { VISIT_EVERY_MS, canName, heartMeter, inboxLabel, kindLabel, nameProblem, newestItem, promiseLine, visitDue } from './bond'
import type { InboxItem } from './bondTypes'

const ask: InboxItem = {
  id: 9, at: 100, kind: 'ask', text: 'I found a cave north of home. What should we call it?',
  data: { ask: 'name', words: 'a cave north of home' }, read: false,
}

describe('the heart meter', () => {
  it('fills a heart for every 20 points, halves rounding up, and says how close Mimo feels', () => {
    expect(heartMeter({ level: 62, feeling: 'close' })).toEqual({ full: 4, label: 'Bond 62 · close' })
    expect(heartMeter({ level: 0, feeling: 'shy' })).toEqual({ full: 0, label: 'Bond 0 · shy' })
    expect(heartMeter({ level: 100, feeling: 'devoted' })?.full).toBe(5)
    expect(heartMeter(undefined)).toBeNull()
  })

  it('names the request Mimo took up while it lasts', () => {
    const taken = { goal: 'herd', title: 'A herd of its own', until: 500 }
    expect(promiseLine(taken, 400)).toBe('Promised: A herd of its own')
    expect(promiseLine(taken, 500)).toBe('')
    expect(promiseLine(null, 400)).toBe('')
  })
})

describe('the inbox', () => {
  it('counts unread messages on its button and names their kinds', () => {
    expect(inboxLabel({ unread: 3, newest: [] })).toBe('Inbox (3)')
    expect(inboxLabel({ unread: 0, newest: [] })).toBe('Inbox')
    expect(inboxLabel(undefined)).toBe('Inbox')
    expect(kindLabel('ask')).toBe('Asks you')
    expect(kindLabel('something new')).toBe('News')
    expect(newestItem([ask, { ...ask, id: 4 }])).toBe(9)
  })

  it('takes a name for a place Mimo asked about, once', () => {
    expect(canName(ask)).toBe(true)
    expect(canName({ ...ask, data: { ...ask.data, answer: 'Echo Hollow' } })).toBe(false)
    expect(canName({ ...ask, data: { care: 'snack' } })).toBe(false)
    expect(nameProblem('Echo Hollow')).toBeNull()
    expect(nameProblem('  ')).toBe('Write a name first.')
    expect(nameProblem('<b>')).toContain('letters, digits')
    expect(nameProblem('x'.repeat(25))).toContain('1 to 24')
  })
})

describe('visits', () => {
  it('are told when the viewer opens and every ten minutes while the tab shows', () => {
    expect(visitDue(null, 0, true)).toBe(true)
    expect(visitDue(0, VISIT_EVERY_MS - 1, true)).toBe(false)
    expect(visitDue(0, VISIT_EVERY_MS, true)).toBe(true)
    expect(visitDue(0, VISIT_EVERY_MS, false)).toBe(false)
  })
})

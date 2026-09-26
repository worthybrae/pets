import { describe, expect, it } from 'vitest'
import {
  VISIT_EVERY_MS, answeredLine, canName, heartMeter, inboxLabel, kindLabel, nameProblem, newestItem, promiseLine, unreadIds,
  visitDue,
} from './bond'
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

  it('shows a promise waiting for its goal, and a shy maybe softly (Bond final fix wave, I5 and m6)', () => {
    const waiting = { goal: 'thinking_machine', title: 'A thinking machine', until: null, after: 'First circuits' }
    expect(promiseLine(waiting, 1_000_000)).toBe('Promised, after first circuits: A thinking machine')
    expect(promiseLine({ goal: 'cave', title: 'Look into a cave', until: 500, maybe: true }, 400)).toBe('Maybe later: Look into a cave')
    expect(promiseLine({ goal: 'cave', title: 'Look into a cave', until: null, after: 'A herd of its own', maybe: true }, 400))
      .toBe('Maybe later: Look into a cave')
  })
})

describe('the inbox', () => {
  it('counts unread messages on its button and names their kinds', () => {
    expect(inboxLabel({ unread: 3, newest: [] })).toBe('Inbox (3)')
    expect(inboxLabel({ unread: 0, newest: [] })).toBe('Inbox')
    expect(inboxLabel(undefined)).toBe('Inbox')
    expect(kindLabel('ask')).toBe('Asks you')
    expect(kindLabel('something new')).toBe('News')
    // Bond's final fix wave (m1): a seed hatching is no first sighting, and a find is a discovery.
    expect(kindLabel('hatched')).toBe('Hatched')
    expect(kindLabel('found')).toBe('Discovery')
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

  it('marks read only the unread messages it listed, and says what answered an ask (I7, m14)', () => {
    expect(unreadIds([ask, { ...ask, id: 4, read: true }, { ...ask, id: 2 }])).toEqual([9, 2])
    expect(answeredLine({ ...ask, data: { ...ask.data, answer: 'Echo Hollow' } })).toBe('You named it Echo Hollow.')
    expect(answeredLine({ ...ask, data: { care: 'snack', done: true } })).toBe('You gave it a snack.')
    expect(answeredLine({ ...ask, data: { care: 'bandage', done: true } })).toBe('You gave it a bandage.')
    expect(answeredLine({ ...ask, data: { care: 'snack' } })).toBe('')
    expect(answeredLine(ask)).toBe('')
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

import { describe, expect, it } from 'vitest'
import { expeditionLine, journalButton, journalEntries, journalTitle } from './journal'
import { purposeText } from './hud'
import type { Expedition, JournalEntry } from './types'

const journal: JournalEntry[] = [
  {
    thing: 'skitter', kind: 'creature', words: 'a skitter', fact: 'Skitters come out of caves at night.',
    line: 'Skitters crawl out of the caves at night.', unlocks: '', at: 20,
  },
  {
    thing: 'gravel', kind: 'block', words: 'gravel', fact: 'Gravel sometimes hides flint.',
    line: 'Gravel sometimes hides flint.', unlocks: 'digs gravel for flint', at: 10,
  },
]

const out: Expedition = { phase: 'out', direction: 'east', far: 132, target: 180, nights: 1, camping: false }

describe('the journal', () => {
  it('is titled for the pet and counts its lessons on the button', () => {
    expect(journalTitle('Pebble')).toBe('What Pebble has learned')
    expect(journalButton(journal)).toBe('Journal (2)')
    expect(journalButton([])).toBe('Journal')
    expect(journalButton(undefined)).toBe('Journal')
  })

  it('lists each lesson in Mimo\'s voice, with the plain fact when Jev phrased it and what it unlocks', () => {
    expect(journalEntries(journal, 'Pebble')).toEqual([
      { key: 'skitter', label: 'Creature', line: 'Skitters crawl out of the caves at night.',
        fact: 'Skitters come out of caves at night.', unlocks: null },
      { key: 'gravel', label: 'Block', line: 'Gravel sometimes hides flint.', fact: null,
        unlocks: 'Now Pebble digs gravel for flint.' },
    ])
    expect(journalEntries(undefined, 'Pebble')).toEqual([])
  })
})

describe('the expedition line', () => {
  it('follows the expedition from packing to home', () => {
    expect(expeditionLine({ ...out, phase: 'packing', direction: null, far: 0, target: null, nights: 0 }))
      .toBe('Expedition: packing food and torches')
    expect(expeditionLine({ ...out, nights: 0 })).toBe('Expedition east · 132 of 180 blocks out')
    expect(expeditionLine(out)).toBe('Expedition east · 132 of 180 blocks out · 1 night out')
    expect(expeditionLine({ ...out, camping: true })).toBe('Expedition: making camp for the night')
    expect(expeditionLine({ ...out, phase: 'homeward', nights: 2 })).toBe('Expedition: heading home · 2 nights out')
    expect(expeditionLine({ ...out, phase: 'home' })).toBe('Expedition: home again')
  })

  it('is left out without an expedition, or with an API from before them', () => {
    expect(expeditionLine(null)).toBeNull()
    expect(expeditionLine(undefined)).toBeNull()
  })

  it('names the purposes expeditions and the journal add', () => {
    expect(purposeText({ purpose: 'investigate', reflex: null, choosing: false })).toBe('Taking a closer look')
    expect(purposeText({ purpose: 'camp', reflex: null, choosing: false })).toBe('Making camp')
    expect(purposeText({ purpose: 'come_home', reflex: null, choosing: false })).toBe('Coming home from an expedition')
  })
})

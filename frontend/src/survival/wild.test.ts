import { describe, expect, it } from 'vitest'
import {
  ASK_BUBBLE_SECONDS, SICK_HOP, SICK_TINT, ailmentLine, askBubble, canAnswer, closedLine, lessonCounts, memorialLessons,
  petAilment, questionsLabel, shiverAt, survivalEntries, wildBadge,
} from './wild'
import type { InboxItem } from './bondTypes'
import type { Ailments, SurvivalLesson } from './types'

const TUMMY: Ailments = { sick: { kind: 'tummy', label: 'Tummy ache', words: 'My tummy hurts.', minutes: 7 }, wound: null }
const LESSONS: SurvivalLesson[] = [
  { name: 'berries', words: 'red berries', fact: 'Bright red berries are safe to eat.', known: true, source: 'from_you' },
  { name: 'fire', words: 'a campfire', fact: 'Two logs and three sticks make a campfire.', known: true, source: 'figured' },
  { name: 'bed', words: 'a bed', fact: 'Six planks make a bed.', known: false, source: null },
]

function question(data: InboxItem['data']): InboxItem {
  return { id: 1, at: 10, kind: 'ask', text: 'Can I eat them?', data, read: false }
}

describe('wild', () => {
  it('says what ails Mimo on the HUD, and nothing when it is well', () => {
    expect(ailmentLine(TUMMY)).toBe('Tummy ache · 7 min')
    expect(ailmentLine({ sick: { kind: 'chill', label: 'Chill', words: '', minutes: 18 }, wound: null })).toBe('Chill · 18 min')
    expect(ailmentLine({ sick: null, wound: { festering: true, dressed: false, minutes: 40 } })).toBe('Wound festering')
    expect(ailmentLine({ ...TUMMY, wound: { festering: false, dressed: true, minutes: 3 } })).toBe('Tummy ache · 7 min · Wound dressed')
    expect(ailmentLine({ sick: null, wound: null })).toBeNull()
    expect(ailmentLine(undefined)).toBeNull()
  })

  it('badges a wild pet and counts its open questions', () => {
    expect(wildBadge('wild')).toBe('Wild')
    expect(wildBadge('gentle')).toBeNull()
    expect(wildBadge(undefined)).toBeNull()
    expect(questionsLabel({ unread: 1, newest: [], questions: [{ id: 1, text: 'a', chips: ['x'], yes_no: false }] })).toBe('? 1')
    expect(questionsLabel({ unread: 0, newest: [] })).toBeNull()
  })

  it('offers chips on an open question and words on a closed one', () => {
    expect(canAnswer(question({ ask: 'wonder', chips: ['Yes', 'No'] }))).toBe(true)
    expect(canAnswer(question({ ask: 'wonder', chips: ['Yes'], closed: 'taught' }))).toBe(false)
    expect(canAnswer(question({ ask: 'name' }))).toBe(false)
    expect(closedLine(question({ ask: 'wonder', closed: 'taught' }))).toBe('You told me')
    expect(closedLine(question({ ask: 'wonder', closed: 'doubted' }))).toBe('Not sure about that one')
    expect(closedLine(question({ ask: 'wonder', closed: 'figured' }))).toBe('I figured it out')
    expect(closedLine(question({ ask: 'wonder' }))).toBe('')
  })

  it('lists the survival lessons with their sources, the unknown ones as "?", and tallies them', () => {
    expect(survivalEntries(LESSONS).map((entry) => [entry.line, entry.source])).toEqual([
      ['Bright red berries are safe to eat.', 'from you'], ['Two logs and three sticks make a campfire.', 'worked it out'],
      ['?', null]])
    expect(lessonCounts(LESSONS)).toEqual({ fromYou: 1, figured: 1 })
    expect(memorialLessons(LESSONS)).toBe('1 lesson from you · 1 worked out alone')
    expect(memorialLessons([])).toBeNull()
  })

  it('shows a sickness, a chill and a wound on the pet', () => {
    expect(petAilment(TUMMY)).toEqual({ tint: SICK_TINT, droop: true, hop: SICK_HOP, shiver: false, wrap: false, mark: false })
    expect(petAilment({ sick: { kind: 'chill', label: 'Chill', words: '', minutes: 1 }, wound: null }).shiver).toBe(true)
    expect(petAilment({ sick: null, wound: { festering: true, dressed: false, minutes: 1 } }))
      .toEqual({ tint: 0, droop: false, hop: 1, shiver: false, wrap: false, mark: true })
    expect(petAilment(null).tint).toBe(0)
    expect(shiverAt(0.1)).not.toBe(0)
    expect(shiverAt(1.5)).toBe(0)
  })

  it('floats a "?" over the pet for a few seconds after it asks', () => {
    const asked = [{ id: 1, text: 'a', chips: [], yes_no: false, at: 100 }]
    expect(askBubble(asked, 100 + ASK_BUBBLE_SECONDS - 1)).toBe(true)
    expect(askBubble(asked, 100 + ASK_BUBBLE_SECONDS + 1)).toBe(false)
    expect(askBubble([], 100)).toBe(false)
  })
})

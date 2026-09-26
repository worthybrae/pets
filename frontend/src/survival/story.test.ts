import { describe, expect, it } from 'vitest'
import type { DiaryEntry, InboxView } from './bondTypes'
import { NOTIFY_KEY, diaryLines, loadNotify, newestUnread, notifyPlan, saveNotify, storyToShow } from './story'

const story: DiaryEntry = { id: 12, at: 100, day: 3, text: 'Day 3 was a good one. I ate. I hope you visit again soon.', writer: 'rules', read: false }

describe('the story', () => {
  it('shows first while it is unread, until the owner closes it', () => {
    expect(storyToShow(story, 0)).toBe(story)
    expect(storyToShow(story, 12)).toBeNull()
    expect(storyToShow({ ...story, read: true }, 0)).toBeNull()
    expect(storyToShow(null, 0)).toBeNull()
    expect(storyToShow(undefined, 0)).toBeNull()
  })

  it('lists the diary by day for the memorial', () => {
    expect(diaryLines([story])).toEqual([{ key: 12, day: 'Day 3', text: story.text }])
    expect(diaryLines(undefined)).toEqual([])
  })

  it('names every day a story of a long absence tells (pre-flight 2)', () => {
    expect(diaryLines([{ ...story, last: 7 }])[0].day).toBe('Days 3 to 7')
    expect(diaryLines([{ ...story, last: null }])[0].day).toBe('Day 3')
  })
})

describe('notifications', () => {
  const inbox: InboxView = {
    unread: 3,
    newest: [
      { id: 9, at: 3, kind: 'danger', text: 'I saw a gloomling coming.', data: {}, read: false },
      { id: 8, at: 2, kind: 'found', text: 'I met my first skitter.', data: {}, read: false },
      { id: 5, at: 1, kind: 'report', text: 'I reached a goal: iron tools.', data: {}, read: false },
    ],
  }

  it('tell of the messages newer than the last told, in one notification', () => {
    expect(newestUnread(inbox)).toBe(9)
    expect(notifyPlan(inbox, 8, 'Pebble')).toEqual({ title: 'Pebble: Danger', body: 'I saw a gloomling coming.', upTo: 9 })
    expect(notifyPlan(inbox, 5, 'Pebble')).toEqual({ title: '2 new messages from Pebble', body: 'I saw a gloomling coming.', upTo: 9 })
    expect(notifyPlan(inbox, 9, 'Pebble')).toBeNull()
    expect(notifyPlan(undefined, 0, 'Pebble')).toBeNull()
  })

  it('are off until the owner turns them on, and the choice is remembered', () => {
    const saved = new Map<string, string>()
    const storage = () => ({ getItem: (key: string) => saved.get(key) ?? null, setItem: (key: string, value: string) => { saved.set(key, value) } })
    expect(loadNotify(storage)).toBe(false)
    saveNotify(storage, true)
    expect(saved.get(NOTIFY_KEY)).toBe('on')
    expect(loadNotify(storage)).toBe(true)
    expect(loadNotify(() => { throw new Error('blocked') })).toBe(false)
  })
})

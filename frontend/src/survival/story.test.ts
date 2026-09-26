import { describe, expect, it } from 'vitest'
import type { DiaryEntry, InboxView } from './bondTypes'
import {
  NOTIFY_KEY, diaryLines, loadNotify, memorialDiary, newestUnread, notifyPlan, notifyShown, saveNotify, storyToShow,
} from './story'

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

  it('pops up a story about an absence whenever it arrives, and never one written for an owner who was there', () => {
    // Bond follow-up, N3 (the controller's ruling amending I4): after a laptop sleep the owed story comes minutes
    // after the viewer opened, and still pops up; a story written while the owner watched never does.
    const owed = { ...story, id: 13, day: 4, last: 9 }
    expect(storyToShow(owed, 0)).toBe(owed)
    expect(storyToShow({ ...owed, present: false }, 0)).toEqual({ ...owed, present: false })
    expect(storyToShow({ ...story, present: true }, 0)).toBeNull()
    expect(storyToShow({ ...owed, present: true }, 0)).toBeNull()
    expect(storyToShow(owed, 13)).toBeNull()  // closed
  })

  it('shows every story on the memorial, from the life\'s own detail (I8)', () => {
    const stories = Array.from({ length: 25 }, (_, index) => ({ ...story, id: index + 1, day: index + 1 }))
    expect(memorialDiary(stories.slice(-10), { diary: stories })).toHaveLength(25)
    expect(memorialDiary(stories.slice(-10), null)).toHaveLength(10)  // until the detail comes
    expect(memorialDiary(undefined, { diary: undefined })).toEqual([])
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
    expect(notifyPlan(inbox, 8, 'Pebble')).toEqual({ notice: { title: 'Pebble: Danger', body: 'I saw a gloomling coming.' }, upTo: 9 })
    expect(notifyPlan(inbox, 5, 'Pebble')).toEqual({
      notice: { title: '2 new messages from Pebble', body: 'I saw a gloomling coming.' }, upTo: 9,
    })
    expect(notifyPlan(inbox, 9, 'Pebble')).toBeNull()
    expect(notifyPlan(undefined, 0, 'Pebble')).toBeNull()
  })

  it('never claim a count the five newest cannot show (m11)', () => {
    const many: InboxView = { unread: 40, newest: [9, 8, 7, 6, 5].map((id) => ({ ...inbox.newest[0], id })) }
    expect(notifyPlan(many, 0, 'Pebble')?.notice?.title).toBe('New messages from Pebble')
  })

  it('move the mark past a story written for an owner who was there, and never tell of it (N4)', () => {
    // The re-review's probe: with only a present story new, the mark never moved, so switching tabs told it.
    const watched: InboxView = {
      unread: 1, newest: [{ ...inbox.newest[0], id: 50, kind: 'story', text: 'Day 3 was a good one.', data: { present: true } }],
    }
    expect(notifyPlan(watched, 49, 'Clover')).toEqual({ notice: null, upTo: 50 })
    expect(notifyPlan(watched, 50, 'Clover')).toBeNull()
    const away: InboxView = { unread: 1, newest: [{ ...watched.newest[0], data: { present: false } }] }
    expect(notifyPlan(away, 49, 'Clover')).toEqual({ notice: { title: 'Clover: While you were away', body: 'Day 3 was a good one.' }, upTo: 50 })
    const both: InboxView = { unread: 2, newest: [watched.newest[0], { ...inbox.newest[0], id: 48 }] }
    expect(notifyPlan(both, 47, 'Clover')).toEqual({ notice: { title: 'Clover: Danger', body: 'I saw a gloomling coming.' }, upTo: 50 })
  })

  it('show as on only while the browser still grants them (Task 15)', () => {
    expect(notifyShown(true, 'granted')).toBe(true)
    expect(notifyShown(true, 'denied')).toBe(false)
    expect(notifyShown(true, undefined)).toBe(false)
    expect(notifyShown(false, 'granted')).toBe(false)
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

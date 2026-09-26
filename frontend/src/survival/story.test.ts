import { describe, expect, it } from 'vitest'
import type { DiaryEntry, InboxView } from './bondTypes'
import {
  NOTIFY_KEY, awayLongEnough, diaryLines, gameDayMs, loadNotify, memorialDiary, newestUnread, notifyPlan, notifyShown,
  openedStoryId, saveNotify, storyOnOpen, storyToShow,
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

  it('pops up only the story unread when the viewer opened, never one written while the owner watches (I4)', () => {
    const opened = openedStoryId(story)
    expect(opened).toBe(12)
    expect(storyOnOpen(opened, story, 0)).toBe(story)
    const grown = { ...story, last: 5, text: 'Days 3 to 5 were busy ones.' }
    expect(storyOnOpen(opened, grown, 0)).toBe(grown)  // the same story, grown while unread
    const newer = { ...story, id: 13, day: 4 }
    expect(storyOnOpen(opened, newer, 0)).toBeNull()  // written mid-session: quietly to the inbox and diary
    expect(storyOnOpen(opened, story, 12)).toBeNull()  // closed
    expect(storyOnOpen(openedStoryId({ ...story, read: true }), story, 0)).toBeNull()
    expect(openedStoryId(null)).toBeNull()
    expect(storyOnOpen(null, story, 0)).toBeNull()
  })

  it('pops up again when the tab comes back after a game day hidden', () => {
    const clock = { day_number: 3, seconds_into_day: 0, time_of_day: 0, phase: 'day' as const, day_seconds: 3600, time_scale: 1 }
    expect(gameDayMs(clock)).toBe(3_600_000)
    expect(gameDayMs(undefined)).toBe(3_600_000)
    expect(awayLongEnough(0, 3_600_001, 3_600_000)).toBe(true)
    expect(awayLongEnough(0, 3_599_999, 3_600_000)).toBe(false)
    expect(awayLongEnough(null, 9e9, 3_600_000)).toBe(false)
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
    expect(notifyPlan(inbox, 8, 'Pebble')).toEqual({ title: 'Pebble: Danger', body: 'I saw a gloomling coming.', upTo: 9 })
    expect(notifyPlan(inbox, 5, 'Pebble')).toEqual({ title: '2 new messages from Pebble', body: 'I saw a gloomling coming.', upTo: 9 })
    expect(notifyPlan(inbox, 9, 'Pebble')).toBeNull()
    expect(notifyPlan(undefined, 0, 'Pebble')).toBeNull()
  })

  it('never claim a count the five newest cannot show (m11), and a story written while watched is quiet (I4)', () => {
    const many: InboxView = { unread: 40, newest: [9, 8, 7, 6, 5].map((id) => ({ ...inbox.newest[0], id })) }
    expect(notifyPlan(many, 0, 'Pebble')?.title).toBe('New messages from Pebble')
    const story: InboxView = { unread: 1, newest: [{ ...inbox.newest[0], id: 10, kind: 'story', text: 'Day 3 was a good one.' }] }
    expect(notifyPlan(story, 9, 'Pebble', true)).toBeNull()
    expect(notifyPlan(story, 9, 'Pebble', false)?.title).toBe('Pebble: While you were away')
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

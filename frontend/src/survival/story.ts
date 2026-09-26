import { request } from './api'
import { kindLabel } from './bond'
import type { DiaryEntry, InboxView } from './bondTypes'
import type { Clock } from './types'

/** Where the owner's choice to be notified is kept (this browser only). */
export const NOTIFY_KEY = 'mimo.notify'

/** The story to show first: the newest, while it is unread and the owner has not just closed it. */
export function storyToShow(story: DiaryEntry | null | undefined, closed: number): DiaryEntry | null {
  return story && !story.read && story.id !== closed ? story : null
}

/** The story that was waiting when the viewer opened (or the tab came back after a game day away): the newest
 * while unread, else null (Bond's final fix wave, I4). */
export function openedStoryId(story: DiaryEntry | null | undefined): number | null {
  return story && !story.read ? story.id : null
}

/** The story to pop up (I4): only the one waiting when the viewer opened, grown or not, while unread and not
 * just closed. A story written while the owner watches goes quietly into the inbox and the diary. */
export function storyOnOpen(opened: number | null, story: DiaryEntry | null | undefined, closed: number): DiaryEntry | null {
  return opened !== null && story?.id === opened ? storyToShow(story, closed) : null
}

/** A game day in real milliseconds, from the clock (an hour at the production scale). */
export function gameDayMs(clock: Pick<Clock, 'day_seconds' | 'time_scale'> | undefined): number {
  return clock && clock.time_scale > 0 ? (clock.day_seconds / clock.time_scale) * 1000 : 3_600_000
}

/** Whether the tab was hidden longer than a game day (I4): then the story waiting pops up as on opening. */
export function awayLongEnough(hiddenAt: number | null, now: number, dayMs: number): boolean {
  return hiddenAt !== null && now - hiddenAt > dayMs
}

/** The memorial's diary (I8): every story, from the life's own detail once it came, else the summary's newest. */
export function memorialDiary(summary: DiaryEntry[] | undefined, detail: { diary?: DiaryEntry[] } | null): DiaryEntry[] {
  return detail?.diary ?? summary ?? []
}

/** Whether notifications show as on (Task 15): chosen, and still granted by the browser. */
export function notifyShown(chosen: boolean, permission: string | undefined): boolean {
  return chosen && permission === 'granted'
}

/** "Day 3", for a diary entry. */
export function diaryDay(entry: Pick<DiaryEntry, 'day' | 'last'>): string {
  return entry.last && entry.last > entry.day ? `Days ${entry.day} to ${entry.last}` : `Day ${entry.day}`
}

/** A diary, oldest first, as the memorial lists it: "Day 3: ...". */
export function diaryLines(diary: DiaryEntry[] | undefined): { key: number; day: string; text: string }[] {
  return (diary ?? []).map((entry) => ({ key: entry.id, day: diaryDay(entry), text: entry.text }))
}

export function loadNotify(storage: () => Pick<Storage, 'getItem'>): boolean {
  try {
    return storage().getItem(NOTIFY_KEY) === 'on'
  } catch {
    return false
  }
}

export function saveNotify(storage: () => Pick<Storage, 'setItem'>, on: boolean): void {
  try {
    storage().setItem(NOTIFY_KEY, on ? 'on' : 'off')
  } catch {
    // Blocked or full storage: the choice lasts for this visit only.
  }
}

/** The newest unread message id, so messages already there when the viewer opens never notify. */
export function newestUnread(inbox: InboxView | undefined): number {
  return (inbox?.newest ?? []).reduce((newest, item) => Math.max(newest, item.id), 0)
}

/** One browser notification for the unread messages newer than the last one notified, or null. Bond's final
 * fix wave: when every message the snapshot shows is new there may be more, so no count is claimed (m11); and a
 * story written while the owner watches (`watching`) goes quietly, as its pop-up does (I4). */
export function notifyPlan(inbox: InboxView | undefined, lastNotified: number, name: string, watching = false):
  { title: string; body: string; upTo: number } | null {
  const shown = inbox?.newest ?? []
  const fresh = shown.filter((item) => item.id > lastNotified)
  const told = watching ? fresh.filter((item) => item.kind !== 'story') : fresh
  if (told.length === 0) return null
  const newest = told.reduce((best, item) => item.id > best.id ? item : best)
  const upTo = fresh.reduce((best, item) => Math.max(best, item.id), 0)
  const title = told.length === 1 ? `${name}: ${kindLabel(newest.kind)}`
    : fresh.length === shown.length && (inbox?.unread ?? 0) > shown.length ? `New messages from ${name}`
      : `${told.length} new messages from ${name}`
  return { title, body: newest.text, upTo }
}

export const fetchDiary = () => request<{ entries: DiaryEntry[] }>('/api/mimo/diary')
export const markStoryRead = (id: number) => request<{ unread: number }>('/api/mimo/inbox/read', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }),
})

import { request } from './api'
import { kindLabel } from './bond'
import type { DiaryEntry, InboxView } from './bondTypes'

/** Where the owner's choice to be notified is kept (this browser only). */
export const NOTIFY_KEY = 'mimo.notify'

/** The story to show first: the newest, while it is unread and the owner has not just closed it. */
export function storyToShow(story: DiaryEntry | null | undefined, closed: number): DiaryEntry | null {
  return story && !story.read && story.id !== closed ? story : null
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

/** One browser notification for the unread messages newer than the last one notified, or null. */
export function notifyPlan(inbox: InboxView | undefined, lastNotified: number, name: string):
  { title: string; body: string; upTo: number } | null {
  const fresh = (inbox?.newest ?? []).filter((item) => item.id > lastNotified)
  if (fresh.length === 0) return null
  const newest = fresh.reduce((best, item) => item.id > best.id ? item : best)
  const title = fresh.length === 1 ? `${name}: ${kindLabel(newest.kind)}` : `${fresh.length} new messages from ${name}`
  return { title, body: newest.text, upTo: newest.id }
}

export const fetchDiary = () => request<{ entries: DiaryEntry[] }>('/api/mimo/diary')
export const markStoryRead = (id: number) => request<{ unread: number }>('/api/mimo/inbox/read', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }),
})

import { request } from './api'
import { kindLabel } from './bond'
import type { DiaryEntry, InboxView } from './bondTypes'

/** Where the owner's choice to be notified is kept (this browser only). */
export const NOTIFY_KEY = 'mimo.notify'

/** The story to pop up: the newest, while it is unread, is about an absence and the owner has not just closed it.
 * Bond follow-up, N3 (the controller's ruling amending I4): a story written for an owner who was there
 * (`present`) never pops up and goes quietly into the inbox and the diary, while one about an absence pops up
 * whenever it arrives, the owed story after a laptop sleep among them. */
export function storyToShow(story: DiaryEntry | null | undefined, closed: number): DiaryEntry | null {
  return story && !story.read && !story.present && story.id !== closed ? story : null
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

/** The unread messages newer than the last one notified: how far that mark moves (`upTo`), and the one browser
 * notification to show for them, or no notice when there is nothing to tell; null when nothing is new. Bond's
 * final fix wave: when every message the snapshot shows is new there may be more, so no count is claimed (m11).
 * Bond follow-up (N4): a story written for an owner who was there (`present`) is never told, as it never pops
 * up, and the mark still moves past it. */
export function notifyPlan(inbox: InboxView | undefined, lastNotified: number, name: string):
  { notice: { title: string; body: string } | null; upTo: number } | null {
  const shown = inbox?.newest ?? []
  const fresh = shown.filter((item) => item.id > lastNotified)
  if (fresh.length === 0) return null
  const upTo = fresh.reduce((best, item) => Math.max(best, item.id), 0)
  const told = fresh.filter((item) => !(item.kind === 'story' && item.data.present))
  if (told.length === 0) return { notice: null, upTo }
  const newest = told.reduce((best, item) => item.id > best.id ? item : best)
  const title = told.length === 1 ? `${name}: ${kindLabel(newest.kind)}`
    : fresh.length === shown.length && (inbox?.unread ?? 0) > shown.length ? `New messages from ${name}`
      : `${told.length} new messages from ${name}`
  return { notice: { title, body: newest.text }, upTo }
}

export const fetchDiary = () => request<{ entries: DiaryEntry[] }>('/api/mimo/diary')
export const markStoryRead = (id: number) => request<{ unread: number }>('/api/mimo/inbox/read', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id }),
})

import { request } from './api'
import type { BondView, InboxItem, InboxView, RequestView } from './bondTypes'
import { closedLine } from './wild'

/** Hearts in the HUD's meter: each stands for 20 points of bond. */
export const HEARTS = 5
/** The viewer tells the world the owner is here when it opens, then this often while the tab shows. */
export const VISIT_EVERY_MS = 10 * 60 * 1000
/** A place name the owner may give (backend/survival/inbox.py NAME_LIMIT and PLACE_NAME). */
export const NAME_LIMIT = 24
const PLACE_NAME = /^[A-Za-z0-9][A-Za-z0-9 '-]*$/

/** The heart meter: how many hearts are full (halves round up), and its words. */
export function heartMeter(bond: BondView | undefined): { full: number; label: string } | null {
  if (!bond) return null
  const level = Math.min(100, Math.max(0, Math.round(bond.level)))
  return { full: Math.ceil(level / (100 / HEARTS)), label: `Bond ${level} · ${bond.feeling}` }
}

/** "Inbox (3)" while messages are unread, else "Inbox". */
export function inboxLabel(inbox: InboxView | undefined): string {
  return inbox && inbox.unread > 0 ? `Inbox (${inbox.unread})` : 'Inbox'
}

// Bond's final fix wave (m1): a find, a first sighting among them, is a discovery; a seed hatching has its own.
const KIND_LABELS: Record<string, string> = {
  ask: 'Asks you', report: 'News', found: 'Discovery', hatched: 'Hatched', danger: 'Danger', story: 'While you were away',
}

/** A message's kind in words. */
export function kindLabel(kind: string): string {
  return KIND_LABELS[kind] ?? 'News'
}

/** A question from Mimo the owner can still answer with a name. */
export function canName(item: InboxItem): boolean {
  return item.kind === 'ask' && item.data.ask === 'name' && !item.data.answer
}

/** Why a place name cannot be given, or null when it can. */
export function nameProblem(text: string): string | null {
  const name = text.split(/\s+/).filter(Boolean).join(' ')
  if (!name) return 'Write a name first.'
  if (name.length > NAME_LIMIT || !PLACE_NAME.test(name)) return `A name is 1 to ${NAME_LIMIT} letters, digits, spaces, ' or -.`
  return null
}

/** "Promised: A herd of its own", while a request of the owner's lasts; '' otherwise. Bond's final fix
 * wave: a promise waiting for its goal (I5, no `until` yet) says what it waits for, "Promised, after first
 * circuits: A thinking machine", and a shy maybe (m6) says "Maybe later: Look into a cave". */
export function promiseLine(taken: RequestView | null | undefined, serverTime: number): string {
  if (!taken || (taken.until !== null && serverTime >= taken.until)) return ''
  if (taken.maybe) return `Maybe later: ${taken.title}`
  if (taken.until === null && taken.after) return `Promised, after ${taken.after.charAt(0).toLowerCase()}${taken.after.slice(1)}: ${taken.title}`
  return `Promised: ${taken.title}`
}

/** The newest message id. */
export function newestItem(items: InboxItem[]): number {
  return items.reduce((newest, item) => Math.max(newest, item.id), 0)
}

/** The unread messages among those listed: the ones opening the inbox marks read (Bond's final fix wave, I7). */
export function unreadIds(items: InboxItem[]): number[] {
  return items.filter((item) => !item.read).map((item) => item.id)
}

/** What answered one of Mimo's asks: the name given, or (m14) the day's snack or bandage, or (W1) how one of its
 * questions closed; '' while it waits. */
export function answeredLine(item: InboxItem): string {
  if (item.data.ask === 'wonder') return closedLine(item)
  if (item.data.answer) return `You named it ${item.data.answer}.`
  if (item.data.care && item.data.done) return `You gave it a ${item.data.care}.`
  return ''
}

/** Whether to tell the world the owner is here again: never sent, or VISIT_EVERY_MS since, with the tab showing. */
export function visitDue(lastVisit: number | null, now: number, visible: boolean): boolean {
  return visible && (lastVisit === null || now - lastVisit >= VISIT_EVERY_MS)
}

export const fetchInbox = () => request<{ items: InboxItem[]; unread: number }>('/api/mimo/inbox')
const postJson = <T>(path: string, body?: unknown) => request<T>(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}),
})
export const markInboxRead = (ids: number[]) => postJson<{ unread: number }>('/api/mimo/inbox/read', { ids })
export const namePlace = (id: number, text: string) => postJson<{ item: InboxItem }>(`/api/mimo/inbox/${id}/answer`, { text })
/** W1: the owner answers one of Mimo's questions with the chip at `choice`. */
export const answerQuestion = (id: number, choice: number) =>
  postJson<{ item: InboxItem }>(`/api/mimo/inbox/${id}/answer`, { choice })
export const noteVisit = () => postJson<{ bond: BondView }>('/api/mimo/visit')

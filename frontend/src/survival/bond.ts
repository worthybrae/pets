import { request } from './api'
import type { BondView, InboxItem, InboxView, RequestView } from './bondTypes'

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

const KIND_LABELS: Record<string, string> = {
  ask: 'Asks you', report: 'News', found: 'First sighting', danger: 'Danger', story: 'While you were away',
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

/** "Promised: A herd of its own", while a request of the owner's lasts; '' otherwise. */
export function promiseLine(taken: RequestView | null | undefined, serverTime: number): string {
  return taken && serverTime < taken.until ? `Promised: ${taken.title}` : ''
}

/** The newest message id, to mark everything shown read. */
export function newestItem(items: InboxItem[]): number {
  return items.reduce((newest, item) => Math.max(newest, item.id), 0)
}

/** Whether to tell the world the owner is here again: never sent, or VISIT_EVERY_MS since, with the tab showing. */
export function visitDue(lastVisit: number | null, now: number, visible: boolean): boolean {
  return visible && (lastVisit === null || now - lastVisit >= VISIT_EVERY_MS)
}

export const fetchInbox = () => request<{ items: InboxItem[]; unread: number }>('/api/mimo/inbox')
const postJson = <T>(path: string, body?: unknown) => request<T>(path, {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body ?? {}),
})
export const markInboxRead = (upTo: number) => postJson<{ unread: number }>('/api/mimo/inbox/read', { up_to: upTo })
export const namePlace = (id: number, text: string) => postJson<{ item: InboxItem }>(`/api/mimo/inbox/${id}/answer`, { text })
export const noteVisit = () => postJson<{ bond: BondView }>('/api/mimo/visit')

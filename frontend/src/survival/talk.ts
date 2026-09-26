import { request } from './api'
import type { ChatLeft, ChatLine, ChatView } from './bondTypes'

/** Characters in one line to Mimo (backend/survival/talk.py TEXT_LIMIT). */
export const TEXT_LIMIT = 280
/** Below this many lines left in the game hour, the panel says how many. */
export const FEW_LEFT = 5

/** The words as the server keeps them: one line, spaces collapsed. */
export function cleanDraft(text: string): string {
  return text.split(/\s+/).filter(Boolean).join(' ')
}

/** Why a draft cannot be sent, or null when it can. */
export function draftProblem(text: string): string | null {
  const words = cleanDraft(text)
  if (!words) return 'Write something first.'
  if (words.length > TEXT_LIMIT) return `Keep it to ${TEXT_LIMIT} characters.`
  return null
}

/** Characters left in the draft (negative when it is too long). */
export function charactersLeft(text: string): number {
  return TEXT_LIMIT - cleanDraft(text).length
}

/** What the limits leave, in words; '' while there is plenty. */
export function limitText(left: ChatLeft | undefined, name: string): string {
  if (!left) return ''
  if (left.day <= 0) return `That's a lot of talk for one day. ${name} will be glad to chat tomorrow.`
  if (left.hour <= 0) return `${name} needs a breather. Try again in a little while.`
  if (left.hour <= FEW_LEFT) return `${left.hour} ${left.hour === 1 ? 'line' : 'lines'} left this hour.`
  return ''
}

/** Whether the Send button works now. */
export function canSend(text: string, chat: ChatView | undefined, sending: boolean): boolean {
  const left = chat?.left
  return !sending && draftProblem(text) === null && (!left || (left.hour > 0 && left.day > 0))
}

/** "Pebble is thinking…" while a reply is on its way. */
export function waitingText(chat: ChatView | undefined, name: string): string {
  return chat?.waiting ? `${name} is thinking…` : ''
}

/** The newest line Mimo wrote, or 0. */
export function newestReply(chat: ChatView | undefined): number {
  return (chat?.lines ?? []).reduce((newest, line) => line.who === 'mimo' ? Math.max(newest, line.id) : newest, 0)
}

/** Replies from Mimo newer than the one the owner last saw. */
export function unseenReplies(chat: ChatView | undefined, seen: number): number {
  return (chat?.lines ?? []).filter((line) => line.who === 'mimo' && line.id > seen).length
}

/** The Talk button: "Talk", or "Talk (2)" with replies the owner has not seen. */
export function talkLabel(chat: ChatView | undefined, seen: number): string {
  const unseen = unseenReplies(chat, seen)
  return unseen > 0 ? `Talk (${unseen})` : 'Talk'
}

/** Who wrote a line, for the panel. */
export function speaker(line: ChatLine, name: string): string {
  return line.who === 'owner' ? 'You' : name
}

/** Write a line to Mimo. Its reply comes later, in /api/mimo's chat. */
export const sendChat = (text: string) => request<{ id: number; text: string; left: ChatLeft }>('/api/mimo/chat', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
})

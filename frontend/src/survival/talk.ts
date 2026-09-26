import { request } from './api'
import type { ChatLeft, ChatLine, ChatView } from './bondTypes'

/** Characters in one line to Mimo (backend/survival/talk.py TEXT_LIMIT). */
export const TEXT_LIMIT = 280
/** Below this many lines left in the game hour, the panel says how many. */
export const FEW_LEFT = 5

/** The joiner inside an emoji family (👨‍👩‍👧), which the cleaning keeps. */
const JOINER = '\u200d'

/** The words as the server keeps them (backend/survival/talk.py clean): control characters become
 * spaces, other invisible characters (format marks, lone surrogates) are dropped but for the joiner,
 * and spaces collapse to one line. */
export function cleanDraft(text: string): string {
  return text
    .replace(/\p{Cc}/gu, ' ')
    .replace(/[\p{Cf}\p{Cs}]/gu, (char) => (char === JOINER ? char : ''))
    .split(/\s+/)
    .filter(Boolean)
    .join(' ')
}

/** Characters as the server counts them: code points, so an emoji is one, not two. */
export function textLength(text: string): number {
  return Array.from(text).length
}

/** Why a draft cannot be sent, or null when it can. */
export function draftProblem(text: string): string | null {
  const words = cleanDraft(text)
  if (!words) return 'Write something first.'
  if (textLength(words) > TEXT_LIMIT) return `Keep it to ${TEXT_LIMIT} characters.`
  return null
}

/** Characters left in the draft (negative when it is too long). */
export function charactersLeft(text: string): number {
  return TEXT_LIMIT - textLength(cleanDraft(text))
}

/** A key pressed in the chat box, as the panel reads it. */
export interface TalkKey {
  key: string
  shiftKey: boolean
  /** True while an input method is composing a character (Japanese, Chinese…): its Enter picks the character. */
  isComposing: boolean
}

/** Whether a key in the chat box sends the draft: Enter, without Shift and not while composing. */
export function sendsOnKey({ key, shiftKey, isComposing }: TalkKey): boolean {
  return key === 'Enter' && !shiftKey && !isComposing
}

/** Whether a key closes the talk panel: Escape. */
export function closesOnKey(key: string): boolean {
  return key === 'Escape'
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

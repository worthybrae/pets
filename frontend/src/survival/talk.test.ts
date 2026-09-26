import { describe, expect, it } from 'vitest'
import type { ChatView } from './bondTypes'
import {
  TEXT_LIMIT, canSend, charactersLeft, cleanDraft, closesOnKey, draftProblem, limitText, newestReply, sendsOnKey,
  speaker, talkLabel, textLength, unseenReplies, waitingText,
} from './talk'

const chat: ChatView = {
  lines: [
    { id: 4, at: 10, who: 'owner', text: 'Hi!' },
    { id: 5, at: 11, who: 'mimo', text: 'Hi! I am gathering wood.' },
    { id: 6, at: 20, who: 'owner', text: 'What is your goal?' },
    { id: 7, at: 22, who: 'mimo', text: 'Iron tools: 40% done.' },
  ],
  waiting: false,
  left: { hour: 18, day: 198 },
}

describe('a draft', () => {
  it('is one line of at most 280 characters, as the server keeps it', () => {
    expect(cleanDraft('  hello\n  there ')).toBe('hello there')
    expect(draftProblem('   ')).toBe('Write something first.')
    expect(draftProblem('a'.repeat(TEXT_LIMIT))).toBeNull()
    expect(draftProblem(`${'a'.repeat(TEXT_LIMIT)}!`)).toBe('Keep it to 280 characters.')
    expect(charactersLeft('a  b')).toBe(TEXT_LIMIT - 3)
  })

  it('is cleaned as the server cleans it: controls become spaces, invisible marks go, emoji families stay', () => {
    expect(cleanDraft('a\u0007b\u0000c')).toBe('a b c')
    expect(cleanDraft('left\u202eright\u200b!')).toBe('leftright!')
    expect(cleanDraft('\ufeffhi')).toBe('hi')
    expect(cleanDraft('👨\u200d👩\u200d👧 hi')).toBe('👨\u200d👩\u200d👧 hi')
    expect(cleanDraft('bad\ud800 half')).toBe('bad half')
  })

  it('counts characters as the server does, an emoji as one', () => {
    expect(textLength('🙂🙂')).toBe(2)
    expect(draftProblem('🙂'.repeat(TEXT_LIMIT))).toBeNull()
    expect(charactersLeft('🙂 hi')).toBe(TEXT_LIMIT - 4)
    expect(draftProblem('🙂'.repeat(TEXT_LIMIT + 1))).toBe('Keep it to 280 characters.')
  })

  it('can be sent while the limits leave room and nothing is sending', () => {
    expect(canSend('hi', chat, false)).toBe(true)
    expect(canSend('hi', chat, true)).toBe(false)
    expect(canSend('', chat, false)).toBe(false)
    expect(canSend('hi', { ...chat, left: { hour: 0, day: 150 } }, false)).toBe(false)
    expect(canSend('hi', undefined, false)).toBe(true)
  })
})

describe('the keys', () => {
  it('send on Enter, not with Shift or while an input method composes, and close on Escape', () => {
    expect(sendsOnKey({ key: 'Enter', shiftKey: false, isComposing: false })).toBe(true)
    expect(sendsOnKey({ key: 'Enter', shiftKey: true, isComposing: false })).toBe(false)
    expect(sendsOnKey({ key: 'Enter', shiftKey: false, isComposing: true })).toBe(false)
    expect(sendsOnKey({ key: 'a', shiftKey: false, isComposing: false })).toBe(false)
    expect(closesOnKey('Escape')).toBe(true)
    expect(closesOnKey('Enter')).toBe(false)
  })
})

describe('the limits', () => {
  it('say nothing while there is plenty, then how many lines are left, then why not', () => {
    expect(limitText({ hour: 18, day: 198 }, 'Pebble')).toBe('')
    expect(limitText({ hour: 1, day: 198 }, 'Pebble')).toBe('1 line left this hour.')
    expect(limitText({ hour: 4, day: 198 }, 'Pebble')).toBe('4 lines left this hour.')
    expect(limitText({ hour: 0, day: 198 }, 'Pebble')).toBe('Pebble needs a breather. Try again in a little while.')
    expect(limitText({ hour: 3, day: 0 }, 'Pebble')).toContain('glad to chat tomorrow')
    expect(limitText(undefined, 'Pebble')).toBe('')
  })
})

describe('the talk', () => {
  it('names who wrote each line and says when a reply is coming', () => {
    expect(chat.lines.map((line) => speaker(line, 'Pebble'))).toEqual(['You', 'Pebble', 'You', 'Pebble'])
    expect(waitingText({ ...chat, waiting: true }, 'Pebble')).toBe('Pebble is thinking…')
    expect(waitingText(chat, 'Pebble')).toBe('')
  })

  it('counts the replies the owner has not seen on the Talk button', () => {
    expect(newestReply(chat)).toBe(7)
    expect(newestReply(undefined)).toBe(0)
    expect(unseenReplies(chat, 5)).toBe(1)
    expect(talkLabel(chat, 0)).toBe('Talk (2)')
    expect(talkLabel(chat, 7)).toBe('Talk')
    expect(talkLabel(undefined, 0)).toBe('Talk')
  })
})

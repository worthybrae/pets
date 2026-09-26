import { describe, expect, it } from 'vitest'
import type { ChatView } from './bondTypes'
import {
  TEXT_LIMIT, canSend, charactersLeft, cleanDraft, draftProblem, limitText, newestReply, speaker, talkLabel,
  unseenReplies, waitingText,
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

  it('can be sent while the limits leave room and nothing is sending', () => {
    expect(canSend('hi', chat, false)).toBe(true)
    expect(canSend('hi', chat, true)).toBe(false)
    expect(canSend('', chat, false)).toBe(false)
    expect(canSend('hi', { ...chat, left: { hour: 0, day: 150 } }, false)).toBe(false)
    expect(canSend('hi', undefined, false)).toBe(true)
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

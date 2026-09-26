import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import type { ChatView } from './bondTypes'
import {
  TEXT_LIMIT, canSend, charactersLeft, closesOnKey, draftProblem, limitText, sendChat, sendsOnKey, speaker, waitingText,
} from './talk'

/** Talking with Mimo: the newest lines and a box to write in, over the world and the HUD. */
export default function TalkPanel({ name, chat, onSent, onClose }: {
  name: string
  chat: ChatView | undefined
  /** Refreshes the stream, so the owner's line shows at once. */
  onSent: () => Promise<void>
  onClose: () => void
}) {
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const end = useRef<HTMLDivElement>(null)
  const box = useRef<HTMLInputElement>(null)
  // A second Enter in the same moment sees no new state yet: this guard does.
  const busy = useRef(false)
  const lines = chat?.lines ?? []
  const newest = lines.length > 0 ? lines[lines.length - 1].id : 0
  const waiting = Boolean(chat?.waiting)
  useEffect(() => { end.current?.scrollIntoView({ block: 'end' }) }, [newest, waiting])

  const send = async () => {
    if (busy.current || sending) return
    const problem = draftProblem(text)
    if (problem) {
      setError(problem)
      return
    }
    if (!canSend(text, chat, false)) return  // the limits: the panel already says why
    busy.current = true
    setSending(true)
    setError('')
    try {
      await sendChat(text)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That did not go through. Try again.')
      return
    } finally {
      busy.current = false
      setSending(false)
    }
    setText('')
    box.current?.focus()
    // The line went through: a refresh that fails now is not the owner's problem, the next poll shows it.
    onSent().catch(() => undefined)
  }

  const left = charactersLeft(text)
  return createPortal(
    <div className="fixed inset-0 z-40 flex items-end justify-end bg-[#203b38]/25 p-3 sm:items-stretch sm:p-6" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={`Talk with ${name}`} onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => {
          if (closesOnKey(event.key)) {
            event.stopPropagation()
            onClose()
          }
        }}
        className="flex max-h-[80vh] w-full flex-col rounded-3xl bg-[#f5faf7] text-[#243e3d] shadow-2xl sm:max-h-none sm:w-96">
        <div className="flex items-center justify-between gap-3 border-b border-[#d6e5dc] px-5 py-3">
          <h2 className="text-lg font-semibold">Talk with {name}</h2>
          <button type="button" onClick={onClose} aria-label={`Close the talk with ${name}`} className="rounded-xl bg-[#e1eee7] px-3 py-1 text-xl">×</button>
        </div>
        <div className="flex-1 space-y-2 overflow-y-auto px-5 py-3 text-sm" aria-live="polite">
          {lines.length === 0 && <p className="text-[#65817b]">Say hi to {name}. It answers from what it is up to and how it feels.</p>}
          {lines.map((line) => (
            <div key={line.id} className={line.who === 'owner' ? 'flex justify-end' : 'flex justify-start'}>
              <p className={`max-w-[85%] rounded-2xl px-3 py-2 leading-5 ${line.who === 'owner' ? 'bg-[#315e58] text-white' : 'bg-[#e1eee7]'}`}>
                <span className="sr-only">{speaker(line, name)}: </span>{line.text}
              </p>
            </div>
          ))}
          {waiting && <p className="text-xs italic text-[#65817b]">{waitingText(chat, name)}</p>}
          <div ref={end} />
        </div>
        <form onSubmit={(event) => { event.preventDefault(); void send() }} className="border-t border-[#d6e5dc] px-5 py-3">
          <div className="flex gap-2">
            <input ref={box} value={text} onChange={(event) => setText(event.target.value)} maxLength={TEXT_LIMIT * 2}
              autoFocus aria-label={`Write to ${name}`} placeholder={`Write to ${name}…`}
              onKeyDown={(event) => {
                if (sendsOnKey({ key: event.key, shiftKey: event.shiftKey, isComposing: event.nativeEvent.isComposing })) {
                  event.preventDefault()
                  void send()
                }
              }}
              className="min-w-0 flex-1 rounded-xl border border-[#bfd5cd] bg-white px-3 py-2 text-sm outline-none focus:border-[#315e58]" />
            <button type="submit" disabled={!canSend(text, chat, sending)}
              className="rounded-xl bg-[#315e58] px-3 py-2 text-sm font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-40">Send</button>
          </div>
          <p className="mt-1 flex justify-between gap-3 text-xs text-[#65817b]">
            <span role="status">{error || limitText(chat?.left, name)}</span>
            <span className={left < 0 ? 'text-[#b5473a]' : undefined}>{left}</span>
          </p>
        </form>
      </section>
    </div>,
    document.body,
  )
}

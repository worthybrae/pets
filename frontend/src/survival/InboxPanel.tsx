import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { answeredLine, canName, fetchInbox, kindLabel, markInboxRead, nameProblem, namePlace, unreadIds } from './bond'
import type { InboxItem } from './bondTypes'
import { useEscape } from './escape'

/** Mimo's messages to its owner, newest first. Opening it marks read the ones it lists (Bond's final fix
 * wave, I7: never the ones it does not show); a naming ask takes a name. B3: where the owner turns
 * browser notifications on or off. */
export default function InboxPanel({ name, notify, canNotify, onNotify, onChanged, onClose }: {
  name: string
  /** Notifications are on. */
  notify: boolean
  /** This browser can notify (the Notification API is there). */
  canNotify: boolean
  onNotify: (on: boolean) => void
  /** Refreshes the stream (the unread count, the chat). */
  onChanged: () => Promise<void>
  onClose: () => void
}) {
  const [items, setItems] = useState<InboxItem[] | null>(null)
  const [drafts, setDrafts] = useState<Record<number, string>>({})
  const [error, setError] = useState('')
  useEscape(onClose)

  useEffect(() => {
    let cancelled = false
    fetchInbox().then(async (inbox) => {
      if (cancelled) return
      setItems(inbox.items)
      const listed = unreadIds(inbox.items)
      if (listed.length > 0) {
        await markInboxRead(listed)
        await onChanged()
      }
    }).catch((failure: unknown) => {
      if (!cancelled) setError(failure instanceof Error ? failure.message : 'The inbox could not be loaded.')
    })
    return () => { cancelled = true }
  }, [onChanged])

  const answer = async (item: InboxItem) => {
    const text = drafts[item.id] ?? ''
    const problem = nameProblem(text)
    if (problem) {
      setError(problem)
      return
    }
    try {
      const { item: named } = await namePlace(item.id, text)
      setItems((current) => current?.map((known) => known.id === named.id ? named : known) ?? null)
      setError('')
      await onChanged()
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'That name did not go through. Try again.')
    }
  }

  return createPortal(
    <div className="fixed inset-0 z-40 flex items-end justify-end bg-[#203b38]/25 p-3 sm:items-stretch sm:p-6" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={`${name}'s messages`} onClick={(event) => event.stopPropagation()}
        className="flex max-h-[80vh] w-full flex-col rounded-3xl bg-[#f5faf7] text-[#243e3d] shadow-2xl sm:max-h-none sm:w-96">
        <div className="flex items-center justify-between gap-3 border-b border-[#d6e5dc] px-5 py-3">
          <h2 className="text-lg font-semibold">From {name}</h2>
          <button type="button" onClick={onClose} aria-label="Close the inbox" className="rounded-xl bg-[#e1eee7] px-3 py-1 text-xl">×</button>
        </div>
        <ul className="flex-1 space-y-3 overflow-y-auto px-5 py-3 text-sm">
          {items === null && !error && <li className="text-[#65817b]">Opening…</li>}
          {items?.length === 0 && <li className="text-[#65817b]">Nothing yet. {name} writes when something happens.</li>}
          {items?.map((item) => (
            <li key={item.id} className={`rounded-2xl px-3 py-2 ${item.read ? 'bg-white/60' : 'bg-[#e1eee7]'}`}>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#65817b]">
                {kindLabel(item.kind)} · {new Date(item.at * 1000).toLocaleString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' })}
              </p>
              <p className="mt-1 leading-5">{item.text}</p>
              {answeredLine(item) && <p className="mt-1 text-xs text-[#54726e]">{answeredLine(item)}</p>}
              {canName(item) && (
                <form className="mt-2 flex gap-2" onSubmit={(event) => { event.preventDefault(); void answer(item) }}>
                  <input value={drafts[item.id] ?? ''} maxLength={48} aria-label="A name for the place"
                    onChange={(event) => setDrafts((current) => ({ ...current, [item.id]: event.target.value }))}
                    placeholder="Echo Hollow" className="min-w-0 flex-1 rounded-xl border border-[#bfd5cd] bg-white px-3 py-1.5 text-sm" />
                  <button type="submit" className="rounded-xl bg-[#315e58] px-3 py-1.5 text-sm font-medium text-white hover:bg-[#244b47]">Name it</button>
                </form>
              )}
            </li>
          ))}
        </ul>
        {error && <p className="border-t border-[#d6e5dc] px-5 py-2 text-xs text-[#a65b50]" role="status">{error}</p>}
        {canNotify && (
          <label className="flex items-center gap-2 border-t border-[#d6e5dc] px-5 py-2 text-xs text-[#54726e]">
            <input type="checkbox" checked={notify} onChange={(event) => onNotify(event.target.checked)} />
            Tell me when {name} writes, while this tab is open
          </label>
        )}
      </section>
    </div>,
    document.body,
  )
}

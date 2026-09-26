import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import type { DiaryEntry } from './bondTypes'
import { diaryDay, fetchDiary } from './story'

/** Mimo's diary: the newest stories, newest first. */
export default function DiaryPanel({ name, onClose }: { name: string; onClose: () => void }) {
  const [entries, setEntries] = useState<DiaryEntry[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    fetchDiary().then((diary) => { if (!cancelled) setEntries(diary.entries) }).catch((failure: unknown) => {
      if (!cancelled) setError(failure instanceof Error ? failure.message : 'The diary could not be loaded.')
    })
    return () => { cancelled = true }
  }, [])
  return createPortal(
    <div className="fixed inset-0 z-40 flex items-end justify-end bg-[#203b38]/25 p-3 sm:items-stretch sm:p-6" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={`${name}'s diary`} onClick={(event) => event.stopPropagation()}
        className="flex max-h-[80vh] w-full flex-col rounded-3xl bg-[#f5faf7] text-[#243e3d] shadow-2xl sm:max-h-none sm:w-96">
        <div className="flex items-center justify-between gap-3 border-b border-[#d6e5dc] px-5 py-3">
          <h2 className="text-lg font-semibold">{name}'s diary</h2>
          <button type="button" onClick={onClose} aria-label="Close the diary" className="rounded-xl bg-[#e1eee7] px-3 py-1 text-xl">×</button>
        </div>
        <ul className="flex-1 space-y-4 overflow-y-auto px-5 py-3 text-sm leading-6">
          {entries === null && !error && <li className="text-[#65817b]">Opening…</li>}
          {entries?.length === 0 && <li className="text-[#65817b]">No stories yet. {name} writes one at the first dawn after you visit.</li>}
          {entries?.map((entry) => (
            <li key={entry.id}>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#65817b]">{diaryDay(entry)}</p>
              <p className="mt-1 text-[#315e58]">{entry.text}</p>
            </li>
          ))}
        </ul>
        {error && <p className="border-t border-[#d6e5dc] px-5 py-2 text-xs text-[#a65b50]" role="status">{error}</p>}
      </section>
    </div>,
    document.body,
  )
}

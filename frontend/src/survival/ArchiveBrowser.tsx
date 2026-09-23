import { useEffect, useState } from 'react'
import { fetchLives } from './api'
import { lifeLine } from './hud'
import type { LifeRow } from './types'

/** Every life, newest first. Opening one shows its world read-only. */
export default function ArchiveBrowser({ onOpen, onClose }: {
  onOpen: (lifeId: number) => void
  onClose: () => void
}) {
  const [lives, setLives] = useState<LifeRow[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchLives().then(
      (rows) => { if (!cancelled) setLives(rows) },
      (failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'The lives could not be loaded.') },
    )
    return () => { cancelled = true }
  }, [])

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label="Lives" onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 text-[#243e3d] shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Archive</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">Lives</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close lives" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        {error && <p className="mt-4 text-sm text-[#a65b50]" role="alert">{error}</p>}
        {!lives && !error && <p className="mt-4 text-sm text-[#54726e]">Loading…</p>}
        <ul className="mt-5 space-y-2">
          {lives?.map((life) => (
            <li key={life.id} className="flex items-center justify-between gap-3 rounded-2xl bg-[#e9f2eb] px-4 py-3">
              <div className="min-w-0">
                <p className="truncate font-semibold">{life.name} <span className="text-xs font-normal text-[#65817b]">#{life.id}</span></p>
                <p className="text-xs text-[#54726e]">{lifeLine(life)} · born {new Date(life.born_at * 1000).toLocaleDateString()}</p>
              </div>
              <button type="button" onClick={() => onOpen(life.id)}
                className="shrink-0 rounded-lg bg-[#315e58] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#244b47]">View world</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

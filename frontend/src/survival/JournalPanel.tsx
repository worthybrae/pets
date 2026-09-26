import { journalEntries, journalTitle } from './journal'
import type { JournalEntry } from './types'

/** L4b: the knowledge journal, what Mimo learned about the world, newest first. */
export default function JournalPanel({ name, journal, onClose }: {
  name: string
  journal: readonly JournalEntry[] | undefined
  onClose: () => void
}) {
  const entries = journalEntries(journal, name)
  const title = journalTitle(name)
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Knowledge journal</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close the journal" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">
          The first time {name} meets something new, it walks up, looks it over, takes a sample and writes down what it learned.
        </p>
        {entries.length === 0 && <p className="mt-6 text-sm text-[#65817b]">Nothing yet: {name} has not studied anything.</p>}
        <ul className="mt-6 space-y-3">
          {entries.map((entry) => (
            <li key={entry.key} className="rounded-xl bg-[#e9f2eb] px-4 py-3 text-sm leading-6">
              <span className="mr-2 rounded-md bg-white/70 px-2 py-0.5 text-xs font-semibold text-[#315e58]">{entry.label}</span>
              <span className="italic text-[#243e3d]">“{entry.line}”</span>
              {entry.fact && <p className="mt-1 text-xs text-[#54726e]">{entry.fact}</p>}
              {entry.unlocks && <p className="mt-1 text-xs font-semibold text-[#3c7a68]">{entry.unlocks}</p>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

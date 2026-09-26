import { memoriesTitle, memorySections } from './memories'
import type { MemoriesView } from './mindTypes'

const MOOD_MARKS = { glad: '♥', sad: '·', '': '' }

/** Mind M3: what Mimo remembers, beside the journal: lately, the moments that mattered, its thoughts and its days. */
export default function MemoriesPanel({ name, memories, onClose }: {
  name: string
  memories: MemoriesView | undefined
  onClose: () => void
}) {
  const sections = memorySections(memories)
  const title = memoriesTitle(name)
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Memories</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close the memories" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">
          Each night {name} sleeps on its day: what mattered stays, small things fade, and every day is kept in a line.
        </p>
        {sections.length === 0 && <p className="mt-6 text-sm text-[#65817b]">Nothing yet: {name} is only starting to remember.</p>}
        {sections.map((section) => (
          <div key={section.title} className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">{section.title}</p>
            <ul className="mt-2 space-y-2">
              {section.lines.map((line) => (
                <li key={line.key} className="rounded-xl bg-[#e9f2eb] px-4 py-2.5 text-sm leading-6">
                  <span className="mr-2 rounded-md bg-white/70 px-2 py-0.5 text-xs font-semibold text-[#315e58]">{line.day}</span>
                  {line.fromYou && <span className="mr-2 rounded-md bg-[#f3e3c4] px-2 py-0.5 text-xs font-semibold text-[#8a6a2f]">From you</span>}
                  <span className="text-[#243e3d]">{line.text}</span>
                  {line.mood && <span className="ml-2 text-xs text-[#8aa39d]" aria-hidden>{MOOD_MARKS[line.mood]}</span>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </div>
  )
}

import { otherEvents, reachedLine } from './goals'
import { lifeLine } from './hud'
import { memorialMemories } from './memories'
import type { LifeSummary } from './types'

/** Shown after a pet dies, until the owner moves on to the next egg. */
export default function Memorial({ life, onViewWorld, onNextEgg }: {
  life: LifeSummary
  onViewWorld: () => void
  onNextEgg: () => void
}) {
  const remembered = memorialMemories(life.memories)
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#1d263b] px-4 py-10 text-[#243e3d]">
      <section className="w-full max-w-md rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8" aria-label={`In memory of ${life.name}`}>
        <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">In memory of</p>
        <h1 className="mt-1 text-4xl font-semibold tracking-tight">{life.name}</h1>
        <p className="mt-3 text-sm text-[#54726e]">{lifeLine(life)}.</p>
        {otherEvents(life.notable_events).length > 0 && (
          <ul className="mt-5 space-y-2 border-l-2 border-[#d6e5dc] pl-4 text-sm text-[#54726e]">
            {otherEvents(life.notable_events).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
        )}
        {(life.goals_reached ?? []).length > 0 && (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Goals reached</p>
            <ul className="mt-2 space-y-1 text-sm text-[#54726e]">
              {(life.goals_reached ?? []).map((goal) => <li key={goal.name}>{reachedLine(goal)}</li>)}
            </ul>
          </div>
        )}
        {remembered.thoughts.length > 0 && (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">What {life.name} thought</p>
            <ul className="mt-2 space-y-1 text-sm italic text-[#54726e]">
              {remembered.thoughts.map((line) => <li key={line.key}>“{line.text}”</li>)}
            </ul>
          </div>
        )}
        {remembered.days.length > 0 && (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Day by day</p>
            <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm text-[#54726e]">
              {remembered.days.map((line) => <li key={line.key}><span className="font-semibold">{line.day}:</span> {line.text}</li>)}
            </ul>
          </div>
        )}
        <div className="mt-7 flex flex-col gap-2 sm:flex-row">
          <button type="button" onClick={onViewWorld}
            className="flex-1 rounded-xl border border-[#bfd5cd] px-4 py-2.5 text-sm font-medium text-[#315e58] hover:bg-white">View {life.name}'s world</button>
          <button type="button" onClick={onNextEgg}
            className="flex-1 rounded-xl bg-[#315e58] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#244b47]">Hatch a new egg</button>
        </div>
      </section>
    </main>
  )
}

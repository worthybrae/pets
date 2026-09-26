import { useEscape } from './escape'
import type { WorkshopView } from './types'
import { workshopLine, workshopRows, workshopTitle } from './workshop'

/** Making: the Workshop panel, the machines Mimo built and what each shows now, oldest first. */
export default function WorkshopPanel({ name, workshop, onClose }: {
  name: string
  workshop: WorkshopView | undefined
  onClose: () => void
}) {
  useEscape(onClose)
  const rows = workshopRows(workshop)
  const line = workshopLine(workshop)
  const title = workshopTitle(name)
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Workshop</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">{title}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close the workshop" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">
          {name} wires copper into machines: levers and lamps first, then clocks, memory and a computer that counts its days.
        </p>
        {line && <p className="mt-3 text-sm font-medium text-[#315e58]">{line}</p>}
        {rows.length === 0 && <p className="mt-6 text-sm text-[#65817b]">No machines yet: {name} has not wired anything up.</p>}
        <ul className="mt-6 space-y-3">
          {rows.map((row, index) => (
            <li key={`${row.key}-${index}`} className="rounded-xl bg-[#e9f2eb] px-4 py-3 text-sm leading-6">
              <span className="mr-2 rounded-md bg-white/70 px-2 py-0.5 text-xs font-semibold text-[#315e58]">{row.status}</span>
              <span className="font-medium text-[#243e3d]">{row.name}</span>
              {row.detail && <p className="mt-1 font-mono text-xs text-[#54726e]">{row.detail}</p>}
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

import { dialPosition } from './clock'
import { actionText, careLabel, clockTime, dayLabel, purposeText, vitalBars, type VitalLevel } from './hud'
import type { AliveResponse, CareKind } from './types'

const LEVEL_COLORS: Record<VitalLevel, string> = { ok: '#4d8c77', low: '#d6a14a', critical: '#c76e5c' }
const PANEL = 'rounded-2xl border border-white/75 bg-[#f5faf7]/90 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md'

/** A half-circle dial with the sun by day and the moon by night. */
function SkyDial({ secondsIntoDay }: { secondsIntoDay: number }) {
  const { body, progress } = dialPosition(secondsIntoDay)
  const angle = Math.PI * (1 - progress)
  const x = 30 + Math.cos(angle) * 24
  const y = 30 - Math.sin(angle) * 24
  return (
    <svg viewBox="0 0 60 34" className="h-9 w-16 shrink-0" role="img" aria-label={body === 'sun' ? 'Sun' : 'Moon'}>
      <path d="M6 30 A24 24 0 0 1 54 30" fill="none" stroke="#bfd5cd" strokeWidth="2" strokeDasharray="3 3" />
      <line x1="2" y1="30.5" x2="58" y2="30.5" stroke="#bfd5cd" strokeWidth="1.5" />
      <circle cx={x} cy={y} r="5" fill={body === 'sun' ? '#f5c46b' : '#c9d4f0'} stroke={body === 'sun' ? '#e0a23c' : '#8f9fc8'} />
    </svg>
  )
}

export default function SurvivalHud({ state, online, busy, message, onCare, onHello, onFollow, onCrafting, onOpenLives }: {
  state: AliveResponse
  online: boolean
  busy: boolean
  message: string
  onCare: (kind: CareKind) => void
  onHello: () => void
  onFollow: () => void
  onCrafting: () => void
  /** Shows a Lives button that opens the archive. */
  onOpenLives?: () => void
}) {
  const { clock, life } = state
  const careKinds: CareKind[] = ['snack', 'bandage']
  return (
    <>
      <div className="absolute inset-x-4 top-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:top-8 sm:flex-row sm:items-start sm:justify-between">
        <section className={`${PANEL} px-4 py-3 sm:w-80`} aria-label={`${life.name}'s day`}>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-lg font-semibold leading-tight">{life.name}</p>
              <p className="text-xs text-[#54726e]">{dayLabel(clock.day_number, clock.phase)} · {clockTime(clock.seconds_into_day)}</p>
            </div>
            <SkyDial secondsIntoDay={clock.seconds_into_day} />
          </div>
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{purposeText(state)}</p>
          <p className="mt-0.5 text-xs text-[#54726e]">
            <span className={online ? 'text-[#3c9a73]' : 'text-[#c76e5c]'}>●</span> {online ? actionText(state.action, state.status) : 'Worker offline'}
          </p>
          <p className="mt-1 text-sm italic leading-5 text-[#315e58]">“{state.last_thought}”</p>
        </section>
        <section className={`${PANEL} grid grid-cols-2 gap-x-4 gap-y-2 px-4 py-3 text-xs sm:w-64 sm:grid-cols-1`} aria-label="Vitals">
          {vitalBars(state.vitals).map((bar) => (
            <div key={bar.key}>
              <div className="flex justify-between"><span>{bar.label}</span><span className="tabular-nums">{bar.value}</span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
                aria-valuenow={bar.value} aria-valuemin={0} aria-valuemax={100} aria-label={bar.label}>
                <div className="h-full rounded-full transition-[width] duration-700" style={{ width: `${bar.value}%`, backgroundColor: LEVEL_COLORS[bar.level] }} />
              </div>
            </div>
          ))}
        </section>
      </div>

      <div className="absolute inset-x-4 bottom-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:bottom-8 sm:flex-row sm:items-end sm:justify-between">
        <section className={`${PANEL} px-4 py-3 sm:max-w-md`} aria-label="Care">
          <div className="flex flex-wrap gap-2">
            {careKinds.map((kind) => (
              <button key={kind} type="button" disabled={busy || state.care[kind] <= 0} onClick={() => onCare(kind)}
                className="rounded-xl bg-[#315e58] px-3 py-2 text-sm font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-40">
                {careLabel(kind, state.care[kind])}
              </button>
            ))}
            <button type="button" disabled={busy} onClick={onHello}
              className="rounded-xl border border-[#bfd5cd] px-3 py-2 text-sm font-medium text-[#315e58] hover:bg-white disabled:opacity-40">Say hello</button>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium text-[#315e58]">
            <button type="button" onClick={onFollow} className="underline decoration-[#8cafa2] underline-offset-4">Follow {life.name}</button>
            <button type="button" onClick={onCrafting} className="underline decoration-[#8cafa2] underline-offset-4">Blocks & crafting</button>
            {onOpenLives && <button type="button" onClick={onOpenLives} className="underline decoration-[#8cafa2] underline-offset-4">Lives</button>}
          </div>
          {message && <p className="mt-2 text-xs text-[#a65b50]" role="status">{message}</p>}
        </section>
        <section className={`${PANEL} hidden w-64 px-4 py-3 text-xs md:block`} aria-label="Recent events">
          <p className="mb-2 font-semibold">What happened</p>
          <ul className="space-y-1.5 text-[#54726e]">
            {state.events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
        </section>
      </div>
    </>
  )
}

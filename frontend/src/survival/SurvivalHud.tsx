import { useEffect, useRef, useState, type ReactNode } from 'react'
import { CAMERA_MODES, modeLabel, type AutoPick, type CameraMode } from './cameraModes'
import { dialPosition } from './clock'
import {
  actionText, careLabel, clockTime, dangerText, dayLabel, homeText, hurtFlashDelay, purposeText, vitalBars, type VitalLevel,
} from './hud'
import { ringLine, ringTone } from './frontier'
import { curiosityBar, goalHint, goalLine, planSteps, tripLines } from './goals'
import { expeditionLine, journalButton } from './journal'
import { memoriesButton } from './memories'
import { computerCaption, workshopButton } from './workshop'
import { ailmentLine, wildBadge } from './wild'
import { seasonBadge } from './seasons'
import { weatherLine } from './weather'
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

/** L2: a red glow at the screen's edges that fades once, `delay` seconds after it mounts (one per blow). */
function HurtFlash({ delay }: { delay: number }) {
  const glow = useRef<HTMLDivElement>(null)
  const [start] = useState(delay)
  useEffect(() => {
    const fade = glow.current?.animate([{ opacity: 1 }, { opacity: 0 }],
      { duration: 700, delay: start * 1000, easing: 'ease-out', fill: 'forwards' })
    return () => fade?.cancel()
  }, [start])
  return <div ref={glow} aria-hidden
    className="pointer-events-none absolute inset-0 z-20 opacity-0 shadow-[inset_0_0_120px_30px_rgba(199,70,58,0.55)]" />
}

/** Auto, Overview, Close and Eyes as one small segmented control; the chosen one shows auto's pick. */
function CameraSwitch({ mode, autoPick, onChange }: { mode: CameraMode; autoPick: AutoPick | null; onChange: (mode: CameraMode) => void }) {
  return (
    <div className="mt-2 flex items-center gap-2" title="Press C to switch the camera">
      <span className="hidden text-xs text-[#54726e] sm:inline">Camera</span>
      <div role="group" aria-label="Camera" className="inline-flex max-w-full rounded-lg border border-[#bfd5cd] bg-white/50 p-0.5 text-xs font-medium">
        {CAMERA_MODES.map((option) => (
          <button key={option} type="button" aria-pressed={option === mode} onClick={() => onChange(option)}
            className={`whitespace-nowrap rounded-md px-2 py-1 ${option === mode ? 'bg-[#315e58] text-white' : 'text-[#315e58] hover:bg-white'}`}>
            {modeLabel(option, option === mode ? autoPick : null)}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function SurvivalHud({ state, online, busy, message, cameraMode, autoPick, minimap, onCameraMode, onCare, onHello, onFollow, onCrafting, onJournal, onMemories, onWorkshop, onOpenLives, bond }: {
  state: AliveResponse
  online: boolean
  busy: boolean
  message: string
  cameraMode: CameraMode
  /** What auto has picked, once it has. */
  autoPick: AutoPick | null
  /** The minimap, or the button that shows it: bottom right, above the recent events. */
  minimap?: ReactNode
  onCameraMode: (mode: CameraMode) => void
  onCare: (kind: CareKind) => void
  onHello: () => void
  onFollow: () => void
  onCrafting: () => void
  /** L4b: opens the knowledge journal. */
  onJournal: () => void
  /** Mind M3: opens the Memories panel. */
  onMemories: () => void
  /** Making: opens the Workshop panel. */
  onWorkshop?: () => void
  /** Shows a Lives button that opens the archive. */
  onOpenLives?: () => void
  /** Bond: talking with Mimo, under the care buttons. */
  bond?: ReactNode
}) {
  const { clock, life } = state
  const careKinds: CareKind[] = ['snack', 'bandage']
  const home = homeText(state.structures)
  const ring = ringLine(state.ring)
  const danger = dangerText(state.creatures, state.position, state.sheltered)
  const flash = hurtFlashDelay(state.hurt_at, state.server_time)
  const goal = goalLine(state.goal)
  const plan = planSteps(state.goal)
  const trip = state.reflex ? null : tripLines(state.trip)
  const curious = curiosityBar(state.curiosity)
  const expedition = expeditionLine(state.expedition)
  const caption = computerCaption(life.name, state.workshop, clock.day_number)
  const workshop = workshopButton(state.workshop)
  const ailing = ailmentLine(state.ailments)
  const badge = wildBadge(state.difficulty)
  const season = seasonBadge(state.sky, clock.day_number)
  const weather = weatherLine(state.sky?.weather)
  return (
    <>
      {flash !== null && <HurtFlash key={state.hurt_at ?? 0} delay={flash} />}
      <div className="absolute inset-x-4 top-4 z-10 flex flex-col gap-3 sm:inset-x-8 sm:top-8 sm:flex-row sm:items-start sm:justify-between">
        <section className={`${PANEL} px-4 py-3 sm:w-80`} aria-label={`${life.name}'s day`}>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              {/* W1's final fix wave: the badge sits beside the name, never inside its truncated line */}
              <div className="flex min-w-0 items-center gap-2">
                <p className="min-w-0 truncate text-lg font-semibold leading-tight">{life.name}</p>
                {badge && <span className="shrink-0 rounded-md bg-[#e8d9b8] px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#7a5a24]"
                  title="A wild pet learns to survive from you, or the hard way">{badge}</span>}
              </div>
              <p className="text-xs text-[#54726e]">{dayLabel(clock.day_number, clock.phase)} · {clockTime(clock.seconds_into_day)}</p>
              {season && <p className="truncate text-xs text-[#54726e]" title="The season">{season}{weather && ` · ${weather}`}</p>}
            </div>
            <SkyDial secondsIntoDay={clock.seconds_into_day} />
          </div>
          <p className="mt-2 text-sm font-medium leading-5 text-[#315e58]">{trip ? trip.label : purposeText(state)}</p>
          {trip && <p className="truncate text-xs text-[#54726e]">{trip.detail}</p>}
          {danger && <p className="mt-0.5 text-sm font-semibold text-[#b5473a]" role="status">{danger}</p>}
          {ailing && <p className="mt-0.5 text-xs font-semibold text-[#7d6b2c]" role="status">{ailing}</p>}
          {goal && (
            <div className="mt-1.5" title={goalHint(state.goal)}>
              <div className="flex items-baseline justify-between gap-2 text-xs text-[#315e58]">
                <span className="truncate font-semibold">{goal.label}</span>
                <span className="tabular-nums">{goal.percent}%</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
                aria-valuenow={goal.percent} aria-valuemin={0} aria-valuemax={100} aria-label={goal.label}>
                <div className="h-full rounded-full bg-[#6b8fb5] transition-[width] duration-700" style={{ width: `${goal.percent}%` }} />
              </div>
              {plan.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-[#54726e]" aria-label="Today's plan">
                  {plan.map((step) => (
                    <li key={step.text} className={step.done ? 'text-[#8aa39d] line-through' : undefined}>
                      {step.done ? '✓' : '·'} {step.text}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {expedition && <p className="mt-1 truncate text-xs font-medium text-[#8a6a2f]">{expedition}</p>}
          {home && <p className="mt-0.5 truncate text-xs text-[#54726e]">{home}</p>}
          {ring && (
            <p className={`mt-0.5 truncate text-xs ${ringTone(state.ring) === 'wary' ? 'font-semibold text-[#a8662c]' : 'text-[#54726e]'}`}
              title="The farther from home, the tougher the creatures and the richer the finds">{ring}</p>
          )}
          {caption && <p className="mt-0.5 truncate font-mono text-xs font-semibold text-[#8a6a2f]" aria-label="Computer">{caption}</p>}
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
          {curious && (
            <div title={curious.hint}>
              <div className="flex justify-between"><span>Curiosity</span><span className="tabular-nums">{curious.percent}</span></div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
                aria-valuenow={curious.percent} aria-valuemin={0} aria-valuemax={100} aria-label="Curiosity">
                <div className="h-full rounded-full bg-[#b58a3c] transition-[width] duration-700" style={{ width: `${curious.percent}%` }} />
              </div>
            </div>
          )}
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
            <button type="button" onClick={onJournal} className="underline decoration-[#8cafa2] underline-offset-4">{journalButton(state.journal)}</button>
            <button type="button" onClick={onMemories} className="underline decoration-[#8cafa2] underline-offset-4">{memoriesButton(state.memories)}</button>
            {workshop && onWorkshop && <button type="button" onClick={onWorkshop} className="underline decoration-[#8cafa2] underline-offset-4">{workshop}</button>}
            {onOpenLives && <button type="button" onClick={onOpenLives} className="underline decoration-[#8cafa2] underline-offset-4">Lives</button>}
          </div>
          {bond}
          <CameraSwitch mode={cameraMode} autoPick={autoPick} onChange={onCameraMode} />
          {message && <p className="mt-2 text-xs text-[#a65b50]" role="status">{message}</p>}
        </section>
        {/* On phones the map sits above the care panel, on the right; on wider screens in the
            right-hand column, above the recent events. */}
        <div className="order-first flex flex-col items-end gap-3 self-end sm:order-none">
          {minimap}
          <section className={`${PANEL} hidden w-64 px-4 py-3 text-xs md:block`} aria-label="Recent events">
            <p className="mb-2 font-semibold">What happened</p>
            <ul className="space-y-1.5 text-[#54726e]">
              {state.events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
            </ul>
          </section>
        </div>
      </div>
    </>
  )
}

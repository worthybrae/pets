import type { ActionKind, CareKind, ClockPhase, LifeRow, MimoAction, VitalName, Vitals } from './types'

export type VitalLevel = 'ok' | 'low' | 'critical'

export interface VitalBar {
  key: VitalName
  label: string
  value: number
  level: VitalLevel
}

export const HUD_VITALS: VitalName[] = ['health', 'hunger', 'warmth', 'energy', 'air']
const LABELS: Record<VitalName, string> = {
  health: 'Health', hunger: 'Hunger', warmth: 'Warmth', energy: 'Energy', air: 'Air', mood: 'Mood',
}
/** Below `critical` the vital hurts Mimo or is about to; below `low` it needs attention soon. */
const THRESHOLDS: Record<VitalName, { low: number; critical: number }> = {
  health: { low: 50, critical: 25 },
  hunger: { low: 30, critical: 15 },
  warmth: { low: 35, critical: 20 },
  energy: { low: 25, critical: 10 },
  air: { low: 60, critical: 30 },
  mood: { low: 30, critical: 15 },
}
const PHASE_NAMES: Record<ClockPhase, string> = {
  dawn: 'Dawn', day: 'Day', dusk: 'Dusk', night: 'Night', pre_dawn: 'Before dawn',
}
const STATUS_TEXT: Record<string, string> = { idle: 'Standing still', sleeping: 'Sleeping', dead: 'Gone' }
const CAUSES: Record<string, string> = {
  starvation: 'starvation', cold: 'the cold', drowning: 'drowning', fall: 'a fall', creature: 'a creature',
}

export function vitalBars(vitals: Vitals, names: VitalName[] = HUD_VITALS): VitalBar[] {
  return names.map((key) => {
    const value = Math.round(Math.min(100, Math.max(0, vitals[key])))
    const { low, critical } = THRESHOLDS[key]
    return { key, label: LABELS[key], value, level: value < critical ? 'critical' : value < low ? 'low' : 'ok' }
  })
}

export function dayLabel(dayNumber: number, phase: ClockPhase): string {
  return `Day ${dayNumber} · ${PHASE_NAMES[phase]}`
}

/** A 24-hour game time where dawn starts at 06:00. */
export function clockTime(secondsIntoDay: number): string {
  const minutes = Math.floor((((secondsIntoDay / 3600) * 24 + 6) % 24) * 60)
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

export function statusText(status: string): string {
  return STATUS_TEXT[status] ?? status.replaceAll('_', ' ')
}

const ACTION_WORDS: Partial<Record<ActionKind, string>> = {
  walk: 'Walking', swim: 'Swimming', fall: 'Falling!', mine: 'Mining', place: 'Placing', eat: 'Eating',
  craft: 'Crafting', smelt: 'Smelting', sleep: 'Sleeping',
}

/** The current step in plain words ("Mining oak log"); the status when Mimo is between steps or waiting. */
export function actionText(action: MimoAction | null, status: string): string {
  const words = action ? ACTION_WORDS[action.kind] : undefined
  if (!action || !words) return statusText(status)
  const object = action.block ?? action.item ?? action.recipe
  return object ? `${words} ${object.replaceAll('_', ' ')}` : words
}

export function careLabel(kind: CareKind, remaining: number): string {
  return `${kind === 'snack' ? 'Give snack' : 'Bandage'} · ${remaining} left today`
}

export function causeText(cause: string | null): string {
  return cause ? CAUSES[cause] ?? cause.replaceAll('_', ' ') : 'unknown causes'
}

export function daysText(days: number): string {
  return days === 1 ? '1 day' : `${days} days`
}

/** One line for the memorial and the archive list. */
export function lifeLine(life: Pick<LifeRow, 'kind' | 'alive' | 'days' | 'cause'>): string {
  if (life.kind === 'legacy') return `Retired after ${daysText(life.days)}`
  if (life.alive) return `Alive · day ${life.days}`
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
}

/** The worker ticks every second; a state older than 10 s means it stopped. */
export function workerOnline(serverTime: number, lastTickAt: number): boolean {
  return serverTime - lastTickAt < 10
}

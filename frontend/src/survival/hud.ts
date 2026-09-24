import { REPLAY_DELAY } from './replay'
import type {
  ActionKind, Built, CareKind, Chests, ClockPhase, Creature, LifeRow, MimoAction, Point, SurvivalState, VitalName, Vitals,
} from './types'

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
/** Causes of death that are a creature's kind (L2): the pet was caught, not killed by the world. */
const CAUGHT_BY = new Set(['gloomling', 'skitter', 'creature'])
/** How close (blocks, across) a hostile creature is for the HUD to warn of it. */
export const DANGER_REACH = 12
/**
 * How far above or below Mimo it may be, matching the server's THREAT_RISE
 * (backend/survival/creatures/defense.py): the same rule that decides whether a hostile can raise
 * an alarm or turn Mimo to flee or fight, so the HUD's warning means the same "dangerous" the game
 * does. Deeper is a cave under Mimo's feet.
 */
export const DANGER_RISE = 2
/** How long after a blow (server seconds) its flash may still start. */
const FLASH_WINDOW = 3

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
  craft: 'Crafting', smelt: 'Smelting', sleep: 'Sleeping', pick: 'Picking', harvest: 'Harvesting',
  till: 'Tilling', plant: 'Planting', fish: 'Fishing', cook: 'Cooking', store: 'Putting away', take: 'Taking out',
  drop: 'Dropping', attack: 'Attacking', shoot: 'Shooting',
}

/** A block or item in plain words: a crop's stage and a bush's ripeness are left out. */
export function thingName(name: string): string {
  return name.replace(/_(ripe|\d)$/, '').replaceAll('_', ' ')
}

/** The current step in plain words ("Mining oak log"); the status when Mimo is between steps or waiting. */
export function actionText(action: MimoAction | null, status: string): string {
  const words = action ? ACTION_WORDS[action.kind] : undefined
  if (!action || !words) return statusText(status)
  const object = action.block ?? action.item ?? action.recipe
  return object ? `${words} ${thingName(object)}` : words
}

const PURPOSE_TEXT: Record<string, string> = {
  gather_wood: 'Gathering wood', gather_stone: 'Digging for stone', mine_ore: 'Mining ore',
  craft_tools: 'Making a tool', explore: 'Exploring', go_home: 'Going home', sleep: 'Settling down to sleep',
  rest: 'Resting', eat: 'Having a meal', escape: 'Digging out of a pit', forage: 'Foraging for food',
  fish: 'Fishing', farm: 'Tending the farm', cook: 'Cooking a meal', build_shelter: 'Building a shelter',
  build_farm: 'Laying out a farm', build_storage: 'Putting things away', drop_items: 'Dropping what it cannot use',
  light_up: 'Lighting torches', hunt: 'Hunting', make_gear: 'Making gear',
  gather_flint: 'Digging for flint', build_pen: 'Building a pen', stock_pen: 'Planting creature seeds',
}
const REFLEX_TEXT: Record<string, string> = {
  surface: 'Swimming for air!', avoid_drop: 'Backing away from a drop', eat_now: 'Eating in a hurry',
  warm_up: 'Getting warm', head_home: 'Hurrying home before dark', collapse: 'Collapsed from exhaustion',
  flee: 'Running away!', fight: 'Fighting back!',
}

function sentence(name: string): string {
  const words = name.replaceAll('_', ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** What Mimo is up to in plain words: a reflex first, then its purpose, or that it is choosing. */
export function purposeText(state: Pick<SurvivalState, 'purpose' | 'reflex' | 'choosing'>): string {
  if (state.reflex) return REFLEX_TEXT[state.reflex] ?? sentence(state.reflex)
  if (state.purpose) return PURPOSE_TEXT[state.purpose] ?? sentence(state.purpose)
  return state.choosing ? 'Deciding what to do' : 'Taking it easy'
}

/**
 * Mimo's home in a few words: the shelter it built (or is building), or null before it starts one.
 * An API from before M5 sends no `structures`: that reads as nothing built.
 */
export function homeText(structures: readonly Built[] | null | undefined): string | null {
  const shelter = [...(structures ?? [])].reverse().find((built) => built.kind === 'shelter')
  if (!shelter) return null
  return shelter.status === 'done' ? `Home: ${shelter.name}` : `Building ${shelter.name}`
}

/**
 * What Mimo keeps in its chests, most first, like "40 dirt, 5 gravel"; null when they are empty.
 * An API from before M5 sends no `chests`: that reads as none.
 */
export function chestText(chests: Chests | null | undefined): string | null {
  const totals = new Map<string, number>()
  for (const chest of Object.values(chests ?? {})) {
    for (const [item, count] of Object.entries(chest)) totals.set(item, (totals.get(item) ?? 0) + count)
  }
  const items = [...totals].filter(([, count]) => count > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return items.length ? items.map(([item, count]) => `${count} ${item.replaceAll('_', ' ')}`).join(', ') : null
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
  if (life.cause && CAUGHT_BY.has(life.cause)) return `Survived ${daysText(life.days)} · caught by a ${thingName(life.cause)}`
  return `Survived ${daysText(life.days)} · died of ${causeText(life.cause)}`
}

/**
 * The HUD's danger line (L2): the living hostile creatures within DANGER_REACH blocks of Mimo across
 * and DANGER_RISE up or down, like "A gloomling is close!", or null. The server lists creatures
 * nearest first; a burning one is no danger. While Mimo is `sheltered` (the server says it stands in
 * a room or passage of the shelter it built, where no blow reaches) nothing is close enough to warn of.
 */
export function dangerText(creatures: readonly Creature[] | null | undefined, position: Point,
  sheltered = false): string | null {
  if (sheltered) return null
  const near = (creatures ?? []).filter((creature) => creature.hostile && creature.state !== 'dead'
    && creature.state !== 'burning' && Math.abs(creature.y - position.y) <= DANGER_RISE
    && Math.hypot(creature.x - position.x, creature.z - position.z) <= DANGER_REACH)
  if (near.length === 0) return null
  const kind = thingName(near[0].kind)
  if (near.length === 1) return `A ${kind} is close!`
  return new Set(near.map((creature) => creature.kind)).size === 1 ? `${near.length} ${kind}s are close!`
    : `${near.length} creatures are close!`
}

/**
 * Seconds from now until the HUD flashes for Mimo's last blow (L2), so the flash lands with the
 * pet drawn REPLAY_DELAY behind the server; null when there is no blow to flash for.
 */
export function hurtFlashDelay(hurtAt: number | null | undefined, serverTime: number): number | null {
  if (hurtAt === null || hurtAt === undefined) return null
  const age = serverTime - hurtAt
  return age < 0 || age > FLASH_WINDOW ? null : Math.max(0, REPLAY_DELAY - age)
}

/** The worker ticks every second; a state older than 10 s means it stopped. */
export function workerOnline(serverTime: number, lastTickAt: number): boolean {
  return serverTime - lastTickAt < 10
}

import type { WorldPlan } from '../components/world/worldPlanner'
import type { AttributeTier } from '../components/hatch/types'
import type { Rarity } from '../data/rarity'

/** Shapes of the survival API (backend/survival/snapshot.py and backend/api). */

export type ClockPhase = 'dawn' | 'day' | 'dusk' | 'night' | 'pre_dawn'
export type VitalName = 'health' | 'hunger' | 'warmth' | 'energy' | 'air' | 'mood'
export type Vitals = Record<VitalName, number>
export type CareKind = 'snack' | 'bandage'
export type CareRemaining = Record<CareKind, number>

export interface Point {
  x: number
  y: number
  z: number
}

export interface Clock {
  day_number: number
  seconds_into_day: number
  time_of_day: number
  phase: ClockPhase
  day_seconds: number
  time_scale: number
}

export interface ServerEgg {
  attributes: { category: string; option: { name: string; tier: AttributeTier; value: number }; points: number }[]
  name: string
  totalPoints: number
  rarity: Rarity
}

export interface MimoEvent {
  id: number
  at: number
  kind: string
  text: string
}

export interface Recipe {
  ingredients: Record<string, number>
  output: Record<string, number>
  station?: string
}

export interface LifeRow {
  id: number
  name: string
  kind: 'legacy' | 'survival'
  seed: string
  spawn_x: number
  spawn_z: number
  born_at: number
  died_at: number | null
  cause: string | null
  egg: ServerEgg | null
  traits: Record<string, number>
  alive: boolean
  /** Game days for survival lives, real days for the legacy life. */
  days: number
}

export interface LifeSummary extends LifeRow {
  notable_events: MimoEvent[]
}

export interface SurvivalState {
  clock: Clock
  vitals: Vitals
  position: Point
  status: string
  last_thought: string
  events: MimoEvent[]
  inventory: Record<string, number>
  recipes: Record<string, Recipe>
  blocks_seq: number
  care: CareRemaining
  world_seed: string
  last_tick_at: number
  server_time: number
  died_at: number | null
  cause: string | null
}

export interface AliveResponse extends SurvivalState {
  phase: 'alive'
  life: LifeRow
}

export interface EggResponse {
  phase: 'egg'
  egg: ServerEgg
  last_life: LifeSummary | null
  server_time: number
}

export type MimoResponse = AliveResponse | EggResponse

/** The retired legacy world's snapshot, as /api/lives/1 returns it. */
export interface LegacyState {
  name: string
  world_seed: string
  position: { x: number; y?: number; z: number }
  plans: WorldPlan[]
  currentIndex: number
  progress: number
  blocks_seq: number
  events: MimoEvent[]
  last_thought: string
}

export interface LifeDetail {
  life: LifeRow
  notable_events: MimoEvent[]
  state: LegacyState | SurvivalState
}

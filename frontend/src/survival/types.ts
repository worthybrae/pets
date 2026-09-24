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

export type ActionKind = 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'craft' | 'smelt' | 'sleep' | 'wait'
  | 'pick' | 'harvest' | 'till' | 'plant' | 'fish' | 'cook' | 'store' | 'take' | 'drop' | 'attack' | 'shoot'

/** One cell of a walk, swim or fall, with the server time Mimo gets there. */
export interface PathPoint extends Point {
  at: number
  /** True on water-surface cells. */
  swim?: boolean
}

/** The step Mimo is doing now (backend/survival/steps.py and actions.py). */
export interface MimoAction {
  kind: ActionKind
  started_at: number
  /** Null while sleeping: sleep ends once Mimo is rested and it is not night. */
  ends_at: number | null
  path?: PathPoint[]
  target?: Point
  block?: string
  item?: string
  recipe?: string
  /** How far a fall drops. */
  blocks?: number
  /** A shot (L2): whether the arrow flies true. */
  hit?: boolean
}

/** A step that finished, oldest first. Waits are left out. */
export interface FinishedAction {
  kind: ActionKind
  started_at: number
  ended_at: number
  /** Interrupted: a reflex or a fall cut it short (`reason` names which). */
  result: 'done' | 'failed' | 'interrupted'
  target?: Point
  block?: string
  item?: string
  recipe?: string
  reason?: string
  /** Why it failed: no_path, out_of_reach, gone, missing_item, blocked or bad_step. */
  code?: string
  /** The purpose or reflex that planned it. */
  purpose?: string
  /** Walks, swims and falls keep their timed path (the newest few only), for replay. */
  path?: PathPoint[]
  /** A shot (L2): whether the arrow flew true. */
  hit?: boolean
}

/** A leaf that decayed after its tree lost its logs, at server time `at`. */
export interface LeafDecay extends Point {
  at: number
}

/** Something Mimo built or is building (backend/survival/memory.py structures), by its anchor. */
export interface Built extends Point {
  id: number
  kind: 'shelter' | 'farm' | 'pen'
  name: string
  status: 'building' | 'done'
}

/** What each chest holds, keyed "x,y,z". */
export type Chests = Record<string, Record<string, number>>

/** An 8x8-block patch of ground Mimo visited: [rx, rz, visits] with rx = x // 8, rz = z // 8.
 * Visits are capped at 9: the minimap only needs to know it was seen. */
export type ExploredPatch = [number, number, number]

/** Home, or the nearest farm Mimo remembers (backend/survival/snapshot.py landmarks_view). */
export interface Landmark extends Point {
  kind: 'home' | 'farm'
}

/** What a creature is doing (backend/survival/creatures/view.py); a finished walk reads idle. */
export type CreatureState = 'idle' | 'walking' | 'grazing' | 'fleeing' | 'swimming' | 'dead'
  | 'chasing' | 'attacking' | 'burning'

/** A creature within 48 blocks of Mimo, standing in the cell its last move ends in. */
export interface Creature extends Point {
  id: number
  /** rabbit, chicken, sheep, cow or fish in L1; other kinds come later. */
  kind: string
  /** Radians around +y; 0 faces +z. */
  heading: number
  /** Health left, 0..1. */
  health: number
  state: CreatureState
  /** Server time it was last hit: a flash, a knock back and its health bar. */
  hurt_at?: number
  /** Server time it died, and what it dropped: a puff with the drops popping out. */
  dead_at?: number
  drops?: string[]
  /** Server time a fish leapt at Mimo's hook. */
  caught_at?: number
  /** L2: a gloomling or skitter, which hunts Mimo. */
  hostile?: boolean
  /** L3: grown from a creature seed Mimo planted; never hunted. Only sent when true. */
  tame?: boolean
  /** Server time a hostile last struck Mimo: its lunge. */
  struck_at?: number
  /** Server time a hostile caught fire in the sun. */
  burning_at?: number
}

/** A creature's last move, for replay: one block from `from` to `to`, or through every cell of `cells`. */
export interface CreatureMove {
  id: number
  from: Point
  to: Point
  started: number
  ends: number
  /** [x, y, z] of every cell from `from` to `to` when the move is longer than one block; each takes as long. */
  cells?: [number, number, number][]
}

export type PickerName = 'jev' | 'luna' | 'utility'

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
  action: MimoAction | null
  recent_actions: FinishedAction[]
  /** Leaves that decayed lately, newest last, for a puff as each goes. */
  decays: LeafDecay[]
  /** What Mimo built, oldest first (M5). */
  structures: Built[]
  /** What its chests hold (M5). */
  chests: Chests
  /** The creatures within 48 blocks, nearest first, and their last moves (L1). */
  creatures: Creature[]
  creature_moves: CreatureMove[]
  /** When a creature last hurt Mimo (server time) and its kind (L2); an older API sends neither. */
  hurt_at?: number | null
  hurt_by?: string | null
  /** Mimo stands in a room or passage of the shelter it built, where no blow reaches (L2); an older API sends none. */
  sheltered?: boolean
  /** The patches Mimo visited within 96 blocks of it, for the minimap's fog of war. */
  explored: ExploredPatch[]
  /** Its home and nearest farm, for the minimap. */
  landmarks: Landmark[]
  /** The purpose Mimo is working on, like "gather_wood", or null. */
  purpose: string | null
  /** A reflex that took over, like "head_home", or null. */
  reflex: string | null
  /** Who chose the purpose. */
  picker: PickerName | null
  /** True while Mimo waits for its next choice. */
  choosing: boolean
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

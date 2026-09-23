import type { FinishedAction, MimoAction, Point } from './types'

export const CRACK_STAGES = 6
export const PLACE_BOUNCE_SECONDS = 0.35
export const BURST_SECONDS = 0.6
export const POP_SECONDS = 0.6
/**
 * An 8×8 crack in the soft pixel style. Row 0 is the top. Each digit is the stage from which
 * that pixel shows: the crack starts in the middle and spreads to the edges.
 */
const CRACK_ART = [
  '.....5..',
  '..6.4...',
  '...34..6',
  '.4.2...5',
  '..21.3..',
  '.3..2...',
  '4....3.6',
  '.5....4.',
]
const CRACK_COLOR = [44, 36, 32, 190]
const GRAVITY = 9.8
const GOLDEN_ANGLE = 2.39996

/** Which crack stage (0 = none, 1..CRACK_STAGES) shows on the block being mined at server time t. */
export function crackStage(action: MimoAction | null, t: number): number {
  if (!action || action.kind !== 'mine' || action.ends_at === null) return 0
  const span = action.ends_at - action.started_at
  const progress = span > 0 ? (t - action.started_at) / span : 1
  if (progress <= 0) return 0
  return Math.min(CRACK_STAGES, Math.floor(progress * CRACK_STAGES) + 1)
}

/** 64 flags, row 0 at the top: 1 where a crack pixel shows at this stage. */
export function crackMask(stage: number): Uint8Array {
  const mask = new Uint8Array(64)
  CRACK_ART.forEach((row, j) => {
    for (let i = 0; i < row.length; i++) {
      if (row[i] !== '.' && Number(row[i]) <= stage) mask[j * 8 + i] = 1
    }
  })
  return mask
}

/** RGBA texels for an 8×8 THREE.DataTexture, bottom row first like the terrain atlas. */
export function crackTexels(stage: number): Uint8Array {
  const mask = crackMask(stage)
  const data = new Uint8Array(64 * 4)
  for (let j = 0; j < 8; j++) {
    for (let i = 0; i < 8; i++) {
      if (mask[j * 8 + i]) data.set(CRACK_COLOR, ((7 - j) * 8 + i) * 4)
    }
  }
  return data
}

function easeOutBack(p: number): number {
  const c1 = 1.70158
  const c3 = c1 + 1
  return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2
}

/** Scale of a just-placed block: in from 0.6 with a small bounce past full size. */
export function placeScale(elapsed: number): number {
  if (elapsed <= 0) return 0.6
  if (elapsed >= PLACE_BOUNCE_SECONDS) return 1
  return 0.6 + 0.4 * easeOutBack(elapsed / PLACE_BOUNCE_SECONDS)
}

/** Offsets of break particles `elapsed` seconds after a block breaks: out and up, then down. */
export function burst(count: number, elapsed: number): Point[] {
  return Array.from({ length: count }, (_, index) => {
    const angle = index * GOLDEN_ANGLE
    const speed = 1.4 + (index % 3) * 0.4
    const rise = 2.4 + (index % 2) * 0.8
    return {
      x: Math.cos(angle) * speed * elapsed,
      y: rise * elapsed - (GRAVITY / 2) * elapsed * elapsed,
      z: Math.sin(angle) * speed * elapsed,
    }
  })
}

/** The dropped item hops out of the broken block and shrinks as it flies to the pet. */
export function itemPop(elapsed: number, from: Point, to: Point): { position: Point; scale: number } {
  const p = Math.min(1, Math.max(0, elapsed / POP_SECONDS))
  const glide = p * p
  return {
    position: {
      x: from.x + (to.x - from.x) * glide,
      y: from.y + (to.y - from.y) * glide + Math.sin(Math.PI * p) * 0.6,
      z: from.z + (to.z - from.z) * glide,
    },
    scale: 1 - 0.7 * p,
  }
}

export interface BlockEffect {
  /** Unique per step: kind, cell and end time. */
  key: string
  kind: 'break' | 'place'
  cell: Point
  block: string
  /** Server time the step ends. */
  at: number
}

/** Breaks and placements from finished steps and the running one, one per step. */
export function blockEffects(action: MimoAction | null, recent: FinishedAction[]): BlockEffect[] {
  const found = new Map<string, BlockEffect>()
  const add = (kind: string, cell: Point | undefined, block: string | undefined, at: number | null) => {
    if ((kind !== 'mine' && kind !== 'place') || !cell || !block || at === null) return
    const key = `${kind}:${cell.x},${cell.y},${cell.z}:${at}`
    if (!found.has(key)) found.set(key, { key, kind: kind === 'mine' ? 'break' : 'place', cell, block, at })
  }
  for (const entry of recent) if (entry.result === 'done') add(entry.kind, entry.target, entry.block, entry.ended_at)
  if (action) add(action.kind, action.target, action.block, action.ends_at)
  return [...found.values()]
}

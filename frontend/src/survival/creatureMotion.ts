import { facingToward } from './motion'
import type { Creature, CreatureMove, Point } from './types'

/**
 * Where a creature is and how it moves at a moment, from the snapshot (backend/survival/creatures
 * /view.py), drawn REPLAY_DELAY behind the server like the pet: its recent moves (the viewer's
 * history of them, creatureMoves.ts) are replayed cell by cell, and the moments in its state (hurt,
 * died, caught) play once each.
 */

/** Where a creature stands at a moment: cell coordinates, fractional while it moves. */
export interface Placement extends Point {
  /** Radians around +y; 0 faces +z. */
  facing: number
  moving: boolean
  /** Cells passed since the move began, fractional, for the hop cycle. */
  travelled: number
}

/** How the body moves on top of its placement. */
export interface Look {
  /** Extra height in blocks: hops, bobbing, a fish's leap. */
  lift: number
  /** Lean forward, in radians. */
  pitch: number
  /** Roll onto the side, in radians: a fish's wiggle, a dead animal tipping over. */
  roll: number
  /** The head's dip, in radians: down to graze. */
  headPitch: number
  /** 0..1: how red the hurt flash is. */
  flash: number
  /** Blocks pushed along the facing by a blow (it faces away as it flees). */
  knock: number
  /** 1 normally, shrinking to 0 as a dead creature puffs away. */
  size: number
}

export const FLASH_SECONDS = 0.35
export const KNOCK_SECONDS = 0.25
export const KNOCK_BLOCKS = 0.35
export const TIP_SECONDS = 0.3
export const PUFF_AFTER = 0.5
export const PUFF_LENGTH = 0.8
export const LEAP_SECONDS = 0.8
export const BAR_SECONDS = 3
const GRAZE_PITCH = 0.8

const cellCache = new WeakMap<CreatureMove, Point[]>()

/** Every cell a move passes, from `from` to `to`, worked out once per move. */
export function cellsOf(move: CreatureMove): Point[] {
  let cells = cellCache.get(move)
  if (!cells) {
    cells = move.cells?.length ? move.cells.map(([x, y, z]) => ({ x, y, z })) : [move.from, move.to]
    cellCache.set(move, cells)
  }
  return cells
}

function standing(at: Point, facing: number): Placement {
  return { x: at.x, y: at.y, z: at.z, facing, moving: false, travelled: 0 }
}

/**
 * Where a creature is at server time `t`, from its recent moves (oldest first): along the latest
 * one that has started by then while it runs (a later one takes over the moment it starts), at
 * the end of it once it is over and the next has not started, where the server has the creature
 * once its last move is over, and at the start of the first before any has begun.
 */
export function placeAt(creature: Creature, moves: readonly CreatureMove[] | undefined, t: number): Placement {
  const list = moves ?? []
  let latest = -1
  list.forEach((move, index) => {
    if (move.started <= t) latest = index
  })
  const move = list[Math.max(0, latest)]
  if (!move || (t >= move.ends && latest === list.length - 1)) return standing(creature, creature.heading)
  const cells = cellsOf(move)
  const steps = cells.length - 1
  if (steps < 1) return standing(cells[0], creature.heading)
  if (t >= move.ends) return standing(cells[steps], facingToward(cells[steps - 1], cells[steps]) ?? creature.heading)
  const span = move.ends - move.started
  const along = t <= move.started || span <= 0 ? 0 : ((t - move.started) / span) * steps
  const index = Math.min(steps - 1, Math.floor(along))
  const from = cells[index]
  const to = cells[index + 1]
  const p = along - index
  return {
    x: from.x + (to.x - from.x) * p,
    y: from.y + (to.y - from.y) * p,
    z: from.z + (to.z - from.z) * p,
    facing: facingToward(from, to) ?? creature.heading,
    moving: t > move.started,
    travelled: along,
  }
}

/** Seconds since `at`, or null when it has not happened yet (or never did). */
function since(at: number | undefined, t: number): number | null {
  return at === undefined || t < at ? null : t - at
}

/** How the creature's body moves at server time `t`; `clock` runs on for idle motion, `hop` is its kind's hop. */
export function lookAt(creature: Creature, place: Placement, t: number, clock: number, hop: number): Look {
  const look: Look = { lift: 0, pitch: 0, roll: 0, headPitch: 0, flash: 0, knock: 0, size: 1 }
  const wobble = clock + creature.id * 1.7
  if (creature.kind === 'fish') {
    look.lift = Math.sin(wobble * 2) * 0.04
    look.roll = Math.sin(wobble * 3) * 0.15
  } else if (place.moving) {
    look.lift = Math.abs(Math.sin(Math.PI * place.travelled)) * hop
    look.pitch = 0.08 * Math.sin(2 * Math.PI * place.travelled)
  } else if (creature.state === 'grazing') {
    look.headPitch = GRAZE_PITCH + 0.08 * Math.sin(wobble * 6)
  } else {
    look.lift = Math.sin(wobble * 1.5) * 0.015
  }
  const hurt = since(creature.hurt_at, t)
  if (hurt !== null && hurt < FLASH_SECONDS) look.flash = 1 - hurt / FLASH_SECONDS
  if (hurt !== null && hurt < KNOCK_SECONDS) look.knock = KNOCK_BLOCKS * Math.sin((Math.PI * hurt) / KNOCK_SECONDS)
  const leapt = since(creature.caught_at, t)
  if (leapt !== null && leapt < LEAP_SECONDS) {
    look.lift += 1.1 * Math.sin((Math.PI * leapt) / LEAP_SECONDS)
    look.pitch = -1.2 + (2.4 * leapt) / LEAP_SECONDS
  }
  const dead = since(creature.dead_at, t)
  if (dead !== null) {
    look.roll = (Math.PI / 2) * Math.min(1, dead / TIP_SECONDS)
    look.lift = 0.15 * Math.min(1, dead / TIP_SECONDS)
    look.headPitch = 0
    look.size = dead < PUFF_AFTER ? 1 : Math.max(0, 1 - (dead - PUFF_AFTER) / PUFF_LENGTH)
  }
  return look
}

/** The health bar over a creature: shown for BAR_SECONDS after a hit it lived through. */
export function healthBar(creature: Creature, t: number): { shown: boolean; fraction: number } {
  const hurt = since(creature.hurt_at, t)
  const dead = since(creature.dead_at, t)
  return { shown: hurt !== null && hurt < BAR_SECONDS && dead === null, fraction: Math.max(0, Math.min(1, creature.health)) }
}

/** Seconds into a dead creature's puff (it starts once the body has tipped over), or null. */
export function puffAge(creature: Creature, t: number): number | null {
  const dead = since(creature.dead_at, t)
  if (dead === null || dead < PUFF_AFTER || dead >= PUFF_AFTER + PUFF_LENGTH) return null
  return dead - PUFF_AFTER
}

/** The drops popping out of a puff `age` seconds in: up in an arc, spread apart, shrinking. */
export function dropPops(drops: readonly string[] | undefined, age: number): { item: string; offset: Point; scale: number }[] {
  const p = Math.min(1, Math.max(0, age / PUFF_LENGTH))
  const shown = drops ?? []
  return shown.map((item, index) => {
    const spread = (index - (shown.length - 1) / 2) * 0.35
    return { item, offset: { x: spread * p, y: 0.4 + 1.1 * Math.sin((Math.PI * p) / 2), z: 0 }, scale: 1 - 0.6 * p }
  })
}

/** Whether to draw a creature at all: not once a dead one's puff is over. */
export function drawn(creature: Creature, t: number): boolean {
  const dead = since(creature.dead_at, t)
  return dead === null || dead < PUFF_AFTER + PUFF_LENGTH
}

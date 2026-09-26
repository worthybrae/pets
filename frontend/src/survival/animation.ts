import type { ActionKind, MimoAction, Point } from './types'

export type PetMove = 'idle' | 'walk' | 'swim' | 'fall' | 'mine' | 'place' | 'eat' | 'sleep' | 'work' | 'fish' | 'swing'
  | 'aim'

/** How the body moves on top of its position. */
export interface BodyPose {
  /** Extra height in blocks. */
  lift: number
  /** Lean forward, in radians. */
  pitch: number
  /** Roll onto the side, in radians; π/2 lies flat. */
  roll: number
  /** Vertical stretch; 1 is the normal shape. */
  stretch: number
}

export interface Puff {
  x: number
  y: number
  scale: number
  opacity: number
}

export const LIE_DOWN_SECONDS = 0.6
const MOVES: Record<ActionKind, PetMove> = {
  walk: 'walk', swim: 'swim', fall: 'fall', mine: 'mine', place: 'place', eat: 'eat', sleep: 'sleep',
  craft: 'work', smelt: 'work', wait: 'idle', pick: 'place', harvest: 'mine', till: 'mine', plant: 'place',
  fish: 'fish', cook: 'work', store: 'place', take: 'place', drop: 'place', attack: 'swing', shoot: 'aim',
  flip: 'place',  // Making: a lever thrown, a button pressed
}
const HOP_HEIGHT = 0.22
const SWING_SECONDS = 0.45
/** An attack lunges forward and back once: a sword swing lasts 0.5 s, a bare hand 0.6 s. */
const LUNGE_SECONDS = 0.5
/** A shot (L2): the bow is drawn for this long, then the arrow flies (archery.ts). */
export const DRAW_SECONDS = 0.6
const RECOIL_SECONDS = 0.3
const NIBBLES_PER_SECOND = 3
const Z_PERIOD = 2.4
const Z_COUNT = 3
const CRUMB_PERIOD = 0.5

/** The animation for the current step at server time t. After a step ends the pet idles until the next arrives. */
export function moveFor(action: MimoAction | null, t: number, swimming = false): PetMove {
  const resting: PetMove = swimming ? 'swim' : 'idle'
  if (!action || (action.ends_at !== null && t >= action.ends_at)) return resting
  const move = MOVES[action.kind]
  return move === 'walk' && swimming ? 'swim' : move
}

/** Body offsets for a move. */
export function bodyPose(move: PetMove, stepTime: number, travelled: number, clock: number): BodyPose {
  const pose: BodyPose = { lift: 0, pitch: 0, roll: 0, stretch: 1 }
  switch (move) {
    case 'walk':
      pose.lift = Math.abs(Math.sin(Math.PI * travelled)) * HOP_HEIGHT
      pose.pitch = 0.08
      break
    case 'swim':
      pose.lift = -0.35 + Math.sin(clock * 3) * 0.06
      pose.pitch = 0.1
      break
    case 'fall':
      pose.pitch = -0.3
      pose.stretch = 1.08
      break
    case 'mine':
      pose.pitch = 0.35 * Math.max(0, Math.sin((2 * Math.PI * stepTime) / SWING_SECONDS))
      break
    case 'place':
      pose.pitch = 0.4 * Math.sin(Math.PI * Math.min(1, stepTime / 0.3))
      break
    case 'eat':
      pose.pitch = 0.09 * (1 + Math.sin(2 * Math.PI * NIBBLES_PER_SECOND * stepTime))
      break
    case 'sleep': {
      const down = Math.min(1, stepTime / LIE_DOWN_SECONDS)
      pose.roll = (Math.PI / 2) * down
      // Lying on its side, the pet's half-width would sink into the ground without this.
      pose.lift = 0.45 * down
      break
    }
    case 'work':
      pose.pitch = 0.06 * Math.sin(stepTime * 8)
      break
    case 'swing': {
      // A lunge at the target (the pet already faces it): forward and a little up, then back.
      const lunge = Math.sin(Math.PI * Math.min(1, stepTime / LUNGE_SECONDS))
      pose.pitch = 0.55 * lunge
      pose.lift = 0.08 * lunge
      break
    }
    case 'aim':
      // Leaning back as it draws the bow, then a little recoil forward as the arrow goes.
      pose.pitch = stepTime < DRAW_SECONDS
        ? -0.18 * (stepTime / DRAW_SECONDS)
        : 0.12 * Math.max(0, 1 - (stepTime - DRAW_SECONDS) / RECOIL_SECONDS)
      break
    case 'fish':
      // Leaning over the water, with a slow bob now and then as if something nibbles.
      pose.pitch = 0.28 + 0.04 * Math.max(0, Math.sin(stepTime * 1.3)) ** 8
      pose.lift = -0.04
      break
    default:
      pose.lift = Math.sin(clock * 2) * 0.05
  }
  return pose
}

/** Three floating z's above a sleeping pet, rising and fading one after another. */
export function zPuffs(sleepTime: number): Puff[] {
  return Array.from({ length: Z_COUNT }, (_, index) => {
    const age = sleepTime - LIE_DOWN_SECONDS - (index * Z_PERIOD) / Z_COUNT
    if (age < 0) return { x: 0, y: 0, scale: 0, opacity: 0 }
    const p = (age % Z_PERIOD) / Z_PERIOD
    return { x: 0.15 + p * 0.3, y: p * 1.2, scale: 0.6 + 0.4 * p, opacity: p < 0.7 ? 1 : (1 - p) / 0.3 }
  })
}

/** Crumbs dropping from the mouth while the pet eats, relative to the mouth. */
export function crumbs(stepTime: number): Point[] {
  return [0, 1, 2].map((index) => {
    const p = ((stepTime + index * 0.17) % CRUMB_PERIOD) / CRUMB_PERIOD
    return { x: (index - 1) * 0.08 * (1 + p), y: -0.4 * p * p, z: 0.05 * p }
  })
}

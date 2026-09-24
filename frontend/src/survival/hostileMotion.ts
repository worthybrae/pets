import type { Look } from './creatureMotion'
import type { Creature, Point } from './types'

/**
 * How the hostile creatures move on top of what every creature does (creatureMotion.lookAt), from
 * the snapshot's `struck_at`, `burning_at` and state (backend/survival/creatures/view.py): a lunge
 * each time one strikes Mimo, a forward hunch while it chases, a skitter's scuttle as it goes, and
 * a burning gloomling's flicker as it shrinks away in the sun, with flames over it.
 */

export const STRIKE_SECONDS = 0.4
/** As long as a gloomling burns before it goes (backend/survival/creatures/hostiles.py BURN_SECONDS). */
export const BURN_SECONDS = 3
export const FLAME_BITS = 5
const FLAME_CYCLE = 0.6

function since(at: number | undefined, t: number): number | null {
  return at === undefined || t < at ? null : t - at
}

/** A hostile's look at server time `t` (`clock` runs on for idle motion); any other creature's comes back as it is. */
export function hostileLook(creature: Creature, look: Look, t: number, clock: number): Look {
  if (!creature.hostile) return look
  const next = { ...look }
  if (creature.state === 'chasing') next.pitch += 0.15
  if (creature.kind === 'skitter' && (creature.state === 'chasing' || creature.state === 'walking')) {
    next.roll += 0.12 * Math.sin(clock * 24)
  }
  const struck = since(creature.struck_at, t)
  if (struck !== null && struck < STRIKE_SECONDS) {
    const lunge = Math.sin((Math.PI * struck) / STRIKE_SECONDS)
    next.pitch += 0.6 * lunge
    next.lift += 0.05 * lunge
  }
  const burning = since(creature.burning_at, t)
  if (creature.state === 'burning' && burning !== null) {
    next.flash = Math.max(next.flash, 0.55 + 0.45 * Math.sin(clock * 20))
    next.size = Math.min(next.size, Math.max(0.2, 1 - (0.6 * burning) / BURN_SECONDS))
  }
  return next
}

/** Flames over a burning creature `height` blocks tall: FLAME_BITS bits rising and shrinking, as
 * offsets from its feet in blocks, with their size (1 at the bottom). None when it is not burning. */
export function flames(creature: Creature, t: number, height: number): (Point & { scale: number })[] {
  const burning = since(creature.burning_at, t)
  if (creature.state !== 'burning' || burning === null) return []
  return Array.from({ length: FLAME_BITS }, (_, index) => {
    const age = ((burning + index * 0.13) % FLAME_CYCLE) / FLAME_CYCLE
    const angle = index * 2.4
    return { x: Math.cos(angle) * 0.25, y: height * (0.3 + 0.8 * age), z: Math.sin(angle) * 0.25, scale: 1 - age }
  })
}

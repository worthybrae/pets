import type { MimoAction, Point } from './types'

/**
 * An arrow in flight (L2). A shot (backend/survival/creatures/archery.py) spends its first
 * RELEASE share drawing the bow; then the arrow flies from the pet to the creature it aimed at in a
 * low arc and lands when the shot ends. A shot that misses (`hit` false) flies on past the target
 * and drops. Cell coordinates; the arrow flies from the pet's chest to the target's middle.
 */

export const RELEASE = 0.6
/** Blocks a missed arrow flies past its target. */
export const MISS_PAST = 3
/** How high the arc rises, per block of flight. */
const ARC = 0.08
const CHEST = 0.8
const MIDDLE = 0.6

export interface ArrowPose extends Point {
  /** Radians around +y: 0 flies toward +z. */
  yaw: number
  /** Radians up from level: positive while it climbs. */
  pitch: number
}

/** Where the arrow of `step` is at server time `t`, shot from `from` (the pet's cell), or null. */
export function arrowAt(step: MimoAction | null, from: Point, t: number): ArrowPose | null {
  if (!step || step.kind !== 'shoot' || !step.target || step.ends_at === null) return null
  const release = step.started_at + (step.ends_at - step.started_at) * RELEASE
  if (t < release || t >= step.ends_at || step.ends_at <= release) return null
  const start = { x: from.x + 0.5, y: from.y + CHEST, z: from.z + 0.5 }
  let end = { x: step.target.x + 0.5, y: step.target.y + MIDDLE, z: step.target.z + 0.5 }
  const across = Math.hypot(end.x - start.x, end.z - start.z) || 1
  if (step.hit === false) {
    const on = (across + MISS_PAST) / across
    end = { x: start.x + (end.x - start.x) * on, y: step.target.y + 0.1, z: start.z + (end.z - start.z) * on }
  }
  const p = (t - release) / (step.ends_at - release)
  const flight = Math.hypot(end.x - start.x, end.z - start.z)
  const rise = ARC * flight
  return {
    x: start.x + (end.x - start.x) * p,
    y: start.y + (end.y - start.y) * p + rise * 4 * p * (1 - p),
    z: start.z + (end.z - start.z) * p,
    yaw: Math.atan2(end.x - start.x, end.z - start.z),
    pitch: Math.atan2(end.y - start.y + rise * 4 * (1 - 2 * p), flight),
  }
}

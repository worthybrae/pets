export type Vec3 = [number, number, number]

const EASE_RATE = 2

function normalize([x, y, z]: Vec3): Vec3 {
  const length = Math.hypot(x, y, z) || 1
  return [x / length, y / length, z / length]
}

/**
 * Eases a camera offset (camera position minus its focus point) from `current` toward
 * `target`'s direction, normalized and scaled to `distance`. Used so the fly-in's steep
 * starting offset settles into the normal follow angle instead of jumping there, and so
 * orbiting (which sets its own offset) is left alone whenever this isn't called.
 */
export function easeOffset(current: Vec3, target: Vec3, distance: number, dt: number): Vec3 {
  const [nx, ny, nz] = normalize(target)
  const goal: Vec3 = [nx * distance, ny * distance, nz * distance]
  const t = 1 - Math.exp(-EASE_RATE * dt)
  return [
    current[0] + (goal[0] - current[0]) * t,
    current[1] + (goal[1] - current[1]) * t,
    current[2] + (goal[2] - current[2]) * t,
  ]
}

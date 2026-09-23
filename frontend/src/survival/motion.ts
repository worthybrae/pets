import type { MimoAction, PathPoint, Point } from './types'

/** Where the pet is at a moment. Cell coordinates, fractional while moving; the pet stands at the cell's center. */
export interface Pose {
  x: number
  y: number
  z: number
  /** Heading in radians around +y (0 faces +z), or null to keep the last heading. */
  facing: number | null
  /** Path cells passed since the step began, fractional, for the hop cycle. */
  travelled: number
  /** True while the pet floats on water. */
  swimming: boolean
}

const PATH_KINDS = new Set(['walk', 'swim', 'fall'])

/** Server time now: the last response's server_time plus the local time since it arrived. */
export function serverNow(serverTime: number, receivedAt: number, now: number): number {
  return serverTime + Math.max(0, now - receivedAt)
}

export function facingToward(from: { x: number; z: number }, to: { x: number; z: number }): number | null {
  const dx = to.x - from.x
  const dz = to.z - from.z
  return dx === 0 && dz === 0 ? null : Math.atan2(dx, dz)
}

/** Turn `current` toward `target` by `amount` (0..1) of the way, the short way round. */
export function turnToward(current: number, target: number, amount: number): number {
  const difference = Math.atan2(Math.sin(target - current), Math.cos(target - current))
  return current + difference * amount
}

function alongPath(path: PathPoint[], t: number, falling: boolean): Pose {
  const last = path[path.length - 1]
  if (path.length === 1 || t >= last.at) {
    const previous = path[path.length - 2]
    return {
      x: last.x, y: last.y, z: last.z, facing: previous ? facingToward(previous, last) : null,
      travelled: path.length - 1, swimming: Boolean(last.swim),
    }
  }
  let index = 0
  while (index < path.length - 2 && t >= path[index + 1].at) index++
  const from = path[index]
  const to = path[index + 1]
  const span = to.at - from.at
  const p = span > 0 ? Math.min(1, Math.max(0, (t - from.at) / span)) : 1
  // A fall speeds up: the drop grows with the square of the time.
  const drop = falling ? p * p : p
  return {
    x: from.x + (to.x - from.x) * p,
    y: from.y + (to.y - from.y) * drop,
    z: from.z + (to.z - from.z) * p,
    facing: facingToward(from, to),
    travelled: index + p,
    swimming: Boolean(to.swim),
  }
}

/** Where the pet is and which way it faces at server time `t`. `rest` is the server's position. */
export function poseAt(action: MimoAction | null, rest: Point, t: number): Pose {
  if (action?.path && action.path.length > 0 && PATH_KINDS.has(action.kind)) {
    return alongPath(action.path, t, action.kind === 'fall')
  }
  return {
    x: rest.x, y: rest.y, z: rest.z, facing: action?.target ? facingToward(rest, action.target) : null,
    travelled: 0, swimming: false,
  }
}

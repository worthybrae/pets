import type { FinishedAction, MimoAction, PathPoint, Point } from './types'

/**
 * The viewer draws Mimo this many seconds behind server time. The server can start and finish a
 * short step between two polls; with the pet drawn a moment late, that step is still in
 * `recent_actions` when its time comes, so it plays out instead of Mimo jumping.
 */
export const REPLAY_DELAY = 1.5

export interface Replay {
  /** The step Mimo was doing at the replay time, or null between steps. */
  step: MimoAction | null
  /** Where Mimo stood when no path moves it. */
  rest: Point
}

function asStep(entry: FinishedAction): MimoAction {
  const step: MimoAction = { kind: entry.kind, started_at: entry.started_at, ends_at: entry.ended_at }
  if (entry.path) step.path = entry.path
  if (entry.target) step.target = entry.target
  if (entry.block) step.block = entry.block
  if (entry.item) step.item = entry.item
  if (entry.recipe) step.recipe = entry.recipe
  if (entry.hit !== undefined) step.hit = entry.hit
  return step
}

function startOf(path: PathPoint[] | undefined): Point | null {
  return path && path.length > 0 ? { x: path[0].x, y: path[0].y, z: path[0].z } : null
}

/** The last cell a path reached by `end` (a cut walk stops partway). */
function reachedBy(path: PathPoint[], end: number): Point {
  let spot = path[0]
  for (const point of path) if (point.at <= end) spot = point
  return { x: spot.x, y: spot.y, z: spot.z }
}

/**
 * The step to draw at server time `t`, from the finished steps (oldest first) and the current
 * one, and where Mimo stood between steps: the end of the last path before `t`, else the start of
 * the next walk, else the server's `position`.
 */
export function replayAt(action: MimoAction | null, recent: FinishedAction[], position: Point, t: number): Replay {
  let rest: Point | null = null
  for (const entry of recent) {
    if (entry.started_at > t) return { step: null, rest: rest ?? startOf(entry.path) ?? position }
    if (t < entry.ended_at) return { step: asStep(entry), rest: rest ?? position }
    if (entry.path && entry.path.length > 0) rest = reachedBy(entry.path, entry.ended_at)
  }
  if (action && action.started_at <= t) return { step: action, rest: rest ?? position }
  return { step: null, rest: rest ?? startOf(action?.path) ?? position }
}

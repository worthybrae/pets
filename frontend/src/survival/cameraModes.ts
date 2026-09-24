import type { Cutaway } from '../engine/columnRenderer'
import type { Vec3 } from './camera'
import { cutawayFor as terrainCutaway, underground, type BlockReader } from './cutaway'
import { facingToward, poseAt } from './motion'
import type { ActionKind, MimoAction, Point } from './types'

/**
 * The follow camera's modes, as pure maths (FollowCamera.tsx drives the three.js camera with it).
 *
 * - Overview: the orbit camera from high up and to the side, as before.
 * - Close: about five blocks behind Pip and three up, turning with it, so a tunnel reads as a cave.
 * - Eyes: from Pip's eye, looking where it walks or works.
 * - Auto: overview on the surface and close underground (`belowGround`), switching only once the
 *   new place has held for AUTO_HOLD_SECONDS, so a tunnel mouth doesn't make it flicker.
 *
 * Positions are world coordinates. `focus` is Pip's feet at the middle of its cell, (pose.x + 0.5,
 * pose.y, pose.z + 0.5); yaw is radians around +y with 0 facing +z (motion.ts), and pitch is
 * radians up from level.
 */

export type CameraMode = 'auto' | 'overview' | 'close' | 'eyes'
/** What the camera does on a frame: auto has resolved to overview or close. */
export type ViewMode = Exclude<CameraMode, 'auto'>
export type AutoPick = 'overview' | 'close'

/** Where the camera sits and the point it looks at. */
export interface Shot {
  position: Vec3
  lookAt: Vec3
}

/** In the order the HUD shows them and `C` cycles through them. */
export const CAMERA_MODES: readonly CameraMode[] = ['auto', 'overview', 'close', 'eyes']
const NAMES: Record<CameraMode, string> = { auto: 'Auto', overview: 'Overview', close: 'Close', eyes: 'Eyes' }
export const CAMERA_MODE_KEY = 'mimo.cameraMode'

/** The overview camera's direction from its focus (about 35 degrees up), before scaling. */
export const OVERVIEW_DIRECTION: Vec3 = [18, 13, 18]
export const CLOSE_DISTANCE = 5
export const MIN_CLOSE_DISTANCE = 3
export const MAX_CLOSE_DISTANCE = 10
/** The close camera's height per block of distance behind Pip: 3 up at 5 back. */
const CLOSE_RISE = 0.6
/** Pip's head over its feet, where the close camera looks. */
export const HEAD_HEIGHT = 0.8
/** Pip's eye over its feet, inside a one-block tunnel. */
export const EYE_HEIGHT = 0.75
/** How far the eye camera sits ahead of Pip's middle, so its own head isn't in view. */
export const EYE_FORWARD = 0.3
/** How far ahead of the eye its look point is. */
const LOOK_AHEAD = 4
export const MAX_PITCH = Math.PI / 3
/** Within this of Pip's head the camera is inside it, and the pet is not drawn. */
const INSIDE_PET = 1.2
/** How far past the close camera the close cut reaches, so the camera and its near plane sit in
 * open air, not inside the rock around a tunnel. */
export const CLOSE_CUT_MARGIN = 1.5
export const AUTO_HOLD_SECONDS = 1.5
/** How long the camera takes to move to a new mode's shot. */
export const SWITCH_SECONDS = 0.4
/** The near plane in eyes mode, with tunnel walls a fraction of a block away. */
export const EYES_NEAR = 0.05
/** Damping rates (per second) once a switch is done. */
export const CLOSE_FOLLOW_RATE = 6
export const EYES_FOLLOW_RATE = 20
export const YAW_RATE = 4
export const PITCH_RATE = 4
const WHEEL_ZOOM = 0.002

const PATH_KINDS = new Set<ActionKind>(['walk', 'swim', 'fall'])
/** Steps Pip faces its target for. Smelt, store, take and drop are here too: the pet turns to
 * the furnace or chest for them (motion.ts), so the close camera stays behind it. */
const WORK_KINDS = new Set<ActionKind>([
  'mine', 'place', 'pick', 'harvest', 'till', 'plant', 'fish', 'cook', 'eat', 'craft', 'smelt', 'store', 'take', 'drop',
])
const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value))
}

function wrapAngle(angle: number): number {
  return Math.atan2(Math.sin(angle), Math.cos(angle))
}

function blankShot(): Shot {
  return { position: [0, 0, 0], lookAt: [0, 0, 0] }
}

export function isCameraMode(value: unknown): value is CameraMode {
  return CAMERA_MODES.includes(value as CameraMode)
}

export function nextMode(mode: CameraMode): CameraMode {
  return CAMERA_MODES[(CAMERA_MODES.indexOf(mode) + 1) % CAMERA_MODES.length]
}

/** The mode's name, with auto's pick once it has made one: "Auto (close)". */
export function modeLabel(mode: CameraMode, pick: AutoPick | null): string {
  return mode === 'auto' && pick ? `${NAMES.auto} (${pick})` : NAMES[mode]
}

export interface KeyPress {
  key: string
  ctrlKey?: boolean
  metaKey?: boolean
  altKey?: boolean
  shiftKey?: boolean
  target?: unknown
}

function typingIn(target: unknown): boolean {
  if (typeof target !== 'object' || target === null) return false
  const element = target as { tagName?: unknown; isContentEditable?: unknown }
  return element.isContentEditable === true
    || (typeof element.tagName === 'string' && TYPING_TAGS.has(element.tagName.toUpperCase()))
}

/** Whether a key press cycles the camera: C, without Ctrl, Cmd or Alt, and not while typing. */
export function isCameraKey(event: KeyPress): boolean {
  if (event.key !== 'c' && event.key !== 'C') return false
  return !event.ctrlKey && !event.metaKey && !event.altKey && !typingIn(event.target)
}

/** The remembered mode, or auto. `storage` may throw (blocked storage), and so may reading it. */
export function loadCameraMode(storage: () => Pick<Storage, 'getItem'>): CameraMode {
  try {
    const saved = storage().getItem(CAMERA_MODE_KEY)
    return isCameraMode(saved) ? saved : 'auto'
  } catch {
    return 'auto'
  }
}

export function saveCameraMode(storage: () => Pick<Storage, 'setItem'>, mode: CameraMode): void {
  try {
    storage().setItem(CAMERA_MODE_KEY, mode)
  } catch {
    // Blocked or full storage: the choice lasts for this visit only.
  }
}

/** The cell a work step acts on, or null for any other step. */
export function workTarget(step: MimoAction | null): Point | null {
  return step?.target && WORK_KINDS.has(step.kind) ? step.target : null
}

/**
 * Which way Pip faces at server time `t` in the replayed `step` (see replay.ts): along its path
 * while it walks, swims or falls, toward the target cell while it works, and otherwise (or when
 * that has no horizontal direction, like a straight drop or mining straight down) `last`.
 */
export function headingOf(step: MimoAction | null, rest: Point, t: number, last: number): number {
  if (step?.path && step.path.length > 0 && PATH_KINDS.has(step.kind)) return poseAt(step, rest, t).facing ?? last
  const target = workTarget(step)
  const facing = target ? facingToward(rest, target) : null
  return facing ?? last
}

/** `current` moved toward `target` by exponential damping over `dt` seconds. */
export function damp(current: number, target: number, dt: number, rate: number): number {
  return current + (target - current) * (1 - Math.exp(-rate * dt))
}

/** A yaw damped toward `target` along the shorter arc, wrapped to ±π. */
export function smoothYaw(current: number, target: number, dt: number, rate: number): number {
  return wrapAngle(damp(current, current + wrapAngle(target - current), dt, rate))
}

/** Where the close camera sits for Pip at `focus` facing `yaw`, `distance` blocks behind. */
export function closeCamera(focus: Vec3, yaw: number, distance: number, out: Shot = blankShot()): Shot {
  const back = clamp(distance, MIN_CLOSE_DISTANCE, MAX_CLOSE_DISTANCE)
  const [x, y, z] = focus
  out.position[0] = x - Math.sin(yaw) * back
  out.position[1] = y + back * CLOSE_RISE
  out.position[2] = z - Math.cos(yaw) * back
  out.lookAt[0] = x
  out.lookAt[1] = y + HEAD_HEIGHT
  out.lookAt[2] = z
  return out
}

/** The close camera's distance after a wheel turn (`deltaY` > 0 moves it out). */
export function zoomClose(distance: number, deltaY: number): number {
  return clamp(distance * Math.exp(deltaY * WHEEL_ZOOM), MIN_CLOSE_DISTANCE, MAX_CLOSE_DISTANCE)
}

/** The camera at Pip's eye, looking along `yaw`, tilted by `pitch` (clamped to ±MAX_PITCH). */
export function eyesCamera(focus: Vec3, yaw: number, pitch: number, out: Shot = blankShot()): Shot {
  const tilt = clamp(pitch, -MAX_PITCH, MAX_PITCH)
  const forwardX = Math.sin(yaw)
  const forwardZ = Math.cos(yaw)
  const [x, y, z] = focus
  out.position[0] = x + forwardX * EYE_FORWARD
  out.position[1] = y + EYE_HEIGHT
  out.position[2] = z + forwardZ * EYE_FORWARD
  out.lookAt[0] = out.position[0] + forwardX * Math.cos(tilt) * LOOK_AHEAD
  out.lookAt[1] = out.position[1] + Math.sin(tilt) * LOOK_AHEAD
  out.lookAt[2] = out.position[2] + forwardZ * Math.cos(tilt) * LOOK_AHEAD
  return out
}

/** The eye camera's pitch toward the middle of a work `target` cell, or level without one. */
export function eyesPitch(focus: Vec3, yaw: number, target: Point | null): number {
  if (!target) return 0
  const eyeX = focus[0] + Math.sin(yaw) * EYE_FORWARD
  const eyeZ = focus[2] + Math.cos(yaw) * EYE_FORWARD
  const rise = target.y + 0.5 - (focus[1] + EYE_HEIGHT)
  const across = Math.hypot(target.x + 0.5 - eyeX, target.z + 0.5 - eyeZ)
  return clamp(Math.atan2(rise, across), -MAX_PITCH, MAX_PITCH)
}

/** Whether a camera at `camera` is inside Pip at `focus`, so the pet should not be drawn. */
export function hidesPet(camera: Vec3, focus: Vec3): boolean {
  return Math.hypot(camera[0] - focus[0], camera[1] - focus[1] - HEAD_HEIGHT, camera[2] - focus[2]) < INSIDE_PET
}

/** Where the overview camera settles when it follows `focus` from `distance` away. */
export function overviewCamera(focus: Vec3, distance: number, out: Shot = blankShot()): Shot {
  const length = Math.hypot(...OVERVIEW_DIRECTION)
  for (let axis = 0; axis < 3; axis++) {
    out.position[axis] = focus[axis] + (OVERVIEW_DIRECTION[axis] / length) * distance
    out.lookAt[axis] = focus[axis]
  }
  return out
}

/**
 * Whether auto counts Pip, in `cell`, as underground: covered (cutaway.ts `underground`) and down in
 * the natural ground, whose top block at its column is at `groundTop` (worldgen terrainHeight). A
 * tunnel, cave or dug home counts; a shelter it built on the ground doesn't, so there auto keeps the
 * overview and its wall and roof cutaway.
 */
export function belowGround(store: BlockReader, cell: Point, groundTop: number): boolean {
  return cell.y <= groundTop && underground(store, cell)
}

/**
 * Auto's pick: close while Pip is underground, overview otherwise, changing from `current` only
 * once the new condition has held since `since` for AUTO_HOLD_SECONDS (times in seconds).
 */
export function autoMode(current: AutoPick, underground: boolean, since: number, now: number): AutoPick {
  const wanted: AutoPick = underground ? 'close' : 'overview'
  if (wanted === current) return current
  return now - since >= AUTO_HOLD_SECONDS ? wanted : current
}

function ease(progress: number): number {
  const p = clamp(progress, 0, 1)
  return p * p * (3 - 2 * p)
}

/**
 * How much of the remaining way to a new shot to move this frame, `elapsed` seconds after a mode
 * switch: an eased move that arrives after `duration` whatever the frame rate. 1 once it's over.
 */
export function switchFactor(elapsed: number, dt: number, duration = SWITCH_SECONDS): number {
  const before = ease(elapsed / duration)
  if (before >= 1) return 1
  return (ease((elapsed + dt) / duration) - before) / (1 - before)
}

/**
 * The close cut's radius for the close camera `distance` blocks behind Pip (clamped the way
 * closeCamera clamps it): out to just past the camera, so it never starts inside rock, and no
 * wider, so a tunnel still reads as a cave. About 6.5 blocks at the usual 5.
 */
export function closeCutRadius(distance: number): number {
  return clamp(distance, MIN_CLOSE_DISTANCE, MAX_CLOSE_DISTANCE) + CLOSE_CUT_MARGIN
}

/**
 * The terrain cut for a view mode. Overview keeps cutaway.ts's cut as it is: over Mimo underground,
 * and over the walls and roofs of its shelter when they hide it from the camera (`walled`, held by
 * cutaway.ts holdWallCut). Close keeps both but centred on Pip out to closeCutRadius of the current
 * `closeDistance`, so the tunnel reads as a cave from just above and behind. Eyes has none: Pip is
 * inside the tunnel and sees its real walls and roof.
 */
export function cutawayFor(mode: ViewMode, store: BlockReader, pose: Point, walled: boolean,
  closeDistance = CLOSE_DISTANCE): Cutaway | null {
  if (mode === 'eyes') return null
  const cut = terrainCutaway(store, pose, walled)
  if (!cut || mode === 'overview') return cut
  return { ...cut, radius: closeCutRadius(closeDistance) }
}

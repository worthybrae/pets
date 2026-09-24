import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import type { OrbitControls as OrbitControlsType } from 'three-stdlib'
import * as THREE from 'three'
import { easeOffset, type Vec3 } from './camera'
import {
  CLOSE_DISTANCE, CLOSE_FOLLOW_RATE, EYES_FOLLOW_RATE, EYES_NEAR, OVERVIEW_DIRECTION, PITCH_RATE, SWITCH_SECONDS,
  YAW_RATE, autoMode, belowGround, closeCamera, damp, eyesCamera, eyesPitch, headingOf, hidesPet, overviewCamera, smoothYaw,
  switchFactor, workTarget, zoomClose, type AutoPick, type CameraMode, type Shot, type ViewMode,
} from './cameraModes'
import type { BlockReader } from './cutaway'
import { poseAt } from './motion'
import type { Replay } from './replay'
import { fogRange } from '../engine/fog'
import { terrainHeight } from '../engine/worldgen'

interface Focus {
  x: number
  z: number
}

/** The replayed step at a replay time `t`, as replayAt gives it. */
export interface ReplayedStep extends Replay {
  t: number
}

/** Per-frame camera state, kept out of React. */
interface Track {
  heading: number
  yaw: number
  pitch: number
  /** Auto's pick, null outside auto. */
  pick: AutoPick | null
  below: boolean
  since: number
  reported: AutoPick | null
  /** The mode being drawn, null before the first frame. */
  shown: ViewMode | null
  switchedAt: number
  /** Whether the latest switch moves the camera (not the first overview frame, which flies in). */
  glide: boolean
  cut: ViewMode
  closeDistance: number
  baseNear: number
  feet: Vec3
  focus: Vec3
  eye: Vec3
  shot: Shot
  desired: THREE.Vector3
  offset: THREE.Vector3
}

function newTrack(near: number): Track {
  return {
    heading: 0, yaw: 0, pitch: 0, pick: null, below: false, since: 0, reported: null, shown: null, switchedAt: 0,
    glide: false, cut: 'overview', closeDistance: CLOSE_DISTANCE, baseNear: near,
    feet: [0, 0, 0], focus: [0, 0, 0], eye: [0, 0, 0], shot: { position: [0, 0, 0], lookAt: [0, 0, 0] },
    desired: new THREE.Vector3(), offset: new THREE.Vector3(),
  }
}

/** Pixels per line for wheel events that count in lines (Firefox). */
const WHEEL_LINE = 16

/**
 * The camera, in the mode `mode` (cameraModes.ts). Overview is orbit controls that glide after a
 * focus point; close and eyes follow Pip themselves with the controls off, and the wheel moves the
 * close camera nearer or farther. A switch between modes glides over SWITCH_SECONDS. Every mode
 * keeps the fog past the camera's target and reports chunk changes.
 */
export default function FollowCamera({ focus, focusY, stepAt, initialFocus, initialFocusY, distance, follow, viewDistance, mode = 'overview', store, onView, onAutoPick, onOrbit, onChunkChange }: {
  focus: Focus
  focusY: number
  /** When present, read each frame instead of the static `focus`/`focusY`, to track the replayed pet. */
  stepAt?: () => ReplayedStep
  initialFocus: Focus
  initialFocusY: number
  distance: number
  follow: boolean
  viewDistance: number
  mode?: CameraMode
  /** For auto's underground test: its blocks, and its seed for the natural ground height. */
  store: BlockReader & { readonly seed: string }
  /**
   * Called each frame with the mode whose terrain cut to draw (eyes switches the cut off only once
   * the camera has arrived) and whether the camera is inside Pip, which then isn't drawn.
   */
  onView?: (cut: ViewMode, petHidden: boolean) => void
  /** Called when auto picks overview or close. */
  onAutoPick?: (pick: AutoPick) => void
  onOrbit: () => void
  onChunkChange: (x: number, z: number) => void
}) {
  const controlsRef = useRef<OrbitControlsType>(null)
  const lastChunk = useRef('')
  const track = useRef<Track | null>(null)
  const gl = useThree((three) => three.gl)

  useEffect(() => {
    const element = gl.domElement
    const wheel = (event: WheelEvent) => {
      const state = track.current
      if (!state || state.shown !== 'close') return
      state.closeDistance = zoomClose(state.closeDistance, event.deltaMode === 1 ? event.deltaY * WHEEL_LINE : event.deltaY)
    }
    element.addEventListener('wheel', wheel, { passive: true })
    return () => element.removeEventListener('wheel', wheel)
  }, [gl])

  useFrame((state, delta) => {
    const controls = controlsRef.current
    if (!controls) return
    const { camera } = state
    track.current ??= newTrack(camera.near)
    const s = track.current
    const now = state.clock.elapsedTime
    const replayed = stepAt?.()
    const pose = replayed ? poseAt(replayed.step, replayed.rest, replayed.t) : null
    s.focus[0] = pose ? pose.x : focus.x
    s.focus[1] = pose ? pose.y : focusY
    s.focus[2] = pose ? pose.z : focus.z
    s.feet[0] = s.focus[0] + 0.5
    s.feet[1] = s.focus[1]
    s.feet[2] = s.focus[2] + 0.5

    // Where Pip faces and looks, tracked in every mode so a switch starts from where it faces now.
    const first = s.shown === null
    if (replayed) s.heading = headingOf(replayed.step, replayed.rest, replayed.t, s.heading)
    s.yaw = first ? s.heading : smoothYaw(s.yaw, s.heading, delta, YAW_RATE)
    s.pitch = damp(s.pitch, eyesPitch(s.feet, s.yaw, replayed ? workTarget(replayed.step) : null), delta, PITCH_RATE)

    let viewMode: ViewMode
    if (mode === 'auto') {
      const cell = { x: Math.round(s.focus[0]), y: Math.round(s.focus[1]), z: Math.round(s.focus[2]) }
      const below = belowGround(store, cell, terrainHeight(cell.x, cell.z, store.seed))
      if (s.pick === null || below !== s.below) {
        s.below = below
        s.since = now
      }
      s.pick = s.pick === null ? (below ? 'close' : 'overview') : autoMode(s.pick, below, s.since, now)
      if (s.pick !== s.reported) {
        s.reported = s.pick
        onAutoPick?.(s.pick)
      }
      viewMode = s.pick
    } else {
      s.pick = null
      viewMode = mode
    }
    if (viewMode !== s.shown) {
      // The first overview frame keeps the fly-in; every other switch glides to the new shot.
      s.glide = !(first && viewMode === 'overview')
      s.shown = viewMode
      s.switchedAt = now
    }
    const elapsed = now - s.switchedAt
    const gliding = s.glide && elapsed < SWITCH_SECONDS
    // Eyes turns the cut off once the camera is at the eye; until then the last cut stays.
    if (!(viewMode === 'eyes' && gliding)) s.cut = viewMode

    if (camera instanceof THREE.PerspectiveCamera) {
      const near = viewMode === 'eyes' ? EYES_NEAR : s.baseNear
      if (camera.near !== near) {
        camera.near = near
        camera.updateProjectionMatrix()
      }
    }

    if (viewMode === 'overview' && !gliding) {
      controls.enabled = true
      if (follow) {
        const movement = s.desired.set(s.focus[0], s.focus[1], s.focus[2]).sub(controls.target)
          .multiplyScalar(1 - Math.exp(-3 * delta))
        controls.target.add(movement)
        camera.position.add(movement)
        const offset = s.offset.copy(camera.position).sub(controls.target)
        const [ex, ey, ez] = easeOffset([offset.x, offset.y, offset.z], OVERVIEW_DIRECTION, distance, delta)
        camera.position.set(controls.target.x + ex, controls.target.y + ey, controls.target.z + ez)
        controls.update()
      }
    } else {
      // Close, eyes, or gliding back to the overview: the controls are off and the camera moves itself.
      controls.enabled = false
      const shot = viewMode === 'close' ? closeCamera(s.feet, s.yaw, s.closeDistance, s.shot)
        : viewMode === 'eyes' ? eyesCamera(s.feet, s.yaw, s.pitch, s.shot)
          : overviewCamera(s.focus, distance, s.shot)
      const amount = gliding
        ? switchFactor(elapsed, delta)
        : 1 - Math.exp(-(viewMode === 'eyes' ? EYES_FOLLOW_RATE : CLOSE_FOLLOW_RATE) * delta)
      const [px, py, pz] = shot.position
      const [lx, ly, lz] = shot.lookAt
      camera.position.set(
        camera.position.x + (px - camera.position.x) * amount,
        camera.position.y + (py - camera.position.y) * amount,
        camera.position.z + (pz - camera.position.z) * amount,
      )
      controls.target.set(
        controls.target.x + (lx - controls.target.x) * amount,
        controls.target.y + (ly - controls.target.y) * amount,
        controls.target.z + (lz - controls.target.z) * amount,
      )
      camera.lookAt(controls.target)
    }
    s.eye[0] = camera.position.x
    s.eye[1] = camera.position.y
    s.eye[2] = camera.position.z
    onView?.(s.cut, hidesPet(s.eye, s.feet))

    // Fog follows the live camera distance, so zooming out does not fade Mimo into fog early.
    const fog = state.scene.fog
    if (fog instanceof THREE.Fog) {
      const [near, far] = fogRange(viewDistance, camera.position.distanceTo(controls.target))
      fog.near = near
      fog.far = far
    }
    const cx = Math.floor(controls.target.x / 16)
    const cz = Math.floor(controls.target.z / 16)
    const key = `${cx},${cz}`
    if (key !== lastChunk.current) {
      lastChunk.current = key
      onChunkChange(cx, cz)
    }
  })

  return (
    <OrbitControls ref={controlsRef} target={[initialFocus.x, initialFocusY, initialFocus.z]}
      enableDamping dampingFactor={0.08} minDistance={11} maxDistance={130}
      maxPolarAngle={Math.PI / 2.04} onStart={onOrbit} />
  )
}

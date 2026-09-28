import { useMemo, useRef, type ReactNode } from 'react'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import PetVoxels from '../components/world/PetVoxels'
import { previewPet } from '../components/world/previewWorld'
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import { BODY_MIDDLE, TUNIC_SCALE, capVoxels, hurtGlow, tunicVoxels } from './petGear'
import { poseAt, turnToward } from './motion'
import { replayAt } from './replay'
import type { Ailments, FinishedAction, MimoAction, Point } from './types'
import { petAilment, shiverAt } from './wild'

const SCALE = 0.31
/** The pet's voxels span x -1..2 in model units, so its middle sits half a voxel right of the origin. */
const MODEL_OFFSET: [number, number, number] = [-0.5 * SCALE, 0, 0]
const TURN_RATE = 10
const HELLO_HOP_SECONDS = 0.7
const Z_COLOR = '#f5faf7'
const CRUMB_COLOR = '#c99a6b'
const BAR: [number, number, number] = [0.24, 0.05, 0.05]
const NO_STEPS: FinishedAction[] = []
const UNDER_BODY: [number, number, number] = [-BODY_MIDDLE[0], -BODY_MIDDLE[1], -BODY_MIDDLE[2]]
const GLOW_COLOR = '#e0463a'
const SICK_COLOR = '#7fb069'  // W1: a sick pet's green tint
const WRAP_COLOR = '#f4f0e4'
const MARK_COLOR = '#b5473a'
const ASK_COLOR = '#f5c46b'
/** W1: a "?" of little boxes floating over the pet's head, as [x, y] in pet units. */
const QUESTION_MARK: [number, number][] = [[-0.08, 0.3], [0, 0.36], [0.08, 0.3], [0.08, 0.22], [0, 0.14], [0, 0.06], [0, -0.06]]

/** One floating "z" made of three thin bars, in the voxel style. */
function SleepZ() {
  return (
    <group>
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={BAR} />
        <meshBasicMaterial color={Z_COLOR} transparent depthWrite={false} />
      </mesh>
      <mesh rotation={[0, 0, Math.atan2(0.2, 0.24)]}>
        <boxGeometry args={[0.31, 0.05, 0.05]} />
        <meshBasicMaterial color={Z_COLOR} transparent depthWrite={false} />
      </mesh>
      <mesh position={[0, -0.1, 0]}>
        <boxGeometry args={BAR} />
        <meshBasicMaterial color={Z_COLOR} transparent depthWrite={false} />
      </mesh>
    </group>
  )
}

function setOpacity(object: THREE.Object3D, opacity: number) {
  object.traverse((child) => {
    if (child instanceof THREE.Mesh && child.material instanceof THREE.MeshBasicMaterial) child.material.opacity = opacity
  })
}

/**
 * The survival pet, driven by the step it was doing at `now` (the current step or a finished one,
 * see replay.ts): it follows a walk's timed path, turns to face where it goes or what it works on,
 * and plays the step's animation. L2: it wears the leather tunic and cap it carries (`tunic`,
 * `cap`) and glows red for a moment when a creature hits it (`hurtAt`, server time). Cheap on
 * phones: no React state changes per frame, a handful of meshes, and all per-frame work in one
 * useFrame.
 */
export default function SurvivalPet({ action, recent = NO_STEPS, position, now, onPetClick, hopSignal = 0, hidden,
  tunic = null, cap = null, hurtAt = null, ailments = null, asking = false, children }: {
  action: MimoAction | null
  /** Finished steps, oldest first, so short steps between polls still play out. */
  recent?: FinishedAction[]
  /** The server's position for the pet, used when no path says where it stands. */
  position: Point
  /** The time to draw, in server seconds (WorldCanvas passes server time minus REPLAY_DELAY). */
  now: () => number
  onPetClick?: () => void
  hopSignal?: number
  /** Read each frame: true while the camera is inside the pet (eyes mode), which then draws none
   * of its meshes. Lights, like its night glow, stay on. */
  hidden?: () => boolean
  /** L3: the tunic and cap it wears (petGear.wornTunic and wornCap), or null. */
  tunic?: string | null
  cap?: string | null
  hurtAt?: number | null
  /** W1: what ails it (a green tint, a droop and a slower hop while sick, a shiver with a chill, a wrap on a
   * dressed wound, a red mark while one festers) and whether it has just asked something (a "?" over it). */
  ailments?: Ailments | null
  asking?: boolean
  children?: ReactNode
}) {
  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const zs = useRef<THREE.Group>(null)
  const crumbBits = useRef<THREE.Group>(null)
  const heading = useRef<number | null>(null)
  const hello = useRef({ signal: hopSignal, left: 0 })
  const drawn = useRef(true)
  const glow = useRef<THREE.Mesh>(null)
  const glowMaterial = useRef<THREE.MeshBasicMaterial>(null)
  const tunicParts = useMemo(() => tunicVoxels(tunic ? { [tunic]: 1 } : {}), [tunic])
  const ailing = useMemo(() => petAilment(ailments), [ailments])
  const capParts = useMemo(() => capVoxels(cap ? { [cap]: 1 } : {}), [cap])

  useFrame((state, delta) => {
    const t = now()
    const { step, rest } = replayAt(action, recent, position, t)
    const pose = poseAt(step, rest, t)
    const move = moveFor(step, t, pose.swimming)
    const stepTime = step ? Math.max(0, t - step.started_at) : 0
    const shape = bodyPose(move, stepTime, pose.travelled, state.clock.elapsedTime)
    if (hello.current.signal !== hopSignal) hello.current = { signal: hopSignal, left: HELLO_HOP_SECONDS }
    hello.current.left = Math.max(0, hello.current.left - delta)
    const hop = hello.current.left > 0 ? Math.sin((1 - hello.current.left / HELLO_HOP_SECONDS) * Math.PI) * 0.5 : 0
    if (pose.facing !== null) {
      heading.current = heading.current === null
        ? pose.facing
        : turnToward(heading.current, pose.facing, 1 - Math.exp(-TURN_RATE * delta))
    }
    if (root.current) {
      root.current.position.set(pose.x + 0.5, pose.y + (shape.lift + hop) * ailing.hop, pose.z + 0.5)
      root.current.rotation.y = heading.current ?? 0
    }
    if (body.current) {
      const shiver = ailing.shiver ? shiverAt(state.clock.elapsedTime) : 0
      body.current.rotation.set(shape.pitch + (ailing.droop ? 0.12 : 0), 0, shape.roll + shiver)
      body.current.scale.set(1, shape.stretch, 1)
    }
    const floating = zs.current
    if (floating) {
      floating.visible = move === 'sleep'
      if (floating.visible) {
        zPuffs(stepTime).forEach((puff, index) => {
          const z = floating.children[index]
          if (!z) return
          z.position.set(puff.x, puff.y, 0)
          z.scale.setScalar(puff.scale)
          setOpacity(z, puff.opacity)
        })
      }
    }
    const bits = crumbBits.current
    if (bits) {
      bits.visible = move === 'eat'
      if (bits.visible) crumbs(stepTime).forEach((bit, index) => bits.children[index]?.position.set(bit.x, bit.y, bit.z))
    }
    // Meshes only: hiding the group would also drop its glow light, and a light count change
    // recompiles every lit material.
    const show = !hidden?.()
    if (root.current && (show !== drawn.current || !show)) {
      drawn.current = show
      root.current.traverse((child) => {
        if (child instanceof THREE.Mesh) child.visible = show
      })
    }
    const red = hurtGlow(hurtAt, t)
    if (glow.current) glow.current.visible = show && red > 0
    if (glowMaterial.current) glowMaterial.current.opacity = 0.45 * red
  })

  const click = (event: ThreeEvent<MouseEvent>) => {
    event.stopPropagation()
    hello.current.left = HELLO_HOP_SECONDS
    onPetClick?.()
  }

  return (
    <group ref={root} onClick={click}>
      <group ref={body}>
        <group position={MODEL_OFFSET} scale={SCALE}>
          <PetVoxels voxels={previewPet.voxels} />
          {tunicParts.length > 0 && (
            <group position={BODY_MIDDLE} scale={TUNIC_SCALE}>
              <group position={UNDER_BODY}>
                <PetVoxels voxels={tunicParts} />
              </group>
            </group>
          )}
          {capParts.length > 0 && <PetVoxels voxels={capParts} />}
          {children}
        </group>
        {ailing.tint > 0 && (
          <mesh position={[0, 0.95, 0.1]}>
            <boxGeometry args={[1.08, 1.92, 1.08]} />
            <meshBasicMaterial color={SICK_COLOR} transparent opacity={ailing.tint} depthWrite={false} />
          </mesh>
        )}
        {ailing.wrap && (
          <mesh position={[0.36, 0.45, 0.05]}>
            <boxGeometry args={[0.08, 0.2, 0.42]} />
            <meshLambertMaterial color={WRAP_COLOR} />
          </mesh>
        )}
        {ailing.mark && (
          <mesh position={[0.35, 0.45, 0.05]}>
            <boxGeometry args={[0.06, 0.14, 0.14]} />
            <meshBasicMaterial color={MARK_COLOR} />
          </mesh>
        )}
        <mesh ref={glow} position={[0, 0.95, 0.1]} visible={false}>
          <boxGeometry args={[1.1, 1.95, 1.1]} />
          <meshBasicMaterial ref={glowMaterial} color={GLOW_COLOR} transparent opacity={0} depthWrite={false} />
        </mesh>
      </group>
      {asking && (
        <group position={[0, 1.6, 0]}>
          {QUESTION_MARK.map(([x, y]) => (
            <mesh key={`${x},${y}`} position={[x, y, 0]}>
              <boxGeometry args={[0.07, 0.07, 0.07]} />
              <meshBasicMaterial color={ASK_COLOR} />
            </mesh>
          ))}
        </group>
      )}
      <group ref={zs} position={[0, 1.15, 0]} visible={false}>
        {[0, 1, 2].map((index) => <SleepZ key={index} />)}
      </group>
      <group ref={crumbBits} position={[0, 0.78, 0.7]} visible={false}>
        {[0, 1, 2].map((index) => (
          <mesh key={index}>
            <boxGeometry args={[0.05, 0.05, 0.05]} />
            <meshLambertMaterial color={CRUMB_COLOR} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

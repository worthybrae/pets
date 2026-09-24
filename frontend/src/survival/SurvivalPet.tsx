import { useRef, type ReactNode } from 'react'
import { useFrame, type ThreeEvent } from '@react-three/fiber'
import * as THREE from 'three'
import PetVoxels from '../components/world/PetVoxels'
import { previewPet } from '../components/world/previewWorld'
import { bodyPose, crumbs, moveFor, zPuffs } from './animation'
import { poseAt, turnToward } from './motion'
import { replayAt } from './replay'
import type { FinishedAction, MimoAction, Point } from './types'

const SCALE = 0.31
/** The pet's voxels span x -1..2 in model units, so its middle sits half a voxel right of the origin. */
const MODEL_OFFSET: [number, number, number] = [-0.5 * SCALE, 0, 0]
const TURN_RATE = 10
const HELLO_HOP_SECONDS = 0.7
const Z_COLOR = '#f5faf7'
const CRUMB_COLOR = '#c99a6b'
const BAR: [number, number, number] = [0.24, 0.05, 0.05]
const NO_STEPS: FinishedAction[] = []

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
 * and plays the step's animation. Cheap on phones: no React state changes per frame, a handful of
 * meshes, and all per-frame work in one useFrame.
 */
export default function SurvivalPet({ action, recent = NO_STEPS, position, now, onPetClick, hopSignal = 0, hidden, children }: {
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
  children?: ReactNode
}) {
  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const zs = useRef<THREE.Group>(null)
  const crumbBits = useRef<THREE.Group>(null)
  const heading = useRef<number | null>(null)
  const hello = useRef({ signal: hopSignal, left: 0 })
  const drawn = useRef(true)

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
      root.current.position.set(pose.x + 0.5, pose.y + shape.lift + hop, pose.z + 0.5)
      root.current.rotation.y = heading.current ?? 0
    }
    if (body.current) {
      body.current.rotation.set(shape.pitch, 0, shape.roll)
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
          {children}
        </group>
      </group>
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

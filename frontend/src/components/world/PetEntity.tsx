import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { PetEntity as PetEntityType } from '../../types/world'
import { type WorldCollider, getGroundLevel, canMoveTo, GRAVITY, TERMINAL_VELOCITY } from './physics'
import ThoughtBubble from './ThoughtBubble'

type WanderState = 'idle' | 'walking' | 'pausing'

const WANDER_RADIUS = 30
const WALK_SPEED = 3
const PAUSE_MIN = 1.5
const PAUSE_MAX = 4
const IDLE_BEFORE_FIRST_WALK = 2
const BOB_AMPLITUDE = 0.06
const BOB_SPEED = 2.5

interface PetEntityProps {
  pet: PetEntityType
  thought?: string | null
  collider?: WorldCollider
  onPositionChange?: (pos: { x: number; y: number; z: number }) => void
}

function randomTarget(origin: { x: number; z: number }, collider?: WorldCollider) {
  // Try up to 15 times to find a reachable, valid target
  for (let attempt = 0; attempt < 15; attempt++) {
    const angle = Math.random() * Math.PI * 2
    const dist = 4 + Math.random() * (WANDER_RADIUS - 4)
    const x = origin.x + Math.cos(angle) * dist
    const z = origin.z + Math.sin(angle) * dist

    if (!collider) return new THREE.Vector3(x, 0, z)

    // Check the target is walkable (has ground, is reachable)
    const groundY = getGroundLevel(collider, x, z)
    if (canMoveTo(collider, x, z, groundY)) {
      return new THREE.Vector3(x, groundY, z)
    }
  }
  // Fallback: stay near origin
  return new THREE.Vector3(origin.x, 0, origin.z)
}

export default function PetEntity({ pet, thought, collider, onPositionChange }: PetEntityProps) {
  const groupRef = useRef<THREE.Group>(null)
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)
  const initializedRef = useRef(false)
  const prevVoxelsRef = useRef(pet.voxels)

  // Wander state machine refs
  const wanderState = useRef<WanderState>('idle')
  const stateTimer = useRef(IDLE_BEFORE_FIRST_WALK)
  const currentPos = useRef(new THREE.Vector3(pet.position.x, pet.position.y, pet.position.z))
  const targetPos = useRef(new THREE.Vector3(pet.position.x, 0, pet.position.z))
  const currentRotY = useRef(0)
  const origin = useRef({ x: pet.position.x, z: pet.position.z })

  // Physics state
  const velocityY = useRef(0)
  const isGrounded = useRef(true)

  useFrame((_, delta) => {
    timeRef.current += delta

    // --- Voxel instancing setup ---
    if (meshRef.current && (!initializedRef.current || prevVoxelsRef.current !== pet.voxels)) {
      const mesh = meshRef.current
      const dummy = new THREE.Object3D()
      const color = new THREE.Color()

      for (let i = 0; i < pet.voxels.length; i++) {
        const v = pet.voxels[i]
        dummy.position.set(v.x * 0.25 + 0.125, v.y * 0.25 + 0.125, v.z * 0.25 + 0.125)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
      initializedRef.current = true
      prevVoxelsRef.current = pet.voxels
    }

    // --- Physics: Gravity ---
    const groundY = collider
      ? getGroundLevel(collider, currentPos.current.x, currentPos.current.z)
      : 1 // default ground at y=1

    if (currentPos.current.y > groundY) {
      // In the air — apply gravity
      velocityY.current = Math.max(velocityY.current - GRAVITY * delta, -TERMINAL_VELOCITY)
      currentPos.current.y += velocityY.current * delta
      isGrounded.current = false

      // Landed
      if (currentPos.current.y <= groundY) {
        currentPos.current.y = groundY
        velocityY.current = 0
        isGrounded.current = true
      }
    } else if (currentPos.current.y < groundY) {
      // Below ground (stepped up or terrain raised) — snap up smoothly
      currentPos.current.y = THREE.MathUtils.lerp(currentPos.current.y, groundY, 10 * delta)
      if (Math.abs(currentPos.current.y - groundY) < 0.05) {
        currentPos.current.y = groundY
      }
      isGrounded.current = true
      velocityY.current = 0
    } else {
      isGrounded.current = true
      velocityY.current = 0
    }

    // --- Wander state machine (only move when grounded) ---
    stateTimer.current -= delta

    if (isGrounded.current) {
      if (wanderState.current === 'idle') {
        if (stateTimer.current <= 0) {
          targetPos.current = randomTarget(origin.current, collider)
          wanderState.current = 'walking'
        }
      } else if (wanderState.current === 'walking') {
        const dir = new THREE.Vector3(
          targetPos.current.x - currentPos.current.x,
          0,
          targetPos.current.z - currentPos.current.z,
        )
        const dist = dir.length()

        if (dist < 0.3) {
          // Arrived
          wanderState.current = 'pausing'
          stateTimer.current = PAUSE_MIN + Math.random() * (PAUSE_MAX - PAUSE_MIN)
        } else {
          dir.normalize()
          const step = Math.min(WALK_SPEED * delta, dist)

          const nextX = currentPos.current.x + dir.x * step
          const nextZ = currentPos.current.z + dir.z * step

          // Physics collision check
          const blocked = collider
            ? !canMoveTo(collider, nextX, nextZ, currentPos.current.y)
            : false

          if (blocked) {
            // Blocked — pick a new target
            targetPos.current = randomTarget(origin.current, collider)
          } else {
            currentPos.current.x = nextX
            currentPos.current.z = nextZ

            // Rotate to face movement direction
            const goalAngle = Math.atan2(dir.x, dir.z)
            currentRotY.current = THREE.MathUtils.lerp(
              currentRotY.current,
              goalAngle,
              6 * delta,
            )

            onPositionChange?.({
              x: currentPos.current.x,
              y: currentPos.current.y,
              z: currentPos.current.z,
            })
          }
        }
      } else if (wanderState.current === 'pausing') {
        if (stateTimer.current <= 0) {
          targetPos.current = randomTarget(origin.current, collider)
          wanderState.current = 'walking'
        }
      }
    }

    // --- Apply position + idle bob + rotation ---
    if (groupRef.current) {
      const bob = isGrounded.current ? Math.sin(timeRef.current * BOB_SPEED) * BOB_AMPLITUDE : 0
      groupRef.current.position.x = currentPos.current.x
      groupRef.current.position.y = currentPos.current.y + bob
      groupRef.current.position.z = currentPos.current.z
      groupRef.current.rotation.y = currentRotY.current
    }
  })

  if (pet.voxels.length === 0) return null

  return (
    <group
      ref={groupRef}
      position={[pet.position.x, pet.position.y, pet.position.z]}
    >
      <ThoughtBubble thought={thought ?? null} />
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, pet.voxels.length]}
        frustumCulled={false}
      >
        <boxGeometry args={[0.25, 0.25, 0.25]} />
        <meshStandardMaterial roughness={0.4} metalness={0.1} />
      </instancedMesh>
    </group>
  )
}

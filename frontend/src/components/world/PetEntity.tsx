import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { PetEntity as PetEntityType } from '../../types/world'

type WanderState = 'idle' | 'walking' | 'pausing'

const WANDER_RADIUS = 20
const WALK_SPEED = 3
const PAUSE_MIN = 1.5
const PAUSE_MAX = 4
const IDLE_BEFORE_FIRST_WALK = 2

interface PetEntityProps {
  pet: PetEntityType
  onPositionChange?: (pos: { x: number; y: number; z: number }) => void
}

function randomTarget(origin: { x: number; z: number }) {
  const angle = Math.random() * Math.PI * 2
  const dist = 4 + Math.random() * (WANDER_RADIUS - 4)
  return new THREE.Vector3(
    origin.x + Math.cos(angle) * dist,
    0,
    origin.z + Math.sin(angle) * dist,
  )
}

export default function PetEntity({ pet, onPositionChange }: PetEntityProps) {
  const groupRef = useRef<THREE.Group>(null)
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)
  const initializedRef = useRef(false)
  const prevVoxelsRef = useRef(pet.voxels)

  // Wander state machine refs (persist across frames without re-renders)
  const wanderState = useRef<WanderState>('idle')
  const stateTimer = useRef(IDLE_BEFORE_FIRST_WALK)
  const currentPos = useRef(new THREE.Vector3(pet.position.x, 0, pet.position.z))
  const targetPos = useRef(new THREE.Vector3(pet.position.x, 0, pet.position.z))
  const currentRotY = useRef(0)
  const origin = useRef({ x: pet.position.x, z: pet.position.z })

  useFrame((_, delta) => {
    timeRef.current += delta

    // --- Voxel instancing setup ---
    if (meshRef.current && (!initializedRef.current || prevVoxelsRef.current !== pet.voxels)) {
      const mesh = meshRef.current
      const dummy = new THREE.Object3D()
      const color = new THREE.Color()

      for (let i = 0; i < pet.voxels.length; i++) {
        const v = pet.voxels[i]
        dummy.position.set(v.x + 0.5, v.y + 0.5, v.z + 0.5)
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

    // --- Wander state machine ---
    stateTimer.current -= delta

    if (wanderState.current === 'idle') {
      if (stateTimer.current <= 0) {
        targetPos.current = randomTarget(origin.current)
        wanderState.current = 'walking'
      }
    } else if (wanderState.current === 'walking') {
      const dir = targetPos.current.clone().sub(currentPos.current)
      dir.y = 0
      const dist = dir.length()

      if (dist < 0.3) {
        // Arrived — pause
        wanderState.current = 'pausing'
        stateTimer.current = PAUSE_MIN + Math.random() * (PAUSE_MAX - PAUSE_MIN)
      } else {
        dir.normalize()
        const step = Math.min(WALK_SPEED * delta, dist)
        currentPos.current.addScaledVector(dir, step)

        // Rotate to face movement direction
        const goalAngle = Math.atan2(dir.x, dir.z)
        currentRotY.current = THREE.MathUtils.lerp(
          currentRotY.current,
          goalAngle,
          6 * delta,
        )

        onPositionChange?.({
          x: currentPos.current.x,
          y: 0,
          z: currentPos.current.z,
        })
      }
    } else if (wanderState.current === 'pausing') {
      if (stateTimer.current <= 0) {
        targetPos.current = randomTarget(origin.current)
        wanderState.current = 'walking'
      }
    }

    // --- Apply position + bob + rotation ---
    if (groupRef.current) {
      groupRef.current.position.x = currentPos.current.x
      groupRef.current.position.z = currentPos.current.z
      groupRef.current.position.y = pet.position.y + Math.sin(timeRef.current * 2) * 0.1
      groupRef.current.rotation.y = currentRotY.current
    }
  })

  if (pet.voxels.length === 0) return null

  return (
    <group
      ref={groupRef}
      position={[pet.position.x, pet.position.y, pet.position.z]}
    >
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, pet.voxels.length]}
        frustumCulled={false}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial roughness={0.4} metalness={0.1} />
      </instancedMesh>
    </group>
  )
}

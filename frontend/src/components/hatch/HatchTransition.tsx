import { useRef, useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface HatchTransitionProps {
  eggVoxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  petVoxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  phase: 'idle' | 'shatter' | 'reform' | 'complete'
  onComplete: () => void
}

const VOXEL_SIZE = 0.25
const SHATTER_DURATION = 1.5 // seconds
const REFORM_DURATION = 2.0

export default function HatchTransition({
  eggVoxels,
  petVoxels,
  phase,
  onComplete,
}: HatchTransitionProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const progressRef = useRef(0)
  const [currentPhase, setCurrentPhase] = useState(phase)

  // Max count is the larger of egg or pet voxels
  const maxCount = Math.max(eggVoxels.length, petVoxels.length)

  // Precompute random scatter directions for shatter effect
  const scatterDirs = useMemo(() => {
    return Array.from({ length: maxCount }, () => ({
      x: (Math.random() - 0.5) * 10,
      y: Math.random() * 8 + 2,
      z: (Math.random() - 0.5) * 10,
    }))
  }, [maxCount])

  useFrame((_, delta) => {
    if (!meshRef.current || currentPhase === 'idle' || currentPhase === 'complete') return

    const mesh = meshRef.current
    const matrix = new THREE.Matrix4()
    const color = new THREE.Color()

    if (currentPhase === 'shatter') {
      progressRef.current += delta / SHATTER_DURATION
      const t = Math.min(progressRef.current, 1)

      // Egg voxels scatter outward
      for (let i = 0; i < eggVoxels.length; i++) {
        const v = eggVoxels[i]
        const scatter = scatterDirs[i]
        const ease = t * t // accelerating

        matrix.setPosition(
          (v.x * 0.5 + scatter.x * ease) * VOXEL_SIZE,
          (v.y * 0.5 + scatter.y * ease - 5 * ease * ease) * VOXEL_SIZE,
          (v.z * 0.5 + scatter.z * ease) * VOXEL_SIZE,
        )
        // Scale down as they scatter
        const scale = 1 - t * 0.8
        matrix.scale(new THREE.Vector3(scale, scale, scale))
        mesh.setMatrixAt(i, matrix)

        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }

      // Hide unused instances
      for (let i = eggVoxels.length; i < maxCount; i++) {
        matrix.setPosition(0, -1000, 0)
        matrix.scale(new THREE.Vector3(0, 0, 0))
        mesh.setMatrixAt(i, matrix)
      }

      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

      if (t >= 1) {
        progressRef.current = 0
        setCurrentPhase('reform')
      }
    } else if (currentPhase === 'reform') {
      progressRef.current += delta / REFORM_DURATION
      const t = Math.min(progressRef.current, 1)
      const ease = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2 // ease in-out

      // Pet voxels converge from scattered positions to final positions
      for (let i = 0; i < petVoxels.length; i++) {
        const v = petVoxels[i]
        const scatter = scatterDirs[i % scatterDirs.length]

        const startX = scatter.x * 2
        const startY = scatter.y * 2
        const startZ = scatter.z * 2

        const finalX = v.x * VOXEL_SIZE
        const finalY = v.y * VOXEL_SIZE
        const finalZ = v.z * VOXEL_SIZE

        matrix.identity()
        matrix.setPosition(
          startX + (finalX - startX) * ease,
          startY + (finalY - startY) * ease,
          startZ + (finalZ - startZ) * ease,
        )
        mesh.setMatrixAt(i, matrix)

        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }

      // Hide unused instances
      for (let i = petVoxels.length; i < maxCount; i++) {
        matrix.setPosition(0, -1000, 0)
        matrix.scale(new THREE.Vector3(0, 0, 0))
        mesh.setMatrixAt(i, matrix)
      }

      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

      if (t >= 1) {
        setCurrentPhase('complete')
        onComplete()
      }
    }
  })

  // Sync phase from props
  useMemo(() => {
    if (phase !== currentPhase && phase !== 'idle') {
      progressRef.current = 0
      setCurrentPhase(phase)
    }
  }, [phase])

  if (maxCount === 0) return null

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, maxCount]}>
      <boxGeometry args={[VOXEL_SIZE, VOXEL_SIZE, VOXEL_SIZE]} />
      <meshStandardMaterial roughness={0.4} metalness={0.1} />
    </instancedMesh>
  )
}

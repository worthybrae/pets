import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Chunk } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'

interface VoxelChunkProps {
  chunk: Chunk
  onVoxelClick?: (metadataId: string) => void
}

export default function VoxelChunk({ chunk, onVoxelClick }: VoxelChunkProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const glowMeshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)

  const worldOffsetX = chunk.chunk_x * CHUNK_SIZE
  const worldOffsetY = chunk.chunk_y * CHUNK_SIZE
  const worldOffsetZ = chunk.chunk_z * CHUNK_SIZE

  const { regularVoxels, glowVoxels } = useMemo(() => {
    const regular: typeof chunk.voxels = []
    const glow: typeof chunk.voxels = []
    for (const v of chunk.voxels) {
      if (v.metadata_id) {
        glow.push(v)
      } else {
        regular.push(v)
      }
    }
    return { regularVoxels: regular, glowVoxels: glow }
  }, [chunk.voxels])

  // Set up regular instanced mesh
  useMemo(() => {
    if (!meshRef.current) return
    const mesh = meshRef.current
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()

    for (let i = 0; i < regularVoxels.length; i++) {
      const v = regularVoxels[i]
      dummy.position.set(
        worldOffsetX + v.x + 0.5,
        worldOffsetY + v.y + 0.5,
        worldOffsetZ + v.z + 0.5
      )
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      color.setRGB(v.r / 255, v.g / 255, v.b / 255)
      mesh.setColorAt(i, color)
    }
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [regularVoxels, worldOffsetX, worldOffsetY, worldOffsetZ])

  // Set up glow instanced mesh
  useMemo(() => {
    if (!glowMeshRef.current) return
    const mesh = glowMeshRef.current
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()

    for (let i = 0; i < glowVoxels.length; i++) {
      const v = glowVoxels[i]
      dummy.position.set(
        worldOffsetX + v.x + 0.5,
        worldOffsetY + v.y + 0.5,
        worldOffsetZ + v.z + 0.5
      )
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
      color.setRGB(v.r / 255, v.g / 255, v.b / 255)
      mesh.setColorAt(i, color)
    }
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [glowVoxels, worldOffsetX, worldOffsetY, worldOffsetZ])

  // Animate glow voxels
  useFrame((_, delta) => {
    timeRef.current += delta
    if (!glowMeshRef.current || glowVoxels.length === 0) return

    const mesh = glowMeshRef.current
    const dummy = new THREE.Object3D()
    const pulse = 1 + 0.05 * Math.sin(timeRef.current * 3)

    for (let i = 0; i < glowVoxels.length; i++) {
      const v = glowVoxels[i]
      dummy.position.set(
        worldOffsetX + v.x + 0.5,
        worldOffsetY + v.y + 0.5,
        worldOffsetZ + v.z + 0.5
      )
      dummy.scale.setScalar(pulse)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)
    }
    mesh.instanceMatrix.needsUpdate = true
  })

  const handleGlowClick = (e: THREE.Event & { instanceId?: number }) => {
    if (e.instanceId !== undefined && onVoxelClick) {
      const voxel = glowVoxels[e.instanceId]
      if (voxel?.metadata_id) {
        onVoxelClick(voxel.metadata_id)
      }
    }
  }

  return (
    <group>
      {regularVoxels.length > 0 && (
        <instancedMesh
          ref={meshRef}
          args={[undefined, undefined, regularVoxels.length]}
          frustumCulled={true}
        >
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial
            vertexColors
            transparent
            opacity={0.95}
          />
        </instancedMesh>
      )}
      {glowVoxels.length > 0 && (
        <instancedMesh
          ref={glowMeshRef}
          args={[undefined, undefined, glowVoxels.length]}
          frustumCulled={true}
          onClick={handleGlowClick}
        >
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial
            vertexColors
            transparent
            opacity={0.9}
            emissive={new THREE.Color(0.3, 0.3, 0.3)}
            emissiveIntensity={1.5}
          />
        </instancedMesh>
      )}
    </group>
  )
}

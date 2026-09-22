import { useEffect, useRef, useMemo } from 'react'
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
  const glassMeshRef = useRef<THREE.InstancedMesh>(null)
  const waterMeshRef = useRef<THREE.InstancedMesh>(null)
  const glowMeshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)
  const regularInitRef = useRef(false)
  const glassInitRef = useRef(false)
  const waterInitRef = useRef(false)
  const glowInitRef = useRef(false)

  const worldOffsetX = chunk.chunk_x * CHUNK_SIZE
  const worldOffsetY = chunk.chunk_y * CHUNK_SIZE
  const worldOffsetZ = chunk.chunk_z * CHUNK_SIZE

  const { regularVoxels, glassVoxels, waterVoxels, glowVoxels } = useMemo(() => {
    const regular: typeof chunk.voxels = []
    const glass: typeof chunk.voxels = []
    const water: typeof chunk.voxels = []
    const glow: typeof chunk.voxels = []
    for (const v of chunk.voxels) {
      if (v.metadata_id || v.material === 'lantern' || v.material === 'lava' || v.material === 'furnace') {
        glow.push(v)
      } else if (v.material === 'glass') {
        glass.push(v)
      } else if (v.material === 'water') {
        water.push(v)
      } else {
        regular.push(v)
      }
    }
    return { regularVoxels: regular, glassVoxels: glass, waterVoxels: water, glowVoxels: glow }
  }, [chunk])

  useEffect(() => {
    regularInitRef.current = false
    glassInitRef.current = false
    waterInitRef.current = false
    glowInitRef.current = false
  }, [chunk.voxels])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (waterMeshRef.current) waterMeshRef.current.position.y = Math.sin(timeRef.current * 1.3) * 0.025

    // Initialize regular mesh (guaranteed ref exists in useFrame)
    if (meshRef.current && !regularInitRef.current && regularVoxels.length > 0) {
      regularInitRef.current = true
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
        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    }

    for (const [mesh, voxels, initialized] of [
      [glassMeshRef.current, glassVoxels, glassInitRef],
      [waterMeshRef.current, waterVoxels, waterInitRef],
    ] as const) {
      if (!mesh || initialized.current || !voxels.length) continue
      initialized.current = true
      const dummy = new THREE.Object3D()
      const color = new THREE.Color()
      for (let i = 0; i < voxels.length; i++) {
        const v = voxels[i]
        dummy.position.set(worldOffsetX + v.x + 0.5, worldOffsetY + v.y + 0.5, worldOffsetZ + v.z + 0.5)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    }

    // Initialize + animate glow mesh
    if (glowMeshRef.current && glowVoxels.length > 0) {
      const mesh = glowMeshRef.current
      const dummy = new THREE.Object3D()

      if (!glowInitRef.current) {
        glowInitRef.current = true
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
          color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
          mesh.setColorAt(i, color)
        }
        if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
      }

      // Pulse animation
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
    }
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
          frustumCulled={false}
        >
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial roughness={0.85} />
        </instancedMesh>
      )}
      {glassVoxels.length > 0 && (
        <instancedMesh ref={glassMeshRef} args={[undefined, undefined, glassVoxels.length]} frustumCulled={false}>
          <boxGeometry args={[1, 1, 1]} />
          <meshPhysicalMaterial transparent opacity={0.38} depthWrite={false} roughness={0.1} metalness={0.05} side={THREE.DoubleSide} />
        </instancedMesh>
      )}
      {waterVoxels.length > 0 && (
        <instancedMesh ref={waterMeshRef} args={[undefined, undefined, waterVoxels.length]} frustumCulled={false}>
          <boxGeometry args={[1, 0.82, 1]} />
          <meshPhysicalMaterial transparent opacity={0.58} depthWrite={false} roughness={0.12} metalness={0.1} side={THREE.DoubleSide} />
        </instancedMesh>
      )}
      {glowVoxels.length > 0 && (
        <instancedMesh
          ref={glowMeshRef}
          args={[undefined, undefined, glowVoxels.length]}
          frustumCulled={false}
          onClick={handleGlowClick}
        >
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial
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

import { useLayoutEffect, useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Chunk } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'

interface VoxelChunkProps {
  chunk: Chunk
  onVoxelClick?: (metadataId: string) => void
}

function meshCapacity(count: number) {
  return 2 ** Math.ceil(Math.log2(Math.max(1, count)))
}

export default function VoxelChunk({ chunk, onVoxelClick }: VoxelChunkProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const glassMeshRef = useRef<THREE.InstancedMesh>(null)
  const waterMeshRef = useRef<THREE.InstancedMesh>(null)
  const glowMeshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)

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

  useLayoutEffect(() => {
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    for (const [mesh, voxels] of [
      [meshRef.current, regularVoxels],
      [glassMeshRef.current, glassVoxels],
      [waterMeshRef.current, waterVoxels],
      [glowMeshRef.current, glowVoxels],
    ] as const) {
      if (!mesh) continue
      mesh.count = voxels.length
      for (let i = 0; i < voxels.length; i++) {
        const v = voxels[i]
        const [width, height, depth] = v.size ?? [1, 1, 1]
        const [offsetX, offsetY, offsetZ] = v.offset ?? [0, 0, 0]
        dummy.position.set(
          worldOffsetX + v.x + 0.5 + offsetX,
          worldOffsetY + v.y + height / 2 + offsetY,
          worldOffsetZ + v.z + 0.5 + offsetZ,
        )
        dummy.scale.set(width, height, depth)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
      mesh.visible = true
    }
  }, [chunk, regularVoxels, glassVoxels, waterVoxels, glowVoxels, worldOffsetX, worldOffsetY, worldOffsetZ])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (waterMeshRef.current) waterMeshRef.current.position.y = Math.sin(timeRef.current * 1.3) * 0.025
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
          args={[undefined, undefined, meshCapacity(regularVoxels.length)]}
          visible={false}
          frustumCulled={false}
        >
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial roughness={0.85} />
        </instancedMesh>
      )}
      {glassVoxels.length > 0 && (
        <instancedMesh ref={glassMeshRef} args={[undefined, undefined, meshCapacity(glassVoxels.length)]} visible={false} frustumCulled={false}>
          <boxGeometry args={[1, 1, 1]} />
          <meshPhysicalMaterial transparent opacity={0.38} depthWrite={false} roughness={0.1} metalness={0.05} side={THREE.DoubleSide} />
        </instancedMesh>
      )}
      {waterVoxels.length > 0 && (
        <instancedMesh ref={waterMeshRef} args={[undefined, undefined, meshCapacity(waterVoxels.length)]} visible={false} frustumCulled={false}>
          <boxGeometry args={[1, 0.82, 1]} />
          <meshPhysicalMaterial transparent opacity={0.58} depthWrite={false} roughness={0.12} metalness={0.1} side={THREE.DoubleSide} />
        </instancedMesh>
      )}
      {glowVoxels.length > 0 && (
        <instancedMesh
          ref={glowMeshRef}
          args={[undefined, undefined, meshCapacity(glowVoxels.length)]}
          visible={false}
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

import { useMemo } from 'react'
import type { Chunk } from '../../types/world'
import VoxelChunk from './VoxelChunk'

interface WorldManagerProps {
  chunks: Chunk[]
  cameraChunkX?: number
  cameraChunkY?: number
  cameraChunkZ?: number
  viewDistance?: number
  onVoxelClick?: (metadataId: string) => void
}

export default function WorldManager({
  chunks,
  cameraChunkX = 0,
  cameraChunkY = 0,
  cameraChunkZ = 0,
  viewDistance = 3,
  onVoxelClick,
}: WorldManagerProps) {
  const visibleChunks = useMemo(() => {
    return chunks.filter((chunk) => {
      const dx = Math.abs(chunk.chunk_x - cameraChunkX)
      const dy = Math.abs(chunk.chunk_y - cameraChunkY)
      const dz = Math.abs(chunk.chunk_z - cameraChunkZ)
      return dx <= viewDistance && dy <= viewDistance && dz <= viewDistance
    })
  }, [chunks, cameraChunkX, cameraChunkY, cameraChunkZ, viewDistance])

  return (
    <group>
      {visibleChunks.map((chunk) => (
        <VoxelChunk
          key={`${chunk.chunk_x}_${chunk.chunk_y}_${chunk.chunk_z}`}
          chunk={chunk}
          onVoxelClick={onVoxelClick}
        />
      ))}
    </group>
  )
}

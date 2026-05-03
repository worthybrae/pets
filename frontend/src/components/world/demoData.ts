import type { Chunk, PetEntity } from '../../types/world'

// Demo pet: a small white creature (cross shape)
export const demoPet: PetEntity = {
  position: { x: 0, y: 1, z: 0 },
  voxels: [
    // Body core
    { x: 0, y: 0, z: 0, r: 255, g: 255, b: 255, a: 255 },
    { x: 0, y: 1, z: 0, r: 255, g: 255, b: 255, a: 255 },
    { x: 0, y: 2, z: 0, r: 240, g: 240, b: 255, a: 255 },
    // Arms
    { x: -1, y: 1, z: 0, r: 230, g: 230, b: 255, a: 255 },
    { x: 1, y: 1, z: 0, r: 230, g: 230, b: 255, a: 255 },
  ],
}

// Helper: create a voxel
function v(x: number, y: number, z: number, r: number, g: number, b: number, metadataId?: string) {
  return { x, y, z, r, g, b, a: 255, metadata_id: metadataId }
}

// Chunk (0,0,0): ground floor and a small structure
const chunk000Voxels = [
  // Ground plane (scattered dark tiles for orientation)
  ...Array.from({ length: 10 }, (_, i) =>
    v(i + 3, 0, 3, 30, 30, 40)
  ),
  ...Array.from({ length: 10 }, (_, i) =>
    v(i + 3, 0, 4, 25, 25, 35)
  ),
  ...Array.from({ length: 10 }, (_, i) =>
    v(i + 3, 0, 5, 30, 30, 40)
  ),
  ...Array.from({ length: 10 }, (_, i) =>
    v(i + 3, 0, 6, 25, 25, 35)
  ),
  ...Array.from({ length: 10 }, (_, i) =>
    v(i + 3, 0, 7, 30, 30, 40)
  ),

  // Small tower (purple/violet)
  v(5, 1, 5, 139, 92, 246),
  v(5, 2, 5, 139, 92, 246),
  v(5, 3, 5, 139, 92, 246),
  v(5, 4, 5, 167, 139, 250),
  v(5, 5, 5, 196, 181, 253),

  // Artifact on top of tower (clickable)
  v(5, 6, 5, 255, 215, 0, 'artifact-golden-memory'),

  // Small garden (greens)
  v(8, 1, 3, 34, 197, 94),
  v(9, 1, 3, 22, 163, 74),
  v(8, 1, 4, 22, 163, 74),
  v(9, 1, 4, 34, 197, 94),
  v(10, 1, 3, 74, 222, 128),
  v(10, 1, 4, 34, 197, 94),

  // Water pool (blues)
  v(3, 0, 9, 59, 130, 246),
  v(4, 0, 9, 59, 130, 246),
  v(3, 0, 10, 96, 165, 250),
  v(4, 0, 10, 96, 165, 250),
  v(5, 0, 9, 59, 130, 246),
  v(5, 0, 10, 59, 130, 246),
]

// Chunk (1,0,0): an archway / structure
const chunk100Voxels = [
  // Arch left pillar
  v(0, 0, 8, 180, 80, 80),
  v(0, 1, 8, 180, 80, 80),
  v(0, 2, 8, 180, 80, 80),
  v(0, 3, 8, 180, 80, 80),
  v(0, 4, 8, 200, 100, 100),

  // Arch right pillar
  v(3, 0, 8, 180, 80, 80),
  v(3, 1, 8, 180, 80, 80),
  v(3, 2, 8, 180, 80, 80),
  v(3, 3, 8, 180, 80, 80),
  v(3, 4, 8, 200, 100, 100),

  // Arch top
  v(1, 4, 8, 220, 120, 120),
  v(2, 4, 8, 220, 120, 120),

  // Clickable artifact in the arch
  v(1, 2, 8, 255, 100, 200, 'artifact-arch-secret'),

  // Scattered crystals
  v(6, 0, 2, 100, 200, 255),
  v(6, 1, 2, 130, 220, 255),
  v(7, 0, 3, 100, 200, 255),
  v(8, 0, 5, 150, 100, 255),
  v(8, 1, 5, 180, 130, 255),
  v(8, 2, 5, 200, 160, 255),
]

// Chunk (0,0,1): more world features
const chunk001Voxels = [
  // Staircase going up
  ...Array.from({ length: 8 }, (_, i) =>
    v(2, i, 2 + i, 60 + i * 10, 60 + i * 10, 80 + i * 10)
  ),

  // Floating platform
  v(4, 5, 5, 200, 200, 200),
  v(5, 5, 5, 200, 200, 200),
  v(6, 5, 5, 200, 200, 200),
  v(4, 5, 6, 200, 200, 200),
  v(5, 5, 6, 200, 200, 200),
  v(6, 5, 6, 200, 200, 200),

  // Glowing orb on platform (clickable)
  v(5, 6, 5, 255, 255, 100, 'artifact-floating-orb'),

  // Some trees (brown + green)
  v(10, 0, 10, 139, 90, 43),
  v(10, 1, 10, 139, 90, 43),
  v(10, 2, 10, 139, 90, 43),
  v(9, 3, 9, 34, 139, 34),
  v(10, 3, 9, 34, 139, 34),
  v(11, 3, 9, 34, 139, 34),
  v(9, 3, 10, 34, 139, 34),
  v(10, 3, 10, 50, 160, 50),
  v(11, 3, 10, 34, 139, 34),
  v(9, 3, 11, 34, 139, 34),
  v(10, 3, 11, 34, 139, 34),
  v(11, 3, 11, 34, 139, 34),
  v(10, 4, 10, 50, 180, 50),
]

export const demoChunks: Chunk[] = [
  { chunk_x: 0, chunk_y: 0, chunk_z: 0, voxels: chunk000Voxels },
  { chunk_x: 1, chunk_y: 0, chunk_z: 0, voxels: chunk100Voxels },
  { chunk_x: 0, chunk_y: 0, chunk_z: 1, voxels: chunk001Voxels },
]

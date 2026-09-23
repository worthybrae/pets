import type { Chunk, PetEntity, Voxel } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'

type Color = readonly [number, number, number]

const grass: Color[] = [
  [126, 174, 135],
  [137, 184, 141],
  [147, 191, 150],
  [119, 166, 131],
]
const dirt: Color = [126, 105, 89]
const stone: Color = [153, 143, 132]
const sand: Color = [221, 202, 158]
const water: Color = [103, 179, 203]
const path: Color = [215, 196, 159]
const trunk: Color = [128, 94, 73]
const leaves: Color[] = [[86, 145, 117], [100, 160, 126], [112, 170, 132]]

const voxels = new Map<string, Voxel>()

function add(x: number, y: number, z: number, color: Color, size?: Voxel['size'], offset?: Voxel['offset']) {
  voxels.set(`${x},${y},${z}`, { x, y, z, r: color[0], g: color[1], b: color[2], a: 255,
    material: color === water ? 'water' : undefined, size, offset })
}

function hash(x: number, z: number) {
  return Math.abs((x * 73856093) ^ (z * 19349663))
}

function inPond(x: number, z: number) {
  return ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1
}

for (let x = -11; x <= 11; x++) {
  for (let z = -11; z <= 11; z++) {
    const distance = Math.hypot(x, z)
    const edge = (hash(x, z) % 5) * 0.16
    if (distance > 10.4 + edge) continue

    if (distance < 7.2) add(x, -3, z, stone)
    if (distance < 9.1) add(x, -2, z, dirt)
    add(x, -1, z, distance > 9 ? sand : dirt)

    const pond = inPond(x, z)
    const shore = ((x + 5) / 4.2) ** 2 + ((z - 4) / 3.4) ** 2 < 1
    const walkway = x >= 0 && x <= 6 && Math.abs(z + Math.round(x * 0.55)) <= 0.6
    const color = pond ? water : shore || distance > 9.3 ? sand : walkway ? path : grass[hash(x, z) % grass.length]
    add(x, 0, z, color)
  }
}

// A small home at the end of the path.
for (let x = 4; x <= 7; x++) {
  for (let z = -6; z <= -3; z++) {
    add(x, 0, z, path)
    for (let y = 1; y <= 3; y++) {
      const wall = x === 4 || x === 7 || z === -6 || z === -3
      const door = x === 5 && z === -3 && y <= 2
      if (wall && !door) add(x, y, z, [229, 206, 171])
    }
  }
}
for (let x = 3; x <= 8; x++) {
  for (let z = -7; z <= -2; z++) {
    add(x, 4, z, [193, 112, 100])
    if (x > 3 && x < 8 && z > -7 && z < -2) add(x, 5, z, [207, 128, 110])
  }
}
add(5, 2, -6, [105, 162, 177])
add(6, 2, -6, [105, 162, 177])

// One broad tree gives the island a silhouette.
for (let y = 1; y <= 5; y++) add(-6, y, -4, trunk)
for (let x = -8; x <= -4; x++) {
  for (let z = -6; z <= -2; z++) {
    if (Math.abs(x + 6) + Math.abs(z + 4) > 3) continue
    add(x, 5, z, leaves[hash(x, z) % leaves.length])
    if (Math.abs(x + 6) + Math.abs(z + 4) <= 2) add(x, 6, z, leaves[(hash(x, z) + 1) % leaves.length])
  }
}
add(-6, 7, -4, leaves[1])

// Flowers and stepping stones make the ground feel inhabited.
for (const [x, z, color] of [
  [-8, 0, [246, 192, 124]], [-7, 1, [243, 164, 168]], [-2, -5, [250, 218, 139]],
  [1, -6, [243, 164, 168]], [8, 1, [246, 192, 124]], [7, 5, [250, 218, 139]],
  [-1, 7, [243, 164, 168]], [3, 7, [246, 192, 124]],
] as const) {
  add(x, 1, z, [90, 151, 113], [0.14, 0.55, 0.14])
  add(x, 2, z, color, [0.36, 0.36, 0.36], [0, -0.62, 0])
}
for (const [x, z] of [[-3, 2], [-2, 1], [3, 2], [4, 1]] as const) add(x, 1, z, [218, 207, 181], [0.75, 0.18, 0.75])

function chunkFor(voxel: Voxel) {
  const chunkX = Math.floor(voxel.x / CHUNK_SIZE)
  const chunkY = Math.floor(voxel.y / CHUNK_SIZE)
  const chunkZ = Math.floor(voxel.z / CHUNK_SIZE)
  return { chunkX, chunkY, chunkZ }
}

const chunkMap = new Map<string, Chunk>()
for (const voxel of voxels.values()) {
  const { chunkX, chunkY, chunkZ } = chunkFor(voxel)
  const key = `${chunkX},${chunkY},${chunkZ}`
  let chunk = chunkMap.get(key)
  if (!chunk) {
    chunk = { chunk_x: chunkX, chunk_y: chunkY, chunk_z: chunkZ, voxels: [] }
    chunkMap.set(key, chunk)
  }
  chunk.voxels.push({
    ...voxel,
    x: voxel.x - chunkX * CHUNK_SIZE,
    y: voxel.y - chunkY * CHUNK_SIZE,
    z: voxel.z - chunkZ * CHUNK_SIZE,
  })
}

export const previewChunks = [...chunkMap.values()]

const petVoxels: Voxel[] = []
function petVoxel(x: number, y: number, z: number, color: Color) {
  petVoxels.push({ x, y, z, r: color[0], g: color[1], b: color[2], a: 255 })
}

const fur: Color = [242, 173, 148]
const lightFur: Color = [251, 204, 176]
const ear: Color = [215, 122, 129]

for (let x = -1; x <= 1; x++) {
  for (let z = -1; z <= 0; z++) {
    petVoxel(x, 0, z, fur)
    petVoxel(x, 1, z, fur)
  }
}
for (let x = -1; x <= 1; x++) {
  for (let z = 0; z <= 1; z++) {
    petVoxel(x, 2, z, lightFur)
    petVoxel(x, 3, z, lightFur)
  }
}
for (const x of [-1, 1]) {
  petVoxel(x, 4, 0, fur)
  petVoxel(x, 5, 0, ear)
  petVoxel(x, 0, 1, lightFur)
}
petVoxel(0, 1, -2, lightFur)

export const previewPet: PetEntity = {
  position: { x: 0, y: 1, z: 0 },
  voxels: petVoxels,
}

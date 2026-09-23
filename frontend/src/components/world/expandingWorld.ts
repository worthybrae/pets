import type { BlockEdit, Chunk, Voxel } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'
import { previewChunks } from './previewWorld'
import { baseMaterial, biomeAt, DEFAULT_WORLD_SEED, hash32, LEGACY_RADIUS, SEA_LEVEL, surfaceMaterial, terrainHeight } from './worldgen'

export { terrainHeight } from './worldgen'

type Color = readonly [number, number, number]

export const ORBITAL_STATION = { x: 48, z: 0, radius: 20, centerY: 22 } as const

export interface BuildProgress {
  projectIndex: number
  stepIndex: number
}

export interface BuildProject {
  name: string
  site: { x: number; z: number }
  standOff: number
  landmark?: { radius: number; centerY: number }
  voxels: Voxel[]
}

interface SphericalLandmarkPlan {
  name: string
  site: { x: number; z: number }
  radius: number
  centerY: number
  trenchWidth: number
  dish: { x: number; y: number; radius: number }
}

const grass: Color[][] = [
  [[126, 171, 137], [129, 174, 139], [123, 168, 134]],
  [[132, 177, 140], [127, 172, 136], [130, 175, 138]],
  [[122, 168, 136], [125, 171, 139], [119, 165, 133]],
]

function hash(x: number, z: number) {
  return Math.abs((x * 73856093) ^ (z * 19349663))
}

function voxel(x: number, y: number, z: number, color: Color): Voxel {
  return { x, y, z, r: color[0], g: color[1], b: color[2], a: 255 }
}

function chunkKey(x: number, y: number, z: number) {
  return `${x},${y},${z}`
}

function chunkOf(v: Voxel) {
  return {
    x: Math.floor(v.x / CHUNK_SIZE),
    y: Math.floor(v.y / CHUNK_SIZE),
    z: Math.floor(v.z / CHUNK_SIZE),
  }
}

function localize(v: Voxel, cx: number, cy: number, cz: number): Voxel {
  return { ...v, x: v.x - cx * CHUNK_SIZE, y: v.y - cy * CHUNK_SIZE, z: v.z - cz * CHUNK_SIZE }
}

function globalize(v: Voxel, chunk: Chunk): Voxel {
  return {
    ...v,
    x: v.x + chunk.chunk_x * CHUNK_SIZE,
    y: v.y + chunk.chunk_y * CHUNK_SIZE,
    z: v.z + chunk.chunk_z * CHUNK_SIZE,
  }
}

const terrainCache = new Map<string, Chunk>()

export function makeTerrainChunk(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): Chunk {
  const cacheKey = `${seed}:${cx},${cz}`
  const cached = terrainCache.get(cacheKey)
  if (cached) return cached
  const voxels: Voxel[] = []
  const add = (x: number, y: number, z: number, color: Color, size?: Voxel['size'], offset?: Voxel['offset']) => {
    voxels.push({ ...voxel(x, y, z, color), size, offset })
  }

  for (let x = 0; x < CHUNK_SIZE; x++) {
    for (let z = 0; z < CHUNK_SIZE; z++) {
      const wx = cx * CHUNK_SIZE + x
      const wz = cz * CHUNK_SIZE + z
      const height = terrainHeight(wx, wz, seed)
      const biome = biomeAt(wx, wz, seed)
      const surface = surfaceMaterial(wx, wz, seed)
      const neighborFloor = Math.min(
        terrainHeight(wx + 1, wz, seed), terrainHeight(wx - 1, wz, seed),
        terrainHeight(wx, wz + 1, seed), terrainHeight(wx, wz - 1, seed),
      )
      const bottom = Math.max(0, Math.min(height - 2, neighborFloor + 1))
      for (let y = bottom; y <= height; y++) {
        const material = y === height ? surface : y >= height - 1 ? biome === 'desert' ? 'sand' : 'dirt' : 'stone'
        const palette = grass[hash32(wx, 0, wz, seed, 10) % grass.length]
        const color: Color = material === 'grass' ? palette[hash32(wx, y, wz, seed, 11) % palette.length]
          : material === 'moss' ? [112, 158, 125]
            : material === 'sand' ? [222, 203, 158]
              : material === 'snow' ? [236, 241, 243]
                : material === 'dirt' ? [126, 105, 89] : [143, 151, 154]
        add(x, y, z, color)
      }
      if (height < SEA_LEVEL && Math.hypot(wx, wz) > LEGACY_RADIUS) {
        for (let y = height + 1; y <= SEA_LEVEL; y++) {
          voxels.push({ ...voxel(x, y, z, [103, 179, 203]), material: 'water' })
        }
      }

      // Leave room at chunk edges so a tree canopy stays inside its chunk.
      if (height < SEA_LEVEL || biome === 'desert' || biome === 'alpine' ||
          Math.hypot(wx, wz) < 17 || x < 3 || x > 12 || z < 3 || z > 12) continue
      const nearSiteX = Math.min(((wx % 13) + 13) % 13, 13 - (((wx % 13) + 13) % 13)) < 5
      const nearSiteZ = Math.min(((wz % 13) + 13) % 13, 13 - (((wz % 13) + 13) % 13)) < 5
      if (nearSiteX && nearSiteZ) continue

      const treeChance = Math.hypot(wx, wz) <= LEGACY_RADIUS ? hash(wx, wz) % 257 === 0
        : hash32(wx, 0, wz, seed, 12) % (biome === 'forest' ? 78 : 300) === 0
      if (treeChance) {
        for (let y = height + 1; y <= height + 4; y++) add(x, y, z, [126, 94, 74])
        for (let dx = -2; dx <= 2; dx++) {
          for (let dz = -2; dz <= 2; dz++) {
            if (Math.abs(dx) + Math.abs(dz) > 3) continue
            add(x + dx, height + 5, z + dz, [91, 151, 119])
            if (Math.abs(dx) + Math.abs(dz) < 2) add(x + dx, height + 6, z + dz, [110, 168, 128])
          }
        }
      } else if (hash32(wx, 0, wz, seed, 13) % 97 === 0) {
        add(x, height + 1, z, [89, 147, 112], [0.14, 0.55, 0.14])
        add(x, height + 2, z, hash(wx + 1, wz) % 2 ? [242, 178, 153] : [245, 216, 143],
          [0.36, 0.36, 0.36], [0, -0.62, 0])
      }
    }
  }

  const chunk = { chunk_x: cx, chunk_y: 0, chunk_z: cz, voxels }
  terrainCache.set(cacheKey, chunk)
  if (terrainCache.size > 512) terrainCache.delete(terrainCache.keys().next().value!)
  return chunk
}

export function placeVoxels(chunks: Chunk[], values: Voxel[], seed = DEFAULT_WORLD_SEED): Chunk[] {
  if (values.length === 0) return chunks
  const next = [...chunks]
  const indices = new Map(next.map((chunk, index) => [chunkKey(chunk.chunk_x, chunk.chunk_y, chunk.chunk_z), index]))
  const touched = new Map<string, { voxels: Voxel[]; positions: Map<string, number> }>()

  for (const value of values) {
    const { x: cx, y: cy, z: cz } = chunkOf(value)
    const key = chunkKey(cx, cy, cz)
    let index = indices.get(key)
    if (index === undefined) {
      index = next.length
      next.push(cy === 0 ? makeTerrainChunk(cx, cz, seed) : { chunk_x: cx, chunk_y: cy, chunk_z: cz, voxels: [] })
      indices.set(key, index)
    }
    let record = touched.get(key)
    if (!record) {
      const voxels = [...next[index].voxels]
      const positions = new Map(voxels.map((v, i) => [`${v.x},${v.y},${v.z}`, i]))
      record = { voxels, positions }
      touched.set(key, record)
    }
    const local = localize(value, cx, cy, cz)
    const positionKey = `${local.x},${local.y},${local.z}`
    const existing = record.positions.get(positionKey)
    if (existing === undefined) {
      record.positions.set(positionKey, record.voxels.length)
      record.voxels.push(local)
    } else {
      record.voxels[existing] = local
    }
  }

  for (const [key, record] of touched) {
    const index = indices.get(key)!
    next[index] = { ...next[index], voxels: record.voxels }
  }
  return next
}

const blockColors: Record<string, Color> = {
  grass: [127, 173, 137], dirt: [126, 105, 89], stone: [153, 151, 148],
  sand: [222, 203, 158], gravel: [159, 166, 162], wood: [139, 105, 82],
  glass: [160, 218, 218], water: [103, 179, 203], lantern: [247, 213, 143],
  leaves: [101, 164, 128],
}

export function applyBlockEdits(chunks: Chunk[], edits: BlockEdit[], catalog: Record<string, { color: number[] }> = {},
  seed = DEFAULT_WORLD_SEED): Chunk[] {
  if (!edits.length) return chunks
  const colorOf = (material: string): Color => {
    const color = catalog[material]?.color
    return color && color.length >= 3 ? [color[0], color[1], color[2]] : blockColors[material] ?? [180, 130, 180]
  }
  // Generate the exposed layers only around excavations. The deeper world is
  // implicit bedrock/stone until Mimo digs into it.
  const underground: Voxel[] = []
  for (const edit of edits) {
    if (edit.material !== 'air' || edit.y > 0) continue
    for (let x = edit.x - 2; x <= edit.x + 2; x++) for (let z = edit.z - 2; z <= edit.z + 2; z++) {
      for (let y = -5; y <= Math.max(-1, terrainHeight(x, z, seed)); y++) {
        const material = baseMaterial(x, y, z, seed)
        if (material !== 'air') underground.push({ ...voxel(x, y, z, colorOf(material)), material })
      }
    }
  }
  let next = placeVoxels(chunks, underground, seed)
  next = placeVoxels(next, edits.filter((edit) => edit.material !== 'air').map((edit) => ({
    ...voxel(edit.x, edit.y, edit.z, colorOf(edit.material)),
    material: edit.material,
  })), seed)
  const removed = new Set(edits.filter((edit) => edit.material === 'air').map((edit) => `${edit.x},${edit.y},${edit.z}`))
  return next.map((chunk) => ({ ...chunk, voxels: chunk.voxels.filter((value) => !removed.has(
    `${value.x + chunk.chunk_x * CHUNK_SIZE},${value.y + chunk.chunk_y * CHUNK_SIZE},${value.z + chunk.chunk_z * CHUNK_SIZE}`
  )) }))
}

export function ensureTerrainAround(chunks: Chunk[], x: number, z: number, radius = 2,
  seed = DEFAULT_WORLD_SEED): Chunk[] {
  const centerX = Math.floor(x / CHUNK_SIZE)
  const centerZ = Math.floor(z / CHUNK_SIZE)
  const known = new Set(chunks.map((chunk) => chunkKey(chunk.chunk_x, chunk.chunk_y, chunk.chunk_z)))
  const next = [...chunks]
  for (let cx = centerX - radius; cx <= centerX + radius; cx++) {
    for (let cz = centerZ - radius; cz <= centerZ + radius; cz++) {
      const key = chunkKey(cx, 0, cz)
      if (known.has(key)) continue
      next.push(makeTerrainChunk(cx, cz, seed))
      known.add(key)
    }
  }
  return next
}

function spiralSite(index: number) {
  let x = 0
  let z = 0
  let dx = 1
  let dz = 0
  let segmentLength = 1
  let segmentProgress = 0
  let turns = 0
  for (let i = 0; i <= index; i++) {
    x += dx
    z += dz
    segmentProgress++
    if (segmentProgress === segmentLength) {
      segmentProgress = 0
      const nextDx = -dz
      dz = dx
      dx = nextDx
      turns++
      if (turns % 2 === 0) segmentLength++
    }
  }
  return { x: x * 13, z: z * 13 }
}

function compileSphericalLandmark(plan: SphericalLandmarkPlan): BuildProject {
  // The planner supplies a few dimensions; the world engine emits the blocks.
  const radius = Math.max(8, Math.min(48, Math.round(plan.radius)))
  const blocks: Voxel[] = []
  for (let y = -radius; y <= radius; y++) {
    for (let x = -radius; x <= radius; x++) {
      for (let z = -radius; z <= radius; z++) {
        const distance = Math.hypot(x, y, z)
        if (Math.abs(distance - radius) > 0.55) continue
        const dishDistance = Math.hypot(x - plan.dish.x, y - plan.dish.y)
        const dish = z > radius / 2 && dishDistance < plan.dish.radius
        const trench = Math.abs(y) <= plan.trenchWidth
        const color: Color = dish
          ? dishDistance < plan.dish.radius / 2 ? [91, 155, 171] : [91, 101, 112]
          : trench ? [97, 110, 117]
            : hash(x + 30, z + y) % 7 === 0 ? [174, 186, 185] : [189, 200, 198]
        blocks.push(voxel(plan.site.x + x, plan.centerY + y, plan.site.z + z, color))
      }
    }
  }
  blocks.sort((a, b) => a.y - b.y || a.z - b.z || a.x - b.x)
  return {
    name: plan.name,
    site: plan.site,
    standOff: radius + 5,
    landmark: { radius, centerY: plan.centerY },
    voxels: blocks,
  }
}

export function makeProject(index: number): BuildProject {
  if (index === 0) {
    return compileSphericalLandmark({
      name: 'an orbital station',
      site: { x: ORBITAL_STATION.x, z: ORBITAL_STATION.z },
      radius: ORBITAL_STATION.radius,
      centerY: ORBITAL_STATION.centerY,
      trenchWidth: 1,
      dish: { x: -8, y: 6, radius: 6 },
    })
  }

  const site = spiralSite(index)
  const blocks: Voxel[] = []
  const add = (dx: number, y: number, dz: number, color: Color) => {
    blocks.push(voxel(site.x + dx, y, site.z + dz, color))
  }

  if (index % 3 === 1) {
    for (let x = -2; x <= 2; x++) {
      for (let z = -2; z <= 2; z++) {
        if (Math.abs(x) === 2 || Math.abs(z) === 2) add(x, 0, z, [222, 203, 163])
      }
    }
    for (const [x, z, flower] of [
      [-1, -1, [246, 184, 153]], [1, -1, [245, 219, 145]],
      [-1, 1, [227, 169, 191]], [1, 1, [246, 184, 153]],
    ] as const) {
      add(x, 1, z, [92, 149, 112])
      add(x, 2, z, flower)
    }
    add(0, 0, 0, [102, 179, 199])
    return { name: 'a flower garden', site, standOff: 5, voxels: blocks }
  }

  if (index % 3 === 2) {
    for (let x = -2; x <= 2; x++) {
      for (let z = -2; z <= 2; z++) add(x, 0, z, [196, 184, 162])
    }
    for (let y = 1; y <= 5; y++) {
      for (const x of [-1, 1]) for (const z of [-1, 1]) add(x, y, z, [216, 199, 167])
    }
    for (let x = -2; x <= 2; x++) {
      for (let z = -2; z <= 2; z++) add(x, 6, z, [187, 126, 113])
    }
    add(0, 7, 0, [243, 207, 137])
    return { name: 'a lookout tower', site, standOff: 5, voxels: blocks }
  }

  for (let x = -2; x <= 2; x++) {
    for (let z = -2; z <= 2; z++) add(x, 0, z, [224, 202, 166])
  }
  for (let y = 1; y <= 3; y++) {
    for (let x = -2; x <= 2; x++) {
      for (let z = -2; z <= 2; z++) {
        const wall = Math.abs(x) === 2 || Math.abs(z) === 2
        const door = x === 0 && z === 2 && y <= 2
        if (wall && !door) add(x, y, z, [236, 213, 180])
      }
    }
  }
  for (let x = -3; x <= 3; x++) {
    for (let z = -3; z <= 3; z++) add(x, 4, z, [198, 116, 102])
  }
  add(-1, 2, 2, [116, 169, 178])
  add(1, 2, 2, [116, 169, 178])
  return { name: 'a cottage', site, standOff: 5, voxels: blocks }
}

export function loadBuildProgress(): BuildProgress {
  try {
    const saved = JSON.parse(localStorage.getItem('cradl-preview-build-v2') || 'null')
    if (Number.isInteger(saved?.projectIndex) && saved.projectIndex >= 0 &&
        Number.isInteger(saved?.stepIndex) && saved.stepIndex >= 0 && saved.projectIndex < 1000) {
      return { projectIndex: saved.projectIndex, stepIndex: saved.stepIndex }
    }
  } catch {
    // A stale or malformed local save should not prevent the preview from opening.
  }
  return { projectIndex: 0, stepIndex: 0 }
}

export function saveBuildProgress(progress: BuildProgress) {
  try {
    localStorage.setItem('cradl-preview-build-v2', JSON.stringify(progress))
  } catch {
    // The world keeps building in memory if storage is unavailable.
  }
}

export function worldForProgress(progress: BuildProgress): Chunk[] {
  let chunks = ensureTerrainAround([], 0, 0)
  chunks = placeVoxels(chunks, previewChunks.flatMap((chunk) => chunk.voxels.map((value) => globalize(value, chunk))))
  for (let index = 0; index <= progress.projectIndex; index++) {
    const project = makeProject(index)
    chunks = ensureTerrainAround(chunks, project.site.x, project.site.z)
    const count = index < progress.projectIndex ? project.voxels.length : Math.min(progress.stepIndex, project.voxels.length)
    chunks = placeVoxels(chunks, project.voxels.slice(0, count))
  }
  return chunks
}

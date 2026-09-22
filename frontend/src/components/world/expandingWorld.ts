import type { BlockEdit, Chunk, Voxel } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'
import { previewChunks } from './previewWorld'

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
  [[127, 173, 137], [133, 178, 141], [123, 169, 133]],
  [[143, 183, 138], [149, 188, 142], [139, 179, 134]],
  [[116, 163, 139], [122, 168, 144], [112, 159, 135]],
]

function hash(x: number, z: number) {
  return Math.abs((x * 73856093) ^ (z * 19349663))
}

export function terrainHeight(x: number, z: number) {
  if (Math.hypot(x, z) < 17 || Math.hypot(x - ORBITAL_STATION.x, z - ORBITAL_STATION.z) < 27) return 0
  const wave = Math.sin(x * 0.085) + Math.cos(z * 0.075) + Math.sin((x + z) * 0.037)
  return wave > 1.65 ? 3 : wave > 1.15 ? 2 : wave > 0.65 ? 1 : 0
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

export function makeTerrainChunk(cx: number, cz: number): Chunk {
  const voxels: Voxel[] = []
  const add = (x: number, y: number, z: number, color: Color) => {
    voxels.push(voxel(x, y, z, color))
  }

  for (let x = 0; x < CHUNK_SIZE; x++) {
    for (let z = 0; z < CHUNK_SIZE; z++) {
      const wx = cx * CHUNK_SIZE + x
      const wz = cz * CHUNK_SIZE + z
      const region = Math.sin(wx * 0.095) + Math.cos(wz * 0.085) + Math.sin((wx + wz) * 0.055)
      const palette = grass[region > 0.7 ? 1 : region < -0.7 ? 2 : 0]
      const height = terrainHeight(wx, wz)
      for (let y = 0; y <= height; y++) {
        add(x, y, z, y === height ? palette[hash(wx, wz) % palette.length] : y >= height - 1 ? [126, 105, 89] : [153, 151, 148])
      }

      // Keep the village and future project sites clear for construction.
      if (Math.hypot(wx, wz) < 17 || x < 3 || x > 12 || z < 3 || z > 12) continue
      const nearSiteX = Math.min(((wx % 13) + 13) % 13, 13 - (((wx % 13) + 13) % 13)) < 5
      const nearSiteZ = Math.min(((wz % 13) + 13) % 13, 13 - (((wz % 13) + 13) % 13)) < 5
      if (nearSiteX && nearSiteZ) continue

      if (hash(wx, wz) % 257 === 0) {
        for (let y = height + 1; y <= height + 4; y++) add(x, y, z, [126, 94, 74])
        for (let dx = -2; dx <= 2; dx++) {
          for (let dz = -2; dz <= 2; dz++) {
            if (Math.abs(dx) + Math.abs(dz) > 3) continue
            add(x + dx, height + 5, z + dz, [91, 151, 119])
            if (Math.abs(dx) + Math.abs(dz) < 2) add(x + dx, height + 6, z + dz, [110, 168, 128])
          }
        }
      } else if (hash(wx, wz) % 71 === 0) {
        add(x, height + 1, z, [89, 147, 112])
        add(x, height + 2, z, hash(wx + 1, wz) % 2 ? [242, 178, 153] : [245, 216, 143])
      }
    }
  }

  return { chunk_x: cx, chunk_y: 0, chunk_z: cz, voxels }
}

export function placeVoxels(chunks: Chunk[], values: Voxel[]): Chunk[] {
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
      next.push(cy === 0 ? makeTerrainChunk(cx, cz) : { chunk_x: cx, chunk_y: cy, chunk_z: cz, voxels: [] })
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

export function applyBlockEdits(chunks: Chunk[], edits: BlockEdit[], catalog: Record<string, { color: number[] }> = {}): Chunk[] {
  if (!edits.length) return chunks
  const colorOf = (material: string): Color => {
    const color = catalog[material]?.color
    return color && color.length >= 3 ? [color[0], color[1], color[2]] : blockColors[material] ?? [180, 130, 180]
  }
  const undergroundMaterial = (x: number, y: number, z: number) => {
    if (y === -5) return 'bedrock'
    if (y === -1) return 'dirt'
    const oreSeed = Math.abs(x * 31 + z * 17 + y * 101)
    return oreSeed % 37 === 0 ? 'iron_ore' : oreSeed % 19 === 0 ? 'coal_ore' : 'stone'
  }
  // Generate the exposed layers only around excavations. The deeper world is
  // implicit bedrock/stone until Mimo digs into it.
  const underground: Voxel[] = []
  for (const edit of edits) {
    if (edit.material !== 'air' || edit.y > 0) continue
    for (let x = edit.x - 2; x <= edit.x + 2; x++) for (let z = edit.z - 2; z <= edit.z + 2; z++) {
      for (let y = -5; y <= -1; y++) {
        const material = undergroundMaterial(x, y, z)
        underground.push({ ...voxel(x, y, z, colorOf(material)), material })
      }
    }
  }
  let next = placeVoxels(chunks, underground)
  next = placeVoxels(next, edits.filter((edit) => edit.material !== 'air').map((edit) => ({
    ...voxel(edit.x, edit.y, edit.z, colorOf(edit.material)),
    material: edit.material,
  })))
  const removed = new Set(edits.filter((edit) => edit.material === 'air').map((edit) => `${edit.x},${edit.y},${edit.z}`))
  return next.map((chunk) => ({ ...chunk, voxels: chunk.voxels.filter((value) => !removed.has(
    `${value.x + chunk.chunk_x * CHUNK_SIZE},${value.y + chunk.chunk_y * CHUNK_SIZE},${value.z + chunk.chunk_z * CHUNK_SIZE}`
  )) }))
}

export function ensureTerrainAround(chunks: Chunk[], x: number, z: number, radius = 2): Chunk[] {
  const centerX = Math.floor(x / CHUNK_SIZE)
  const centerZ = Math.floor(z / CHUNK_SIZE)
  const known = new Set(chunks.map((chunk) => chunkKey(chunk.chunk_x, chunk.chunk_y, chunk.chunk_z)))
  const next = [...chunks]
  for (let cx = centerX - radius; cx <= centerX + radius; cx++) {
    for (let cz = centerZ - radius; cz <= centerZ + radius; cz++) {
      const key = chunkKey(cx, 0, cz)
      if (known.has(key)) continue
      next.push(makeTerrainChunk(cx, cz))
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

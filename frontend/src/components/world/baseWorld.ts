/**
 * Procedural base world generator.
 * Creates a large meadow with grass, trees, flowers, ponds, and rocks.
 * Uses a seeded PRNG so the world is identical every load —
 * no need to persist terrain voxels in the database.
 *
 * Also exports a collision set (solidPositions) so the pet
 * can't walk through trees, rocks, or into ponds.
 */
import type { Chunk, Voxel } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'

// Mulberry32 — fast, deterministic PRNG
function mulberry32(seed: number) {
  return () => {
    let t = (seed += 0x6d2b79f5)
    t = Math.imul(t ^ (t >>> 15), 1 | t)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

interface WorldVoxel {
  wx: number
  wy: number
  wz: number
  r: number
  g: number
  b: number
  a: number
}

export interface BaseWorldData {
  chunks: Chunk[]
  /** "wx,wz" keys for positions the pet cannot walk through */
  solidPositions: Set<string>
}

// Convert a world coordinate to chunk index + chunk-local offset
function toChunkLocal(w: number) {
  const chunk = Math.floor(w / CHUNK_SIZE)
  return { chunk, local: w - chunk * CHUNK_SIZE }
}

// Bucket world-space voxels into Chunk objects
function groupIntoChunks(voxels: WorldVoxel[]): Chunk[] {
  const map = new Map<string, Chunk>()
  for (const v of voxels) {
    const cx = toChunkLocal(v.wx)
    const cy = toChunkLocal(v.wy)
    const cz = toChunkLocal(v.wz)
    const key = `${cx.chunk},${cy.chunk},${cz.chunk}`
    if (!map.has(key)) {
      map.set(key, {
        chunk_x: cx.chunk,
        chunk_y: cy.chunk,
        chunk_z: cz.chunk,
        voxels: [],
      })
    }
    map.get(key)!.voxels.push({
      x: cx.local,
      y: cy.local,
      z: cz.local,
      r: v.r,
      g: v.g,
      b: v.b,
      a: v.a,
    })
  }
  return Array.from(map.values())
}

// ---- Feature generators ----

function makeTree(wx: number, wz: number, rng: () => number): WorldVoxel[] {
  const out: WorldVoxel[] = []
  const trunkH = 3 + Math.floor(rng() * 3) // 3–5 blocks

  // Trunk
  for (let y = 1; y <= trunkH; y++) {
    const s = 0.85 + rng() * 0.15
    out.push({
      wx, wy: y, wz,
      r: Math.round(101 * s), g: Math.round(67 * s), b: Math.round(33 * s), a: 255,
    })
  }

  // Canopy — layered blob of leaves
  const canopyBase = trunkH + 1
  const canopyLayers = 2 + Math.floor(rng() * 2) // 2–3

  for (let dy = 0; dy < canopyLayers; dy++) {
    const r = dy === 0 || dy === canopyLayers - 1 ? 1 : 2
    for (let dx = -r; dx <= r; dx++) {
      for (let dz = -r; dz <= r; dz++) {
        if (Math.abs(dx) === r && Math.abs(dz) === r && rng() > 0.4) continue
        const s = 0.7 + rng() * 0.3
        out.push({
          wx: wx + dx, wy: canopyBase + dy, wz: wz + dz,
          r: Math.round(28 + 32 * s), g: Math.round(95 + 65 * s), b: Math.round(18 + 22 * s), a: 255,
        })
      }
    }
  }

  return out
}

// ---- Main generator ----

// World bounds: 5×5 chunks centered near origin
const MIN_COORD = -32
const MAX_COORD = 48

const TREE_POSITIONS = [
  // Northwest
  { x: -28, z: -26 }, { x: -18, z: -15 }, { x: -25, z: -4 },
  { x: -10, z: -22 }, { x: -5, z: -8 },
  // Northeast
  { x: 15, z: -25 }, { x: 30, z: -20 }, { x: 42, z: -10 },
  { x: 25, z: -5 }, { x: 38, z: 5 },
  // Southwest
  { x: -22, z: 15 }, { x: -12, z: 28 }, { x: -28, z: 40 },
  { x: -5, z: 18 }, { x: 5, z: 35 },
  // Southeast
  { x: 18, z: 20 }, { x: 35, z: 15 }, { x: 42, z: 30 },
  { x: 28, z: 38 }, { x: 15, z: 42 },
]

const PONDS = [
  { x: 24, z: 14, radius: 4 }, // main pond
  { x: -16, z: 32, radius: 2 }, // small pond
]

const ROCK_CLUSTERS = [
  { x: -3, z: 5 },
  { x: 33, z: -15 },
  { x: 10, z: -18 },
  { x: -20, z: 25 },
  { x: 40, z: 22 },
  { x: 12, z: 38 },
]

const FLOWER_COLORS = [
  { r: 220, g: 50, b: 50 },   // red
  { r: 255, g: 220, b: 50 },  // yellow
  { r: 170, g: 50, b: 210 },  // purple
  { r: 245, g: 230, b: 230 }, // white
  { r: 255, g: 140, b: 50 },  // orange
]

export function generateBaseWorld(): BaseWorldData {
  const rng = mulberry32(42)
  const voxels: WorldVoxel[] = []
  const solidPositions = new Set<string>()

  // ── Pre-mark exclusion zones (no grass here) ──
  const excluded = new Set<string>()

  for (const pond of PONDS) {
    for (let dx = -pond.radius; dx <= pond.radius; dx++) {
      for (let dz = -pond.radius; dz <= pond.radius; dz++) {
        if (dx * dx + dz * dz <= pond.radius * pond.radius + 1) {
          const px = pond.x + dx
          const pz = pond.z + dz
          excluded.add(`${px},${pz}`)
          solidPositions.add(`${px},${pz}`) // pet can't walk into water
        }
      }
    }
  }

  for (const t of TREE_POSITIONS) {
    excluded.add(`${t.x},${t.z}`)
    solidPositions.add(`${t.x},${t.z}`) // tree trunk is solid
  }

  // ── Ground plane (grass + dirt) ──
  for (let wx = MIN_COORD; wx < MAX_COORD; wx++) {
    for (let wz = MIN_COORD; wz < MAX_COORD; wz++) {
      if (excluded.has(`${wx},${wz}`)) continue

      const n = rng()
      let r: number, g: number, b: number
      if (n < 0.04) {
        // Dirt patch
        r = 110 + Math.floor(rng() * 30)
        g = 85 + Math.floor(rng() * 20)
        b = 55 + Math.floor(rng() * 15)
      } else {
        // Grass — subtle variation
        const s = 0.75 + rng() * 0.25
        r = Math.round(48 * s + 18)
        g = Math.round(130 * s + 32)
        b = Math.round(20 * s + 12)
      }
      voxels.push({ wx, wy: 0, wz, r, g, b, a: 255 })
    }
  }

  // ── Ponds ──
  for (const pond of PONDS) {
    for (let dx = -pond.radius; dx <= pond.radius; dx++) {
      for (let dz = -pond.radius; dz <= pond.radius; dz++) {
        if (dx * dx + dz * dz <= pond.radius * pond.radius + 1) {
          const s = 0.85 + rng() * 0.15
          voxels.push({
            wx: pond.x + dx, wy: 0, wz: pond.z + dz,
            r: Math.round(35 * s), g: Math.round(110 * s), b: Math.round(210 * s), a: 255,
          })
        }
      }
    }
  }

  // ── Trees ──
  for (const t of TREE_POSITIONS) {
    voxels.push(...makeTree(t.x, t.z, rng))
  }

  // ── Flowers ──
  for (let i = 0; i < 80; i++) {
    const fx = Math.floor(rng() * (MAX_COORD - MIN_COORD)) + MIN_COORD
    const fz = Math.floor(rng() * (MAX_COORD - MIN_COORD)) + MIN_COORD
    if (excluded.has(`${fx},${fz}`)) continue
    const c = FLOWER_COLORS[Math.floor(rng() * FLOWER_COLORS.length)]
    voxels.push({ wx: fx, wy: 1, wz: fz, r: c.r, g: c.g, b: c.b, a: 255 })
  }

  // ── Rock clusters ──
  for (const rp of ROCK_CLUSTERS) {
    const count = 3 + Math.floor(rng() * 4)
    for (let i = 0; i < count; i++) {
      const dx = Math.floor(rng() * 3) - 1
      const dz = Math.floor(rng() * 3) - 1
      const dy = Math.floor(rng() * 2)
      const s = 0.5 + rng() * 0.3
      const rx = rp.x + dx
      const rz = rp.z + dz
      voxels.push({
        wx: rx, wy: dy, wz: rz,
        r: Math.round(140 * s), g: Math.round(140 * s), b: Math.round(148 * s), a: 255,
      })
      if (dy >= 1) solidPositions.add(`${rx},${rz}`) // protruding rocks are solid
    }
  }

  // ── Tall grass tufts ──
  for (let i = 0; i < 50; i++) {
    const gx = Math.floor(rng() * (MAX_COORD - MIN_COORD)) + MIN_COORD
    const gz = Math.floor(rng() * (MAX_COORD - MIN_COORD)) + MIN_COORD
    if (excluded.has(`${gx},${gz}`)) continue
    const s = 0.7 + rng() * 0.3
    voxels.push({
      wx: gx, wy: 1, wz: gz,
      r: Math.round(40 * s + 15), g: Math.round(120 * s + 40), b: Math.round(18 * s + 8), a: 255,
    })
  }

  return { chunks: groupIntoChunks(voxels), solidPositions }
}

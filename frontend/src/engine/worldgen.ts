// Keep this file in sync with backend/services/worldgen.py. shared/worldgen-fixture.json
// checks both ports cell by cell. The seed is persisted as a decimal string so
// JavaScript never rounds its 64-bit value.
import { AIR, blockId } from './blocks'

export const DEFAULT_WORLD_SEED = '13897963875510148821'
export const LEGACY_RADIUS = 192
const TRANSITION_WIDTH = 48
export const SEA_LEVEL = 2
export const CHUNK_SIZE = 16
export const WORLD_MIN_Y = -8
export const WORLD_HEIGHT = 128
export const WORLD_MAX_Y = WORLD_MIN_Y + WORLD_HEIGHT - 1
const HOME_RADIUS = 12
const MASK = 0xffffffff
// Wild food on generated land (see backend/services/worldgen.py).
const FOREST_EDGE = 0.16
const BUSH_RARITY = 97
const MUSHROOM_RARITY = 67
const CAVE_MUSHROOM_RARITY = 29
const seedCache = new Map<string, [number, number]>()
const heightCache = new Map<string, number>()

function mod(value: number, n: number): number {
  return ((value % n) + n) % n
}

function seedParts(seed: string): [number, number] {
  let parts = seedCache.get(seed)
  if (!parts) {
    const value = BigInt.asUintN(64, BigInt(seed))
    parts = [Number(value & 0xffffffffn), Number(value >> 32n)]
    seedCache.set(seed, parts)
  }
  return parts
}

export function hash32(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED, channel = 0): number {
  const [low, high] = seedParts(seed)
  let value = (low ^ Math.imul(high, 0x9e3779b1) ^ Math.imul(x, 0x85ebca6b) ^
    Math.imul(y, 0x27d4eb2f) ^ Math.imul(z, 0xc2b2ae35) ^ Math.imul(channel, 0x165667b1)) >>> 0
  value = Math.imul(value ^ (value >>> 16), 0x7feb352d) >>> 0
  value = Math.imul(value ^ (value >>> 15), 0x846ca68b) >>> 0
  return (value ^ (value >>> 16)) >>> 0
}

/** The viewer's original position hash. Python reproduces JavaScript's int32 XOR. */
export function legacyHash(x: number, z: number): number {
  return Math.abs((x * 73856093) ^ (z * 19349663))
}

function smooth(value: number) { return value * value * (3 - 2 * value) }
function lerp(a: number, b: number, t: number) { return a + (b - a) * t }

function noise2(x: number, z: number, scale: number, seed: string, channel: number): number {
  const gx = Math.floor(x / scale), gz = Math.floor(z / scale)
  const fx = smooth(x / scale - gx), fz = smooth(z / scale - gz)
  const sample = (dx: number, dz: number) => hash32(gx + dx, 0, gz + dz, seed, channel) / MASK * 2 - 1
  return lerp(lerp(sample(0, 0), sample(1, 0), fx), lerp(sample(0, 1), sample(1, 1), fx), fz)
}

function noise3(x: number, y: number, z: number, scale: number, seed: string, channel: number): number {
  const gx = Math.floor(x / scale), gy = Math.floor(y / scale), gz = Math.floor(z / scale)
  const fx = smooth(x / scale - gx), fy = smooth(y / scale - gy), fz = smooth(z / scale - gz)
  const sample = (dx: number, dy: number, dz: number) => hash32(gx + dx, gy + dy, gz + dz, seed, channel) / MASK * 2 - 1
  const a = lerp(lerp(sample(0, 0, 0), sample(1, 0, 0), fx),
    lerp(sample(0, 0, 1), sample(1, 0, 1), fx), fz)
  const b = lerp(lerp(sample(0, 1, 0), sample(1, 1, 0), fx),
    lerp(sample(0, 1, 1), sample(1, 1, 1), fx), fz)
  return lerp(a, b, fy)
}

function legacyHeight(x: number, z: number): number {
  if (Math.hypot(x, z) < 17 || Math.hypot(x - 48, z) < 27) return 0
  const wave = Math.sin(x * 0.085) + Math.cos(z * 0.075) + Math.sin((x + z) * 0.037)
  return wave > 1.65 ? 3 : wave > 1.15 ? 2 : wave > 0.65 ? 1 : 0
}

export function terrainHeight(x: number, z: number, seed = DEFAULT_WORLD_SEED): number {
  const key = `${seed}:${x},${z}`
  const cached = heightCache.get(key)
  if (cached !== undefined) return cached
  const height = calculateHeight(x, z, seed)
  heightCache.set(key, height)
  if (heightCache.size > 200000) heightCache.clear()
  return height
}

function calculateHeight(x: number, z: number, seed: string): number {
  const radius = Math.hypot(x, z)
  if (radius <= LEGACY_RADIUS) return legacyHeight(x, z)
  const broad = noise2(x, z, 96, seed, 1) * 6
  const detail = noise2(x, z, 32, seed, 2) * 2
  const ridge = Math.max(0, noise2(x, z, 72, seed, 3)) ** 2 * 10
  const generated = Math.max(0, Math.min(18, Math.floor(3.5 + broad + detail + ridge)))
  if (radius >= LEGACY_RADIUS + TRANSITION_WIDTH) return generated
  const blend = smooth((radius - LEGACY_RADIUS) / TRANSITION_WIDTH)
  return Math.floor(legacyHeight(x, z) * (1 - blend) + generated * blend + 0.5)
}

export function biomeAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return 'meadow'
  const height = terrainHeight(x, z, seed)
  if (height >= 11) return 'alpine'
  const heat = noise2(x, z, 160, seed, 4)
  const moisture = noise2(x, z, 160, seed, 5)
  if (heat > 0.08 && moisture < -0.12) return 'desert'
  if (moisture > 0.08) return 'forest'
  return 'meadow'
}

export function surfaceMaterial(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert') return 'sand'
  if (biome === 'alpine') return 'snow'
  if (biome === 'forest' && hash32(x, 0, z, seed, 6) % 7 === 0) return 'moss'
  return 'grass'
}

export function caveAt(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  if (Math.hypot(x, z) <= LEGACY_RADIUS || y <= -5 || y >= terrainHeight(x, z, seed) - 2) return false
  return noise3(x, y, z, 11, seed, 7) > 0.27 && noise3(x, y, z, 5, seed, 8) > -0.12
}

function inPond(x: number, z: number): boolean {
  return ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1
}

const STEPPING_STONES = new Set(['-3,2', '-2,1', '3,2', '4,1'])
const HOME_FLOWERS: [number, number, string][] = [
  [-8, 0, 'flower_orange'], [-7, 1, 'flower_pink'], [-2, -5, 'flower_yellow'], [1, -6, 'flower_pink'],
  [8, 1, 'flower_orange'], [7, 5, 'flower_yellow'], [-1, 7, 'flower_pink'], [3, 7, 'flower_orange'],
]

/** Ground of Mimo's original home island, or null outside it. */
function homeGround(x: number, y: number, z: number): string | null {
  const distance = Math.hypot(x, z)
  if (distance > 10.4 + (legacyHash(x, z) % 5) * 0.16) return null
  if (y === 0) {
    if (x >= 4 && x <= 7 && z >= -6 && z <= -3) return 'dirt_path'
    if (STEPPING_STONES.has(`${x},${z}`)) return 'dirt_path'
    if (inPond(x, z)) return 'water'
    const shore = ((x + 5) / 4.2) ** 2 + ((z - 4) / 3.4) ** 2 < 1
    if (shore || distance > 9.3) return 'sand'
    const walkway = x >= 0 && x <= 6 && Math.abs(z + Math.round(x * 0.55)) <= 0.6
    return walkway ? 'dirt_path' : 'grass'
  }
  if (y === -1) return distance > 9 ? 'sand' : 'dirt'
  if (y === -2 && distance < 9.1) return 'dirt'
  return null
}

function buildHomeBlocks(): Map<string, string> {
  const blocks = new Map<string, string>()
  const put = (x: number, y: number, z: number, name: string) => blocks.set(`${x},${y},${z}`, name)
  for (let x = 4; x <= 7; x++) for (let z = -6; z <= -3; z++) for (let y = 1; y <= 3; y++) {
    const wall = x === 4 || x === 7 || z === -6 || z === -3
    const door = x === 5 && z === -3 && y <= 2
    if (wall && !door) put(x, y, z, 'plaster')
  }
  put(5, 2, -6, 'glass')
  put(6, 2, -6, 'glass')
  for (let x = 3; x <= 8; x++) for (let z = -7; z <= -2; z++) {
    put(x, 4, z, 'roof_tile')
    if (x > 3 && x < 8 && z > -7 && z < -2) put(x, 5, z, 'roof_tile')
  }
  for (let x = -8; x <= -4; x++) for (let z = -6; z <= -2; z++) {
    const spread = Math.abs(x + 6) + Math.abs(z + 4)
    if (spread > 3) continue
    put(x, 5, z, 'leaves')
    if (spread <= 2) put(x, 6, z, 'leaves')
  }
  put(-6, 7, -4, 'leaves')
  for (let y = 1; y <= 5; y++) put(-6, y, -4, 'oak_log')
  for (const [x, z, name] of HOME_FLOWERS) put(x, 1, z, name)
  return blocks
}

const HOME_BLOCKS = buildHomeBlocks()

/** Terrain, water, caves and ores, before trees and plants are added. */
export function terrainBlock(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (y <= -5) return 'bedrock'
  const height = terrainHeight(x, z, seed)
  if (Math.hypot(x, z) <= LEGACY_RADIUS) {
    const home = homeGround(x, y, z)
    if (home) return home
    if (y >= -4 && y < -1) {
      const oreSeed = Math.abs(x * 31 + z * 17 + y * 101)
      return oreSeed % 37 === 0 ? 'iron_ore' : oreSeed % 19 === 0 ? 'coal_ore' : 'stone'
    }
    if (y === -1) return 'dirt'
    if (y === 0 && inPond(x, z)) return 'water'
    if (y === height) return 'grass'
    if (y >= 0 && y < height) return y >= height - 1 ? 'dirt' : 'stone'
    return 'air'
  }
  if (y > height) return y <= SEA_LEVEL ? 'water' : 'air'
  if (y === height) return surfaceMaterial(x, z, seed)
  if (y >= height - 2) return biomeAt(x, z, seed) === 'desert' ? 'sand' : 'dirt'
  if (caveAt(x, y, z, seed)) return 'air'
  const ore = hash32(x, y, z, seed, 9)
  if (ore % 97 === 0) return 'iron_ore'
  if (ore % 61 === 0) return 'coal_ore'
  if (ore % 151 === 0) return 'copper_ore'
  return 'stone'
}

/** Columns where the viewer has always allowed trees and flowers. */
function decorationColumn(x: number, z: number, seed: string): boolean {
  const lx = mod(x, 16), lz = mod(z, 16)
  if (lx < 3 || lx > 12 || lz < 3 || lz > 12 || Math.hypot(x, z) < 17) return false
  if (terrainHeight(x, z, seed) < SEA_LEVEL) return false
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert' || biome === 'alpine') return false
  const mx = mod(x, 13), mz = mod(z, 13)
  return !(Math.min(mx, 13 - mx) < 5 && Math.min(mz, 13 - mz) < 5)
}

/** Ground height under a tree trunk at (x, z), or null when no tree grows there. */
export function treeBase(x: number, z: number, seed = DEFAULT_WORLD_SEED): number | null {
  if (!decorationColumn(x, z, seed)) return null
  const grows = Math.hypot(x, z) <= LEGACY_RADIUS
    ? legacyHash(x, z) % 257 === 0
    : hash32(x, 0, z, seed, 12) % (biomeAt(x, z, seed) === 'forest' ? 78 : 300) === 0
  return grows ? terrainHeight(x, z, seed) : null
}

const treeCache = new Map<string, [number, number, number][]>()

/** [x, z, ground height] of every tree rooted in a chunk. Canopies never leave the chunk. */
export function treesInChunk(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): [number, number, number][] {
  const key = `${seed}:${cx},${cz}`
  let trees = treeCache.get(key)
  if (trees) return trees
  trees = []
  for (let x = cx * 16 + 3; x < cx * 16 + 13; x++) {
    for (let z = cz * 16 + 3; z < cz * 16 + 13; z++) {
      const base = treeBase(x, z, seed)
      if (base !== null) trees.push([x, z, base])
    }
  }
  treeCache.set(key, trees)
  if (treeCache.size > 4096) treeCache.delete(treeCache.keys().next().value!)
  return trees
}

function isLeaf(dx: number, dy: number, dz: number): boolean {
  const ax = Math.abs(dx), az = Math.abs(dz)
  if (dy === 5) return ax <= 2 && az <= 2 && ax + az <= 3
  return dy === 6 && ax + az < 2
}

function treeBlock(x: number, y: number, z: number, seed: string): string | null {
  const trees = treesInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)
  if (trees.some(([tx, tz, base]) => x === tx && z === tz && y > base && y <= base + 4)) return 'oak_log'
  if (trees.some(([tx, tz, base]) => isLeaf(x - tx, y - base, z - tz))) return 'leaves'
  return null
}

/** A ripe berry bush (meadows and forest edges) or a mushroom (forest floor) on generated land. */
export function wildFood(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return null
  const biome = biomeAt(x, z, seed)
  if (biome === 'meadow' || (biome === 'forest' && noise2(x, z, 160, seed, 5) < FOREST_EDGE)) {
    if (hash32(x, 0, z, seed, 15) % BUSH_RARITY === 0) return 'berry_bush_ripe'
  }
  if (biome === 'forest') {
    const roll = hash32(x, 0, z, seed, 16)
    if (roll % MUSHROOM_RARITY === 0) return Math.floor(roll / MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
  }
  return null
}

/** A mushroom on a cave floor: an open cave cell with solid rock (or bedrock) under it. */
export function cavePlant(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  const roll = hash32(x, y, z, seed, 17)
  if (roll % CAVE_MUSHROOM_RARITY !== 0) return null
  if (!caveAt(x, y, z, seed) || caveAt(x, y - 1, z, seed)) return null
  return Math.floor(roll / CAVE_MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
}

/** Flower, wild food or tall grass growing on top of the terrain at (x, z). */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  if (Math.hypot(x, z) <= HOME_RADIUS) return null
  if (decorationColumn(x, z, seed)) {
    if (treeBase(x, z, seed) !== null) return null
    if (hash32(x, 0, z, seed, 13) % 97 === 0) return legacyHash(x + 1, z) % 2 ? 'flower_orange' : 'flower_yellow'
  }
  if (Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) < SEA_LEVEL) return null
  const surface = surfaceMaterial(x, z, seed)
  if (surface !== 'grass' && surface !== 'moss') return null
  return wildFood(x, z, seed) ?? (hash32(x, 0, z, seed, 14) % 19 === 0 ? 'tall_grass' : null)
}

/** Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk, leaves, plant. */
function decorationAt(x: number, y: number, z: number, seed: string): string | null {
  const home = HOME_BLOCKS.get(`${x},${y},${z}`)
  if (home) return home
  const tree = treeBlock(x, y, z, seed)
  if (tree) return tree
  const height = terrainHeight(x, z, seed)
  if (y === height + 1) return plantAt(x, z, seed)
  if (y < height - 2) return cavePlant(x, y, z, seed)
  return null
}

/** The natural block at any cell: terrain first, then decorations in air. */
export function blockAt(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const terrain = terrainBlock(x, y, z, seed)
  if (terrain !== 'air') return terrain
  return decorationAt(x, y, z, seed) ?? 'air'
}

/** Index into a 16 × 128 × 16 column. y is a world y. */
export function columnIndex(lx: number, y: number, lz: number): number {
  return ((y - WORLD_MIN_Y) * CHUNK_SIZE + lz) * CHUNK_SIZE + lx
}

/**
 * Fill a whole column at once. Equivalent to blockAt for every cell, but stamps
 * decorations instead of searching for them per cell.
 */
export function generateColumn(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): Uint8Array {
  const data = new Uint8Array(CHUNK_SIZE * CHUNK_SIZE * WORLD_HEIGHT)
  const x0 = cx * CHUNK_SIZE, z0 = cz * CHUNK_SIZE
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const x = x0 + lx, z = z0 + lz
    const height = terrainHeight(x, z, seed)
    const top = Math.max(height, SEA_LEVEL)
    for (let y = WORLD_MIN_Y; y <= top; y++) {
      // A cave floor plant counts as terrain here: nothing else is ever stamped in a cave.
      const name = terrainBlock(x, y, z, seed)
      const found = name !== 'air' ? name : y < height - 2 ? cavePlant(x, y, z, seed) : null
      if (found) data[columnIndex(lx, y, lz)] = blockId(found)
    }
  }
  const terrain = data.slice()
  // Later stamps win, so stamp in rising precedence: plants, leaves, trunks, home.
  const stamp = (x: number, y: number, z: number, name: string) => {
    const lx = x - x0, lz = z - z0
    if (lx < 0 || lx >= CHUNK_SIZE || lz < 0 || lz >= CHUNK_SIZE || y < WORLD_MIN_Y || y > WORLD_MAX_Y) return
    const index = columnIndex(lx, y, lz)
    if (terrain[index] === AIR) data[index] = blockId(name)
  }
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const plant = plantAt(x0 + lx, z0 + lz, seed)
    if (plant) stamp(x0 + lx, terrainHeight(x0 + lx, z0 + lz, seed) + 1, z0 + lz, plant)
  }
  const trees = treesInChunk(cx, cz, seed)
  for (const [tx, tz, base] of trees) {
    for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (const dy of [5, 6]) {
      if (isLeaf(dx, dy, dz)) stamp(tx + dx, base + dy, tz + dz, 'leaves')
    }
  }
  for (const [tx, tz, base] of trees) for (let y = base + 1; y <= base + 4; y++) stamp(tx, y, tz, 'oak_log')
  for (const [key, name] of HOME_BLOCKS) {
    const [x, y, z] = key.split(',').map(Number)
    stamp(x, y, z, name)
  }
  return data
}

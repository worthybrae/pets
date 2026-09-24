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
// L3, the bigger world: taiga, swamp and birch forest (see backend/services/worldgen.py).
const TAIGA_HEAT = -0.45
const SWAMP_WET = 0.45
const SWAMP_TOP = SEA_LEVEL + 1
const BIRCH_HEAT = 0.3
const PEAK = 15
const TREE_RARITY: Record<string, number> = { forest: 78, birch_forest: 70, taiga: 60, swamp: 150 }
const MEADOW_TREES = 300
const TREE_LOGS: Record<string, string> = { oak: 'oak_log', birch: 'birch_log', spruce: 'spruce_log' }
const TREE_LEAVES: Record<string, string> = { oak: 'leaves', birch: 'birch_leaves', spruce: 'spruce_leaves' }
const CANOPY_TOP = 7
// Canopies reach at most this far; a trunk this close past the clearing's edge keeps its pre-L3 rules,
// so its leaves never change a block the clearing already had.
const RIM_MARGIN = 3
const CACTUS_RARITY = 47
const CANE_RARITY = 11
const DEAD_BUSH_RARITY = 53
const FERN_RARITY = 5
const FRUIT_RARITY = 421
const FRUIT_BIOMES = new Set(['meadow', 'forest', 'birch_forest'])
const SIDES: [number, number][] = [[1, 0], [-1, 0], [0, 1], [0, -1]]
// L3 underground: bigger, taller caves, lakes and lava in them, seams of other stone, gold and diamond.
const CAVE_SCALE = 13
const CAVE_STRETCH = 0.6
const CAVE_OPEN = 0.22
const CAVE_ROOM = -0.15
const LAKE_LEVEL = -2
const LAVA_LEVEL = -4
// Fix round 1 (Task 4 review minor 5): named to match backend/services/worldgen.py's cave_fill and
// lava_in_chunk exactly, so the two can never drift apart.
const LAVA_SCALE = 32
const LAVA_CHANNEL = 28
const LAVA_REGION = 0.25
const GOLD_RARITY = 181
const GOLD_DEPTH = 0
const DIAMOND_RARITY = 331
const DIAMOND_DEPTH = -3
const ASH_DEPTH = -2
const VARIANTS = ['granite', 'andesite', 'diorite']
// L3 on the surface: cave entrances open to the sky (sinkholes and hillside mouths), boulders, outcrops.
const OPENING_REGION = 64
const MOUTH_LENGTH = 12
const MOUTH_TRIES = 6
const OUTCROP_GROUND = 8
const BOULDERS: Record<string, string> = { desert: 'sandstone', meadow: 'andesite', alpine: 'stone' }
const OUTCROPS: Record<string, string> = { desert: 'sandstone', taiga: 'andesite', birch_forest: 'diorite', alpine: 'granite' }
type Openings = [string, ReadonlyMap<string, [number, number]>]
type Rock = [number, number, string, number, string]
const openingCache = new Map<string, Openings>()
const rockCache = new Map<string, Rock[]>()
const biomeCache = new Map<string, string>()
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
  const key = `${seed}:${x},${z}`
  const cached = biomeCache.get(key)
  if (cached !== undefined) return cached
  const biome = calculateBiome(x, z, seed)
  biomeCache.set(key, biome)
  if (biomeCache.size > 200000) biomeCache.clear()
  return biome
}

function calculateBiome(x: number, z: number, seed: string): string {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return 'meadow'
  const height = terrainHeight(x, z, seed)
  if (height >= 11) return 'alpine'
  const heat = noise2(x, z, 160, seed, 4)
  const moisture = noise2(x, z, 160, seed, 5)
  if (heat > 0.08 && moisture < -0.12) return 'desert'
  if (heat < TAIGA_HEAT) return 'taiga'
  if (moisture > SWAMP_WET && height <= SWAMP_TOP) return 'swamp'
  if (moisture > 0.08) return heat > BIRCH_HEAT ? 'birch_forest' : 'forest'
  return 'meadow'
}

export function surfaceMaterial(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert') return 'sand'
  const height = terrainHeight(x, z, seed)
  if (height < SEA_LEVEL && Math.hypot(x, z) > LEGACY_RADIUS) return noise2(x, z, 10, seed, 87) > -0.1 ? 'gravel' : 'sand'
  if (biome === 'alpine') {
    if (height >= PEAK) return 'snow_block'
    return noise2(x, z, 9, seed, 89) > 0.35 ? 'gravel' : 'snow'
  }
  if (biome === 'forest' && hash32(x, 0, z, seed, 6) % 7 === 0) return 'moss'
  if (biome === 'taiga') {
    if (noise2(x, z, 11, seed, 89) > 0.5) return 'gravel'
    if (noise2(x, z, 9, seed, 18) > 0.15) return 'snow'
  }
  if (biome === 'swamp' && noise2(x, z, 7, seed, 19) > 0.05) return 'mud'
  if (shore(x, z, seed) && noise2(x, z, 7, seed, 88) > 0.3) return 'gravel'
  return 'grass'
}

/** Land level with the lakes right beside one (never in the legacy clearing). */
function shore(x: number, z: number, seed: string): boolean {
  return Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) === SEA_LEVEL
    && SIDES.some(([dx, dz]) => terrainHeight(x + dx, z + dz, seed) < SEA_LEVEL)
}

/** A shallow swamp pool: one block of water where swamp ground lies level with the lakes. */
export function swampPool(x: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  return terrainHeight(x, z, seed) === SEA_LEVEL && biomeAt(x, z, seed) === 'swamp' && noise2(x, z, 6, seed, 20) > 0.1
}

export function caveAt(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  if (Math.hypot(x, z) <= LEGACY_RADIUS || y <= -5 || y >= terrainHeight(x, z, seed) - 2) return false
  return noise3(x, y * CAVE_STRETCH, z, CAVE_SCALE, seed, 7) > CAVE_OPEN && noise3(x, y, z, 6, seed, 8) > CAVE_ROOM
}

/** What fills an open cave cell: water low down in a lake region, lava on the lowest floor of a lava
 * region, else air. */
export function caveFill(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (y <= LAKE_LEVEL && noise2(x, z, 40, seed, 27) > 0.3) return 'water'
  if (y === LAVA_LEVEL && noise2(x, z, LAVA_SCALE, seed, LAVA_CHANNEL) > LAVA_REGION) return 'lava'
  return 'air'
}

/** Gravel in patches on cave floors: the rock right under an open cave cell of air. */
function gravelFloor(x: number, y: number, z: number, seed: string): boolean {
  return noise2(x, z, 8, seed, 90) > 0.1 && caveAt(x, y + 1, z, seed) && caveFill(x, y + 1, z, seed) === 'air'
}

/** The rock of a solid cell underground: ashstone in deep seams, blobs of granite, andesite or diorite
 * (one kind to a blob region), else stone. */
function stoneAt(x: number, y: number, z: number, seed: string): string {
  if (y <= ASH_DEPTH && noise3(x, y, z, 9, seed, 29) > 0.35) return 'ashstone'
  if (noise3(x, y, z, 8, seed, 80) > 0.38) {
    return VARIANTS[hash32(Math.floor(x / 24), Math.floor(y / 8), Math.floor(z / 24), seed, 81) % VARIANTS.length]
  }
  return 'stone'
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

/** The cave entrance of a 64x64 region, if it has one: its kind ('sinkhole', 'mouth', or '' for none)
 * and the span of air it carves in each of its columns (see backend/services/worldgen.py). */
export function regionOpenings(rx: number, rz: number, seed = DEFAULT_WORLD_SEED): Openings {
  const key = `${seed}:${rx},${rz}`
  let found = openingCache.get(key)
  if (found) return found
  found = findOpenings(rx, rz, seed)
  openingCache.set(key, found)
  if (openingCache.size > 4096) openingCache.delete(openingCache.keys().next().value!)
  return found
}

function findOpenings(rx: number, rz: number, seed: string): Openings {
  const x0 = rx * OPENING_REGION, z0 = rz * OPENING_REGION
  if (Math.hypot(x0 + 32, z0 + 32) <= LEGACY_RADIUS + OPENING_REGION) return ['', new Map()]
  const roll = hash32(rx, 0, rz, seed, 82)
  if (roll % 8 < 2) {
    const cx = x0 + 12 + (roll >>> 8) % 40, cz = z0 + 12 + (roll >>> 16) % 40
    const ground = terrainHeight(cx, cz, seed)
    const spans = ground > SEA_LEVEL ? sinkhole(cx, cz, ground, seed) : new Map<string, [number, number]>()
    return [spans.size ? 'sinkhole' : '', spans]
  }
  if (roll % 8 < 5) {
    for (let attempt = 0; attempt < MOUTH_TRIES; attempt++) {
      const spot = hash32(rx, attempt, rz, seed, 86)
      const cx = x0 + 12 + spot % 40, cz = z0 + 12 + (spot >>> 8) % 40
      const ground = terrainHeight(cx, cz, seed)
      const spans = ground > SEA_LEVEL ? mouth(cx, cz, ground, seed) : new Map<string, [number, number]>()
      if (spans.size) return ['mouth', spans]
    }
  }
  return ['', new Map()]
}

/** A round shaft five across from the surface down 9 to 13 blocks (never below y -3); none next to water. */
function sinkhole(cx: number, cz: number, ground: number, seed: string): Map<string, [number, number]> {
  const bottom = Math.max(-3, ground - 9 - hash32(cx, 1, cz, seed, 83) % 5)
  const spans = new Map<string, [number, number]>()
  for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) {
    if (dx * dx + dz * dz > 5) continue
    const top = terrainHeight(cx + dx, cz + dz, seed)
    if (top <= SEA_LEVEL) return new Map()
    spans.set(`${cx + dx},${cz + dz}`, [bottom, top])
  }
  return spans
}

/** A tunnel into a hillside from the foot of its steepest rise: 2 wide, up to 3 tall, sinking a block
 * every 2 for 12 blocks. */
function mouth(cx: number, cz: number, ground: number, seed: string): Map<string, [number, number]> {
  let best: [number, number, number] | null = null
  for (const [dx, dz] of SIDES) {
    const rise = terrainHeight(cx + 8 * dx, cz + 8 * dz, seed) - ground
    if (rise >= 1 && (best === null || rise > best[0])) best = [rise, dx, dz]
  }
  const spans = new Map<string, [number, number]>()
  if (best === null) return spans
  const [, dx, dz] = best
  for (let step = 0; step < MOUTH_LENGTH; step++) {
    const floor = ground + 1 - Math.floor(step / 2)
    for (const side of [0, 1]) {
      const x = cx + step * dx - side * dz, z = cz + step * dz + side * dx
      const height = terrainHeight(x, z, seed)
      const top = Math.min(floor + 2, height)
      if (top >= floor && height > SEA_LEVEL) spans.set(`${x},${z}`, [floor, top])
    }
  }
  return spans
}

/** The span of air (lowest y, highest y) a cave entrance carves in the column, or null. */
export function opening(x: number, z: number, seed = DEFAULT_WORLD_SEED): [number, number] | null {
  return regionOpenings(Math.floor(x / OPENING_REGION), Math.floor(z / OPENING_REGION), seed)[1].get(`${x},${z}`) ?? null
}

/** A cave entrance took the column's ground cell: it is open to the sky there. */
export function surfaceOpened(x: number, z: number, seed = DEFAULT_WORLD_SEED): boolean {
  const span = opening(x, z, seed)
  return span !== null && span[1] === terrainHeight(x, z, seed)
}

/** The boulder or outcrop of a chunk, if it has one: [x, z, kind, size, block] of its middle column. */
export function rocksInChunk(cx: number, cz: number, seed = DEFAULT_WORLD_SEED): Rock[] {
  const key = `${seed}:${cx},${cz}`
  let rocks = rockCache.get(key)
  if (rocks) return rocks
  rocks = findRocks(cx, cz, seed)
  rockCache.set(key, rocks)
  if (rockCache.size > 4096) rockCache.delete(rockCache.keys().next().value!)
  return rocks
}

function findRocks(cx: number, cz: number, seed: string): Rock[] {
  const x0 = cx * 16, z0 = cz * 16
  if (Math.hypot(x0 + 8, z0 + 8) <= LEGACY_RADIUS + 16) return []
  const roll = hash32(cx, 0, cz, seed, 84)
  const x = x0 + 3 + roll % 10, z = z0 + 3 + (roll >>> 8) % 10
  const ground = terrainHeight(x, z, seed)
  if (ground <= SEA_LEVEL || swampPool(x, z, seed) || surfaceOpened(x, z, seed)) return []
  const biome = biomeAt(x, z, seed), pick = (roll >>> 16) % 12
  if (ground >= OUTCROP_GROUND && pick < 4) return [[x, z, 'outcrop', 3, OUTCROPS[biome] ?? 'stone']]
  if (pick >= 9) return [[x, z, 'boulder', 1 + (roll >>> 24) % 2, BOULDERS[biome] ?? 'mossy_cobblestone']]
  return []
}

/** The block of the boulder or outcrop standing on a column and the y of its top, or null. */
export function rockColumn(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  for (const [rx, rz, kind, size, block] of rocksInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)) {
    const dx = x - rx, dz = z - rz
    let layers = 0
    if (kind === 'boulder') {
      for (let dy = 1; dy <= size; dy++) {
        if (dx * dx + dz * dz + (dy - 0.5) * (dy - 0.5) * 1.6 <= (size + 0.5) * (size + 0.5)) layers++
      }
    } else if (dx * dx + dz * dz <= size * size && ((dx === 0 && dz === 0) || hash32(x, 3, z, seed, 85) % 3 !== 0)) {
      layers = 1 + hash32(x, 2, z, seed, 85) % 3
    }
    const ground = terrainHeight(x, z, seed)
    if (layers && ground >= SEA_LEVEL && !swampPool(x, z, seed) && !surfaceOpened(x, z, seed) && treeBase(x, z, seed) === null) {
      return [block, ground + layers]
    }
  }
  return null
}

/** Terrain, water, caves and ores, before trees and plants are added. `columnSpan`, when given (even
 * as null), is the column's cave-entrance span (see `opening`): a caller filling a whole column can
 * look it up once and pass it down, instead of `opening` refetching it for every y. */
export function terrainBlock(
  x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED, columnSpan?: [number, number] | null,
): string {
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
  if (y > height) {
    if (y > SEA_LEVEL) return 'air'
    return y === SEA_LEVEL && biomeAt(x, z, seed) === 'taiga' ? 'ice' : 'water'
  }
  const span = columnSpan !== undefined ? columnSpan : opening(x, z, seed)
  if (span !== null && y >= span[0] && y <= span[1]) return 'air'
  if (y === height) return swampPool(x, z, seed) ? 'water' : surfaceMaterial(x, z, seed)
  if (y >= height - 2) {
    const biome = biomeAt(x, z, seed)
    return biome === 'desert' ? 'sand' : biome === 'swamp' && y === height - 1 ? 'mud' : 'dirt'
  }
  if (caveAt(x, y, z, seed)) return caveFill(x, y, z, seed)
  const ore = hash32(x, y, z, seed, 9)
  if (ore % 97 === 0) return 'iron_ore'
  if (ore % 61 === 0) return 'coal_ore'
  if (ore % 151 === 0) return 'copper_ore'
  if (ore % GOLD_RARITY === 0 && y <= GOLD_DEPTH) return 'gold_ore'
  if (ore % DIAMOND_RARITY === 0 && y <= DIAMOND_DEPTH) return 'diamond_ore'
  if (gravelFloor(x, y, z, seed)) return 'gravel'
  return stoneAt(x, y, z, seed)
}

/** Columns where the viewer has always allowed trees and flowers. `rim` is a trunk within RIM_MARGIN
 * of the legacy clearing's edge: it skips the swamp-pool exclusion L3 added, so it grows exactly where
 * it would have before L3 (its canopy can reach inside the clearing). */
function decorationColumn(x: number, z: number, seed: string, rim = false): boolean {
  const lx = mod(x, 16), lz = mod(z, 16)
  if (lx < 3 || lx > 12 || lz < 3 || lz > 12 || Math.hypot(x, z) < 17) return false
  if (terrainHeight(x, z, seed) < SEA_LEVEL) return false
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert' || biome === 'alpine' || surfaceOpened(x, z, seed)) return false
  if (swampPool(x, z, seed) && !rim) return false
  const mx = mod(x, 13), mz = mod(z, 13)
  return !(Math.min(mx, 13 - mx) < 5 && Math.min(mz, 13 - mz) < 5)
}

/** Whether (x, z) was forest under the pre-L3 biomeAt (moisture above 0.08, neither desert nor alpine):
 * desert and alpine are unchanged by L3, so this only needs the old moisture check. */
function legacyForest(x: number, z: number, seed: string): boolean {
  const biome = biomeAt(x, z, seed)
  return biome !== 'desert' && biome !== 'alpine' && noise2(x, z, 160, seed, 5) > 0.08
}

/** Ground height under a tree trunk at (x, z), or null when no tree grows there. */
export function treeBase(x: number, z: number, seed = DEFAULT_WORLD_SEED): number | null {
  const rim = Math.hypot(x, z) <= LEGACY_RADIUS + RIM_MARGIN
  if (!decorationColumn(x, z, seed, rim)) return null
  let grows: boolean
  if (Math.hypot(x, z) <= LEGACY_RADIUS) grows = legacyHash(x, z) % 257 === 0
  else if (rim) grows = hash32(x, 0, z, seed, 12) % (legacyForest(x, z, seed) ? 78 : 300) === 0
  else grows = hash32(x, 0, z, seed, 12) % (TREE_RARITY[biomeAt(x, z, seed)] ?? MEADOW_TREES) === 0
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

/** The wood of the tree rooted at (x, z): oak within RIM_MARGIN of the legacy clearing (its canopy can
 * reach inside), spruce in the taiga, birch in a birch forest (one in five an oak), now and then a
 * birch in a forest, else oak. */
export function treeKind(x: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (Math.hypot(x, z) <= LEGACY_RADIUS + RIM_MARGIN) return 'oak'
  const biome = biomeAt(x, z, seed)
  const roll = hash32(x, 0, z, seed, 21) % 10
  if (biome === 'taiga') return 'spruce'
  if (biome === 'birch_forest') return roll < 2 ? 'oak' : 'birch'
  return biome === 'forest' && roll === 0 ? 'birch' : 'oak'
}

/** The canopy of a tree of `kind` relative to its trunk's ground cell (the trunk wins where they meet). */
function leafOf(kind: string, dx: number, dy: number, dz: number): boolean {
  const ax = Math.abs(dx), az = Math.abs(dz)
  if (kind === 'birch') {
    if (dy === 4 || dy === 5) return ax + az <= 2
    return (dy === 6 && ax + az <= 1) || (dy === 7 && ax + az === 0)
  }
  if (kind === 'spruce') {
    if (dy === 3) return ax <= 2 && az <= 2 && ax + az <= 3
    if (dy === 4 || dy === 6) return ax + az <= 1
    if (dy === 5) return ax + az <= 2
    return dy === 7 && ax + az === 0
  }
  return isLeaf(dx, dy, dz)
}

/** A trunk (of any tree in the chunk) first, then the leaves of the first tree whose canopy has the cell. */
function treeBlock(x: number, y: number, z: number, seed: string): string | null {
  const trees = treesInChunk(Math.floor(x / 16), Math.floor(z / 16), seed)
  for (const [tx, tz, base] of trees) {
    if (x === tx && z === tz && y > base && y <= base + 4) return TREE_LOGS[treeKind(tx, tz, seed)]
  }
  for (const [tx, tz, base] of trees) {
    const kind = treeKind(tx, tz, seed)
    if (leafOf(kind, x - tx, y - base, z - tz)) return TREE_LEAVES[kind]
  }
  return null
}

/** The highest leaf over a column and whose leaves they are (the first tree's on a tie), or null. */
export function canopyTop(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  let top: [string, number] | null = null
  for (const [tx, tz, base] of treesInChunk(Math.floor(x / CHUNK_SIZE), Math.floor(z / CHUNK_SIZE), seed)) {
    const kind = treeKind(tx, tz, seed)
    for (let dy = CANOPY_TOP; dy >= 3; dy--) {
      if (!leafOf(kind, x - tx, dy, z - tz)) continue
      if (top === null || base + dy > top[1]) top = [TREE_LEAVES[kind], base + dy]
      break
    }
  }
  return top
}

/** A ripe berry bush (meadows and forest edges) or a mushroom (forest floor) on generated land. */
export function wildFood(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return null
  const biome = biomeAt(x, z, seed)
  const wooded = biome === 'forest' || biome === 'birch_forest'
  if (biome === 'meadow' || (wooded && noise2(x, z, 160, seed, 5) < FOREST_EDGE)) {
    if (hash32(x, 0, z, seed, 15) % BUSH_RARITY === 0) return 'berry_bush_ripe'
  }
  if (wooded) {
    const roll = hash32(x, 0, z, seed, 16)
    if (roll % MUSHROOM_RARITY === 0) return Math.floor(roll / MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
  }
  return null
}

/** A mushroom on a cave floor: an open cave cell with solid rock (or bedrock) under it, never where
 * an entrance carved the cell below to air. */
export function cavePlant(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  const roll = hash32(x, y, z, seed, 17)
  if (roll % CAVE_MUSHROOM_RARITY !== 0) return null
  if (!caveAt(x, y, z, seed) || caveAt(x, y - 1, z, seed) || caveFill(x, y, z, seed) !== 'air') return null
  const span = opening(x, z, seed)
  if (span !== null && y - 1 >= span[0] && y - 1 <= span[1]) return null
  return Math.floor(roll / CAVE_MUSHROOM_RARITY) % 3 === 0 ? 'red_mushroom' : 'brown_mushroom'
}

/** A cactus in the desert, or sugar cane on a shore right beside a lake, with how many blocks high it
 * stands (1 to 3). Null in the legacy clearing. */
function tallPlant(x: number, z: number, seed: string): [string, number] | null {
  if (Math.hypot(x, z) <= LEGACY_RADIUS) return null
  const biome = biomeAt(x, z, seed)
  if (biome === 'desert') {
    const roll = hash32(x, 0, z, seed, 25)
    return roll % CACTUS_RARITY === 0 ? ['cactus', 1 + Math.floor(roll / CACTUS_RARITY) % 3] : null
  }
  if (!['meadow', 'forest', 'birch_forest', 'swamp'].includes(biome) || !shore(x, z, seed) || swampPool(x, z, seed)) return null
  const rarity = biome === 'swamp' ? Math.floor(CANE_RARITY / 3) : CANE_RARITY
  const roll = hash32(x, 0, z, seed, 26)
  return roll % rarity === 0 ? ['sugar_cane', 1 + Math.floor(roll / rarity) % 3] : null
}

/** What grows on top of the terrain at (x, z) and how many blocks high: a flower, wild food, tall grass,
 * a fern, a dead bush, a pumpkin or a melon stand one high, a cactus or sugar cane 1 to 3. */
export function plantStack(x: number, z: number, seed = DEFAULT_WORLD_SEED): [string, number] | null {
  if (Math.hypot(x, z) <= HOME_RADIUS || surfaceOpened(x, z, seed) || rockColumn(x, z, seed)) return null
  const surface = surfaceMaterial(x, z, seed)
  if (decorationColumn(x, z, seed)) {
    if (treeBase(x, z, seed) !== null) return null
    if (hash32(x, 0, z, seed, 13) % 97 === 0 && (surface === 'grass' || surface === 'moss')) {
      return [legacyHash(x + 1, z) % 2 ? 'flower_orange' : 'flower_yellow', 1]
    }
  }
  if (Math.hypot(x, z) > LEGACY_RADIUS && terrainHeight(x, z, seed) < SEA_LEVEL) return null
  const tall = tallPlant(x, z, seed)
  if (tall) return tall
  const biome = biomeAt(x, z, seed)
  if (surface === 'sand') {
    return biome === 'desert' && hash32(x, 0, z, seed, 22) % DEAD_BUSH_RARITY === 0 ? ['dead_bush', 1] : null
  }
  if ((surface !== 'grass' && surface !== 'moss' && surface !== 'mud') || swampPool(x, z, seed)) return null
  const food = wildFood(x, z, seed)
  if (food) return [food, 1]
  if (biome === 'taiga' && hash32(x, 0, z, seed, 23) % FERN_RARITY === 0) return ['fern', 1]
  if (FRUIT_BIOMES.has(biome) && Math.hypot(x, z) > LEGACY_RADIUS) {
    const roll = hash32(x, 0, z, seed, 24)
    if (roll % FRUIT_RARITY === 0) return [Math.floor(roll / FRUIT_RARITY) % 2 === 0 ? 'pumpkin' : 'melon', 1]
  }
  return hash32(x, 0, z, seed, 14) % (biome === 'swamp' ? 11 : 19) === 0 ? ['tall_grass', 1] : null
}

/** The plant (or fruit) growing on top of the terrain at (x, z): the base of plantStack. */
export function plantAt(x: number, z: number, seed = DEFAULT_WORLD_SEED): string | null {
  return plantStack(x, z, seed)?.[0] ?? null
}

/** Blocks that grow or stand on the terrain, or on a cave floor. Precedence: home, trunk, leaves, rock, plant. */
function decorationAt(x: number, y: number, z: number, seed: string): string | null {
  const home = HOME_BLOCKS.get(`${x},${y},${z}`)
  if (home) return home
  const tree = treeBlock(x, y, z, seed)
  if (tree) return tree
  const height = terrainHeight(x, z, seed)
  const rock = y > height ? rockColumn(x, z, seed) : null
  if (rock) return y <= rock[1] ? rock[0] : null
  if (y > height && y <= height + 3) {
    const stack = plantStack(x, z, seed)
    return stack && y <= height + stack[1] ? stack[0] : null
  }
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
    const span = opening(x, z, seed)
    for (let y = WORLD_MIN_Y; y <= top; y++) {
      // A cave floor plant counts as terrain here: nothing else is ever stamped in a cave.
      const name = terrainBlock(x, y, z, seed, span)
      const found = name !== 'air' ? name : y < height - 2 ? cavePlant(x, y, z, seed) : null
      if (found) data[columnIndex(lx, y, lz)] = blockId(found)
    }
  }
  const terrain = data.slice()
  // Later stamps win, so stamp in rising precedence: plants, rocks, leaves, trunks, home.
  const stamp = (x: number, y: number, z: number, name: string) => {
    const lx = x - x0, lz = z - z0
    if (lx < 0 || lx >= CHUNK_SIZE || lz < 0 || lz >= CHUNK_SIZE || y < WORLD_MIN_Y || y > WORLD_MAX_Y) return
    const index = columnIndex(lx, y, lz)
    if (terrain[index] === AIR) data[index] = blockId(name)
  }
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const stack = plantStack(x0 + lx, z0 + lz, seed)
    if (!stack) continue
    const ground = terrainHeight(x0 + lx, z0 + lz, seed)
    for (let dy = 1; dy <= stack[1]; dy++) stamp(x0 + lx, ground + dy, z0 + lz, stack[0])
  }
  for (let lz = 0; lz < CHUNK_SIZE; lz++) for (let lx = 0; lx < CHUNK_SIZE; lx++) {
    const rock = rockColumn(x0 + lx, z0 + lz, seed)
    if (!rock) continue
    for (let y = terrainHeight(x0 + lx, z0 + lz, seed) + 1; y <= rock[1]; y++) stamp(x0 + lx, y, z0 + lz, rock[0])
  }
  const trees = treesInChunk(cx, cz, seed)
  // Where canopies meet, the first tree's leaves win (as in treeBlock): stamp them last.
  for (const [tx, tz, base] of [...trees].reverse()) {
    const kind = treeKind(tx, tz, seed)
    for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let dy = 3; dy <= CANOPY_TOP; dy++) {
      if (leafOf(kind, dx, dy, dz)) stamp(tx + dx, base + dy, tz + dz, TREE_LEAVES[kind])
    }
  }
  for (const [tx, tz, base] of trees) {
    const log = TREE_LOGS[treeKind(tx, tz, seed)]
    for (let y = base + 1; y <= base + 4; y++) stamp(tx, y, tz, log)
  }
  for (const [key, name] of HOME_BLOCKS) {
    const [x, y, z] = key.split(',').map(Number)
    stamp(x, y, z, name)
  }
  return data
}

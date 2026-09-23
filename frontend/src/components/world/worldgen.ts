// Keep terrain math in sync with backend/services/worldgen.py. The seed is
// persisted as a decimal string so JavaScript never rounds its 64-bit value.
export const DEFAULT_WORLD_SEED = '13897963875510148821'
export const LEGACY_RADIUS = 192
const TRANSITION_WIDTH = 48
export const SEA_LEVEL = 2
const MASK = 0xffffffff
const seedCache = new Map<string, [number, number]>()
const heightCache = new Map<string, number>()

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

export function baseMaterial(x: number, y: number, z: number, seed = DEFAULT_WORLD_SEED): string {
  if (y <= -5) return 'bedrock'
  const height = terrainHeight(x, z, seed)
  if (Math.hypot(x, z) <= LEGACY_RADIUS) {
    if (y >= -4 && y < -1) {
      const oreSeed = Math.abs(x * 31 + z * 17 + y * 101)
      return oreSeed % 37 === 0 ? 'iron_ore' : oreSeed % 19 === 0 ? 'coal_ore' : 'stone'
    }
    if (y === -1) return 'dirt'
    if (y === 0 && ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1) return 'water'
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

import { blockDef, TILES, type Rgb, type TileRecipe } from './blocks'

export const TILE_SIZE = 8
export const ATLAS_COLUMNS = 16
export const ATLAS_SIZE = TILE_SIZE * ATLAS_COLUMNS
// Face order shared with the mesher.
export const FACE_EAST = 0
export const FACE_WEST = 1
export const FACE_UP = 2
export const FACE_DOWN = 3
export const FACE_SOUTH = 4
export const FACE_NORTH = 5

export interface Atlas {
  size: number
  /** RGBA, bottom row first, as THREE.DataTexture reads it with flipY off. */
  data: Uint8Array
  tileIndex: Map<string, number>
  /** faceTiles[id * 6 + face] is the tile drawn on that face of that block. */
  faceTiles: Uint16Array
  waterTile: number
  /** The water tile as first painted, in data row order. */
  waterPixels: Uint8Array
}

type Pixel = [number, number, number, number]
type Painter = (recipe: TileRecipe, random: () => number) => Pixel[]

const N = TILE_SIZE
const AMP = 0.09
const CLEAR: Pixel = [0, 0, 0, 0]

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function hashString(text: string): number {
  let hash = 2166136261
  for (let i = 0; i < text.length; i++) hash = Math.imul(hash ^ text.charCodeAt(i), 16777619)
  return hash >>> 0
}

function tone(color: Rgb, k: number, alpha = 255): Pixel {
  return [color[0] * k, color[1] * k, color[2] * k, alpha]
}

function grid(paint: (i: number, j: number) => Pixel): Pixel[] {
  const pixels: Pixel[] = []
  for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) pixels.push(paint(i, j))
  return pixels
}

const jitter = (random: () => number, amount = AMP) => 1 + (random() - 0.5) * amount
const edge = (i: number, j: number) => i === 0 || j === 0 || i === N - 1 || j === N - 1

/** Tile painters. Row j = 0 is the top of the tile. */
export const PATTERNS: Record<string, Painter> = {
  missing: () => grid((i, j) => ((i >> 1) + (j >> 1)) % 2 ? [255, 0, 255, 255] : [24, 24, 24, 255]),
  noise: ({ color }, random) => grid(() => tone(color, jitter(random))),
  specks: ({ color }, random) => grid(() => tone(color, (random() < 0.14 ? 0.84 : 1) * jitter(random))),
  grass_top: ({ color }, random) => grid(() => tone(color, (random() < 0.14 ? 0.88 : 1) * jitter(random))),
  grass_side: ({ color, accent }, random) => {
    const lips = Array.from({ length: N }, () => 2 + Math.floor(random() * 2))
    return grid((i, j) => tone(j < lips[i] ? accent ?? color : color, jitter(random)))
  },
  log_side: ({ color }, random) => grid((i) => tone(color, (i % 2 ? 0.86 : 1) * jitter(random))),
  log_top: ({ color, accent }, random) => grid((i, j) => {
    const ring = Math.max(Math.abs(i - 3.5), Math.abs(j - 3.5))
    if (ring >= 3) return tone(accent ?? color, jitter(random))
    return tone(color, (Math.round(ring) % 2 ? 0.88 : 1) * jitter(random))
  }),
  planks: ({ color }, random) => grid((i, j) => {
    const board = Math.floor(j / 4)
    const seam = j % 4 === 3 || i === (board * 5 + 3) % N
    return tone(color, (seam ? 0.76 : 1) * jitter(random))
  }),
  cobble: ({ color }, random) => {
    const points = Array.from({ length: 6 }, () => [random() * N, random() * N, 0.82 + random() * 0.28])
    return grid((i, j) => {
      const distances = points.map(([px, py, k]) => {
        const dx = Math.min(Math.abs(i - px), N - Math.abs(i - px))
        const dy = Math.min(Math.abs(j - py), N - Math.abs(j - py))
        return [Math.hypot(dx, dy), k]
      }).sort((a, b) => a[0] - b[0])
      return distances[1][0] - distances[0][0] < 0.8 ? tone(color, 0.62) : tone(color, distances[0][1] * jitter(random))
    })
  },
  ore: ({ color, accent }, random) => {
    const spots = Array.from({ length: 3 }, () => [1 + Math.floor(random() * 6), 1 + Math.floor(random() * 6)])
    return grid((i, j) => spots.some(([x, y]) => Math.abs(i - x) + Math.abs(j - y) <= 1)
      ? tone(accent ?? color, jitter(random))
      : tone(color, (random() < 0.14 ? 0.84 : 1) * jitter(random)))
  },
  leaves: ({ color }, random) => grid(() => tone(color, (random() < 0.2 ? 0.7 : 1) * jitter(random, 0.14))),
  glass: ({ color }, random) => grid((i, j) => {
    if (edge(i, j)) return tone(color, 0.9, 220)
    if (i - j === 2 && i < 6) return tone(color, 1.15, 150)
    return tone(color, jitter(random, 0.04), 70)
  }),
  water: ({ color }, random) => grid(() => tone(color, (random() < 0.08 ? 1.15 : 1) * jitter(random, 0.06), 190)),
  glow: ({ color }, random) => grid((i, j) =>
    tone(color, (1.12 - 0.04 * Math.max(Math.abs(i - 3.5), Math.abs(j - 3.5))) * jitter(random, 0.06))),
  bricks: ({ color, accent }, random) => grid((i, j) => {
    const mortar = j % 4 === 3 || i === (Math.floor(j / 4) % 2 ? 1 : 5)
    return mortar ? tone(accent ?? color, jitter(random, 0.04)) : tone(color, jitter(random))
  }),
  rows: ({ color }, random) => grid((_i, j) => tone(color, (j % 2 ? 0.92 : 1) * jitter(random))),
  panel: ({ color }, random) => grid((i, j) => tone(color, (edge(i, j) ? 0.82 : 1) * jitter(random, 0.045))),
  table_top: ({ color, accent }, random) => grid((i, j) => {
    if (edge(i, j)) return tone(accent ?? color, jitter(random))
    return tone(color, (i === N / 2 || j === N / 2 ? 0.72 : 1) * jitter(random))
  }),
  table_side: ({ color, accent }, random) => grid((i, j) => {
    if (j < 2) return tone(accent ?? color, jitter(random))
    const tool = j >= 3 && j <= 6 && i >= 2 && i <= 5
    return tone(color, (i === 0 || i === N - 1 || tool ? 0.7 : 1) * jitter(random))
  }),
  furnace_side: ({ color, accent }, random) => grid((i, j) => {
    if (i >= 2 && i <= 5 && j >= 4 && j <= 6) return tone(accent ?? color, jitter(random, 0.12))
    const frame = i >= 1 && i <= 6 && j >= 3 && j <= 7
    return tone(color, (frame ? 0.6 : random() < 0.14 ? 0.84 : 1) * jitter(random))
  }),
  sprite_grass: ({ color }, random) => {
    const heights = [0, 4 + Math.floor(random() * 3), 0, 3 + Math.floor(random() * 4),
      5 + Math.floor(random() * 3), 0, 3 + Math.floor(random() * 3), 0]
    return grid((i, j) => j >= N - heights[i] ? tone(color, jitter(random, 0.16)) : CLEAR)
  },
  sprite_flower: ({ color, accent }, random) => grid((i, j) => {
    if (i >= 2 && i <= 4 && j >= 1 && j <= 3) return tone(color, (i === 3 && j === 2 ? 0.8 : 1) * jitter(random))
    if ((i === 3 && j >= 4) || (i === 2 && j === 5) || (i === 4 && j === 6)) return tone(accent ?? color, jitter(random))
    return CLEAR
  }),
}

function tileOrigin(tile: number): [number, number] {
  return [(tile % ATLAS_COLUMNS) * TILE_SIZE, Math.floor(tile / ATLAS_COLUMNS) * TILE_SIZE]
}

function writeTile(data: Uint8Array, tile: number, pixels: Pixel[]): void {
  const [tx, ty] = tileOrigin(tile)
  pixels.forEach((pixel, index) => {
    const i = index % N, j = Math.floor(index / N)
    const offset = ((ty + N - 1 - j) * ATLAS_SIZE + tx + i) * 4
    for (let c = 0; c < 4; c++) data[offset + c] = Math.max(0, Math.min(255, Math.round(pixel[c])))
  })
}

function readTile(data: Uint8Array, tile: number): Uint8Array {
  const [tx, ty] = tileOrigin(tile)
  const pixels = new Uint8Array(N * N * 4)
  for (let row = 0; row < N; row++) {
    const start = ((ty + row) * ATLAS_SIZE + tx) * 4
    pixels.set(data.subarray(start, start + N * 4), row * N * 4)
  }
  return pixels
}

export function buildAtlas(): Atlas {
  const data = new Uint8Array(ATLAS_SIZE * ATLAS_SIZE * 4)
  const tileIndex = new Map<string, number>()
  const names = ['missing', ...Object.keys(TILES).filter((name) => name !== 'missing')]
  if (names.length > ATLAS_COLUMNS * ATLAS_COLUMNS) throw new Error('Texture atlas is full')
  names.forEach((name, index) => {
    tileIndex.set(name, index)
    const recipe = TILES[name] ?? { pattern: 'missing', color: [255, 0, 255] }
    const painter = PATTERNS[recipe.pattern] ?? PATTERNS.missing
    writeTile(data, index, painter(recipe, mulberry32(hashString(name))))
  })
  const faceTiles = new Uint16Array(256 * 6)
  for (let id = 0; id < 256; id++) {
    const { textures } = blockDef(id)
    const perFace = [textures.side, textures.side, textures.top, textures.bottom, textures.side, textures.side]
    perFace.forEach((tile, face) => { faceTiles[id * 6 + face] = tileIndex.get(tile) ?? 0 })
  }
  const waterTile = tileIndex.get('water') ?? 0
  return { size: ATLAS_SIZE, data, tileIndex, faceTiles, waterTile, waterPixels: readTile(data, waterTile) }
}

/** UV rectangle of a tile, inset a quarter texel so neighbors never bleed in. */
export function tileUv(tile: number): [number, number, number, number] {
  const [tx, ty] = tileOrigin(tile)
  const inset = 0.25 / ATLAS_SIZE
  const span = TILE_SIZE / ATLAS_SIZE
  const u0 = tx / ATLAS_SIZE, v0 = ty / ATLAS_SIZE
  return [u0 + inset, v0 + inset, u0 + span - inset, v0 + span - inset]
}

/** Scroll the water tile by whole texel rows. The caller re-uploads the texture. */
export function animateWater(atlas: Atlas, step: number): void {
  const [tx, ty] = tileOrigin(atlas.waterTile)
  const shift = ((step % N) + N) % N
  for (let row = 0; row < N; row++) {
    const source = (row + shift) % N
    atlas.data.set(atlas.waterPixels.subarray(source * N * 4, (source + 1) * N * 4), ((ty + row) * atlas.size + tx) * 4)
  }
}

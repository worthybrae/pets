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
  // L3, the bigger world: stone variants, bark, ice, desert and swamp plants, fruit, fences and ladders.
  speckled: ({ color, accent }, random) => grid(() => {
    const roll = random()
    return tone(roll < 0.24 ? accent ?? color : color, (roll > 0.9 ? 0.9 : 1) * jitter(random))
  }),
  layers: ({ color, accent }, random) => {
    const bands = Array.from({ length: N }, () => random() < 0.35)
    return grid((_i, j) => tone(bands[j] ? accent ?? color : color, (random() < 0.12 ? 0.86 : 1) * jitter(random)))
  },
  birch_bark: ({ color, accent }, random) => {
    const marks = Array.from({ length: 6 }, () => [Math.floor(random() * N), Math.floor(random() * (N - 2))])
    return grid((i, j) => marks.some(([row, from]) => j === row && i >= from && i < from + 2)
      ? tone(accent ?? color, jitter(random))
      : tone(color, (i % 4 === 0 ? 0.94 : 1) * jitter(random, 0.05)))
  },
  ice: ({ color }, random) => grid((i, j) => {
    const streak = (i + j) % 5 === 0 && i > 0 && j > 0
    return tone(color, (streak ? 1.12 : 1) * jitter(random, 0.05), streak ? 215 : 175)
  }),
  cactus: ({ color, accent }, random) => grid((i) => {
    if (i === 0 || i === N - 1) return CLEAR
    return tone(i === 2 || i === 5 ? accent ?? color : color, (random() < 0.1 ? 1.15 : 1) * jitter(random))
  }),
  cactus_top: ({ color, accent }, random) => grid((i, j) => {
    if (edge(i, j)) return CLEAR
    const ring = i === 1 || j === 1 || i === N - 2 || j === N - 2
    return tone(ring ? accent ?? color : color, jitter(random))
  }),
  sprite_cane: ({ color, accent, size = 4 }, random) => {
    const stalks = [1, 4, 6]
    const tops = stalks.map(() => Math.max(0, N - size * 2 - Math.floor(random() * 2)))
    return grid((i, j) => {
      const index = stalks.indexOf(i)
      if (index < 0 || j < tops[index]) return CLEAR
      return tone((j + index) % 3 === 0 ? accent ?? color : color, jitter(random, 0.1))
    })
  },
  ribs: ({ color, accent }, random) => grid((i) =>
    tone(i % 3 === 1 ? accent ?? color : color, (random() < 0.1 ? 0.9 : 1) * jitter(random))),
  stem_top: ({ color, accent }, random) => grid((i, j) => {
    if ((i === 3 || i === 4) && (j === 3 || j === 4)) return tone(accent ?? color, jitter(random))
    return tone(color, (edge(i, j) ? 0.85 : 1) * jitter(random))
  }),
  sprite_fern: ({ color, size = 4 }, random) => grid((i, j) => {
    const rise = N - 1 - j
    if (rise >= size * 2) return CLEAR
    const spread = Math.min(3, Math.floor(rise / 2) + 1)
    if (Math.abs(i - 3.5) > spread || (i + rise) % 2 !== 0) return CLEAR
    return tone(color, (i === 3 || i === 4 ? 0.88 : 1) * jitter(random, 0.14))
  }),
  sprite_twigs: ({ color, size = 4 }, random) => grid((i, j) => {
    const rise = N - 1 - j
    if (rise >= size * 2) return CLEAR
    const stem = rise <= 1 && (i === 3 || i === 4)
    const twig = rise >= 1 && (i === 3 - rise || i === 4 + rise)
    return stem || twig ? tone(color, jitter(random, 0.12)) : CLEAR
  }),
  mossy_cobble: (recipe, random) => {
    const patches = Array.from({ length: 2 }, () => [random() * N, random() * N])
    return PATTERNS.cobble(recipe, random).map((pixel, index) => {
      const i = index % N, j = Math.floor(index / N)
      const moss = patches.some(([x, y]) => Math.hypot(i - x, j - y) < 2.3)
      return moss && recipe.accent ? tone(recipe.accent, jitter(random, 0.14)) : pixel
    })
  },
  ladder: ({ color }, random) => grid((i, j) => {
    const rail = i === 1 || i === N - 2
    const rung = j % 3 === 1 && i > 1 && i < N - 2
    return rail || rung ? tone(color, (rung ? 1.08 : 1) * jitter(random)) : CLEAR
  }),
  fence: ({ color }, random) => grid((i, j) => {
    const post = i === 3 || i === 4
    return post || j === 2 || j === 5 ? tone(color, (post ? 0.9 : 1) * jitter(random)) : CLEAR
  }),
  sprite_sprout: ({ color, accent, size = 2 }, random) => grid((i, j) => {
    const rise = N - 1 - j
    const middle = i === 3 || i === 4
    if (rise === size * 2 && middle) return tone(accent ?? color, jitter(random, 0.05))
    const stem = rise < size * 2 && middle
    const leaf = (rise === size && (i === 2 || i === 5)) || (rise === size + 1 && (i === 1 || i === 6))
    return stem || leaf ? tone(color, jitter(random, 0.12)) : CLEAR
  }),
  // Making (T1): books on shelves, rugs, a kiln's glowing mouth, stairs, windows, a trapdoor, iron bars,
  // a flower pot, a sign, a barrel, a composter and a candle.
  books: ({ color, accent }, random) => {
    const spines: Rgb[] = [accent ?? color, [92, 116, 150], [110, 146, 96], [206, 172, 92]]
    const book = Array.from({ length: N }, () => spines[Math.floor(random() * spines.length)])
    return grid((i, j) => {
      if (j === 0 || j === N - 1 || j === 4 || i === 0 || i === N - 1) return tone(color, 0.82 * jitter(random))
      return tone(book[(i + (j > 4 ? 3 : 0)) % N], (j === 1 || j === 5 ? 1.08 : 1) * jitter(random, 0.06))
    })
  },
  rug: ({ color, accent }, random) => grid((i, j) =>
    edge(i, j) ? tone(accent ?? color, jitter(random)) : tone(color, ((i + j) % 4 === 0 ? 0.9 : 1) * jitter(random))),
  kiln: ({ color, accent }, random) => {
    const bricks = PATTERNS.bricks({ pattern: 'bricks', color, accent: [214, 200, 184] }, random)
    return bricks.map((pixel, index) => {
      const i = index % N, j = Math.floor(index / N)
      return i >= 2 && i <= 5 && j >= 5 && j <= 6 ? tone(accent ?? color, jitter(random, 0.1)) : pixel
    })
  },
  stair_side: (recipe, random) => PATTERNS.planks(recipe, random).map((pixel, index) =>
    index % N < N / 2 && Math.floor(index / N) < N / 2 ? CLEAR : pixel),
  pane: ({ color }, random) => grid((i, j) => {
    if (edge(i, j)) return tone(color, 0.78 * jitter(random, 0.05))
    if (i === 3 || j === 3) return tone(color, 0.9 * jitter(random, 0.05))
    return i - j === 1 && i < 3 ? tone(color, 1.2, 220) : CLEAR
  }),
  trapdoor: ({ color }, random) => grid((i, j) => {
    if ((i === 2 || i === 5) && (j === 2 || j === 5)) return CLEAR
    return tone(color, (edge(i, j) ? 0.8 : j === 3 || j === 4 ? 0.92 : 1) * jitter(random))
  }),
  bars: ({ color }, random) => grid((i, j) => {
    const rail = j === 0 || j === N - 1
    return i % 3 === 1 || rail ? tone(color, (rail ? 0.85 : 1) * jitter(random, 0.05)) : CLEAR
  }),
  sprite_pot: ({ color, accent }, random) => grid((i, j) => {
    if (j === 5) return i >= 1 && i <= 6 ? tone(accent ?? color, 1.1 * jitter(random)) : CLEAR
    if (j > 5) return i >= 2 && i <= 5 ? tone(accent ?? color, (i === 5 ? 0.86 : 1) * jitter(random)) : CLEAR
    const stem = j >= 3 && (i === 3 || i === 4)
    const leaf = (j === 2 && i >= 2 && i <= 5) || (j === 1 && (i === 2 || i === 5))
    return stem || leaf ? tone(color, jitter(random, 0.12)) : CLEAR
  }),
  sprite_sign: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 1 && j <= 4) {
      const words = (j === 2 || j === 3) && i >= 1 && i <= 6 && (i + j) % 3 !== 0
      return tone(words ? accent ?? color : color, (edge(i, j) ? 0.88 : 1) * jitter(random))
    }
    return j >= 5 && (i === 3 || i === 4) ? tone(accent ?? color, jitter(random)) : CLEAR
  }),
  staves: ({ color, accent }, random) => grid((i, j) =>
    j === 1 || j === N - 2 ? tone(accent ?? color, jitter(random, 0.05)) : tone(color, (i % 2 ? 0.88 : 1) * jitter(random))),
  slats: ({ color }, random) => grid((i, j) => {
    const post = i === 0 || i === N - 1
    return post || j % 3 !== 2 ? tone(color, (post ? 0.84 : 1) * jitter(random)) : CLEAR
  }),
  sprite_candle: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 3) return i >= 3 && i <= 4 ? tone(color, (i === 4 ? 0.88 : 1) * jitter(random, 0.05)) : CLEAR
    if (j === 2) return i === 3 ? tone([60, 52, 44], 1) : CLEAR
    return (i === 3 || (j === 1 && i === 4)) ? tone(accent ?? color, 1.1 * jitter(random, 0.05)) : CLEAR
  }),
  // Making (T2): copper wire, levers, buttons, pressure plates, the daylight sensor, the gates (their dots:
  // two for a repeater, one for an inverter, three for a joiner), lamps and the bell. A lit block is the
  // same painter in brighter colours.
  wire: ({ color }, random) => grid((i, j) => {
    const line = i === 3 || i === 4 || j === 3 || j === 4
    return line ? tone(color, (i === 3 || j === 3 ? 1.08 : 1) * jitter(random, 0.06)) : CLEAR
  }),
  sprite_lever: ({ color, accent, size = 1 }, random) => grid((i, j) => {
    if (j >= 6) return i >= 2 && i <= 5 ? tone(accent ?? color, (j === 7 ? 0.85 : 1) * jitter(random)) : CLEAR
    const lean = size === 2 ? 1 : -1
    const at = 3.5 + lean * (5 - j) * 0.5
    if (Math.abs(i - at) > 0.6 || j < 1) return CLEAR
    return tone(color, (j <= 1 ? 1.25 : 1) * jitter(random))
  }),
  sprite_button: ({ color, size = 2 }, random) => grid((i, j) => {
    const top = N - 1 - size
    return i >= 2 && i <= 5 && j >= top ? tone(color, (j === top ? 1.1 : 0.92) * jitter(random)) : CLEAR
  }),
  plate: ({ color }, random) => grid((i, j) => {
    if (edge(i, j)) return CLEAR
    return tone(color, (i === 1 || j === 1 || i === N - 2 || j === N - 2 ? 0.86 : 1) * jitter(random))
  }),
  sensor: ({ color, accent }, random) => grid((i, j) => {
    if (edge(i, j)) return tone(color, 0.85 * jitter(random))
    return (i % 3 === 0 || j % 3 === 0) ? tone(color, jitter(random)) : tone(accent ?? color, jitter(random, 0.05))
  }),
  gate: ({ color, accent, size = 1 }, random) => {
    const dots = [[[3, 3]], [[1, 3], [5, 3]], [[1, 5], [5, 5], [3, 1]]][Math.min(3, Math.max(1, size)) - 1]
    return grid((i, j) => {
      if (dots.some(([x, y]) => (i === x || i === x + 1) && (j === y || j === y + 1))) return tone(accent ?? color, jitter(random, 0.05))
      return tone(color, (edge(i, j) ? 0.82 : 1) * jitter(random, 0.05))
    })
  },
  lamp: ({ color, accent }, random) => grid((i, j) => {
    if (edge(i, j) || i === 3 || j === 3) return tone(accent ?? color, jitter(random, 0.05))
    return tone(color, (i === 1 || j === 1 ? 1.1 : 1) * jitter(random, 0.05))
  }),
  sprite_bell: ({ color, accent }, random) => grid((i, j) => {
    if (j === 0) return i >= 2 && i <= 5 ? tone(accent ?? color, jitter(random)) : CLEAR
    if (j === 7) return i === 3 || i === 4 ? tone(accent ?? color, jitter(random)) : CLEAR
    const half = j <= 2 ? 1 : j <= 4 ? 2 : 3
    if (Math.abs(i - 3.5) > half) return CLEAR
    return tone(color, (i < 3.5 ? 1.12 : 0.9) * jitter(random, 0.06))
  }),
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
  sprite_bush: ({ color, accent }, random) => {
    const berries = accent ? [[1, 4], [3, 3], [5, 5], [2, 6], [6, 3]] : []
    return grid((i, j) => {
      const dx = (i - 3.5) / 4, dy = (j - 4.6) / 3.4
      if (dx * dx + dy * dy > 1) return CLEAR
      if (accent && berries.some(([x, y]) => x === i && y === j)) return tone(accent, jitter(random))
      return tone(color, (random() < 0.22 ? 0.76 : 1) * jitter(random, 0.14))
    })
  },
  sprite_mushroom: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 5 && (i === 3 || i === 4)) return tone(accent ?? color, (i === 4 ? 0.88 : 1) * jitter(random))
    const cap = (j === 2 && i >= 2 && i <= 5) || ((j === 3 || j === 4) && i >= 1 && i <= 6)
    if (!cap) return CLEAR
    const spot = j < 4 && (i + j) % 3 === 0
    return tone(color, (spot ? 1.3 : j === 4 ? 0.82 : 1) * jitter(random))
  }),
  furrows: ({ color }, random) => grid((_i, j) => tone(color, (j % 3 === 2 ? 0.7 : 1.06) * jitter(random))),
  sprite_crop: ({ color, accent, size = 4 }, random) => {
    const stalks = [1, 3, 4, 6]
    const heights = stalks.map(() => Math.max(1, size * 2 - Math.floor(random() * 2)))
    return grid((i, j) => {
      const index = stalks.indexOf(i)
      if (index < 0 || j < N - heights[index]) return CLEAR
      const ear = accent !== undefined && j < N - heights[index] + 3
      return tone(ear ? accent : color, jitter(random, 0.14))
    })
  },
  sprite_leafy: ({ color, accent, size = 4 }, random) => {
    const top = N - size * 2
    return grid((i, j) => {
      if (accent && j === N - 1 && (i === 2 || i === 5)) return tone(accent, jitter(random))
      if (j < top) return CLEAR
      const spread = 1 + Math.floor((j - top) / 2)
      if (Math.abs(i - 3.5) > spread || (i + j) % 3 === 0) return CLEAR
      return tone(color, (j - top < 2 ? 1.1 : 1) * jitter(random, 0.14))
    })
  },
  sprite_sapling: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 4 && i === 3) return tone(accent ?? color, jitter(random))
    const leaf = (j === 1 && i >= 2 && i <= 4) || (j === 2 && i >= 1 && i <= 5) || (j === 3 && (i === 2 || i === 4 || i === 5))
    return leaf ? tone(color, (random() < 0.25 ? 0.8 : 1) * jitter(random, 0.14)) : CLEAR
  }),
  sprite_campfire: ({ color, accent }, random) => grid((i, j) => {
    if (j >= 6) return (j === 6 ? i >= 1 && i <= 6 : i !== 3 && i !== 4) ? tone(accent ?? color, (i % 2 ? 0.86 : 1) * jitter(random)) : CLEAR
    const half = (j - 1) * 0.55
    if (j < 1 || Math.abs(i - 3.5) > half) return CLEAR
    return tone(color, (Math.abs(i - 3.5) < 1 && j >= 3 ? 1.18 : 1) * jitter(random, 0.06))
  }),
  sprite_torch: ({ color, accent }, random) => grid((i, j) => {
    if (i !== 3 && i !== 4) return CLEAR
    if (j >= 3) return tone(accent ?? color, (i === 4 ? 0.86 : 1) * jitter(random))
    return j >= 1 ? tone(color, (j === 2 ? 1 : 1.15) * jitter(random, 0.06)) : CLEAR
  }),
  bed_top: ({ color, accent }, random) => grid((i, j) => {
    if (j <= 2) return tone(accent ?? color, (edge(i, j) ? 0.9 : 1) * jitter(random, 0.04))
    return tone(color, (i === 0 || i === N - 1 ? 0.84 : 1) * jitter(random))
  }),
  bed_side: ({ color, accent }, random) => grid((i, j) => {
    if (j <= 3) return tone(color, (j === 3 ? 0.84 : 1) * jitter(random))
    return tone(accent ?? color, (j >= 6 && i > 0 && i < N - 1 ? 0.55 : 1) * jitter(random))
  }),
  chest_top: ({ color, accent }, random) => grid((i, j) =>
    edge(i, j) ? tone(accent ?? color, jitter(random)) : tone(color, (j % 4 === 3 ? 0.84 : 1) * jitter(random))),
  chest_side: ({ color, accent }, random) => grid((i, j) => {
    if ((i === 3 || i === 4) && (j === 3 || j === 4)) return tone([226, 192, 126], jitter(random, 0.04))
    if (edge(i, j) || j === 3) return tone(accent ?? color, jitter(random))
    return tone(color, jitter(random))
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

import { describe, expect, it } from 'vitest'
import fixture from '../../../shared/worldgen-fixture.json'
import { blockDef, blockId } from './blocks'
import {
  blockAt, cavePlant, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, plantStack, swampPool, terrainHeight,
  treeKind, treesInChunk, wildFood, WORLD_MAX_Y, WORLD_MIN_Y,
} from './worldgen'

const WILD_SEED = '123456789123456789'

function columnMismatches(cx: number, cz: number, seed: string): string[] {
  const data = generateColumn(cx, cz, seed)
  const mismatches: string[] = []
  for (let lx = 0; lx < 16; lx++) for (let lz = 0; lz < 16; lz++) {
    for (let y = WORLD_MIN_Y; y <= WORLD_MAX_Y; y++) {
      const expected = blockAt(cx * 16 + lx, y, cz * 16 + lz, seed)
      const actual = blockDef(data[columnIndex(lx, y, lz)]).name
      if (actual !== expected) mismatches.push(`(${cx * 16 + lx}, ${y}, ${cz * 16 + lz}) ${expected} vs ${actual}`)
    }
  }
  return mismatches
}

describe('worldgen', () => {
  it('matches every cell the Python worldgen wrote to the shared fixture', () => {
    const mismatches: string[] = []
    for (const [seedIndex, x, y, z, material] of fixture.cells) {
      const seed = fixture.seeds[seedIndex]
      const expected = fixture.materials[material]
      const actual = blockAt(x, y, z, seed)
      if (actual !== expected) mismatches.push(`seed ${seed} (${x}, ${y}, ${z}): expected ${expected}, got ${actual}`)
    }
    expect(mismatches.slice(0, 20)).toEqual([])
  })

  it('reproduces the legacy hash', () => {
    expect(legacyHash(1, 0)).toBe(73856093)
    expect(legacyHash(100, 100)).toBe(882750904)
    expect(legacyHash(-7, 3)).toBe(497381208)
  })

  it.each([[0, 0], [0, -1], [-1, -1], [3, 2], [-20, 14]])('generateColumn(%i, %i) agrees with blockAt', (cx, cz) => {
    expect(columnMismatches(cx, cz, DEFAULT_WORLD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates trees inside columns exactly like blockAt', () => {
    let treeChunk: [number, number] | null = null
    for (let cx = 16; cx < 46 && !treeChunk; cx++) {
      for (let cz = -15; cz < 15 && !treeChunk; cz++) if (treesInChunk(cx, cz, WILD_SEED).length) treeChunk = [cx, cz]
    }
    expect(treeChunk).not.toBeNull()
    const [cx, cz] = treeChunk!
    const logs = ['oak_log', 'birch_log', 'spruce_log'].map((name) => blockId(name))
    expect(Array.from(generateColumn(cx, cz, WILD_SEED)).some((id) => logs.includes(id))).toBe(true)
    expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates every wood, the tall plants, fruit, pools and frozen lakes inside columns exactly like blockAt', () => {
    const chunks = new Map<string, [number, number]>()
    const plants = ['cactus', 'sugar_cane', 'pumpkin', 'melon', 'dead_bush', 'fern']
    for (let x = 250; x < 1250 && chunks.size < plants.length; x++) {
      for (let z = -60; z < 60; z += 2) {
        const stack = plantStack(x, z, WILD_SEED)
        if (stack && plants.includes(stack[0]) && !chunks.has(stack[0])) chunks.set(stack[0], [Math.floor(x / 16), Math.floor(z / 16)])
      }
    }
    for (let cx = 16; cx < 80; cx++) for (let cz = -30; cz < 30; cz++) {
      for (const [tx, tz] of treesInChunk(cx, cz, WILD_SEED)) {
        const kind = treeKind(tx, tz, WILD_SEED)
        if (!chunks.has(kind)) chunks.set(kind, [cx, cz])
      }
    }
    expect([...chunks.keys()].sort()).toEqual([...plants, 'birch', 'oak', 'spruce'].sort())
    expect(swampPool(771, -8, WILD_SEED)).toBe(true)  // a swamp pool, in chunk (48, -1)
    chunks.set('pool', [48, -1])
    chunks.set('ice', [15, -15])  // a frozen taiga lake
    expect(Array.from(generateColumn(15, -15, WILD_SEED)).includes(blockId('ice'))).toBe(true)
    for (const [name, [cx, cz]] of chunks) {
      if (name !== 'oak') expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10), name).toEqual([])
    }
  })

  it('generates gold, diamond, cave lakes, lava and the stone seams inside columns exactly like blockAt', () => {
    const deep = ['gold_ore', 'diamond_ore', 'water', 'lava', 'gravel', 'granite', 'andesite', 'diorite', 'ashstone']
    const chunks = new Map<string, [number, number]>()
    for (let x = 250; x < 700 && chunks.size < deep.length; x += 3) {
      for (let z = -100; z < 100; z += 3) {
        for (let y = -4; y < terrainHeight(x, z, WILD_SEED) - 2; y++) {
          const name = blockAt(x, y, z, WILD_SEED)
          if (deep.includes(name) && !chunks.has(name)) chunks.set(name, [Math.floor(x / 16), Math.floor(z / 16)])
        }
      }
    }
    expect([...chunks.keys()].sort()).toEqual([...deep].sort())
    const unique = new Map([...chunks.values()].map((chunk) => [chunk.join(','), chunk]))
    for (const [cx, cz] of unique.values()) expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })

  it('generates wild food and cave mushrooms inside columns exactly like blockAt', () => {
    let foodChunk: [number, number] | null = null
    for (let x = 300; x < 900 && !foodChunk; x++) {
      for (let z = -40; z < 40 && !foodChunk; z++) if (wildFood(x, z, WILD_SEED)) foodChunk = [Math.floor(x / 16), Math.floor(z / 16)]
    }
    let caveChunk: [number, number] | null = null
    for (let x = 250; x < 700 && !caveChunk; x += 3) {
      for (let z = -100; z < 100 && !caveChunk; z += 3) {
        for (let y = -4; y < terrainHeight(x, z, WILD_SEED) - 2 && !caveChunk; y++) {
          if (cavePlant(x, y, z, WILD_SEED)) caveChunk = [Math.floor(x / 16), Math.floor(z / 16)]
        }
      }
    }
    expect(foodChunk).not.toBeNull()
    expect(caveChunk).not.toBeNull()
    for (const [cx, cz] of [foodChunk!, caveChunk!]) expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
    const food = ['berry_bush_ripe', 'brown_mushroom', 'red_mushroom'].map((name) => blockId(name))
    expect(Array.from(generateColumn(...foodChunk!, WILD_SEED)).some((id) => food.includes(id))).toBe(true)
    expect(Array.from(generateColumn(...caveChunk!, WILD_SEED)).some((id) => food.includes(id))).toBe(true)
  })
})

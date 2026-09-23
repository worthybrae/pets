import { describe, expect, it } from 'vitest'
import fixture from '../../../shared/worldgen-fixture.json'
import { blockDef, blockId } from './blocks'
import {
  blockAt, columnIndex, DEFAULT_WORLD_SEED, generateColumn, legacyHash, treesInChunk, WORLD_MAX_Y, WORLD_MIN_Y,
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
    expect(generateColumn(cx, cz, WILD_SEED).includes(blockId('oak_log'))).toBe(true)
    expect(columnMismatches(cx, cz, WILD_SEED).slice(0, 10)).toEqual([])
  })
})

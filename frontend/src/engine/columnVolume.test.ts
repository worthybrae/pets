import { describe, expect, it } from 'vitest'
import { AIR, blockId } from './blocks'
import { buildPaddedVolume, ColumnCache } from './columnVolume'
import { paddedIndex } from './mesher'
import { columnIndex, WORLD_MIN_Y } from './worldgen'

const filled = (id: number) => new Uint8Array(16 * 16 * 128).fill(id)

describe('buildPaddedVolume', () => {
  const columns = new Map([['0,0', filled(3)], ['-1,0', filled(4)], ['1,0', filled(5)]])
  const columnAt = (cx: number, cz: number) => columns.get(`${cx},${cz}`) ?? filled(9)

  it('fills the border from neighbor columns', () => {
    const volume = buildPaddedVolume(0, 0, columnAt, new Int32Array())
    expect(volume[paddedIndex(1, 10, 5)]).toBe(3)
    expect(volume[paddedIndex(0, 10, 5)]).toBe(4)
    expect(volume[paddedIndex(17, 10, 5)]).toBe(5)
    expect(volume[paddedIndex(5, 10, 0)]).toBe(9)
  })

  it('reads the right cell from the neighbor column', () => {
    const west = filled(0)
    west[columnIndex(15, 20, 7)] = 42
    const volume = buildPaddedVolume(0, 0, (cx) => (cx === -1 ? west : filled(0)), new Int32Array())
    expect(volume[paddedIndex(0, 20 - WORLD_MIN_Y, 8)]).toBe(42)
  })

  it('applies edits in range and ignores the rest', () => {
    const edits = Int32Array.from([0, 20, 0, 7, -1, 20, 0, 8, 40, 20, 0, 9])
    const volume = buildPaddedVolume(0, 0, columnAt, edits)
    expect(volume[paddedIndex(1, 20 - WORLD_MIN_Y, 1)]).toBe(7)
    expect(volume[paddedIndex(0, 20 - WORLD_MIN_Y, 1)]).toBe(8)
  })

  it('turns a plant into air when the cell below it was edited', () => {
    const withPlant = filled(0)
    withPlant[columnIndex(5, 20, 5)] = blockId('tall_grass')
    const columnAt = (cx: number, cz: number) => (cx === 0 && cz === 0 ? withPlant : filled(9))
    const edits = Int32Array.from([5, 19, 5, blockId('stone')])
    const volume = buildPaddedVolume(0, 0, columnAt, edits)
    expect(volume[paddedIndex(6, 20 - WORLD_MIN_Y, 6)]).toBe(AIR)
  })

  it('keeps an edit made directly on the plant cell', () => {
    const withPlant = filled(0)
    withPlant[columnIndex(5, 20, 5)] = blockId('tall_grass')
    const columnAt = (cx: number, cz: number) => (cx === 0 && cz === 0 ? withPlant : filled(9))
    const edits = Int32Array.from([5, 20, 5, blockId('flower_pink'), 5, 19, 5, blockId('stone')])
    const volume = buildPaddedVolume(0, 0, columnAt, edits)
    expect(volume[paddedIndex(6, 20 - WORLD_MIN_Y, 6)]).toBe(blockId('flower_pink'))
  })
})

describe('ColumnCache', () => {
  it('generates once and evicts the least recently used column', () => {
    const cache = new ColumnCache('1', 2)
    const first = cache.get(0, 0)
    expect(cache.get(0, 0)).toBe(first)
    cache.get(1, 0)
    cache.get(0, 0)
    cache.get(2, 0)
    expect(cache.size).toBe(2)
    expect(cache.get(0, 0)).toBe(first)
  })
})

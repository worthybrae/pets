import { describe, expect, it } from 'vitest'
import { AIR, blockId } from './blocks'
import { columnIndex } from './worldgen'
import { columnsTouching, WorldStore } from './worldStore'

describe('WorldStore', () => {
  it('falls back to worldgen for untouched cells', () => {
    const store = new WorldStore()
    expect(store.getBlock(0, -6, 0)).toBe(blockId('bedrock'))
    expect(store.getBlock(0, 200, 0)).toBe(0)
  })

  it('reads base columns and lets edits override them, including negative coordinates', () => {
    const store = new WorldStore()
    const column = new Uint8Array(16 * 16 * 128)
    column[columnIndex(15, 40, 0)] = blockId('clay')
    store.setBaseColumn(-1, -2, column)
    expect(store.getBlock(-1, 40, -32)).toBe(blockId('clay'))
    store.applyServerChanges([{ x: -1, y: 40, z: -32, material: 'air' }])
    expect(store.getBlock(-1, 40, -32)).toBe(0)
  })

  it('prefers server edits over the build overlay', () => {
    const store = new WorldStore()
    store.setOverlay([{ x: 3, y: 30, z: 3, material: 'limestone' }])
    expect(store.getBlock(3, 30, 3)).toBe(blockId('limestone'))
    store.applyServerChanges([{ x: 3, y: 30, z: 3, material: 'stone' }])
    expect(store.getBlock(3, 30, 3)).toBe(blockId('stone'))
  })

  it('finds the cells where the server placed a block near a spot', () => {
    const store = new WorldStore()
    store.applyServerChanges([
      { x: 3, y: 1, z: 4, material: 'door' }, { x: 40, y: 1, z: 0, material: 'door' }, { x: 3, y: 2, z: 4, material: 'air' },
    ])
    expect(store.placedCells('door', 0, 0, 32)).toEqual([{ x: 3, y: 1, z: 4 }])
    expect(store.placedCells('bed', 0, 0, 32)).toEqual([])
  })

  it('lists the highest server edit of each edited column in a chunk, dug cells too', () => {
    const store = new WorldStore()
    store.applyServerChanges([
      { x: 3, y: 9, z: 4, material: 'planks' }, { x: 3, y: 12, z: 4, material: 'air' },
      { x: -5, y: 2, z: 4, material: 'stone' }, { x: 20, y: 5, z: 4, material: 'stone' },
    ])
    expect(store.editedColumns(0, 0)).toEqual(new Map([['3,4', 12]]))
    expect(store.editedColumns(-1, 0)).toEqual(new Map([['-5,4', 2]]))
    expect(store.editedColumns(1, 0)).toEqual(new Map([['20,4', 5]]))
    expect(store.editedColumns(5, 5).size).toBe(0)
  })

  it('marks neighbor columns dirty for border blocks', () => {
    expect(columnsTouching(5, 5)).toEqual(['0,0'])
    expect(columnsTouching(16, 5).sort()).toEqual(['0,0', '1,0'])
    expect(columnsTouching(15, 15).sort()).toEqual(['0,0', '0,1', '1,0', '1,1'])
    expect(columnsTouching(-16, 5).sort()).toEqual(['-1,0', '-2,0'])
  })

  it('reports only changed overlay cells', () => {
    const store = new WorldStore()
    const a = { x: 5, y: 30, z: 5, material: 'limestone' }
    const b = { x: 40, y: 30, z: 5, material: 'limestone' }
    expect(store.setOverlay([a, b]).sort()).toEqual(['0,0', '2,0'])
    expect(store.setOverlay([a])).toEqual(['2,0'])
    expect(store.setOverlay([a])).toEqual([])
    expect(store.getBlock(40, 30, 5)).not.toBe(blockId('limestone'))
  })

  it('clears server edits on reset', () => {
    const store = new WorldStore()
    store.applyServerChanges([{ x: 5, y: 30, z: 5, material: 'stone' }])
    expect(store.applyServerChanges([], true)).toEqual(['0,0'])
    expect(store.getBlock(5, 30, 5)).toBe(0)
  })

  it('collects edits for a column and its one-cell border', () => {
    const store = new WorldStore()
    store.setOverlay([{ x: 16, y: 30, z: 0, material: 'limestone' }])
    store.applyServerChanges([
      { x: 0, y: 30, z: 0, material: 'stone' },
      { x: 16, y: 30, z: 0, material: 'glass' },
      { x: 17, y: 30, z: 0, material: 'stone' },
    ])
    const edits = Array.from(store.editsNear(0, 0))
    const cells = []
    for (let i = 0; i < edits.length; i += 4) cells.push(edits.slice(i, i + 4))
    expect(cells).toContainEqual([0, 30, 0, blockId('stone')])
    expect(cells).toContainEqual([16, 30, 0, blockId('glass')])
    expect(cells).not.toContainEqual([17, 30, 0, blockId('stone')])
    expect(cells).toHaveLength(2)
  })

  it('finds nearby server-placed workstations', () => {
    const store = new WorldStore()
    store.applyServerChanges([{ x: 75, y: 1, z: 0, material: 'crafting_table' }, { x: 99, y: 1, z: 0, material: 'furnace' }])
    expect([...store.materialsNear(73, 0, 6)]).toEqual(['crafting_table'])
  })

  it('knows which cells hold a block the server placed', () => {
    const store = new WorldStore()
    store.applyServerChanges([{ x: 3, y: 20, z: 0, material: 'cobblestone' }, { x: 4, y: 20, z: 0, material: 'air' }])
    store.setOverlay([{ x: 5, y: 20, z: 0, material: 'stone' }])
    expect(store.placedAt(3, 20, 0)).toBe(true)
    expect(store.placedAt(4, 20, 0)).toBe(false)  // mined out
    expect(store.placedAt(0, -6, 0)).toBe(false)  // natural bedrock
    expect(store.placedAt(5, 20, 0)).toBe(false)  // the viewer's own overlay, not the server's
  })

  it('keeps overlay layers independent', () => {
    const store = new WorldStore()
    const a = { x: 5, y: 30, z: 5, material: 'limestone' }
    const b = { x: 40, y: 30, z: 5, material: 'polished_stone' }
    store.setOverlay([a], 'finished')
    store.setOverlay([b], 'current')
    expect(store.setOverlay([], 'current').sort()).toEqual(['2,0'])
    expect(store.getBlock(5, 30, 5)).toBe(blockId('limestone'))
    expect(store.getBlock(40, 30, 5)).not.toBe(blockId('polished_stone'))
    const edits = Array.from(store.editsNear(0, 0))
    const cells = []
    for (let i = 0; i < edits.length; i += 4) cells.push(edits.slice(i, i + 4))
    expect(cells).toContainEqual([5, 30, 5, blockId('limestone')])
  })

  it('orders layers by first call even when a layer starts empty', () => {
    const store = new WorldStore()
    store.setOverlay([], 'finished')
    store.setOverlay([{ x: 5, y: 30, z: 5, material: 'limestone' }], 'current')
    store.setOverlay([{ x: 5, y: 30, z: 5, material: 'planks' }], 'finished')
    expect(store.getBlock(5, 30, 5)).toBe(blockId('limestone'))
    const edits = Array.from(store.editsNear(0, 0))
    const cells = []
    for (let i = 0; i < edits.length; i += 4) cells.push(edits.slice(i, i + 4))
    expect(cells).toContainEqual([5, 30, 5, blockId('limestone')])
  })

  it('turns a plant into air when the cell below has a server edit', () => {
    const store = new WorldStore()
    const column = new Uint8Array(16 * 16 * 128)
    column[columnIndex(5, 20, 5)] = blockId('tall_grass')
    store.setBaseColumn(0, 0, column)
    expect(store.getBlock(5, 20, 5)).toBe(blockId('tall_grass'))
    store.applyServerChanges([{ x: 5, y: 19, z: 5, material: 'stone' }])
    expect(store.getBlock(5, 20, 5)).toBe(AIR)
  })

  it('turns a plant into air when the cell below has only an overlay edit', () => {
    const store = new WorldStore()
    const column = new Uint8Array(16 * 16 * 128)
    column[columnIndex(5, 20, 5)] = blockId('tall_grass')
    store.setBaseColumn(0, 0, column)
    store.setOverlay([{ x: 5, y: 19, z: 5, material: 'stone' }])
    expect(store.getBlock(5, 20, 5)).toBe(AIR)
  })

  it('tells subscribers which columns changed', () => {
    const store = new WorldStore()
    const seen: string[][] = []
    const unsubscribe = store.subscribe((columns) => seen.push(columns))
    store.applyServerChanges([{ x: 5, y: 30, z: 5, material: 'stone' }])
    unsubscribe()
    store.applyServerChanges([{ x: 6, y: 30, z: 5, material: 'stone' }])
    expect(seen).toEqual([['0,0']])
  })
})

import { describe, expect, it, vi } from 'vitest'
import {
  AIR, BLOCKS, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
  MISSING_ID, TILES, blockDef, blockId, hasBlock,
} from './blocks'

describe('block registry', () => {
  it('puts air at id 0 and keeps ids below the missing id', () => {
    expect(blockId('air')).toBe(AIR)
    expect(BLOCKS.length).toBeLessThan(MISSING_ID)
    BLOCKS.forEach((block, index) => expect(block.id).toBe(index))
  })

  it('expands a single texture name to every face', () => {
    const stone = blockDef(blockId('stone'))
    expect(stone.textures).toEqual({ top: 'stone', side: 'stone', bottom: 'stone' })
    expect(blockDef(blockId('grass')).textures.side).toBe('grass_side')
  })

  it('uses only tiles that exist', () => {
    for (const block of BLOCKS) {
      for (const tile of Object.values(block.textures)) expect(TILES[tile], `${block.name} → ${tile}`).toBeDefined()
    }
  })

  it('maps unknown names to the missing block and warns once', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(blockId('unobtainium')).toBe(MISSING_ID)
    expect(blockId('unobtainium')).toBe(MISSING_ID)
    expect(warn).toHaveBeenCalledTimes(1)
    expect(hasBlock('unobtainium')).toBe(false)
    expect(blockDef(MISSING_ID).layer).toBe('opaque')
    warn.mockRestore()
  })

  it('fills per-id lookup tables', () => {
    expect(LAYER_BY_ID[blockId('stone')]).toBe(LAYER_OPAQUE)
    expect(LAYER_BY_ID[blockId('water')]).toBe(LAYER_TRANSLUCENT)
    expect(LAYER_BY_ID[blockId('flower_pink')]).toBe(LAYER_CUTOUT)
    expect(LAYER_BY_ID[AIR]).toBe(0)
    expect(GLOW_BY_ID[blockId('lantern')]).toBe(1)
    expect(FLUID_BY_ID[blockId('water')]).toBe(1)
    expect(LAYER_BY_ID[MISSING_ID]).toBe(LAYER_OPAQUE)
  })
})

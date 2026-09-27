import { describe, expect, it, vi } from 'vitest'
import {
  AIR, BLOCKS, CUBE_BY_ID, FLAT_HEIGHT, FLUID_BY_ID, GLOW_BY_ID, HEIGHT_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE,
  LAYER_TRANSLUCENT, MISSING_ID, SLAB_HEIGHT, TILES, blockDef, blockId, hasBlock,
} from './blocks'

/** L3's blocks, in registry order (backend/tests/test_blocks_bigger_world.py). */
const BIGGER_WORLD = ['granite', 'andesite', 'diorite', 'ashstone', 'gold_ore', 'diamond_ore',
  'birch_log', 'birch_leaves', 'birch_planks', 'spruce_log', 'spruce_leaves', 'spruce_planks',
  'snow_block', 'ice', 'mud', 'cactus', 'sugar_cane', 'pumpkin', 'melon', 'fern', 'dead_bush',
  'mossy_cobblestone', 'stone_bricks', 'ladder', 'fence', 'creature_sprout']
/** Making's T1 blocks, right after L3's (backend/tests/test_blocks_making.py). */
const MAKING = ['bookshelf', 'wool_orange', 'wool_pink', 'wool_yellow', 'rug_orange', 'rug_pink', 'rug_yellow', 'kiln',
  'stairs', 'slab', 'glass_pane', 'trapdoor', 'iron_bars', 'flower_pot', 'sign', 'barrel', 'composter', 'candle']
/** Making's T2 blocks, the wiring, right after its T1 blocks (backend/tests/test_blocks_wiring.py). */
const WIRING = ['copper_wire', 'copper_wire_lit', 'lever', 'lever_on', 'button', 'button_on', 'pressure_plate',
  'daylight_sensor', 'repeater', 'repeater_lit', 'inverter', 'inverter_lit', 'joiner', 'joiner_lit', 'lamp', 'lamp_lit', 'bell']
/** L5's blocks, after Making's wiring, the last (backend/tests/test_survival_frontier_gear.py). */
const FRONTIER = ['warding_lantern']

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

  it('adds the food and camp blocks after the existing ones, so older ids never change', () => {
    expect(blockId('berry_bush')).toBe(blockId('flower_yellow') + 1)
    expect(blockId('door')).toBe(blockId('chest') + 1)
    expect(blockId('door')).toBe(blockId('granite') - 1)
    expect(LAYER_BY_ID[blockId('door')]).toBe(0)  // not meshed: the viewer draws doors itself
    for (const name of ['berry_bush_ripe', 'red_mushroom', 'wheat_2', 'carrot_3', 'sapling', 'campfire', 'torch']) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_CUTOUT)
      expect(blockDef(blockId(name)).solid, name).toBe(false)
    }
    expect(LAYER_BY_ID[blockId('farmland')]).toBe(LAYER_OPAQUE)
    expect(blockDef(blockId('farmland')).textures).toEqual({ top: 'farmland_top', side: 'dirt', bottom: 'dirt' })
    expect(GLOW_BY_ID[blockId('campfire')]).toBe(1)
    expect(GLOW_BY_ID[blockId('torch')]).toBe(1)
    expect(GLOW_BY_ID[blockId('sapling')]).toBe(0)
  })

  it('adds the bigger world\'s blocks after the door, plants see-through and the stone solid', () => {
    const names = BLOCKS.map((block) => block.name)
    expect(names.slice(blockId('granite'), blockId('granite') + BIGGER_WORLD.length)).toEqual(BIGGER_WORLD)
    expect(blockId('granite')).toBeGreaterThan(blockId('chest'))
    for (const name of ['cactus', 'sugar_cane', 'fern', 'dead_bush', 'creature_sprout', 'ladder', 'fence']) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_CUTOUT)
    }
    for (const name of ['granite', 'ashstone', 'diamond_ore', 'birch_log', 'spruce_leaves', 'mud', 'pumpkin', 'stone_bricks']) {
      expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_OPAQUE)
    }
    expect(LAYER_BY_ID[blockId('ice')]).toBe(LAYER_TRANSLUCENT)
    expect(blockDef(blockId('snow_block')).textures).toEqual({ top: 'snow', side: 'snow', bottom: 'snow' })
    expect(blockDef(blockId('birch_log')).textures.side).toBe('birch_log_side')
  })

  it('marks the see-through blocks that are drawn as cubes', () => {
    for (const name of ['cactus', 'ladder', 'fence']) {
      expect(CUBE_BY_ID[blockId(name)], name).toBe(1)
      expect(blockDef(blockId(name)).cube, name).toBe(true)
    }
    for (const name of ['sugar_cane', 'fern', 'creature_sprout', 'flower_pink', 'torch', 'stone', 'air']) {
      expect(CUBE_BY_ID[blockId(name)], name).toBe(0)
    }
    expect(CUBE_BY_ID[MISSING_ID]).toBe(0)
  })

  it('adds Making\'s blocks after the bigger world\'s, the thin ones drawn at their height', () => {
    const names = BLOCKS.map((block) => block.name)
    const start = blockId('bookshelf')
    expect(start).toBe(blockId('creature_sprout') + 1)
    expect(names.slice(start, start + MAKING.length)).toEqual(MAKING)
    for (const name of ['rug_orange', 'rug_pink', 'rug_yellow', 'trapdoor']) {
      expect(CUBE_BY_ID[blockId(name)], name).toBe(1)
      expect(HEIGHT_BY_ID[blockId(name)], name).toBeCloseTo(FLAT_HEIGHT)
    }
    expect(HEIGHT_BY_ID[blockId('slab')]).toBe(SLAB_HEIGHT)
    for (const name of ['stairs', 'glass_pane', 'iron_bars', 'composter', 'cactus', 'fence']) {
      expect(CUBE_BY_ID[blockId(name)], name).toBe(1)
      expect(HEIGHT_BY_ID[blockId(name)], name).toBe(1)
    }
    for (const name of ['bookshelf', 'kiln', 'barrel', 'wool_pink']) expect(LAYER_BY_ID[blockId(name)], name).toBe(LAYER_OPAQUE)
    for (const name of ['flower_pot', 'sign', 'candle']) expect(CUBE_BY_ID[blockId(name)], name).toBe(0)  // sprites
    expect(GLOW_BY_ID[blockId('candle')]).toBe(1)
    expect(blockDef(blockId('bookshelf')).textures).toEqual({ top: 'planks', side: 'bookshelf', bottom: 'planks' })
  })

  it('adds the wiring after Making\'s first blocks: wire and gates flat, lit ones glowing, lamps solid', () => {
    const names = BLOCKS.map((block) => block.name)
    const start = blockId('copper_wire')
    expect(start).toBe(blockId('candle') + 1)
    expect(names.slice(start, start + WIRING.length)).toEqual(WIRING)
    for (const name of ['copper_wire', 'copper_wire_lit', 'pressure_plate', 'repeater', 'inverter_lit', 'joiner']) {
      expect(HEIGHT_BY_ID[blockId(name)], name).toBeCloseTo(FLAT_HEIGHT)
    }
    expect(HEIGHT_BY_ID[blockId('daylight_sensor')]).toBe(SLAB_HEIGHT)
    for (const name of ['copper_wire_lit', 'repeater_lit', 'inverter_lit', 'joiner_lit', 'lamp_lit']) {
      expect(GLOW_BY_ID[blockId(name)], name).toBe(1)
      expect(GLOW_BY_ID[blockId(name.replace('_lit', ''))], name).toBe(0)
    }
    expect(LAYER_BY_ID[blockId('lamp_lit')]).toBe(LAYER_OPAQUE)
    for (const name of ['lever', 'lever_on', 'button', 'bell']) expect(CUBE_BY_ID[blockId(name)], name).toBe(0)  // sprites
  })

  it('adds L5\'s warding lantern last, after the wiring, glowing like a lantern', () => {
    const names = BLOCKS.map((block) => block.name)
    expect(blockId('warding_lantern')).toBe(blockId('bell') + 1)
    expect(names.slice(-FRONTIER.length)).toEqual(FRONTIER)
    expect(GLOW_BY_ID[blockId('warding_lantern')]).toBe(1)  // L5: it glows like a lantern
  })
})

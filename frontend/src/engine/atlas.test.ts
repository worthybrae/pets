import { describe, expect, it } from 'vitest'
import { ATLAS_SIZE, FACE_UP, PATTERNS, TILE_SIZE, animateWater, buildAtlas, tileUv, type Atlas } from './atlas'
import { BLOCKS, MISSING_ID, TILES } from './blocks'

/** Pixel (i, j) of a tile, with j = 0 as the top row the way it was painted. */
function pixelAt(atlas: Atlas, tile: number, i: number, j: number): number[] {
  const tx = (tile % 16) * TILE_SIZE, ty = Math.floor(tile / 16) * TILE_SIZE
  const offset = ((ty + TILE_SIZE - 1 - j) * ATLAS_SIZE + tx + i) * 4
  return Array.from(atlas.data.slice(offset, offset + 4))
}

function tilePixels(atlas: Atlas, tile: number): number[][] {
  const pixels: number[][] = []
  for (let j = 0; j < TILE_SIZE; j++) for (let i = 0; i < TILE_SIZE; i++) pixels.push(pixelAt(atlas, tile, i, j))
  return pixels
}

describe('atlas', () => {
  const atlas = buildAtlas()

  it('knows every tile pattern in the registry', () => {
    for (const [name, recipe] of Object.entries(TILES)) expect(PATTERNS[recipe.pattern], name).toBeDefined()
  })

  it('gives every registered block face a real tile', () => {
    for (const block of BLOCKS) {
      if (block.layer === 'none') continue
      for (let face = 0; face < 6; face++) expect(atlas.faceTiles[block.id * 6 + face], `${block.name} face ${face}`).not.toBe(0)
    }
  })

  it('shows unknown ids with the magenta missing tile', () => {
    expect(atlas.faceTiles[MISSING_ID * 6 + FACE_UP]).toBe(0)
    expect(pixelAt(atlas, 0, 2, 0)).toEqual([255, 0, 255, 255])
    expect(pixelAt(atlas, 0, 0, 0)).toEqual([24, 24, 24, 255])
  })

  it('puts the grass lip on the top rows of the side tile', () => {
    const side = atlas.tileIndex.get('grass_side')!
    const top = pixelAt(atlas, side, 3, 0)
    const bottom = pixelAt(atlas, side, 3, 7)
    expect(top[1]).toBeGreaterThan(bottom[1] + 30) // green lip above brown dirt
  })

  it('keeps sprites and glass see-through', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    expect(alphas('tall_grass')).toContain(0)
    expect(alphas('flower_pink')).toContain(0)
    expect(Math.min(...alphas('glass'))).toBeLessThan(255)
    expect(Math.max(...alphas('water'))).toBeLessThan(255)
  })

  it('draws the food and camp sprites on see-through tiles and the new cubes solid', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    for (const name of ['berry_bush', 'berry_bush_ripe', 'brown_mushroom', 'red_mushroom', 'wheat_0', 'wheat_3',
      'carrot_0', 'carrot_3', 'sapling', 'campfire', 'torch']) {
      expect(alphas(name), name).toContain(0)
    }
    for (const name of ['farmland_top', 'bed_top', 'bed_side', 'chest_top', 'chest_side']) {
      expect(Math.min(...alphas(name)), name).toBe(255)
    }
  })

  it('grows crop sprites with each stage and puts berries on the ripe bush only', () => {
    const shown = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).filter((pixel) => pixel[3] > 0).length
    expect(shown('wheat_0')).toBeLessThan(shown('wheat_1'))
    expect(shown('wheat_1')).toBeLessThan(shown('wheat_2'))
    expect(shown('wheat_2')).toBeLessThan(shown('wheat_3'))
    expect(shown('carrot_0')).toBeLessThan(shown('carrot_1'))
    expect(shown('carrot_1')).toBeLessThan(shown('carrot_2'))
    const red = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!)
      .filter((pixel) => pixel[3] > 0 && pixel[0] > pixel[1] + 60).length
    expect(red('berry_bush')).toBe(0)
    expect(red('berry_bush_ripe')).toBeGreaterThan(3)
  })

  it('paints the bigger world: see-through plants, fences and ladders, glassy ice and solid stone and fruit', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    for (const name of ['sugar_cane', 'fern', 'dead_bush', 'creature_sprout', 'ladder', 'fence', 'cactus_side', 'cactus_top']) {
      expect(alphas(name), name).toContain(0)
    }
    for (const name of ['granite', 'andesite', 'diorite', 'ashstone', 'gold_ore', 'diamond_ore', 'birch_log_side',
      'birch_log_top', 'birch_leaves', 'birch_planks', 'spruce_log_side', 'spruce_leaves', 'spruce_planks', 'mud',
      'pumpkin_side', 'pumpkin_top', 'melon_side', 'melon_top', 'mossy_cobblestone', 'stone_bricks']) {
      expect(Math.min(...alphas(name)), name).toBe(255)
    }
    expect(Math.max(...alphas('ice'))).toBeLessThan(255)
    expect(Math.min(...alphas('ice'))).toBeGreaterThan(0)
  })

  it('sizes the new plant sprites by their size, like the crops', () => {
    const top = (name: string) => {
      const pixels = tilePixels(atlas, atlas.tileIndex.get(name)!)
      return Math.floor(pixels.findIndex((pixel) => pixel[3] > 0) / TILE_SIZE)
    }
    expect(top('sugar_cane')).toBe(0) // size 4: a full block, so a stalk two or three high looks whole
    expect(top('fern')).toBeGreaterThan(top('sugar_cane'))
    expect(top('dead_bush')).toBeGreaterThan(top('fern'))
    expect(top('creature_sprout')).toBeGreaterThanOrEqual(top('dead_bush') - 1)
    const recipe = { pattern: 'sprite_fern', color: [84, 138, 96] as [number, number, number] }
    const shown = (size: number) => PATTERNS.sprite_fern({ ...recipe, size }, () => 0.5).filter((pixel) => pixel[3] > 0).length
    expect(shown(1)).toBeLessThan(shown(2))
    expect(shown(2)).toBeLessThan(shown(4))
  })

  it('puts gold and diamond flecks in the stone and dark marks on birch bark', () => {
    const colours = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!)
    expect(colours('gold_ore').some(([r, g, b]) => r > 200 && g > 170 && b < 130)).toBe(true)
    expect(colours('diamond_ore').some(([r, g, b]) => b > 190 && g > 190 && r < 150)).toBe(true)
    expect(colours('birch_log_side').some(([r]) => r < 90)).toBe(true)
  })

  it('paints Making\'s blocks: see-through windows, bars, stairs and sprites, solid shelves, wool, rugs and barrels', () => {
    const alphas = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).map((pixel) => pixel[3])
    for (const name of ['stairs_side', 'glass_pane', 'trapdoor', 'iron_bars', 'flower_pot', 'sign', 'composter_side', 'candle']) {
      expect(alphas(name), name).toContain(0)
      expect(Math.max(...alphas(name)), name).toBe(255)
    }
    for (const name of ['bookshelf', 'wool_orange', 'wool_pink', 'wool_yellow', 'rug_orange', 'rug_pink', 'rug_yellow',
      'kiln_top', 'kiln_side', 'barrel_side', 'barrel_top', 'composter_top']) {
      expect(Math.min(...alphas(name)), name).toBe(255)
    }
    const stairs = tilePixels(atlas, atlas.tileIndex.get('stairs_side')!)
    expect(stairs[0][3]).toBe(0)  // the step: the top left quarter is open...
    expect(stairs[TILE_SIZE * TILE_SIZE - 1][3]).toBe(255)  // ...and the bottom right solid
  })

  it('gives the kiln a glowing mouth and the shelf books of more than one colour', () => {
    const colours = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!)
    expect(colours('kiln_side').some(([r, g, b]) => r > 230 && g > 150 && b < 130)).toBe(true)
    const spines = new Set(colours('bookshelf').slice(TILE_SIZE, 3 * TILE_SIZE).map(([r, g, b]) => `${r >> 5},${g >> 5},${b >> 5}`))
    expect(spines.size).toBeGreaterThan(2)
  })

  it('paints the wiring: see-through wire, sprites and plates, and lit parts brighter than dark ones', () => {
    const pixels = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!)
    const alphas = (name: string) => pixels(name).map((pixel) => pixel[3])
    for (const name of ['copper_wire', 'copper_wire_lit', 'lever', 'lever_on', 'button', 'pressure_plate', 'bell']) {
      expect(alphas(name), name).toContain(0)
    }
    for (const name of ['repeater', 'inverter', 'joiner', 'lamp', 'lamp_lit', 'daylight_sensor_top']) {
      expect(Math.min(...alphas(name)), name).toBe(255)
    }
    const brightness = (name: string) => {
      const shown = pixels(name).filter((pixel) => pixel[3] > 0)
      return shown.reduce((sum, [r, g, b]) => sum + r + g + b, 0) / shown.length
    }
    for (const [lit, dark] of [['copper_wire_lit', 'copper_wire'], ['lamp_lit', 'lamp'], ['repeater_lit', 'repeater']]) {
      expect(brightness(lit), lit).toBeGreaterThan(brightness(dark) + 20)
    }
    expect(pixels('lever')).not.toEqual(pixels('lever_on'))  // the lever leans the other way when thrown
  })

  it('gives a repeater two dots, an inverter one and a joiner three', () => {
    const dots = (name: string) => tilePixels(atlas, atlas.tileIndex.get(name)!).filter(([r, g]) => r > g + 40).length
    expect([dots('inverter'), dots('repeater'), dots('joiner')]).toEqual([4, 8, 12])
  })

  it('insets uvs by a quarter texel', () => {
    const inset = 0.25 / ATLAS_SIZE
    expect(tileUv(0)).toEqual([inset, inset, 8 / 128 - inset, 8 / 128 - inset])
    expect(tileUv(17)).toEqual([8 / 128 + inset, 8 / 128 + inset, 16 / 128 - inset, 16 / 128 - inset])
  })

  it('is deterministic', () => {
    expect(buildAtlas().data).toEqual(atlas.data)
  })

  it('scrolls the water tile in place', () => {
    const scratch = buildAtlas()
    const before = scratch.data.slice()
    const water = tilePixels(scratch, scratch.waterTile)
    animateWater(scratch, 1)
    const after = tilePixels(scratch, scratch.waterTile)
    expect(after).not.toEqual(water)
    const grass = scratch.tileIndex.get('grass_top')!
    expect(tilePixels(scratch, grass)).toEqual(tilePixels({ ...scratch, data: before }, grass))
    animateWater(scratch, 0)
    expect(scratch.data).toEqual(before)
  })
})

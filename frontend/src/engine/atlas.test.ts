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

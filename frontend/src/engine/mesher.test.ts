import { describe, expect, it } from 'vitest'
import { buildAtlas } from './atlas'
import { blockId } from './blocks'
import { cornerAo, meshColumn, PADDED, paddedIndex, type LayerBuffers } from './mesher'
import { WORLD_HEIGHT, WORLD_MIN_Y } from './worldgen'

const { faceTiles } = buildAtlas()

/** Blocks use padded x/z (1..16 is this column, 0 and 17 are neighbors) and world y. */
function mesh(blocks: [number, number, number, string][]) {
  const volume = new Uint8Array(PADDED * PADDED * WORLD_HEIGHT)
  for (const [px, y, pz, name] of blocks) volume[paddedIndex(px, y - WORLD_MIN_Y, pz)] = blockId(name)
  return meshColumn({ cx: 0, cz: 0, volume, faceTiles })
}

const quadCount = (buffers: LayerBuffers) => buffers.indices.length / 6

function quads(buffers: LayerBuffers) {
  const result: { vertices: number[][]; light: number[]; indices: number[] }[] = []
  for (let q = 0; q < quadCount(buffers); q++) {
    const vertices: number[][] = [], light: number[] = []
    for (let k = 0; k < 4; k++) {
      const v = q * 4 + k
      vertices.push([buffers.positions[v * 3], buffers.positions[v * 3 + 1], buffers.positions[v * 3 + 2]])
      light.push(buffers.colors[v * 3])
    }
    result.push({ vertices, light, indices: Array.from(buffers.indices.slice(q * 6, q * 6 + 6)).map((i) => i - q * 4) })
  }
  return result
}

/** The top face of the block at padded (5, 10, 5): world x and z 4..5, y 11. */
function topOfBlock(buffers: LayerBuffers) {
  return quads(buffers).find((quad) => quad.vertices.every(([x, y, z]) => y === 11 && x >= 4 && x <= 5 && z >= 4 && z <= 5))!
}

describe('meshColumn', () => {
  it('draws all six faces of a lone block', () => {
    expect(quadCount(mesh([[5, 10, 5, 'stone']]).opaque)).toBe(6)
  })

  it('hides faces between opaque neighbors', () => {
    expect(quadCount(mesh([[5, 10, 5, 'stone'], [6, 10, 5, 'stone']]).opaque)).toBe(10)
  })

  it('hides faces between blocks of the same translucent kind', () => {
    const result = mesh([[5, 10, 5, 'glass'], [6, 10, 5, 'glass']])
    expect(quadCount(result.translucent)).toBe(10)
    expect(quadCount(result.opaque)).toBe(0)
  })

  it('keeps sand visible under water and lowers the water surface', () => {
    const result = mesh([[5, 10, 5, 'sand'], [5, 11, 5, 'water']])
    expect(quadCount(result.opaque)).toBe(6)
    expect(quadCount(result.translucent)).toBe(5)
    const ys = quads(result.translucent).flatMap((quad) => quad.vertices.map((vertex) => vertex[1]))
    expect(Math.max(...ys)).toBeCloseTo(11.875)
  })

  it('uses neighbor columns to hide border faces', () => {
    expect(quadCount(mesh([[1, 10, 5, 'stone'], [0, 10, 5, 'stone']]).opaque)).toBe(5)
  })

  it('never draws the underside of the world', () => {
    expect(quadCount(mesh([[5, WORLD_MIN_Y, 5, 'bedrock']]).opaque)).toBe(5)
  })

  it('draws plants as two crossed quads', () => {
    const result = mesh([[5, 10, 5, 'flower_pink']])
    expect(quadCount(result.cutout)).toBe(2)
    expect(quadCount(result.opaque)).toBe(0)
  })

  it('scores corner occlusion with the three-neighbor rule', () => {
    expect(cornerAo(0, 0, 0)).toBe(3)
    expect(cornerAo(1, 0, 0)).toBe(2)
    expect(cornerAo(0, 0, 1)).toBe(2)
    expect(cornerAo(1, 0, 1)).toBe(1)
    expect(cornerAo(1, 1, 0)).toBe(0)
  })

  it('darkens the corners next to a wall', () => {
    const top = topOfBlock(mesh([[5, 10, 5, 'stone'], [6, 11, 5, 'stone']]).opaque)
    const nearWall = top.light.filter((_, k) => top.vertices[k][0] === 5)
    const open = top.light.filter((_, k) => top.vertices[k][0] === 4)
    expect(Math.max(...nearWall)).toBeLessThan(Math.min(...open))
  })

  it('splits the quad along the diagonal through a lone dark corner', () => {
    const top = topOfBlock(mesh([[5, 10, 5, 'stone'], [6, 11, 6, 'stone']]).opaque)
    const dark = top.vertices.findIndex(([x, , z]) => x === 5 && z === 5)
    expect(top.indices.filter((index) => index === dark)).toHaveLength(2)
  })

  it('does not shade glowing blocks', () => {
    const top = topOfBlock(mesh([[5, 10, 5, 'lantern'], [6, 11, 5, 'stone']]).opaque)
    expect(new Set(top.light).size).toBe(1)
  })
})

import { describe, expect, it } from 'vitest'
import { AIR, blockId, LAYER_BY_ID, LAYER_CUTOUT } from '../engine/blocks'
import { blockAt, SEA_LEVEL, terrainHeight } from '../engine/worldgen'
import { WorldStore } from '../engine/worldStore'
import {
  composeMap, fogColor, isMapKey, loadMapOpen, MAP_BLOCKS, MAP_RADIUS, mapMarks, mapOrigin, mapShownByDefault, naturalTop, PATCH,
  PatchCache, patchPixels, saveMapOpen, seenPatches, spreadMarks, toMap, topBlock, topColor, travelHeading, UNKNOWN,
} from './overheadMap'
import type { Built, MimoAction } from './types'

const SEED = '13897963875510148821'
// Far from the origin, as every survival life is: generated terrain with water, trees and hills.
const FAR = { x: 3712, z: 4096 }

/** The first block from above that the map shows: not air, and not a small wild plant. */
function scanned(x: number, z: number): { id: number; y: number } {
  for (let y = 40; y > -8; y--) {
    const id = blockId(blockAt(x, y, z, SEED))
    if (id !== AIR && LAYER_BY_ID[id] !== LAYER_CUTOUT) return { id, y }
  }
  return { id: AIR, y: -8 }
}

describe('minimap layout', () => {
  it('centres Mimo, 96 blocks each way, with north (-z) up and east (+x) right', () => {
    const origin = mapOrigin({ x: 100.4, y: 5, z: -20.6 })
    expect(origin).toEqual({ x: 100 - MAP_RADIUS, z: -21 - MAP_RADIUS })
    expect(MAP_BLOCKS).toBe(2 * MAP_RADIUS)
    expect(toMap(100, -21, origin)).toEqual({ px: MAP_RADIUS + 0.5, py: MAP_RADIUS + 0.5 })
    const north = toMap(100, -31, origin)
    const east = toMap(110, -21, origin)
    expect(north.py).toBeLessThan(MAP_RADIUS)
    expect(east.px).toBeGreaterThan(MAP_RADIUS)
  })

  it('counts the patch Mimo stands in as seen, as well as the explored ones', () => {
    const seen = seenPatches([[1, 2, 3], [-1, -1, 1]], { x: 20, y: 5, z: 20 })
    expect([...seen].sort()).toEqual(['-1,-1', '1,2', '2,2'])
    expect([...seenPatches(undefined, { x: -1, y: 5, z: -9 })]).toEqual(['-1,-2'])
  })
})

describe('the terrain seen from above', () => {
  it('matches the 3D world column by column: ground, water and tree tops', () => {
    const kinds = new Set<number>()
    for (let x = FAR.x; x < FAR.x + 64; x += 3) {
      for (let z = FAR.z; z < FAR.z + 64; z += 3) {
        const top = naturalTop(x, z, SEED)
        expect({ x, z, id: top.id, y: top.y }).toEqual({ x, z, ...scanned(x, z) })
        kinds.add(top.id)
      }
    }
    expect(kinds.size).toBeGreaterThan(1)
  })

  it('shows water as water, deeper the lower the ground under it', () => {
    let found = false
    for (let x = FAR.x - 300; x < FAR.x + 300 && !found; x += 2) {
      for (let z = FAR.z - 300; z < FAR.z + 300 && !found; z += 2) {
        if (terrainHeight(x, z, SEED) >= SEA_LEVEL) continue
        const top = naturalTop(x, z, SEED)
        expect(top).toEqual({ id: blockId('water'), y: SEA_LEVEL, depth: SEA_LEVEL - terrainHeight(x, z, SEED) })
        found = true
      }
    }
    expect(found).toBe(true)
  })

  it('lets Mimo’s edits show: what it placed, what it dug and what it planted', () => {
    const store = new WorldStore(SEED)
    const { x, z } = FAR
    const ground = naturalTop(x, z, SEED)
    expect(topBlock(store, x, z)).toEqual(ground)
    store.applyServerChanges([{ x, y: ground.y + 3, z, material: 'planks' }])
    expect(topBlock(store, x, z)).toMatchObject({ id: blockId('planks'), y: ground.y + 3 })
    store.applyServerChanges([{ x, y: ground.y + 3, z, material: 'air' }, { x, y: ground.y, z, material: 'air' }])
    expect(topBlock(store, x, z).y).toBeLessThan(ground.y)
    const beside = naturalTop(x + 1, z, SEED)
    store.applyServerChanges([{ x: x + 1, y: beside.y + 1, z, material: 'wheat_2' }])
    expect(topBlock(store, x + 1, z)).toMatchObject({ id: blockId('wheat_2'), y: beside.y + 1 })
  })

  it('colours by the soft-pixel palette, a little darker low and in deep water, lighter high', () => {
    const grass = blockId('grass')
    const low = topColor({ id: grass, y: 3, depth: 0 })
    const high = topColor({ id: grass, y: 14, depth: 0 })
    expect(high[1]).toBeGreaterThan(low[1])
    const shallow = topColor({ id: blockId('water'), y: SEA_LEVEL, depth: 1 })
    const deep = topColor({ id: blockId('water'), y: SEA_LEVEL, depth: 2 })
    expect(deep[2]).toBeLessThan(shallow[2])
    expect(shallow[2]).toBeGreaterThan(shallow[0])  // water reads blue
    expect(low[1]).toBeGreaterThan(low[0])  // grass reads green
    const sand = topColor({ id: blockId('sand'), y: 5, depth: 0 })
    expect(sand[0]).toBeGreaterThan(sand[2])
  })

  it('greys out land Mimo has not seen, keeping a faint shape', () => {
    const green: [number, number, number] = [120, 180, 110]
    const dark: [number, number, number] = [60, 90, 55]
    const fogged = fogColor(green)
    const spread = (rgb: readonly number[]) => Math.max(...rgb) - Math.min(...rgb)
    expect(spread(fogged)).toBeLessThan(spread(green) / 2)
    expect(fogged[1]).toBeLessThan(green[1])
    expect(fogColor(dark)[1]).toBeLessThan(fogged[1])  // the shape still shows through
  })
})

describe('patches and the composed map', () => {
  it('draws one pixel per block of a patch, north row first', () => {
    const store = new WorldStore(SEED)
    const rx = Math.floor(FAR.x / PATCH), rz = Math.floor(FAR.z / PATCH)
    const pixels = patchPixels(store, rx, rz)
    expect(pixels.length).toBe(PATCH * PATCH * 4)
    const [r, g, b] = topColor(topBlock(store, rx * PATCH + 3, rz * PATCH + 5))
    const at = (5 * PATCH + 3) * 4
    // The relief shade may lift or lower a pixel a little from its plain colour.
    expect(Math.abs(pixels[at] - r)).toBeLessThanOrEqual(16)
    expect(Math.abs(pixels[at + 1] - g)).toBeLessThanOrEqual(16)
    expect(Math.abs(pixels[at + 2] - b)).toBeLessThanOrEqual(16)
    expect(pixels[at + 3]).toBe(255)
  })

  it('computes each patch once, within a budget per draw, and again after an edit in its chunk', () => {
    const store = new WorldStore(SEED)
    const computed: string[] = []
    const cache = new PatchCache(store, (rx, rz) => {
      computed.push(`${rx},${rz}`)
      return new Uint8ClampedArray(PATCH * PATCH * 4)
    })
    const stop = store.subscribe((columns) => cache.invalidate(columns))
    const wanted: [number, number][] = [[0, 0], [1, 0], [2, 0], [3, 0], [0, 2], [0, 3]]
    expect(cache.fill(wanted, 3)).toBe(3)
    expect(cache.get(3, 0)).toBeNull()
    expect(cache.fill(wanted, 3)).toBe(3)
    expect(computed).toEqual(['0,0', '1,0', '2,0', '3,0', '0,2', '0,3'])
    expect(cache.get(0, 0)).not.toBeNull()
    // Chunk 0,0 holds patches 0..1 each way. The row south of it (rz = 2) shades its hills by
    // looking north into the chunk, so it is worked out again too; rz = 3 is not.
    store.applyServerChanges([{ x: 5, y: 9, z: 5, material: 'planks' }])
    cache.fill(wanted, 10)
    expect(computed.slice(6)).toEqual(['0,0', '1,0', '0,2'])
    stop()
    store.applyServerChanges([{ x: 20, y: 9, z: 5, material: 'planks' }])  // chunk 1,0: patches 2..3
    cache.fill(wanted, 10)
    expect(computed.length).toBe(9)  // nothing told the cache this time
  })

  it('composes seen patches in colour, the rest greyed, and patches not drawn yet as unknown', () => {
    const size = 16
    const out = new Uint8ClampedArray(size * size * 4)
    const red = new Uint8ClampedArray(PATCH * PATCH * 4).map((_, i) => (i % 4 === 0 || i % 4 === 3 ? 255 : 0))
    composeMap(out, size, { x: -4, z: 0 }, (rx) => (rx === 1 ? null : red), (rx) => rx === -1)
    const pixel = (px: number, py: number) => Array.from(out.slice((py * size + px) * 4, (py * size + px) * 4 + 4))
    expect(pixel(0, 0)).toEqual([255, 0, 0, 255])  // x = -4: patch -1, seen
    expect(pixel(4, 3)).toEqual([...fogColor([255, 0, 0]), 255])  // x = 0: patch 0, never visited
    expect(pixel(12, 15)).toEqual([...fogColor(UNKNOWN), 255])  // x = 8: patch 1, not drawn yet
  })
})

describe('what the minimap marks', () => {
  const walk = (points: [number, number][]): MimoAction => ({
    kind: 'walk', started_at: 0, ends_at: 10,
    path: points.map(([x, z], i) => ({ x, y: 5, z, at: i })),
  })

  it('points Mimo the way it walks, or nowhere when it stands still', () => {
    expect(travelHeading(walk([[0, 0], [1, 0], [2, 0]]), { x: 1, y: 5, z: 0 })).toBeCloseTo(0)
    expect(travelHeading(walk([[0, 0], [0, -1], [0, -2]]), { x: 0, y: 5, z: -2 })).toBeCloseTo(-Math.PI / 2)
    expect(travelHeading(null, { x: 0, y: 5, z: 0 })).toBeNull()
    expect(travelHeading({ kind: 'mine', started_at: 0, ends_at: 1 }, { x: 0, y: 5, z: 0 })).toBeNull()
  })

  it('marks home and the farm once each, from what Mimo built or remembers, inside the map only', () => {
    const origin = mapOrigin({ x: 0, y: 5, z: 0 })
    const built: Built[] = [
      { id: 1, kind: 'shelter', name: 'Snug Cottage', status: 'done', x: 10, y: 5, z: -4 },
      { id: 2, kind: 'farm', name: 'Farm', status: 'building', x: -30, y: 5, z: 12 },
    ]
    const landmarks = [{ kind: 'home' as const, x: 11, y: 5, z: -4 }, { kind: 'farm' as const, x: 150, y: 5, z: 0 }]
    expect(mapMarks(built, landmarks, origin)).toEqual([
      { kind: 'home', building: false, ...toMap(10, -4, origin) },
      { kind: 'farm', building: true, ...toMap(-30, 12, origin) },
    ])
    expect(mapMarks([], [{ kind: 'home', x: 2, y: 5, z: 3 }], origin)).toEqual([
      { kind: 'home', building: false, ...toMap(2, 3, origin) },
    ])
    expect(mapMarks(undefined, undefined, origin)).toEqual([])
  })

  it('pushes a farm glyph off the house glyph when they would overlap, and leaves far ones be', () => {
    const home = { kind: 'home' as const, building: false, px: 50, py: 50 }
    const east = { kind: 'farm' as const, building: false, px: 56, py: 50 }
    const far = { kind: 'farm' as const, building: true, px: 90, py: 20 }
    const on = { kind: 'farm' as const, building: false, px: 50, py: 50 }
    expect(spreadMarks([home, east, far, on], 16)).toEqual([
      home, { ...east, px: 66 }, far, { ...on, px: 34 },
    ])
    expect(spreadMarks([east], 16)).toEqual([east])
  })
})

describe('showing and hiding the map', () => {
  it('toggles on M, but not while typing or with a modifier held', () => {
    expect(isMapKey({ key: 'm' })).toBe(true)
    expect(isMapKey({ key: 'M', shiftKey: true })).toBe(true)
    expect(isMapKey({ key: 'n' })).toBe(false)
    expect(isMapKey({ key: 'm', ctrlKey: true })).toBe(false)
    expect(isMapKey({ key: 'm', metaKey: true })).toBe(false)
    expect(isMapKey({ key: 'm', target: { tagName: 'INPUT' } })).toBe(false)
    expect(isMapKey({ key: 'm', target: { tagName: 'DIV', isContentEditable: true } })).toBe(false)
  })

  it('remembers the choice, and survives blocked or full storage', () => {
    const saved: Record<string, string> = {}
    const storage = { getItem: (key: string) => saved[key] ?? null, setItem: (key: string, value: string) => { saved[key] = value } }
    expect(loadMapOpen(() => storage, true)).toBe(true)
    expect(loadMapOpen(() => storage, false)).toBe(false)
    saveMapOpen(() => storage, false)
    expect(loadMapOpen(() => storage, true)).toBe(false)
    saveMapOpen(() => storage, true)
    expect(loadMapOpen(() => storage, false)).toBe(true)  // shown on purpose, even on a short screen
    const blocked = () => { throw new Error('SecurityError') }
    expect(loadMapOpen(blocked, true)).toBe(true)
    expect(loadMapOpen(blocked, false)).toBe(false)
    expect(() => saveMapOpen(blocked, false)).not.toThrow()
  })

  it('starts hidden where it would cover the vitals: short phones and short windows', () => {
    expect(mapShownByDefault(375, 812)).toBe(true)
    expect(mapShownByDefault(375, 667)).toBe(true)
    expect(mapShownByDefault(375, 639)).toBe(false)
    expect(mapShownByDefault(360, 560)).toBe(false)
    expect(mapShownByDefault(1280, 800)).toBe(true)
    expect(mapShownByDefault(1280, 600)).toBe(true)
    expect(mapShownByDefault(1280, 560)).toBe(false)
  })
})

import { describe, expect, it } from 'vitest'
import { BAND_ALPHA, ELDER_STRENGTH, elderGlow, emissiveOf, ringBands, ringLine, ringTone } from './frontier'
import { MAP_BLOCKS, mapOrigin } from './overheadMap'

const FAR = { level: 2, name: 'Far wilds', center: { x: 0, z: 0 } }

describe('frontier', () => {
  it('names the ring Mimo stands in, and warns from the far wilds on', () => {
    expect(ringLine(FAR)).toBe('Far wilds · danger 2')
    expect(ringLine({ level: 0, name: 'Home ground', center: { x: 0, z: 0 } })).toBe('Home ground · danger 0')
    expect(ringLine(null)).toBeNull()
    expect(ringLine(undefined)).toBeNull()
    expect(ringTone(FAR)).toBe('wary')
    expect(ringTone({ ...FAR, level: 1 })).toBe('calm')
  })

  it('shades the bands around home that reach onto the map, each danger a little darker', () => {
    const home = ringBands(FAR, mapOrigin({ x: 0, y: 1, z: 0 }))
    expect(home.map((band) => band.level)).toEqual([1, 2])  // 96 blocks each way: the near and far wilds
    expect(home.map((band) => [band.inner, band.outer])).toEqual([[48, 128], [128, 256]])
    expect(home[0]).toMatchObject({ px: MAP_BLOCKS / 2 + 0.5, py: MAP_BLOCKS / 2 + 0.5, alpha: BAND_ALPHA })
    expect(home[1].alpha).toBeCloseTo(2 * BAND_ALPHA)
    const out = ringBands(FAR, mapOrigin({ x: 600, y: 1, z: 0 }))
    expect(out.map((band) => band.level)).toEqual([3, 4])  // 504 to 696 blocks from home
    expect(out[1].outer).toBeGreaterThan(700)
    expect(ringBands(null, mapOrigin({ x: 0, y: 1, z: 0 }))).toEqual([])
  })

  it('lights an elder faintly, and a blow still flashes red over it', () => {
    expect(elderGlow({ elder: true })).toBe(ELDER_STRENGTH)
    expect(elderGlow({})).toBe(0)
    expect(emissiveOf(0, 0)).toEqual([0, 0, 0])
    const [r, g, b] = emissiveOf(0, ELDER_STRENGTH)
    expect(b).toBeGreaterThan(r)
    expect(g).toBeGreaterThan(0)
    expect(emissiveOf(1, ELDER_STRENGTH)).toEqual([0.9, 0.12, 0.1])
  })
})

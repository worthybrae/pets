import { describe, expect, it } from 'vitest'
import {
  blockEffects, burst, CRACK_STAGES, crackMask, crackStage, crackTexels, itemPop, leafPuffs, placeScale, PUFF_SECONDS,
  puffBits, puffStarts,
} from './effects'
import type { FinishedAction, MimoAction } from './types'

const mine: MimoAction = { kind: 'mine', started_at: 10, ends_at: 12, target: { x: 1, y: 2, z: 3 }, block: 'stone' }

describe('cracks', () => {
  it('grow with mining progress', () => {
    expect(crackStage(null, 11)).toBe(0)
    expect(crackStage({ ...mine, kind: 'place' }, 11)).toBe(0)
    expect(crackStage(mine, 10)).toBe(0)
    expect(crackStage(mine, 10.01)).toBe(1)
    expect(crackStage(mine, 11)).toBe(4)
    expect(crackStage(mine, 12)).toBe(CRACK_STAGES)
    expect(crackStage(mine, 15)).toBe(CRACK_STAGES)
  })

  it('add pixels at every stage and keep the earlier ones', () => {
    const counts = Array.from({ length: CRACK_STAGES + 1 }, (_, stage) => crackMask(stage).reduce((sum, value) => sum + value, 0))
    expect(counts).toEqual([0, 1, 4, 8, 13, 16, 19])
    for (let stage = 1; stage <= CRACK_STAGES; stage++) {
      const after = crackMask(stage)
      crackMask(stage - 1).forEach((value, index) => { if (value) expect(after[index]).toBe(1) })
    }
  })

  it('paint dark see-through texels with the top row stored last', () => {
    const texels = crackTexels(CRACK_STAGES)
    let shown = 0
    for (let i = 3; i < texels.length; i += 4) if (texels[i] > 0) shown++
    expect(shown).toBe(19)
    expect(texels[(7 * 8 + 5) * 4 + 3]).toBe(190)
    expect(crackTexels(0).every((value) => value === 0)).toBe(true)
  })
})

describe('placing and breaking', () => {
  it('bounces a placed block in from 0.6', () => {
    expect(placeScale(0)).toBe(0.6)
    expect(Math.max(...[0.05, 0.1, 0.15, 0.2, 0.25, 0.3].map(placeScale))).toBeGreaterThan(1)
    expect(placeScale(0.35)).toBe(1)
    expect(placeScale(2)).toBe(1)
  })

  it('throws particles out and up, then gravity pulls them down', () => {
    expect(burst(8, 0).every((point) => point.x === 0 && point.y === 0 && point.z === 0)).toBe(true)
    const early = burst(8, 0.1)
    expect(early).toHaveLength(8)
    expect(early.every((point) => point.y > 0)).toBe(true)
    expect(burst(8, 0.6)[0].y).toBeLessThan(0)
  })

  it('pops the item from the block to the pet', () => {
    const from = { x: 0, y: 0, z: 0 }
    const to = { x: 2, y: 1, z: 0 }
    expect(itemPop(0, from, to)).toEqual({ position: from, scale: 1 })
    const end = itemPop(0.6, from, to)
    expect(end.position.x).toBeCloseTo(2)
    expect(end.position.y).toBeCloseTo(1)
    expect(end.scale).toBeCloseTo(0.3)
  })
})

describe('blockEffects', () => {
  it('lists finished breaks and placements once each, with the running step', () => {
    const recent: FinishedAction[] = [
      { kind: 'mine', started_at: 1, ended_at: 3, result: 'done', target: { x: 5, y: 1, z: 0 }, block: 'oak_log' },
      { kind: 'place', started_at: 3, ended_at: 3.3, result: 'done', target: { x: 4, y: 1, z: 0 }, block: 'planks' },
      { kind: 'mine', started_at: 4, ended_at: 4, result: 'failed', target: { x: 9, y: 1, z: 0 }, reason: 'out of reach' },
      { kind: 'craft', started_at: 5, ended_at: 6, result: 'done', recipe: 'planks' },
      { kind: 'mine', started_at: 10, ended_at: 12, result: 'done', target: { x: 1, y: 2, z: 3 }, block: 'stone' },
    ]
    const effects = blockEffects(mine, recent)
    expect(effects.map((effect) => [effect.kind, effect.at])).toEqual([['break', 3], ['place', 3.3], ['break', 12]])
    expect(effects[2].key).toBe('mine:1,2,3:12')
  })
})

describe('food, farm and leaf effects', () => {
  it('bursts when Mimo picks or harvests, like a break', () => {
    const recent: FinishedAction[] = [
      { kind: 'pick', started_at: 1, ended_at: 1.5, result: 'done', target: { x: 2, y: 1, z: 0 }, block: 'berry_bush_ripe' },
      { kind: 'harvest', started_at: 2, ended_at: 2.5, result: 'done', target: { x: 3, y: 1, z: 0 }, block: 'wheat_3' },
      { kind: 'till', started_at: 3, ended_at: 4, result: 'done', target: { x: 3, y: 0, z: 0 }, block: 'grass' },
    ]
    expect(blockEffects(null, recent).map((effect) => [effect.kind, effect.block])).toEqual([
      ['break', 'berry_bush_ripe'], ['break', 'wheat_3'],
    ])
  })

  it('shows a puff for each leaf that went in the last moment', () => {
    const decays = [{ x: 1, y: 6, z: 1, at: 10 }, { x: 2, y: 6, z: 1, at: 10.5 }, { x: 3, y: 6, z: 1, at: 20 }]
    expect(leafPuffs(decays, 10.6).map((puff) => [puff.cell.x, Number(puff.age.toFixed(2))])).toEqual([[1, 0.6], [2, 0.1]])
    expect(leafPuffs(decays, 10 + PUFF_SECONDS + 0.01).map((puff) => puff.cell.x)).toEqual([2])
    expect(leafPuffs(decays, 5)).toEqual([])
  })

  it('plays a puff that reached the viewer late from the start instead of skipping it', () => {
    const late = { x: 1, y: 6, z: 1, at: 10 }
    const coming = { x: 2, y: 6, z: 1, at: 13 }
    // First seen at 12, well after the leaf went at 10: its puff starts at 12.
    const seen = puffStarts([late, coming], 12, new Map())
    expect([...seen.values()]).toEqual([12, 13])
    expect(leafPuffs([late], 12, seen).map((puff) => puff.age)).toEqual([0])
    expect(leafPuffs([late], 12.5, puffStarts([late], 12.5, seen)).map((puff) => puff.age)).toEqual([0.5])
    expect(leafPuffs([late], 12 + PUFF_SECONDS, seen)).toEqual([])
    // A start is kept while the decay is listed, and forgotten once it is not.
    expect(puffStarts([late], 30, seen).get('1,6,1:10')).toBe(12)
    expect(puffStarts([coming], 30, seen).size).toBe(1)
  })

  it('spreads a puff out as it fades', () => {
    const start = puffBits(6, 0)
    const late = puffBits(6, PUFF_SECONDS * 0.9)
    expect(start.offsets).toHaveLength(6)
    expect(start.scale).toBe(1)
    expect(late.scale).toBeCloseTo(0.1)
    expect(Math.hypot(late.offsets[0].x, late.offsets[0].z)).toBeGreaterThan(Math.hypot(start.offsets[0].x, start.offsets[0].z))
    expect(late.offsets[0].y).toBeLessThan(start.offsets[0].y)
  })
})

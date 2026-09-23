import { describe, expect, it } from 'vitest'
import { blockEffects, burst, CRACK_STAGES, crackMask, crackStage, crackTexels, itemPop, placeScale } from './effects'
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

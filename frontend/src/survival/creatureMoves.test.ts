import { describe, expect, it } from 'vitest'
import { MOVE_MEMORY, mergeMoves } from './creatureMoves'
import type { CreatureMove } from './types'

function hop(id: number, started: number, ends: number, x = 0): CreatureMove {
  return { id, from: { x, y: 5, z: 0 }, to: { x: x + 1, y: 5, z: 0 }, started, ends }
}

describe('mergeMoves', () => {
  it('keeps each creature\'s moves from poll to poll, oldest first', () => {
    const walk = hop(3, 100, 102)
    const flee = hop(3, 101.2, 103, 1)
    const other = hop(4, 100.5, 101)
    const first = mergeMoves(new Map(), [walk, other], 99)
    expect(first.get(3)).toEqual([walk])
    const second = mergeMoves(first, [flee], 100)
    expect(second.get(3)).toEqual([walk, flee])
    expect(second.get(4)).toEqual([other])
    expect(mergeMoves(new Map(), [flee, walk], 100).get(3)).toEqual([walk, flee])
  })

  it('takes the newest copy of a move the server sends again, such as one cut short by a death', () => {
    const flee = hop(3, 101, 104)
    const cut = { ...flee, ends: 102 }
    const merged = mergeMoves(mergeMoves(new Map(), [flee], 100), [cut], 101)
    expect(merged.get(3)).toEqual([cut])
    expect(merged.get(3)?.[0]).toBe(cut)
  })

  it('forgets moves that ended more than a few seconds before the replay time, and creatures with none left', () => {
    const old = hop(3, 90, 95)
    const recent = hop(3, 96, 98)
    const merged = mergeMoves(new Map([[3, [old, recent]], [5, [hop(5, 80, 81)]]]), undefined, 95 + MOVE_MEMORY + 0.5)
    expect(merged.get(3)).toEqual([recent])
    expect(merged.has(5)).toBe(false)
    expect(mergeMoves(new Map(), [hop(6, 10, 11)], 100).size).toBe(0)
  })

  it('leaves the history it was given as it was', () => {
    const walk = hop(3, 100, 102)
    const history = new Map([[3, [walk]]])
    mergeMoves(history, [hop(3, 101, 103)], 200)
    expect(history.get(3)).toEqual([walk])
    expect(history.size).toBe(1)
  })
})

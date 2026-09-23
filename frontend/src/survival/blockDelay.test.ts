import { describe, expect, it } from 'vitest'
import type { PlacedBlock } from '../engine/worldStore'
import { DelayedBlocks } from './blockDelay'
import { REPLAY_DELAY } from './replay'

const dug = (x: number): PlacedBlock => ({ x, y: 1, z: 0, material: 'air' })

function setup() {
  const applied: [PlacedBlock[], boolean][] = []
  const delayed = new DelayedBlocks((changes, reset) => { applied.push([changes, reset]) })
  return { applied, delayed }
}

describe('DelayedBlocks', () => {
  it('applies the first load at once', () => {
    const { applied, delayed } = setup()
    delayed.push([dug(1)], false, 10)
    expect(applied).toEqual([[[dug(1)], false]])
  })

  it('holds live changes for the replay delay, then applies them in order', () => {
    const { applied, delayed } = setup()
    delayed.goLive()
    delayed.push([dug(1)], false, 10)
    delayed.push([dug(2)], false, 10.5)
    expect(delayed.flush(10 + REPLAY_DELAY - 0.01)).toBe(0)
    expect(applied).toEqual([])
    expect(delayed.flush(10 + REPLAY_DELAY)).toBe(1)
    expect(delayed.flush(20)).toBe(1)
    expect(applied).toEqual([[[dug(1)], false], [[dug(2)], false]])
  })

  it('applies a reset at once, drops what it replaces and waits for the next go-live', () => {
    const { applied, delayed } = setup()
    delayed.goLive()
    delayed.push([dug(1)], false, 10)
    delayed.push([dug(2)], true, 10.2)
    delayed.push([dug(3)], false, 10.3)
    expect(applied).toEqual([[[dug(2)], true], [[dug(3)], false]])
    expect(delayed.flush(30)).toBe(0)
  })
})

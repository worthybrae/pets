import { describe, expect, it } from 'vitest'
import { poseAt } from './motion'
import { REPLAY_DELAY, replayAt } from './replay'
import type { FinishedAction, MimoAction } from './types'

const server = { x: 9, y: 1, z: 9 }
const shortWalk: FinishedAction = {
  kind: 'walk', started_at: 10, ended_at: 10.6, result: 'done',
  path: [{ x: 0, y: 1, z: 0, at: 10 }, { x: 1, y: 1, z: 0, at: 10.3 }, { x: 2, y: 1, z: 0, at: 10.6 }],
}
const mine: MimoAction = { kind: 'mine', started_at: 11, ends_at: 13, target: { x: 3, y: 1, z: 0 }, block: 'oak_log' }

describe('replayAt', () => {
  it('draws Mimo a moment behind the server', () => {
    expect(REPLAY_DELAY).toBe(1.5)
  })

  it('replays a short walk that started and ended between two polls', () => {
    const { step, rest } = replayAt(mine, [shortWalk], server, 10.3)
    expect(step).toMatchObject({ kind: 'walk', started_at: 10, ends_at: 10.6 })
    expect(poseAt(step, rest, 10.45).x).toBeCloseTo(1.5)
  })

  it('stands where the last path ended between steps', () => {
    expect(replayAt(mine, [shortWalk], server, 10.8)).toEqual({ step: null, rest: { x: 2, y: 1, z: 0 } })
  })

  it('plays the current step once its time comes', () => {
    expect(replayAt(mine, [shortWalk], server, 11.5)).toEqual({ step: mine, rest: { x: 2, y: 1, z: 0 } })
  })

  it('waits on the first cell of a walk that has not started yet', () => {
    const walk: MimoAction = {
      kind: 'walk', started_at: 20, ends_at: 20.3,
      path: [{ x: 5, y: 2, z: 5, at: 20 }, { x: 6, y: 2, z: 5, at: 20.3 }],
    }
    expect(replayAt(walk, [], server, 19)).toEqual({ step: null, rest: { x: 5, y: 2, z: 5 } })
  })

  it('rests on the last cell an interrupted walk reached', () => {
    const cut: FinishedAction = { ...shortWalk, ended_at: 10.4, result: 'interrupted', reason: 'head_home' }
    expect(replayAt(null, [cut], server, 12).rest).toEqual({ x: 1, y: 1, z: 0 })
  })

  it('falls back to the server position when no path says', () => {
    const craft: FinishedAction = { kind: 'craft', started_at: 1, ended_at: 2, result: 'done', recipe: 'planks' }
    expect(replayAt(null, [craft], server, 5)).toEqual({ step: null, rest: server })
  })
})

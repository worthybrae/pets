import { describe, expect, it } from 'vitest'
import { facingToward, focusPoint, poseAt, serverNow, turnToward } from './motion'
import type { MimoAction } from './types'

const walk: MimoAction = {
  kind: 'walk', started_at: 10, ends_at: 10.9,
  path: [
    { x: 0, y: 1, z: 0, at: 10 }, { x: 1, y: 1, z: 0, at: 10.3 },
    { x: 2, y: 2, z: 0, at: 10.6 }, { x: 2, y: 2, z: 1, at: 10.9, swim: true },
  ],
}
const rest = { x: 7, y: 3, z: 7 }

describe('serverNow', () => {
  it('adds the local time since the response arrived and never runs backwards', () => {
    expect(serverNow(1000, 50, 52.5)).toBe(1002.5)
    expect(serverNow(1000, 50, 49)).toBe(1000)
  })
})

describe('poseAt', () => {
  it('moves along a walk by arrival times', () => {
    const pose = poseAt(walk, rest, 10.15)
    expect(pose.x).toBeCloseTo(0.5)
    expect(pose.y).toBe(1)
    expect(pose.travelled).toBeCloseTo(0.5)
    expect(pose.facing).toBeCloseTo(Math.PI / 2)
  })

  it('climbs with a step up and faces each new direction', () => {
    const climbing = poseAt(walk, rest, 10.45)
    expect(climbing.x).toBeCloseTo(1.5)
    expect(climbing.y).toBeCloseTo(1.5)
    const turned = poseAt(walk, rest, 10.75)
    expect(turned.z).toBeCloseTo(0.5)
    expect(turned.facing).toBeCloseTo(0)
    expect(turned.swimming).toBe(true)
  })

  it('holds the ends of the path before the start and after the end', () => {
    expect(poseAt(walk, rest, 9)).toMatchObject({ x: 0, y: 1, z: 0 })
    expect(poseAt(walk, rest, 20)).toMatchObject({ x: 2, y: 2, z: 1, travelled: 3 })
  })

  it('drops faster and faster when falling', () => {
    const fall: MimoAction = {
      kind: 'fall', started_at: 0, ends_at: 1, blocks: 8,
      path: [{ x: 3, y: 9, z: 3, at: 0 }, { x: 3, y: 1, z: 3, at: 1 }],
    }
    expect(poseAt(fall, rest, 0.5).y).toBeCloseTo(7)
    expect(poseAt(fall, rest, 0.9).y).toBeCloseTo(9 - 8 * 0.81)
    expect(poseAt(fall, rest, 0.5).facing).toBeNull()
  })

  it('stands at the server position and faces the target of a block step', () => {
    const mine: MimoAction = { kind: 'mine', started_at: 0, ends_at: 2, target: { x: 8, y: 3, z: 8 }, block: 'oak_log' }
    expect(poseAt(mine, rest, 1)).toMatchObject({ x: 7, y: 3, z: 7, travelled: 0, swimming: false })
    expect(poseAt(mine, rest, 1).facing).toBeCloseTo(Math.PI / 4)
    expect(poseAt(null, rest, 1).facing).toBeNull()
  })
})

describe('focusPoint', () => {
  it('follows the same interpolated position poseAt renders, and rests at the server position with no action', () => {
    const pose = poseAt(walk, rest, 10.15)
    expect(focusPoint(walk, rest, 10.15)).toEqual({ x: pose.x, y: pose.y, z: pose.z })
    expect(focusPoint(null, rest, 5)).toEqual({ x: rest.x, y: rest.y, z: rest.z })
  })
})

describe('turning', () => {
  it('faces along the travel direction and turns the short way round', () => {
    expect(facingToward({ x: 0, z: 0 }, { x: 0, z: -1 })).toBeCloseTo(Math.PI)
    expect(facingToward({ x: 1, z: 1 }, { x: 1, z: 1 })).toBeNull()
    expect(turnToward(3, -3, 1)).toBeCloseTo(3 + (2 * Math.PI - 6))
    expect(turnToward(0, 1, 0.5)).toBeCloseTo(0.5)
  })
})

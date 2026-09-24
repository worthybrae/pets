import { describe, expect, it } from 'vitest'
import { AIR, blockId } from '../engine/blocks'
import type { Vec3 } from './camera'
import {
  AUTO_HOLD_SECONDS, CAMERA_MODES, CLOSE_CUT_MARGIN, CLOSE_DISTANCE, EYE_FORWARD, EYE_HEIGHT, HEAD_HEIGHT,
  MAX_CLOSE_DISTANCE, MAX_PITCH, MIN_CLOSE_DISTANCE, OVERVIEW_DIRECTION, SWITCH_SECONDS, autoMode, belowGround,
  closeCamera, cutawayFor, eyesCamera, eyesPitch, headingOf, hidesPet, isCameraKey, loadCameraMode, modeLabel, nextMode,
  overviewCamera, saveCameraMode, smoothYaw, switchFactor, zoomClose,
} from './cameraModes'
import { CUTAWAY_RADIUS, cutawayFor as terrainCutaway, cutsAway } from './cutaway'
import type { MimoAction } from './types'

const STONE = blockId('stone')

/** Stone at y <= 0 and air above, with single cells overridden by name. */
function ground(cells: Record<string, string> = {}) {
  return {
    getBlock(x: number, y: number, z: number): number {
      const named = cells[`${x},${y},${z}`]
      if (named) return named === 'air' ? AIR : blockId(named)
      return y <= 0 ? STONE : AIR
    },
  }
}

function expectVec(actual: Vec3, expected: Vec3) {
  expected.forEach((value, index) => expect(actual[index]).toBeCloseTo(value, 5))
}

/** The signed angle from `a` to `b` the short way round. */
function arc(a: number, b: number): number {
  return Math.atan2(Math.sin(b - a), Math.cos(b - a))
}

describe('the camera modes', () => {
  it('cycles auto, overview, close, eyes and back to auto', () => {
    expect(CAMERA_MODES).toEqual(['auto', 'overview', 'close', 'eyes'])
    expect(nextMode('auto')).toBe('overview')
    expect(nextMode('overview')).toBe('close')
    expect(nextMode('close')).toBe('eyes')
    expect(nextMode('eyes')).toBe('auto')
  })

  it('names the mode, with the pick when auto has made one', () => {
    expect(modeLabel('auto', 'close')).toBe('Auto (close)')
    expect(modeLabel('auto', 'overview')).toBe('Auto (overview)')
    expect(modeLabel('auto', null)).toBe('Auto')
    expect(modeLabel('eyes', 'close')).toBe('Eyes')
    expect(modeLabel('overview', 'close')).toBe('Overview')
  })

  it('cycles on C but not while typing or with a modifier held', () => {
    expect(isCameraKey({ key: 'c' })).toBe(true)
    expect(isCameraKey({ key: 'C', shiftKey: true })).toBe(true)
    expect(isCameraKey({ key: 'x' })).toBe(false)
    expect(isCameraKey({ key: 'c', ctrlKey: true })).toBe(false)
    expect(isCameraKey({ key: 'c', metaKey: true })).toBe(false)
    expect(isCameraKey({ key: 'c', altKey: true })).toBe(false)
    expect(isCameraKey({ key: 'c', target: { tagName: 'INPUT' } })).toBe(false)
    expect(isCameraKey({ key: 'c', target: { tagName: 'TEXTAREA' } })).toBe(false)
    expect(isCameraKey({ key: 'c', target: { tagName: 'SELECT' } })).toBe(false)
    expect(isCameraKey({ key: 'c', target: { tagName: 'DIV', isContentEditable: true } })).toBe(false)
    expect(isCameraKey({ key: 'c', target: { tagName: 'BUTTON' } })).toBe(true)
  })

  it('remembers the chosen mode, and falls back to auto when storage is empty, odd or blocked', () => {
    const saved: Record<string, string> = {}
    const storage = {
      getItem: (key: string) => saved[key] ?? null,
      setItem: (key: string, value: string) => { saved[key] = value },
    }
    expect(loadCameraMode(() => storage)).toBe('auto')
    saveCameraMode(() => storage, 'eyes')
    expect(loadCameraMode(() => storage)).toBe('eyes')
    saveCameraMode(() => storage, 'close')
    expect(loadCameraMode(() => storage)).toBe('close')
    expect(loadCameraMode(() => ({ getItem: () => 'sideways', setItem: () => {} }))).toBe('auto')
    const blocked = () => { throw new Error('SecurityError') }
    expect(loadCameraMode(blocked)).toBe('auto')
    expect(() => saveCameraMode(blocked, 'eyes')).not.toThrow()
    const full = { getItem: () => null, setItem: () => { throw new Error('QuotaExceededError') } }
    expect(() => saveCameraMode(() => full, 'eyes')).not.toThrow()
  })
})

describe('smoothYaw', () => {
  it('turns the short way across ±π and never spins through zero', () => {
    let yaw = 3.0
    for (let frame = 0; frame < 200; frame++) {
      yaw = smoothYaw(yaw, -3.0, 1 / 60, 4)
      expect(Math.abs(yaw)).toBeGreaterThan(2.99)
      expect(yaw).toBeGreaterThan(-Math.PI - 1e-9)
      expect(yaw).toBeLessThanOrEqual(Math.PI + 1e-9)
    }
    expect(yaw).toBeCloseTo(-3.0, 3)
  })

  it('turns the short way the other way round too', () => {
    const yaw = smoothYaw(-3.0, 3.0, 0.1, 4)
    expect(yaw).toBeLessThan(-3.0)
  })

  it('damps by elapsed time, not by frame count', () => {
    const once = smoothYaw(0.2, 2.5, 0.1, 3)
    const twice = smoothYaw(smoothYaw(0.2, 2.5, 0.05, 3), 2.5, 0.05, 3)
    expect(arc(once, twice)).toBeCloseTo(0, 6)
    expect(smoothYaw(1, 1, 0.5, 3)).toBeCloseTo(1)
  })
})

describe('headingOf', () => {
  const walk: MimoAction = {
    kind: 'walk', started_at: 0, ends_at: 2,
    path: [{ x: 0, y: 1, z: 0, at: 0 }, { x: 1, y: 1, z: 0, at: 1 }, { x: 1, y: 1, z: 1, at: 2 }],
  }
  const rest = { x: 0, y: 1, z: 0 }

  it('follows the direction of travel along a walk', () => {
    expect(headingOf(walk, rest, 0.5, 0)).toBeCloseTo(Math.PI / 2)  // toward +x
    expect(headingOf(walk, rest, 1.5, Math.PI / 2)).toBeCloseTo(0)  // toward +z
  })

  it('faces the target cell of a work step', () => {
    const mine: MimoAction = { kind: 'mine', started_at: 0, ends_at: 2, target: { x: -1, y: 1, z: 0 } }
    expect(headingOf(mine, rest, 1, 0)).toBeCloseTo(-Math.PI / 2)
    const harvest: MimoAction = { kind: 'harvest', started_at: 0, ends_at: 2, target: { x: 0, y: 1, z: -2 } }
    expect(Math.abs(headingOf(harvest, rest, 1, 0))).toBeCloseTo(Math.PI)
    for (const kind of ['place', 'pick', 'till', 'plant', 'fish', 'cook', 'eat', 'craft'] as const) {
      expect(headingOf({ kind, started_at: 0, ends_at: 2, target: { x: 3, y: 1, z: 0 } }, rest, 1, 0)).toBeCloseTo(Math.PI / 2)
    }
  })

  it('keeps the last heading otherwise', () => {
    expect(headingOf(null, rest, 1, 0.7)).toBe(0.7)
    expect(headingOf({ kind: 'wait', started_at: 0, ends_at: 2 }, rest, 1, 0.7)).toBe(0.7)
    expect(headingOf({ kind: 'sleep', started_at: 0, ends_at: null, target: { x: 3, y: 1, z: 0 } }, rest, 1, 0.7)).toBe(0.7)
    expect(headingOf({ kind: 'mine', started_at: 0, ends_at: 2 }, rest, 1, 0.7)).toBe(0.7)  // no target
    expect(headingOf({ kind: 'mine', started_at: 0, ends_at: 2, target: { x: 0, y: 0, z: 0 } }, rest, 1, 0.7)).toBe(0.7)  // straight down
    const fall: MimoAction = { kind: 'fall', started_at: 0, ends_at: 1, path: [{ x: 0, y: 5, z: 0, at: 0 }, { x: 0, y: 1, z: 0, at: 1 }] }
    expect(headingOf(fall, rest, 0.5, 0.7)).toBe(0.7)
  })
})

describe('closeCamera', () => {
  it('sits behind Pip along its heading and above, looking at its head', () => {
    const shot = closeCamera([10, 4, 20], 0, CLOSE_DISTANCE)
    expectVec(shot.position, [10, 4 + 3, 20 - 5])
    expectVec(shot.lookAt, [10, 4 + HEAD_HEIGHT, 20])
    const east = closeCamera([10, 4, 20], Math.PI / 2, CLOSE_DISTANCE)
    expectVec(east.position, [5, 7, 20])
  })

  it('keeps the same angle when the wheel moves it nearer or farther', () => {
    const far = closeCamera([0, 0, 0], 0, 10)
    expectVec(far.position, [0, 6, -10])
  })

  it('writes into a reused shot when one is given', () => {
    const out = { position: [0, 0, 0] as Vec3, lookAt: [0, 0, 0] as Vec3 }
    expect(closeCamera([1, 2, 3], 0, 5, out)).toBe(out)
    expectVec(out.position, [1, 5, -2])
  })
})

describe('zoomClose', () => {
  it('moves out on wheel down and in on wheel up, between 3 and 10 blocks', () => {
    expect(zoomClose(5, 100)).toBeGreaterThan(5)
    expect(zoomClose(5, -100)).toBeLessThan(5)
    expect(zoomClose(9.9, 5000)).toBe(MAX_CLOSE_DISTANCE)
    expect(zoomClose(3.1, -5000)).toBe(MIN_CLOSE_DISTANCE)
    expect([MIN_CLOSE_DISTANCE, MAX_CLOSE_DISTANCE]).toEqual([3, 10])
  })
})

describe('eyesCamera', () => {
  it('sits at Pip\'s eye, nudged forward, looking along the heading', () => {
    const shot = eyesCamera([10, 4, 20], 0, 0)
    expectVec(shot.position, [10, 4 + EYE_HEIGHT, 20 + EYE_FORWARD])
    expect(shot.lookAt[0]).toBeCloseTo(10)
    expect(shot.lookAt[1]).toBeCloseTo(4 + EYE_HEIGHT)
    expect(shot.lookAt[2]).toBeGreaterThan(20 + EYE_FORWARD + 1)
    const west = eyesCamera([10, 4, 20], -Math.PI / 2, 0)
    expectVec(west.position, [10 - EYE_FORWARD, 4 + EYE_HEIGHT, 20])
    expect(west.lookAt[0]).toBeLessThan(10 - EYE_FORWARD - 1)
  })

  it('tilts down with a negative pitch, clamped to about 60 degrees', () => {
    const down = eyesCamera([0, 0, 0], 0, -Math.PI / 4)
    const [dx, dy, dz] = down.lookAt.map((value, index) => value - down.position[index])
    expect(Math.atan2(dy, Math.hypot(dx, dz))).toBeCloseTo(-Math.PI / 4)
    const steep = eyesCamera([0, 0, 0], 0, -1.5)
    const [sx, sy, sz] = steep.lookAt.map((value, index) => value - steep.position[index])
    expect(Math.atan2(sy, Math.hypot(sx, sz))).toBeCloseTo(-MAX_PITCH)
    expect(MAX_PITCH).toBeCloseTo(Math.PI / 3)
  })
})

describe('eyesPitch', () => {
  const feet: Vec3 = [0.5, 0, 0.5]  // Pip in cell (0, 0, 0), facing +z

  it('tilts down toward a work target below eye level and up toward one above', () => {
    const below = eyesPitch(feet, 0, { x: 0, y: -1, z: 3 })
    expect(below).toBeLessThan(0)
    expect(below).toBeCloseTo(Math.atan2(-0.5 - EYE_HEIGHT, 3.5 - (0.5 + EYE_FORWARD)))
    const above = eyesPitch(feet, 0, { x: 0, y: 2, z: 2 })
    expect(above).toBeGreaterThan(0)
    expect(above).toBeCloseTo(Math.atan2(2.5 - EYE_HEIGHT, 2.5 - (0.5 + EYE_FORWARD)))
  })

  it('clamps to about ±60 degrees, and is level without a target', () => {
    expect(eyesPitch(feet, 0, { x: 0, y: -1, z: 0 })).toBeCloseTo(-MAX_PITCH)
    expect(eyesPitch(feet, 0, { x: 0, y: 3, z: 0 })).toBeCloseTo(MAX_PITCH)
    expect(eyesPitch(feet, 0, null)).toBe(0)
  })
})

describe('hidesPet', () => {
  it('is true with the camera at Pip\'s eye and false from the close camera', () => {
    const feet: Vec3 = [3.5, 2, 7.5]
    expect(hidesPet(eyesCamera(feet, 1, 0).position, feet)).toBe(true)
    expect(hidesPet(closeCamera(feet, 1, MIN_CLOSE_DISTANCE).position, feet)).toBe(false)
  })
})

describe('overviewCamera', () => {
  it('is where today\'s follow camera settles: along the normal direction, looking at the focus', () => {
    const shot = overviewCamera([4, 2, 6], 26)
    const length = Math.hypot(...OVERVIEW_DIRECTION)
    expectVec(shot.position, [4 + (18 / length) * 26, 2 + (13 / length) * 26, 6 + (18 / length) * 26])
    expectVec(shot.lookAt, [4, 2, 6])
  })
})

describe('autoMode', () => {
  it('switches to close once Pip has been underground for 1.5 s, not before', () => {
    expect(AUTO_HOLD_SECONDS).toBe(1.5)
    expect(autoMode('overview', true, 10, 11.4)).toBe('overview')
    expect(autoMode('overview', true, 10, 11.6)).toBe('close')
  })

  it('switches back to overview once Pip has been out for 1.5 s, not before', () => {
    expect(autoMode('close', false, 20, 21.4)).toBe('close')
    expect(autoMode('close', false, 20, 21.6)).toBe('overview')
  })

  it('stays put while the condition matches the current pick', () => {
    expect(autoMode('close', true, 0, 100)).toBe('close')
    expect(autoMode('overview', false, 0, 100)).toBe('overview')
  })
})

describe('belowGround', () => {
  // In `ground()` the natural ground's top block is at y 0.
  it('is true in a tunnel or dug home under the natural ground', () => {
    expect(belowGround(ground({ '0,-5,0': 'air' }), { x: 0, y: -5, z: 0 }, 0)).toBe(true)
    expect(belowGround(ground({ '0,-1,0': 'air' }), { x: 0, y: -1, z: 0 }, 0)).toBe(true)  // the ground's top block over it
  })

  it('is false in a roofed shelter standing on the ground, so auto keeps the overview there', () => {
    expect(belowGround(ground({ '0,3,0': 'planks' }), { x: 0, y: 1, z: 0 }, 0)).toBe(false)
  })

  it('is false in a pit open to the sky', () => {
    expect(belowGround(ground({ '0,0,0': 'air', '0,-1,0': 'air' }), { x: 0, y: -1, z: 0 }, 0)).toBe(false)
  })
})

describe('switchFactor', () => {
  it('arrives at the new shot after SWITCH_SECONDS', () => {
    expect(SWITCH_SECONDS).toBeCloseTo(0.4)
    const first = switchFactor(0, 1 / 60)
    expect(first).toBeGreaterThan(0)
    expect(first).toBeLessThan(0.1)
    expect(switchFactor(SWITCH_SECONDS - 1 / 60, 1 / 60)).toBeCloseTo(1)
    expect(switchFactor(1, 1 / 60)).toBe(1)
  })

  it('covers the same ground at any frame rate', () => {
    const goal = 10
    let fast = 0
    for (let frame = 0; frame < 12; frame++) fast += (goal - fast) * switchFactor(frame / 60, 1 / 60)
    let slow = 0
    for (let frame = 0; frame < 6; frame++) slow += (goal - slow) * switchFactor(frame / 30, 1 / 30)
    expect(fast).toBeCloseTo(slow, 6)
    expect(fast).toBeGreaterThan(0)
    expect(fast).toBeLessThan(goal)
  })
})

describe('cutawayFor a camera mode', () => {
  const tunnel = ground({ '0,-5,0': 'air' })
  const pose = { x: 0, y: -5, z: 0 }
  const camera = { x: 0.5, y: -2, z: -4.5 }
  /** A wall at x = 3 in front of Mimo (at 0, 1, 0), three blocks tall. */
  const walled = ground({ '3,1,0': 'cobblestone', '3,2,0': 'cobblestone', '3,3,0': 'cobblestone' })

  it('keeps today\'s cutaway in overview', () => {
    expect(cutawayFor('overview', tunnel, pose, camera)).toEqual(terrainCutaway(tunnel, pose, camera))
    expect(cutawayFor('overview', tunnel, pose, camera)?.radius).toBe(CUTAWAY_RADIUS)
  })

  it('cuts around Pip in close out to just past the camera, walls and roofs included', () => {
    const radius = CLOSE_DISTANCE + CLOSE_CUT_MARGIN
    expect(cutawayFor('close', tunnel, pose, camera, CLOSE_DISTANCE)).toEqual({ x: 0.5, y: -3.5, z: 0.5, radius })
    expect(cutawayFor('close', walled, { x: 0, y: 1, z: 0 }, { x: 5.5, y: 4, z: 0.5 }, CLOSE_DISTANCE))
      .toEqual({ x: 0.5, y: 2.5, z: 0.5, radius })
    expect(cutawayFor('close', ground(), { x: 0, y: 1, z: 0 }, camera, CLOSE_DISTANCE)).toBeNull()
    expect(radius).toBeLessThan(CUTAWAY_RADIUS)  // at the usual distance, still tighter than the overview's
  })

  it('never leaves the close camera in rock underground, however far the wheel moved it', () => {
    // Fix wave minor 5: the close camera sits 5 blocks back by default, and a fixed 4.5-block cut
    // left it inside the tunnel's rock.
    for (const distance of [MIN_CLOSE_DISTANCE, CLOSE_DISTANCE, 7.5, MAX_CLOSE_DISTANCE, 40]) {
      const [x, y, z] = closeCamera([0.5, -5, 0.5], 0.7, distance).position
      const at = { x, y, z }
      const cut = cutawayFor('close', tunnel, pose, at, distance)
      expect(cut).not.toBeNull()
      expect(cutsAway(at, cut!, at)).toBe(true)  // the camera's own spot is cut open
      expect(cut!.radius).toBeGreaterThanOrEqual(Math.hypot(x - 0.5, z - 0.5) + 1)
    }
  })

  it('turns the cutaway off in eyes, even underground or walled in', () => {
    expect(cutawayFor('eyes', tunnel, pose, camera)).toBeNull()
    expect(cutawayFor('eyes', walled, { x: 0, y: 1, z: 0 }, { x: 5.5, y: 4, z: 0.5 })).toBeNull()
  })
})

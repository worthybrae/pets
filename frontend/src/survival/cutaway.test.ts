import { describe, expect, it } from 'vitest'
import { AIR, blockId } from '../engine/blocks'
import {
  CUTAWAY_RADIUS, WALL_HOLD_SECONDS, cutawayFor, cutsAway, hidden, holdWallCut, shelterBlocks, underground,
} from './cutaway'
import type { Built } from './types'

const STONE = blockId('stone')

/** Stone at y <= 0 and air above, with single cells overridden by name: those are the blocks the
 * server says were placed (an overridden 'air' is a block mined out). */
function ground(cells: Record<string, string> = {}) {
  return {
    getBlock(x: number, y: number, z: number): number {
      const named = cells[`${x},${y},${z}`]
      if (named) return named === 'air' ? AIR : blockId(named)
      return y <= 0 ? STONE : AIR
    },
    placedAt(x: number, y: number, z: number): boolean {
      const named = cells[`${x},${y},${z}`]
      return named !== undefined && named !== 'air'
    },
  }
}

/** The shelter Mimo built, with its home cell at (1, 1, 0). */
const HOME: Built[] = [{ id: 1, kind: 'shelter', name: "Pip's Snug Cottage", status: 'done', x: 1, y: 1, z: 0 }]

/** A one-block tunnel cell dug at (0, -5, 0), with the rock over it. */
const tunnel = ground({ '0,-5,0': 'air' })

describe('underground', () => {
  it('is true with rock over Mimo within 12 blocks', () => {
    expect(underground(tunnel, { x: 0, y: -5, z: 0 })).toBe(true)
    const shaft = Object.fromEntries(Array.from({ length: 13 }, (_, i) => [`0,${-13 + i},0`, 'air']))
    expect(underground(ground(shaft), { x: 0, y: -13, z: 0 })).toBe(false)  // the rock at y 0 is 13 up
  })

  it('is false on open ground and under a tree canopy', () => {
    expect(underground(ground(), { x: 0, y: 1, z: 0 })).toBe(false)
    expect(underground(ground({ '0,4,0': 'leaves', '0,5,0': 'leaves' }), { x: 0, y: 1, z: 0 })).toBe(false)
  })

  it('counts a roof Mimo stands under', () => {
    expect(underground(ground({ '0,3,0': 'planks' }), { x: 0, y: 1, z: 0 })).toBe(true)
  })

  it('is false with a crafting table, furnace, lantern or glass in the headroom', () => {
    expect(underground(ground({ '0,2,0': 'crafting_table' }), { x: 0, y: 1, z: 0 })).toBe(false)
    expect(underground(ground({ '0,2,0': 'furnace' }), { x: 0, y: 1, z: 0 })).toBe(false)
    expect(underground(ground({ '0,2,0': 'lantern' }), { x: 0, y: 1, z: 0 })).toBe(false)
    expect(underground(ground({ '0,2,0': 'glass' }), { x: 0, y: 1, z: 0 })).toBe(false)
  })

  it('is false with a placed campfire, torch, bed or chest in the headroom', () => {
    expect(['campfire', 'torch', 'bed', 'chest'].map((name) =>
      underground(ground({ '0,2,0': name }), { x: 0, y: 1, z: 0 }))).toEqual([false, false, false, false])
  })
})

describe('a shelter Mimo built', () => {
  /** A wall at x = 3 in front of Mimo (at 0, 1, 0), `height` blocks tall, made of `block`. */
  const wall = (height: number, block = 'cobblestone') =>
    ground(Object.fromEntries(Array.from({ length: height }, (_, i) => [`3,${1 + i},0`, block])))
  const camera = { x: 18, y: 14, z: 0.5 }

  it('counts a dirt or cobblestone roof as cover', () => {
    expect(underground(ground({ '0,3,0': 'dirt' }), { x: 0, y: 1, z: 0 })).toBe(true)
    expect(underground(ground({ '0,4,0': 'cobblestone' }), { x: 0, y: 1, z: 0 })).toBe(true)
  })

  /** Whether `store`'s blocks hide Mimo at (0, 1, 0), counting only what shelterBlocks does. */
  const hides = (store: ReturnType<typeof ground>, from = camera, built = HOME) =>
    hidden(store, { x: 0, y: 1, z: 0 }, from, shelterBlocks(store, built))

  it('is hidden by a wall or roof it built reaching above the cut between it and the camera', () => {
    expect(hides(wall(3))).toBe(true)
    expect(hides(wall(2))).toBe(false)  // the cut would leave it anyway
    expect(hides(wall(3, 'leaves'))).toBe(false)
    expect(hides(wall(3), { x: -18, y: 14, z: 0.5 })).toBe(false)  // seen from the other side
  })

  it('is not hidden by a natural hill, or by blocks away from any shelter it built', () => {
    // Fix wave minor 2: the cut used to fire for any cover on the line to the camera.
    const hill = {
      getBlock: (x: number, y: number) => (y <= 0 || (x >= 3 && y <= 4) ? STONE : AIR),
      placedAt: () => false,
    }
    expect(underground(hill, { x: 0, y: 1, z: 0 })).toBe(false)
    expect(hidden(hill, { x: 0, y: 1, z: 0 }, camera, () => true)).toBe(true)  // it is in the way...
    expect(hidden(hill, { x: 0, y: 1, z: 0 }, camera, shelterBlocks(hill, HOME))).toBe(false)  // ...but not built
    expect(hides(wall(3), camera, [])).toBe(false)
    expect(hides(wall(3), camera, [{ ...HOME[0], x: 40 }])).toBe(false)
    expect(hides(wall(3), camera, [{ ...HOME[0], kind: 'farm' }])).toBe(false)
    expect(hides(wall(3, 'furnace'))).toBe(false)  // a placed station is not a wall
  })

  it('knows the blocks of a shelter from its home cell: three across, one below, four above', () => {
    const built = shelterBlocks(ground({ '4,1,3': 'planks', '5,1,0': 'planks', '1,5,0': 'cobblestone',
      '1,6,0': 'cobblestone', '1,0,0': 'dirt', '1,-1,0': 'dirt' }), HOME)
    expect([built(4, 1, 3), built(5, 1, 0), built(1, 5, 0), built(1, 6, 0), built(1, 0, 0), built(1, -1, 0)])
      .toEqual([true, false, true, false, true, false])
    expect(built(2, 2, 0)).toBe(false)  // air
  })

  it('does not count a natural dirt or cobblestone hill the server never placed', () => {
    // A hill made of building materials, right inside the shelter's own reach box, but never
    // placed by the server: shelterBlocks must not count it, or a natural hill beside a shelter
    // would cut the view open the same way a wall does.
    const hill = {
      getBlock: (x: number, y: number, z: number) =>
        (x === 2 && y === 3 && z === 0) ? blockId('dirt') : (y <= 0 ? STONE : AIR),
      placedAt: () => false,
    }
    expect(shelterBlocks(hill, HOME)(2, 3, 0)).toBe(false)
  })

  it('cuts the walls away when they hide the pet from the camera, and not in the open', () => {
    expect(cutawayFor(wall(3), { x: 0, y: 1, z: 0 }, true)).toEqual({ x: 0.5, y: 2.5, z: 0.5, radius: CUTAWAY_RADIUS })
    expect(cutawayFor(wall(3), { x: 0, y: 1, z: 0 })).toBeNull()
    expect(cutawayFor(ground(), { x: 0, y: 1, z: 0 }, false)).toBeNull()
  })
})

describe('holdWallCut', () => {
  it('cuts at once when a wall Mimo built hides it, and keeps cutting until none has for a moment', () => {
    // Fix wave minor 2: walking along a wall or orbiting past a corner must not make the cut flicker.
    let lastHidden: number | null = null
    const frame = (hiddenNow: boolean, now: number) => {
      const held = holdWallCut(hiddenNow, lastHidden, now)
      lastHidden = held.lastHidden
      return held.on
    }
    expect(frame(false, 0)).toBe(false)
    expect(frame(true, 1)).toBe(true)
    expect(frame(false, 1.1)).toBe(true)  // the line slipped past a corner for a frame
    expect(frame(true, 1.2)).toBe(true)
    expect(frame(false, 1.2 + WALL_HOLD_SECONDS - 0.01)).toBe(true)
    expect(frame(false, 1.2 + WALL_HOLD_SECONDS)).toBe(false)
    expect(frame(false, 9)).toBe(false)
    expect(WALL_HOLD_SECONDS).toBeGreaterThan(0.25)
    expect(WALL_HOLD_SECONDS).toBeLessThanOrEqual(1.5)
  })
})

describe('cutawayFor', () => {
  it('cuts above the pet, around where it is drawn, only when it is underground', () => {
    expect(cutawayFor(tunnel, { x: 0.2, y: -5, z: -0.1 })).toEqual({ x: 0.7, y: -3.5, z: 0.4, radius: CUTAWAY_RADIUS })
    expect(cutawayFor(ground(), { x: 0, y: 1, z: 0 })).toBeNull()
  })
})

describe('cutsAway', () => {
  const cut = { x: 0.5, y: -3.5, z: 0.5, radius: 8 }
  const camera = { x: 17, y: 7, z: 17 }

  it('keeps everything up to the cut height', () => {
    expect(cutsAway({ x: 0.5, y: -4, z: 0.5 }, cut, camera)).toBe(false)
    expect(cutsAway({ x: 3, y: -3.6, z: 3 }, cut, camera)).toBe(false)
  })

  it('cuts above the pet within the radius, and along the line of sight to the camera', () => {
    expect(cutsAway({ x: 6, y: 0, z: 0.5 }, cut, camera)).toBe(true)
    expect(cutsAway({ x: 9, y: 1, z: 9 }, cut, camera)).toBe(true)
  })

  it('keeps ground off to the side and behind the pet', () => {
    expect(cutsAway({ x: 13, y: 1, z: -13 }, cut, camera)).toBe(false)
    expect(cutsAway({ x: -12, y: 0, z: -12 }, cut, camera)).toBe(false)
  })
})

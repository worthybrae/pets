import { describe, expect, it } from 'vitest'
import { AIR, blockId } from '../engine/blocks'
import { CUTAWAY_RADIUS, cutawayFor, cutsAway, hidden, underground } from './cutaway'

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

  it('is hidden by a wall or roof reaching above the cut between it and the camera', () => {
    expect(hidden(wall(3), { x: 0, y: 1, z: 0 }, camera)).toBe(true)
    expect(hidden(wall(2), { x: 0, y: 1, z: 0 }, camera)).toBe(false)  // the cut would leave it anyway
    expect(hidden(wall(3, 'leaves'), { x: 0, y: 1, z: 0 }, camera)).toBe(false)
    expect(hidden(wall(3), { x: 0, y: 1, z: 0 }, { x: -18, y: 14, z: 0.5 })).toBe(false)  // seen from the other side
  })

  it('cuts the walls away when they hide the pet from the camera, and not in the open', () => {
    expect(cutawayFor(wall(3), { x: 0, y: 1, z: 0 }, camera)).toEqual({ x: 0.5, y: 2.5, z: 0.5, radius: CUTAWAY_RADIUS })
    expect(cutawayFor(wall(3), { x: 0, y: 1, z: 0 })).toBeNull()
    expect(cutawayFor(ground(), { x: 0, y: 1, z: 0 }, camera)).toBeNull()
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

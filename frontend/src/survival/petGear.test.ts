import { describe, expect, it } from 'vitest'
import { previewPet } from '../components/world/previewWorld'
import { HURT_GLOW_SECONDS, capVoxels, hurtGlow, tunicVoxels, wornCap, wornTunic } from './petGear'

const key = (voxel: { x: number; y: number; z: number }) => `${voxel.x},${voxel.y},${voxel.z}`

describe('petGear', () => {
  it('puts a tunic over the body and a cap on the head only when Mimo carries them', () => {
    expect(tunicVoxels({})).toEqual([])
    expect(capVoxels(undefined)).toEqual([])
    const body = new Set(previewPet.voxels.filter((voxel) => voxel.y <= 1 && voxel.z >= -1 && voxel.z <= 0).map(key))
    expect(new Set(tunicVoxels({ leather_tunic: 1 }).map(key))).toEqual(body)
    const cap = capVoxels({ leather_cap: 1 })
    const pet = new Set(previewPet.voxels.map(key))
    expect(cap.length).toBe(4)
    expect(cap.some((voxel) => pet.has(key(voxel)))).toBe(false)  // it sits on the head, around the ears
    expect(cap.every((voxel) => voxel.y === 4)).toBe(true)
  })

  it('wears amber-studded armor over iron (L5), in the same places, in amber', () => {
    expect(wornTunic({ iron_tunic: 1, amber_tunic: 1 })).toBe('amber_tunic')
    expect(wornCap({ iron_cap: 1, amber_cap: 1, leather_cap: 1 })).toBe('amber_cap')
    const amber = tunicVoxels({ iron_tunic: 1, amber_tunic: 1 })
    expect(amber.map(key)).toEqual(tunicVoxels({ leather_tunic: 1 }).map(key))
    expect(amber.filter((voxel) => voxel.y === 1).every((voxel) => voxel.r - voxel.b > 100)).toBe(true)
    expect(capVoxels({ amber_cap: 1 }).map(key)).toEqual(capVoxels({ leather_cap: 1 }).map(key))
  })

  it('wears iron over leather, in the same places, in grey', () => {
    expect(wornTunic({ leather_tunic: 1, iron_tunic: 1 })).toBe('iron_tunic')
    expect(wornCap({ leather_cap: 1 })).toBe('leather_cap')
    expect(wornCap({ iron_cap: 0 })).toBeNull()
    expect(wornTunic(undefined)).toBeNull()
    const leather = tunicVoxels({ leather_tunic: 1 })
    const iron = tunicVoxels({ leather_tunic: 1, iron_tunic: 1 })
    expect(iron.map(key)).toEqual(leather.map(key))
    expect(iron.every((voxel) => Math.abs(voxel.r - voxel.b) < 20)).toBe(true)
    expect(leather.every((voxel) => voxel.r - voxel.b > 40)).toBe(true)
    expect(capVoxels({ iron_cap: 1 }).map(key)).toEqual(capVoxels({ leather_cap: 1 }).map(key))
    expect(capVoxels({ iron_cap: 1 })[0].g).toBeGreaterThan(capVoxels({ leather_cap: 1 })[0].g)
  })

  it('glows red at once after a blow and fades', () => {
    expect(hurtGlow(undefined, 10)).toBe(0)
    expect(hurtGlow(10, 9.9)).toBe(0)
    expect(hurtGlow(10, 10)).toBe(1)
    expect(hurtGlow(10, 10 + HURT_GLOW_SECONDS / 2)).toBeCloseTo(0.5)
    expect(hurtGlow(10, 10 + HURT_GLOW_SECONDS)).toBe(0)
  })
})

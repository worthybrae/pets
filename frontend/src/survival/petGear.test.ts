import { describe, expect, it } from 'vitest'
import { previewPet } from '../components/world/previewWorld'
import { HURT_GLOW_SECONDS, capVoxels, hurtGlow, tunicVoxels } from './petGear'

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

  it('glows red at once after a blow and fades', () => {
    expect(hurtGlow(undefined, 10)).toBe(0)
    expect(hurtGlow(10, 9.9)).toBe(0)
    expect(hurtGlow(10, 10)).toBe(1)
    expect(hurtGlow(10, 10 + HURT_GLOW_SECONDS / 2)).toBeCloseTo(0.5)
    expect(hurtGlow(10, 10 + HURT_GLOW_SECONDS)).toBe(0)
  })
})

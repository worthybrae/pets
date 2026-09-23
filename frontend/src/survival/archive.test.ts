import { describe, expect, it } from 'vitest'
import { compileWorldPlan, type WorldPlan } from '../components/world/worldPlanner'
import { isLegacyState, legacyOverlay } from './archive'
import type { LegacyState, SurvivalState } from './types'

const plan = (kind: WorldPlan['kind'], x: number): WorldPlan => ({ kind, site: { x, z: 0 }, variant: 0, observation: '', clearance: 15 })
const station = plan('station', 48)
const plaza = plan('plaza', 200)

describe('legacyOverlay', () => {
  it('shows every block of finished plans', () => {
    expect(legacyOverlay([station], 0, 100)).toHaveLength(compileWorldPlan(station).blocks.length)
  })

  it('shows the plan in progress up to its saved progress', () => {
    const stationBlocks = compileWorldPlan(station).blocks.length
    const plazaBlocks = compileWorldPlan(plaza).blocks.length
    expect(legacyOverlay([station, plaza], 1, 0)).toHaveLength(stationBlocks)
    expect(legacyOverlay([station, plaza], 1, 50)).toHaveLength(stationBlocks + Math.floor(plazaBlocks / 2))
  })
})

describe('isLegacyState', () => {
  it('tells the legacy snapshot from a survival state', () => {
    const legacy = { plans: [station], currentIndex: 0, progress: 100 } as unknown as LegacyState
    const survival = { vitals: {}, clock: {} } as unknown as SurvivalState
    expect(isLegacyState(legacy)).toBe(true)
    expect(isLegacyState(survival)).toBe(false)
  })
})

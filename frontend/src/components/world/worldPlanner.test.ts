import { describe, expect, it } from 'vitest'
import { hasBlock } from '../../engine/blocks'
import { compileWorldPlan, overlayBlocks, type WorldPlan } from './worldPlanner'

const kinds = ['station', 'landing_pad', 'boardwalk', 'greenhouse', 'observatory', 'sculpture', 'grove', 'plaza'] as const
const plan = (kind: WorldPlan['kind'], x = 100): WorldPlan =>
  ({ kind, site: { x, z: 40 }, variant: 3, observation: '', clearance: 15, base_y: 2 })

describe('build compilers', () => {
  it.each(kinds)('%s compiles to blocks from the registry', (kind) => {
    const project = compileWorldPlan(plan(kind))
    expect(project.blocks.length).toBeGreaterThan(0)
    expect([...new Set(project.blocks.filter((block) => !hasBlock(block.material)).map((block) => block.material))]).toEqual([])
  })

  it('keeps the station where it has always been', () => {
    const station = compileWorldPlan(plan('station'))
    expect(station.site).toEqual({ x: 48, z: 0 })
    expect(Math.max(...station.blocks.map((block) => block.y))).toBe(42)
    expect(new Set(station.blocks.map((block) => block.material))).toEqual(new Set(['hull_panel', 'dark_slate', 'solar_panel']))
  })

  it('reveals finished plans fully and the current plan up to stepIndex', () => {
    const plans = [plan('station'), plan('plaza', 200)]
    const station = compileWorldPlan(plans[0]).blocks.length
    expect(overlayBlocks(plans, 1, 5)).toHaveLength(station + 5)
    expect(overlayBlocks(plans, 0, 7)).toHaveLength(7)
  })
})

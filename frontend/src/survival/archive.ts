import { compileWorldPlan, overlayBlocks, type WorldPlan } from '../components/world/worldPlanner'
import type { PlacedBlock } from '../engine/worldStore'
import type { LegacyState, SurvivalState } from './types'

export function isLegacyState(state: LegacyState | SurvivalState): state is LegacyState {
  return 'plans' in state
}

/**
 * The retired legacy world's builds, compiled in the browser as before: every finished plan in
 * full and the plan in progress up to its saved progress.
 */
export function legacyOverlay(plans: WorldPlan[], currentIndex: number, progress: number): PlacedBlock[] {
  const current = plans[currentIndex]
  const placed = current ? Math.floor(compileWorldPlan(current).blocks.length * progress / 100) : 0
  return overlayBlocks(plans, currentIndex, placed)
}

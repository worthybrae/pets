import type { EggProfile } from './types'

export { rollEgg, rollStatsFromEgg, computeQuality, STAT_NAMES } from './eggAttributes'

export const GEN_STATUS = [
  { t: 0, text: 'Creating your companion...' },
  { t: 5, text: 'Shaping consciousness...' },
  { t: 10, text: 'Building its world...' },
  { t: 18, text: 'Almost ready...' },
]

export function readPendingEgg(): { egg: EggProfile; stats: Record<string, number>; quality: string } | null {
  try {
    const raw = localStorage.getItem('pendingEgg')
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}

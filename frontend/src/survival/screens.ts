import type { MimoResponse } from './types'

export interface Received {
  data: MimoResponse
  /** Local time in seconds when the response arrived. */
  receivedAt: number
}

export type ScreenName = 'archive' | 'connecting' | 'alive' | 'memorial' | 'egg'

/**
 * Decides which full-page screen /preview shows. `hatching` overrides everything the poll
 * reports except the archive: once the owner presses Hatch, the egg stays on screen — even if a
 * poll lands mid-animation and reports the pet already alive — until the hatch finishes or fails.
 */
export function pickScreen({ received, hatching, openLife, memorialDismissed }: {
  received: Received | null
  hatching: boolean
  openLife: number | null
  /** The id of the last dismissed memorial's life, or null if none has been dismissed. */
  memorialDismissed: number | null
}): ScreenName {
  if (openLife !== null) return 'archive'
  if (!received) return 'connecting'
  if (hatching) return 'egg'
  const { data } = received
  if (data.phase === 'alive') return 'alive'
  const last = data.last_life
  if (last && last.kind === 'survival' && memorialDismissed !== last.id) return 'memorial'
  return 'egg'
}

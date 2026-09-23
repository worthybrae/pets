import type { MimoResponse } from './types'

/**
 * Whether a freshly polled response should replace what is on screen. Requests can stall and
 * resolve out of order; comparing `server_time` stops a late, older response from clobbering a
 * newer one that already landed.
 */
export function shouldReplace(current: MimoResponse | null, next: MimoResponse): boolean {
  if (!current) return true
  return next.server_time >= current.server_time
}

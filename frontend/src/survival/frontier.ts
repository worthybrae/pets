import { MAP_BLOCKS, toMap, type MapOrigin } from './overheadMap'
import type { Creature, RingView } from './types'

/**
 * The frontier in the viewer (L5): the danger ring Mimo stands in on the HUD, the rings shaded faintly
 * on the minimap around home, and the faint glow of an elder hostile. The rings are the server's
 * (backend/survival/rings.py): home ground under 48 blocks from home, the near wilds to 128, the far
 * wilds to 256, the frontier to 512 and the deep frontier beyond.
 */

/** Where each ring past home ground begins, in blocks from home (danger 1 to 4). */
export const RING_STARTS = [48, 128, 256, 512]
/** How strongly a band of danger 1 is shaded; each level adds as much again. */
export const BAND_ALPHA = 0.05
/** The faint violet an elder glows with, and how strongly (0..1). */
export const ELDER_GLOW: [number, number, number] = [0.55, 0.42, 0.95]
export const ELDER_STRENGTH = 0.35

/** "Far wilds · danger 2": the ring Mimo stands in, or null when the server sends none. */
export function ringLine(ring: RingView | null | undefined): string | null {
  return ring ? `${ring.name} · danger ${ring.level}` : null
}

/** How the ring line is drawn: plain at home ground and in the near wilds, amber farther out. */
export function ringTone(ring: RingView | null | undefined): 'calm' | 'wary' {
  return ring && ring.level >= 2 ? 'wary' : 'calm'
}

/** One shaded band of the minimap: its centre and radii in map blocks (from its top-left corner). */
export interface RingBand {
  px: number
  py: number
  inner: number
  /** The deep frontier has no outer edge: the map's diagonal stands in for it. */
  outer: number
  alpha: number
  level: number
}

/** The bands of danger 1 to 4 around home that reach onto the map, faintest first. */
export function ringBands(ring: RingView | null | undefined, origin: MapOrigin): RingBand[] {
  if (!ring) return []
  const { px, py } = toMap(ring.center.x, ring.center.z, origin)
  const far = Math.hypot(Math.max(Math.abs(px), Math.abs(px - MAP_BLOCKS)), Math.max(Math.abs(py), Math.abs(py - MAP_BLOCKS)))
  const near = Math.max(0, Math.hypot(Math.max(0, -px, px - MAP_BLOCKS), Math.max(0, -py, py - MAP_BLOCKS)))
  return RING_STARTS.map((inner, index) => ({
    px, py, inner, outer: RING_STARTS[index + 1] ?? Math.max(far, inner) + 1, alpha: BAND_ALPHA * (index + 1),
    level: index + 1,
  })).filter((band) => band.outer > near && band.inner < far)
}

/** How much a creature glows on its own (0..1): an elder faintly, anything else not at all. */
export function elderGlow(creature: Pick<Creature, 'elder'>): number {
  return creature.elder ? ELDER_STRENGTH : 0
}

/** The emissive color of a creature's material: the red flash of a blow over its own glow. */
export function emissiveOf(flash: number, glow: number): [number, number, number] {
  if (flash > 0) return [0.9 * flash, 0.12 * flash, 0.1 * flash]
  return [ELDER_GLOW[0] * glow, ELDER_GLOW[1] * glow, ELDER_GLOW[2] * glow]
}

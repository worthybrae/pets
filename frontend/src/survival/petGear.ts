import type { Voxel } from '../types/world'

/**
 * What the pet wears and how a blow shows on it (L2). Mimo wears the armor it carries: a leather
 * tunic over its body and a leather cap between its ears, in the pet model's voxel units
 * (components/world/previewWorld.ts: the body fills x -1..1, y 0..1, z -1..0 and the head x -1..1,
 * y 2..3, z 0..1, with the ears at x -1 and 1, y 4..5, z 0). The tunic is drawn a little larger
 * than the body (TUNIC_SCALE around BODY_MIDDLE) so it sits on the fur.
 */

type Color = readonly [number, number, number]

const LEATHER: Color = [150, 96, 62]
const STITCH: Color = [112, 70, 44]
const IRON: Color = [196, 201, 204]  // L3: iron armor, with darker rivets
const RIVET: Color = [128, 135, 140]
const AMBER: Color = [222, 150, 52]  // L5: amber-studded, over the iron's rivets
export const TUNIC_SCALE = 1.12
/** The middle of the body, in voxel units, that the tunic is scaled around. */
export const BODY_MIDDLE: [number, number, number] = [0.5, 1, 0]
/** How long the pet glows red after a blow, in seconds. */
export const HURT_GLOW_SECONDS = 0.4

function voxel(x: number, y: number, z: number, [r, g, b]: Color): Voxel {
  return { x, y, z, r, g, b, a: 255 }
}

/** The tunic's voxels when Mimo carries a leather tunic, else none; a darker belt along the bottom. */
export function tunicVoxels(inventory: Record<string, number> | null | undefined): Voxel[] {
  const worn = wornTunic(inventory)
  if (worn === null) return []
  const [main, trim] = worn === 'amber_tunic' ? [AMBER, RIVET] : worn === 'iron_tunic' ? [IRON, RIVET] : [LEATHER, STITCH]
  const voxels: Voxel[] = []
  for (let x = -1; x <= 1; x++) {
    for (const z of [-1, 0]) {
      voxels.push(voxel(x, 0, z, trim), voxel(x, 1, z, main))
    }
  }
  return voxels
}

/** The cap's voxels when Mimo carries a leather cap, else none: on top of the head, around the ears. */
export function capVoxels(inventory: Record<string, number> | null | undefined): Voxel[] {
  const worn = wornCap(inventory)
  if (worn === null) return []
  const [main, trim] = worn === 'amber_cap' ? [AMBER, RIVET] : worn === 'iron_cap' ? [IRON, RIVET] : [LEATHER, STITCH]
  return [voxel(0, 4, 0, main), voxel(0, 4, 1, main), voxel(-1, 4, 1, trim), voxel(1, 4, 1, trim)]
}

/** L3: the tunic Mimo wears, iron over leather (L5: amber over iron), or null when it carries none. */
export function wornTunic(inventory: Record<string, number> | null | undefined): string | null {
  return ['amber_tunic', 'iron_tunic', 'leather_tunic'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
}

/** L3: the cap Mimo wears, iron over leather (L5: amber over iron), or null when it carries none. */
export function wornCap(inventory: Record<string, number> | null | undefined): string | null {
  return ['amber_cap', 'iron_cap', 'leather_cap'].find((item) => (inventory?.[item] ?? 0) > 0) ?? null
}

/** How red the pet glows (0..1) at server time `t` after a blow at `hurtAt`: at once, then fading. */
export function hurtGlow(hurtAt: number | null | undefined, t: number): number {
  if (hurtAt === null || hurtAt === undefined || t < hurtAt || t >= hurtAt + HURT_GLOW_SECONDS) return 0
  return 1 - (t - hurtAt) / HURT_GLOW_SECONDS
}

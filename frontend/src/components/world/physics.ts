/**
 * World Physics Engine
 *
 * Core system that enforces Minecraft-like physics:
 * - Gravity: entities fall when unsupported
 * - Ground detection: walk on top of solid blocks
 * - Collision: can't pass through solid blocks at body level
 * - Step-up: can climb 1-block height differences
 *
 * This system is immutable/unmodifiable — it reads world state
 * and provides physics queries. The world itself can change,
 * but the physics rules cannot.
 */
import type { Chunk } from '../../types/world'
import { CHUNK_SIZE } from '../../types/world'

/** Pre-computed physics data structure for fast queries */
export interface WorldCollider {
  /** "x,z" → highest solid y at that column */
  heightmap: Map<string, number>
  /** "x,y,z" → true if a solid block exists there */
  solid: Set<string>
}

/** Physics constants (not modifiable) */
export const GRAVITY = 20 // units/s²
export const STEP_UP_HEIGHT = 1 // max blocks the pet can step up without jumping
export const BODY_HEIGHT = 2 // how many blocks tall the pet's collision box is
export const TERMINAL_VELOCITY = 30 // max fall speed

/**
 * Build a WorldCollider from the current chunk state.
 * Call this whenever chunks change (memoize in React).
 */
export function buildCollider(chunks: Chunk[]): WorldCollider {
  const heightmap = new Map<string, number>()
  const solid = new Set<string>()

  for (const chunk of chunks) {
    const ox = chunk.chunk_x * CHUNK_SIZE
    const oy = chunk.chunk_y * CHUNK_SIZE
    const oz = chunk.chunk_z * CHUNK_SIZE

    for (const v of chunk.voxels) {
      const wx = ox + v.x
      const wy = oy + v.y
      const wz = oz + v.z

      solid.add(`${wx},${wy},${wz}`)

      // Update heightmap (track highest solid y per column)
      const colKey = `${wx},${wz}`
      const current = heightmap.get(colKey)
      if (current === undefined || wy > current) {
        heightmap.set(colKey, wy)
      }
    }
  }

  return { heightmap, solid }
}

/**
 * Get the y-level the entity's feet should be at for a given (x, z).
 * Returns the top of the highest solid block at that column + 1.
 * If no solid blocks exist, returns 0 (void level).
 */
export function getGroundLevel(collider: WorldCollider, x: number, z: number): number {
  const key = `${Math.floor(x)},${Math.floor(z)}`
  const highestSolid = collider.heightmap.get(key)
  if (highestSolid === undefined) return 0
  return highestSolid + 1
}

/**
 * Check if a specific grid cell is solid (occupied by a block).
 */
export function isSolid(collider: WorldCollider, x: number, y: number, z: number): boolean {
  return collider.solid.has(`${x},${y},${z}`)
}

/**
 * Check if an entity can move to a target (x, z) position.
 * Validates:
 * 1. The height difference from current ground is climbable (≤ STEP_UP_HEIGHT)
 * 2. There's enough headroom at the target (BODY_HEIGHT clear blocks above ground)
 *
 * @param currentFeetY - entity's current feet y-level
 */
export function canMoveTo(
  collider: WorldCollider,
  targetX: number,
  targetZ: number,
  currentFeetY: number,
): boolean {
  const tx = Math.floor(targetX)
  const tz = Math.floor(targetZ)
  const targetGround = getGroundLevel(collider, tx, tz)

  // Can't step up more than STEP_UP_HEIGHT blocks
  if (targetGround - currentFeetY > STEP_UP_HEIGHT) {
    return false
  }

  // Check for headroom at the target position (body must fit)
  for (let dy = 0; dy < BODY_HEIGHT; dy++) {
    if (isSolid(collider, tx, targetGround + dy, tz)) {
      return false
    }
  }

  return true
}

/**
 * Apply gravity to a vertical velocity.
 * Returns new velocity (clamped to terminal velocity).
 */
export function applyGravity(velocityY: number, delta: number): number {
  const newVel = velocityY - GRAVITY * delta
  return Math.max(newVel, -TERMINAL_VELOCITY)
}

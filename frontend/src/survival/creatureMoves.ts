import type { CreatureMove } from './types'

/**
 * A short history of each creature's moves, kept by the viewer from poll to poll. The server only
 * sends a creature's latest move (backend/survival/creatures/view.py), and a hit starts a new flee
 * at once, so without the move before it the replay (1.5 s behind the server) would skip ahead to
 * the flee. placeAt (creatureMotion.ts) replays whichever move of the history covers the moment.
 */

/** Seconds before the replay time that a finished move is still kept. */
export const MOVE_MEMORY = 3

/** Each creature's recent moves by id, oldest first. */
export type MoveHistory = ReadonlyMap<number, readonly CreatureMove[]>

/**
 * `history` with a poll's `moves` merged in, and every move that ended more than MOVE_MEMORY
 * seconds before replay time `t` left out (with the creatures that have none left). A move the
 * server sends again (the same creature and start) replaces the kept one: it may have been cut
 * short since, by a death. Returns a new map and leaves `history` as it was.
 */
export function mergeMoves(history: MoveHistory, moves: readonly CreatureMove[] | null | undefined, t: number): Map<number, CreatureMove[]> {
  const recent = (move: CreatureMove) => move.ends >= t - MOVE_MEMORY
  const merged = new Map<number, CreatureMove[]>()
  for (const [id, kept] of history) merged.set(id, kept.filter(recent))
  for (const move of moves ?? []) {
    if (!recent(move)) continue
    const kept = (merged.get(move.id) ?? []).filter((known) => known.started !== move.started)
    merged.set(move.id, [...kept, move].sort((a, b) => a.started - b.started))
  }
  for (const [id, kept] of merged) {
    if (kept.length === 0) merged.delete(id)
  }
  return merged
}

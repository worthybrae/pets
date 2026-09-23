import type { PlacedBlock } from '../engine/worldStore'
import { REPLAY_DELAY } from './replay'

type Apply = (changes: PlacedBlock[], reset: boolean) => void

/** Local time in seconds. */
function localSeconds(): number {
  return performance.now() / 1000
}

/**
 * Server block changes, held back REPLAY_DELAY seconds from when they arrive: the pet is drawn
 * that far behind the server (replay.ts), so a block now changes when the replayed pet mines or
 * places it instead of a moment before. The first load, and a reload after the server's blocks
 * were reset, apply at once until `goLive` is called.
 */
export class DelayedBlocks {
  private readonly apply: Apply
  private readonly delay: number
  private readonly clock: () => number
  private pending: { due: number; changes: PlacedBlock[] }[] = []
  private live = false

  constructor(apply: Apply, delay = REPLAY_DELAY, clock: () => number = localSeconds) {
    this.apply = apply
    this.delay = delay
    this.clock = clock
  }

  /** Changes that arrived at local time `now` (seconds, the local clock by default). */
  push(changes: PlacedBlock[], reset: boolean, now = this.clock()): void {
    if (reset) {
      // A reset replaces every server edit, including the ones still waiting.
      this.pending = []
      this.live = false
      this.apply(changes, true)
    } else if (this.live) {
      this.pending.push({ due: now + this.delay, changes })
    } else {
      this.apply(changes, false)
    }
  }

  /** The store is caught up: hold back changes from now on. */
  goLive(): void {
    this.live = true
  }

  /** Apply every batch due by local time `now`, oldest first. Returns how many were applied. */
  flush(now = this.clock()): number {
    let count = 0
    while (this.pending.length > 0 && this.pending[0].due <= now) {
      this.apply(this.pending.shift()!.changes, false)
      count += 1
    }
    return count
  }
}

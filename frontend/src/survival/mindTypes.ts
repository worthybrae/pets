/** Shapes of Mind in the survival API (backend/survival/mind.py memories_view and life_memories). */

/** One memory (mind.item_of). */
export interface MemoryItem {
  id: number
  /** Server time it happened. */
  at: number
  /** The game day it happened on. */
  day: number
  kind: 'episode' | 'gist' | 'thought' | 'told' | 'lesson'
  /** In Mimo's voice, at most 160 characters. */
  text: string
  /** 1 to 10. */
  importance: number
  /** -2 to 2. */
  feeling: number
}

/** What /api/mimo shows of Mimo's memory, each list newest first. */
export interface MemoriesView {
  count: number
  recent: MemoryItem[]
  moments: MemoryItem[]
  thoughts: MemoryItem[]
  /** The newest days' gists. */
  days: MemoryItem[]
}

/** A life's gists and thoughts for its memorial, oldest first. */
export interface LifeMemories {
  gists: MemoryItem[]
  thoughts: MemoryItem[]
}

/** What /api/mimo adds for Mind while Mimo lives (an older API sends none of it). */
export interface MindFields {
  memories?: MemoriesView
}

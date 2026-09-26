import type { LifeMemories, MemoriesView, MemoryItem } from './mindTypes'

/** The HUD's button for the Memories panel, with how many memories there are once there are any. */
export function memoriesButton(view: MemoriesView | null | undefined): string {
  const count = view?.count ?? 0
  return count > 0 ? `Memories (${count})` : 'Memories'
}

/** The panel's title (Mind M3): "What Pebble remembers". */
export function memoriesTitle(name: string): string {
  return `What ${name} remembers`
}

export interface MemoryLine {
  key: number
  /** "Day 12". */
  day: string
  text: string
  /** How it felt: "glad", "sad" or "" when neither. */
  mood: 'glad' | 'sad' | ''
  /** It was the owner who taught it. */
  fromYou: boolean
}

export interface MemorySection {
  title: string
  lines: MemoryLine[]
}

function lineOf(item: MemoryItem): MemoryLine {
  return {
    key: item.id,
    day: `Day ${item.day}`,
    text: item.kind === 'gist' ? item.text.replace(/^Day \d+: /, '') : item.text,
    mood: item.feeling > 0 ? 'glad' : item.feeling < 0 ? 'sad' : '',
    fromYou: item.kind === 'told',
  }
}

/**
 * The Memories panel's sections, in order: what happened lately, the moments that mattered, Mimo's
 * thoughts, and the day-by-day gists (newest first). A section with nothing in it is left out.
 */
export function memorySections(view: MemoriesView | null | undefined): MemorySection[] {
  if (!view) return []
  const sections: MemorySection[] = [
    { title: 'Lately', lines: view.recent.map(lineOf) },
    { title: 'Moments that mattered', lines: view.moments.map(lineOf) },
    { title: 'Thoughts', lines: view.thoughts.map(lineOf) },
    { title: 'Day by day', lines: view.days.map(lineOf) },
  ]
  return sections.filter((section) => section.lines.length > 0)
}

/** A memorial's memories: the life's thoughts, then its days oldest first (an older API sends none). */
export function memorialMemories(memories: LifeMemories | null | undefined): { thoughts: MemoryLine[]; days: MemoryLine[] } {
  return { thoughts: (memories?.thoughts ?? []).map(lineOf), days: (memories?.gists ?? []).map(lineOf) }
}

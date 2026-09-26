import type { Expedition, JournalEntry } from './types'

/** The journal panel's title (L4b): "What Pebble has learned". */
export function journalTitle(name: string): string {
  return `What ${name} has learned`
}

/** The HUD's button for the journal, with how many lessons it holds once there are any. */
export function journalButton(journal: readonly JournalEntry[] | null | undefined): string {
  const count = journal?.length ?? 0
  return count > 0 ? `Journal (${count})` : 'Journal'
}

const KIND_LABELS: Record<JournalEntry['kind'], string> = {
  block: 'Block', plant: 'Plant', creature: 'Creature', biome: 'Land', landmark: 'Landmark',
}

/**
 * The journal's entries as the panel lists them, newest first: a label for the kind of thing, the line in
 * Mimo's voice, the plain fact when the line is Jev's own phrasing, and what the lesson lets Mimo do.
 */
export function journalEntries(journal: readonly JournalEntry[] | null | undefined, name: string): {
  key: string; label: string; line: string; fact: string | null; unlocks: string | null
}[] {
  return (journal ?? []).map((entry) => ({
    key: entry.thing,
    label: KIND_LABELS[entry.kind] ?? 'Thing',
    line: entry.line,
    fact: entry.line === entry.fact ? null : entry.fact,
    unlocks: entry.unlocks ? `Now ${name} ${entry.unlocks}.` : null,
  }))
}

/**
 * The HUD's expedition line (L4b): "Expedition: packing food and torches", "Expedition east · 132 of 180
 * blocks out · 1 night", "Expedition: making camp for the night", "Expedition: heading home". Null without one.
 */
export function expeditionLine(expedition: Expedition | null | undefined): string | null {
  if (!expedition) return null
  if (expedition.camping) return 'Expedition: making camp for the night'
  const nights = expedition.nights > 0 ? ` · ${expedition.nights} night${expedition.nights === 1 ? '' : 's'} out` : ''
  const way = expedition.direction ? ` ${expedition.direction}` : ''
  switch (expedition.phase) {
    case 'packing': return 'Expedition: packing food and torches'
    case 'out': return `Expedition${way} · ${expedition.far} of ${expedition.target ?? '?'} blocks out${nights}`
    case 'homeward': return `Expedition: heading home${nights}`
    default: return 'Expedition: home again'
  }
}

import type { InboxItem, InboxView, Question } from './bondTypes'
import type { Ailments, Difficulty, SurvivalLesson } from './types'

/**
 * Wild World W1 in the viewer: the ailment line and the "Wild" badge on the HUD, the count of Mimo's open
 * questions, the words on a question the owner answered, the journal's survival lessons with where each came
 * from, the memorial's tally, and how a sickness, a chill or a wound shows on the pet. The rules are the
 * server's (backend/survival/wild.py, ailments.py, questions.py).
 */

/** How long the "?" bubble floats over the pet after it asks (seconds). */
export const ASK_BUBBLE_SECONDS = 10
/** How green a sick pet is tinted (0..1), and how much of its hop is left. */
export const SICK_TINT = 0.25
export const SICK_HOP = 0.6
/** A chill's shiver: a short shake every few seconds. */
export const SHIVER_EVERY = 3
export const SHIVER_SECONDS = 0.4
const SOURCES: Record<string, string> = { from_you: 'from you', figured: 'worked it out', from_start: 'knew from the start' }
const CLOSED: Record<string, string> = {
  taught: 'You told me', noted: 'You told me', doubted: 'Not sure about that one', figured: 'I figured it out',
  set_aside: 'I stopped waiting on this one.',  // W1's final fix wave: a stale question a newer one replaced
}

/** "Tummy ache · 7 min", "Chill · 18 min", "Wound festering", together when there is more than one; null when well. */
export function ailmentLine(ailments: Ailments | null | undefined): string | null {
  const parts: string[] = []
  if (ailments?.sick) parts.push(`${ailments.sick.label} · ${ailments.sick.minutes} min`)
  if (ailments?.wound) parts.push(ailments.wound.festering ? 'Wound festering' : ailments.wound.dressed ? 'Wound dressed' : 'Wound')
  return parts.length ? parts.join(' · ') : null
}

/** The badge beside a wild pet's name; none for a gentle one (or an older API that sends no difficulty). */
export function wildBadge(difficulty: Difficulty | null | undefined): string | null {
  return difficulty === 'wild' ? 'Wild' : null
}

/** "? 2" while Mimo has questions waiting for an answer, else null. */
export function questionsLabel(inbox: InboxView | null | undefined): string | null {
  const count = inbox?.questions?.length ?? 0
  return count > 0 ? `? ${count}` : null
}

/** A question of Mimo's the owner can still answer with a chip. */
export function canAnswer(item: InboxItem): boolean {
  return item.kind === 'ask' && item.data.ask === 'wonder' && !item.data.closed && (item.data.chips?.length ?? 0) > 0
}

/** How a closed question reads: "You told me", "Not sure about that one", "I figured it out" or, set aside, "I stopped
 * waiting on this one."; '' while open. */
export function closedLine(item: InboxItem): string {
  return item.data.closed ? CLOSED[item.data.closed] ?? '' : ''
}

/** The journal's survival section: each lesson with its fact and where it came from, or "?" while unknown. */
export function survivalEntries(survival: readonly SurvivalLesson[] | null | undefined): {
  key: string; words: string; line: string; source: string | null
}[] {
  return (survival ?? []).map((lesson) => ({
    key: lesson.name,
    words: lesson.words,
    line: lesson.known ? lesson.fact : '?',
    source: lesson.known && lesson.source ? SOURCES[lesson.source] ?? null : null,
  }))
}

/** How many survival lessons came from the owner and how many Mimo worked out alone. */
export function lessonCounts(survival: readonly SurvivalLesson[] | null | undefined): { fromYou: number; figured: number } {
  const known = (survival ?? []).filter((lesson) => lesson.known)
  return { fromYou: known.filter((lesson) => lesson.source === 'from_you').length,
    figured: known.filter((lesson) => lesson.source === 'figured').length }
}

/** The memorial's line: "4 lessons from you · 5 worked out alone"; null when it learned none either way. */
export function memorialLessons(survival: readonly SurvivalLesson[] | null | undefined): string | null {
  const { fromYou, figured } = lessonCounts(survival)
  if (fromYou + figured === 0) return null
  const plural = (count: number) => `${count} lesson${count === 1 ? '' : 's'}`
  return `${plural(fromYou)} from you · ${figured} worked out alone`
}

/** How the pet shows its ailments: a green tint and a droop with a slower hop while sick, a shiver with a
 * chill, a white wrap on a dressed wound and a red mark while one festers. */
export function petAilment(ailments: Ailments | null | undefined): {
  tint: number; droop: boolean; hop: number; shiver: boolean; wrap: boolean; mark: boolean
} {
  const sick = ailments?.sick ?? null
  const wound = ailments?.wound ?? null
  return { tint: sick ? SICK_TINT : 0, droop: sick !== null, hop: sick ? SICK_HOP : 1, shiver: sick?.kind === 'chill',
    wrap: Boolean(wound?.dressed), mark: Boolean(wound?.festering) }
}

/** The roll of a chill's shiver at `t` seconds: a short shake every SHIVER_EVERY seconds, still between. */
export function shiverAt(t: number): number {
  const phase = ((t % SHIVER_EVERY) + SHIVER_EVERY) % SHIVER_EVERY
  return phase < SHIVER_SECONDS ? Math.sin(phase * 60) * 0.06 : 0
}

/** Whether the "?" bubble floats over the pet: it asked within ASK_BUBBLE_SECONDS (server seconds). */
export function askBubble(questions: readonly Question[] | null | undefined, serverTime: number): boolean {
  const newest = Math.max(-Infinity, ...(questions ?? []).map((question) => question.at ?? -Infinity))
  return serverTime - newest >= 0 && serverTime - newest <= ASK_BUBBLE_SECONDS
}

import type { Curiosity, Goal, GoalReached, MimoEvent, PlanStep, Trip } from './types'

/** How many steps of the day plan the HUD shows: three milestones and the time set aside to wander. */
export const PLAN_SHOWN = 4

/** The HUD's goal line (L4): "Goal: Iron tools" and its progress in whole percent, or null without a goal. */
export function goalLine(goal: Goal | null | undefined): { label: string; percent: number } | null {
  if (!goal) return null
  return { label: `Goal: ${goal.title}`, percent: Math.round(Math.min(1, Math.max(0, goal.progress)) * 100) }
}

/** Why Mimo wants the goal and who chose it, for the goal line's tooltip; undefined without a goal. */
export function goalHint(goal: Goal | null | undefined): string | undefined {
  if (!goal) return undefined
  const chooser = goal.picker === 'jev' ? ' Jev chose it.' : goal.picker === 'utility' ? ' The rules chose it.' : ''
  return `${goal.why}${chooser}`
}

/** Today's plan toward the goal: the first PLAN_SHOWN steps, as the server wrote them at dawn. */
export function planSteps(goal: Goal | null | undefined): PlanStep[] {
  return (goal?.plan ?? []).slice(0, PLAN_SHOWN)
}

/** The memorial's notable events but the goals reached, which it lists on their own. */
export function otherEvents(events: readonly MimoEvent[]): MimoEvent[] {
  return events.filter((event) => event.kind !== 'goal')
}

/** One goal a life reached, for the memorial: "A home of its own · day 2". */
export function reachedLine(goal: GoalReached): string {
  return `${goal.title} · day ${goal.day}`
}

/**
 * The HUD's lines for an explore trip (L4): what Mimo went looking for ("Exploring to look for iron"),
 * then which way and why ("Heading north: my pickaxe needs it"), or what it found. Null when it is not exploring.
 */
export function tripLines(trip: Trip | null | undefined): { label: string; detail: string } | null {
  if (!trip) return null
  const detail = trip.found ? `Found ${trip.found}` : `Heading ${trip.direction}: ${trip.why}`
  return { label: `Exploring to ${trip.words}`, detail }
}

/** The curiosity bar beside the vitals (L4): its level in whole percent, and how Mimo feels as the tooltip. */
export function curiosityBar(curiosity: Curiosity | null | undefined): { percent: number; hint: string } | null {
  if (!curiosity) return null
  const percent = Math.round(Math.min(100, Math.max(0, curiosity.level)))
  return { percent, hint: curiosity.feeling.charAt(0).toUpperCase() + curiosity.feeling.slice(1) }
}

import type { MachineRow, WorkshopView } from './types'

/** The machines in the Workshop panel, oldest first (Making, backend/survival/machines.py). */
export interface WorkshopRow {
  key: number
  /** Like "A lamp on a lever". */
  name: string
  /** "Working" or "Being built". */
  status: string
  /** What it shows now, like "2 lamps lit" or "Counting: 0101 (5)"; "" for none. */
  detail: string
}

function capitalized(words: string): string {
  return words.charAt(0).toUpperCase() + words.slice(1)
}

function done(machine: MachineRow): boolean {
  return machine.status === 'done'
}

/** The HUD's button for the Workshop panel, with how many machines work; null while Mimo has made nothing. */
export function workshopButton(workshop: WorkshopView | null | undefined): string | null {
  if (!workshop || (!workshop.workshop && workshop.machines.length === 0)) return null
  const working = workshop.machines.filter(done).length
  return working > 0 ? `Workshop (${working})` : 'Workshop'
}

/** The Workshop panel's title: "What Pip has made". */
export function workshopTitle(name: string): string {
  return `What ${name} has made`
}

/** The workshop itself, in the panel's words: "Its workshop: Pip's workshop (being built)". */
export function workshopLine(workshop: WorkshopView | null | undefined): string | null {
  const found = workshop?.workshop
  if (!found) return null
  return found.status === 'done' ? `Its workshop: ${found.name}` : `Its workshop: ${found.name} (being built)`
}

function detail(machine: MachineRow): string {
  if (!done(machine)) return ''
  const readout = machine.readout
  if (readout) {
    return readout.shown ? `Counting: ${readout.bits} (${readout.value})` : `Counting: ${readout.bits} (${readout.value}), display off`
  }
  if (machine.lamps > 0) return machine.lamps === 1 ? '1 lamp lit' : `${machine.lamps} lamps lit`
  return ''
}

/** The panel's rows: every machine Mimo built or is building, oldest first. */
export function workshopRows(workshop: WorkshopView | null | undefined): WorkshopRow[] {
  return (workshop?.machines ?? []).map((machine) => ({
    key: machine.id,
    name: capitalized(machine.name),
    status: done(machine) ? 'Working' : 'Being built',
    detail: detail(machine),
  }))
}

/**
 * The HUD's caption for Mimo's computer (the spec: "Mimo's computer: day 13 = 1101"): the day its lamps
 * spell while they are shown. Its 4 bits count to 15 and round again, so from day 16 the caption gives the
 * count and the day ("Pip's computer: 1110 = 14 (day 62)", short enough for the HUD's line on a phone). Null
 * without a working computer, or while its lever hides the lamps.
 */
export function computerCaption(name: string, workshop: WorkshopView | null | undefined, day: number): string | null {
  const computer = (workshop?.machines ?? []).filter((machine) => done(machine) && machine.machine === 'computer').at(-1)
  const readout = computer?.readout
  if (!readout || !readout.shown) return null
  if (readout.value === day) return `${name}'s computer: day ${day} = ${readout.bits}`
  if (day >= 16 && readout.value === day % 16) {
    return `${name}'s computer: ${readout.bits} = ${readout.value} (day ${day})`
  }
  return `${name}'s computer: ${readout.bits} = ${readout.value}`
}

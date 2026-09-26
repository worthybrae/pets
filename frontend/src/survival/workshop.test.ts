import { describe, expect, it } from 'vitest'
import { computerCaption, workshopButton, workshopLine, workshopRows, workshopTitle } from './workshop'
import type { MachineRow, WorkshopView } from './types'

const lamp: MachineRow = { id: 3, name: 'a lamp on a lever', machine: 'lamp_lever', status: 'done', x: 1, y: 1, z: 1, lamps: 1 }
const computer: MachineRow = {
  id: 9, name: "Pip's computer", machine: 'computer', status: 'done', x: 20, y: 1, z: 20, lamps: 3,
  readout: { value: 13, bits: '1101', shown: true },
}
const view = (machines: MachineRow[], workshop: WorkshopView['workshop'] = null): WorkshopView =>
  ({ workshop, machines, doors_open: [] })

describe('the workshop', () => {
  it('shows its button once Mimo has made something, with the machines that work', () => {
    expect(workshopButton(undefined)).toBeNull()
    expect(workshopButton(view([]))).toBeNull()
    expect(workshopButton(view([], { name: "Pip's workshop", status: 'building' }))).toBe('Workshop')
    expect(workshopButton(view([lamp, { ...computer, status: 'building' }]))).toBe('Workshop (1)')
    expect(workshopTitle('Pip')).toBe('What Pip has made')
    expect(workshopLine(view([], { name: "Pip's workshop", status: 'building' }))).toBe("Its workshop: Pip's workshop (being built)")
    expect(workshopLine(view([], { name: "Pip's workshop", status: 'done' }))).toBe("Its workshop: Pip's workshop")
    expect(workshopLine(view([]))).toBeNull()
  })

  it('lists every machine, oldest first, with its lamps or its count', () => {
    const hidden = { ...computer, readout: { value: 5, bits: '0101', shown: false } }
    expect(workshopRows(view([lamp, { ...lamp, id: 4, lamps: 0 }, computer, hidden, { ...computer, id: 10, status: 'building' }])))
      .toEqual([
        { key: 3, name: 'A lamp on a lever', status: 'Working', detail: '1 lamp lit' },
        { key: 4, name: 'A lamp on a lever', status: 'Working', detail: '' },
        { key: 9, name: "Pip's computer", status: 'Working', detail: 'Counting: 1101 (13)' },
        { key: 9, name: "Pip's computer", status: 'Working', detail: 'Counting: 0101 (5), display off' },
        { key: 10, name: "Pip's computer", status: 'Being built', detail: '' },
      ])
  })

  it("captions the computer's lamps with the day they spell", () => {
    expect(computerCaption('Pip', view([lamp, computer]), 13)).toBe("Pip's computer: day 13 = 1101")
    const wrapped = { ...computer, readout: { value: 1, bits: '0001', shown: true } }
    expect(computerCaption('Pip', view([wrapped]), 17)).toBe("Pip's computer: 0001 = 1 (day 17)")
    const later = { ...computer, readout: { value: 14, bits: '1110', shown: true } }
    expect(computerCaption('Pip', view([later]), 62)).toBe("Pip's computer: 1110 = 14 (day 62)")
    // The longest name a pet is given still leaves room on the HUD's 800 px line and a phone's.
    expect(computerCaption('Juniper', view([later]), 62)!.length).toBeLessThanOrEqual(40)
    expect(computerCaption('Pip', view([computer]), 14)).toBe("Pip's computer: 1101 = 13")  // just before its dawn step
    expect(computerCaption('Pip', view([{ ...computer, readout: { ...computer.readout!, shown: false } }]), 13)).toBeNull()
    expect(computerCaption('Pip', view([{ ...computer, status: 'building' }]), 13)).toBeNull()
    expect(computerCaption('Pip', view([{ ...computer, readout: undefined }]), 13)).toBeNull()  // an older API
    expect(computerCaption('Pip', undefined, 13)).toBeNull()
  })
})

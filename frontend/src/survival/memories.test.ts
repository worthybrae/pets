import { describe, expect, it } from 'vitest'
import { memorialMemories, memoriesButton, memoriesTitle, memorySections } from './memories'
import type { MemoriesView, MemoryItem } from './mindTypes'

function item(id: number, kind: MemoryItem['kind'], text: string, day: number, feeling = 0): MemoryItem {
  return { id, at: 1000 + id, day, kind, text, importance: 5, feeling }
}

const view: MemoriesView = {
  count: 42,
  recent: [item(9, 'told', 'You taught me that cows give beef.', 3, 1), item(8, 'episode', 'I got hit 3 times.', 3, -2)],
  moments: [item(5, 'episode', 'I met my first skitter.', 2, 1)],
  thoughts: [item(7, 'thought', 'I love fishing by the lake.', 3, 2)],
  days: [item(6, 'gist', 'Day 2: met my first skitter and ate five meals.', 2)],
}

describe('the Memories panel', () => {
  it('is titled for the pet and counts the memories on the button', () => {
    expect(memoriesTitle('Pebble')).toBe('What Pebble remembers')
    expect(memoriesButton(view)).toBe('Memories (42)')
    expect(memoriesButton({ ...view, count: 0 })).toBe('Memories')
    expect(memoriesButton(undefined)).toBe('Memories')
  })

  it('lists what happened lately, the moments that mattered, the thoughts and the days', () => {
    const sections = memorySections(view)
    expect(sections.map((section) => section.title)).toEqual(['Lately', 'Moments that mattered', 'Thoughts', 'Day by day'])
    expect(sections[0].lines).toEqual([
      { key: 9, day: 'Day 3', text: 'You taught me that cows give beef.', mood: 'glad', fromYou: true },
      { key: 8, day: 'Day 3', text: 'I got hit 3 times.', mood: 'sad', fromYou: false },
    ])
    expect(sections[3].lines[0]).toEqual({ key: 6, day: 'Day 2', text: 'met my first skitter and ate five meals.',
      mood: '', fromYou: false })
  })

  it('leaves out an empty section, and shows nothing for an API from before Mind', () => {
    expect(memorySections({ ...view, moments: [], thoughts: [] }).map((section) => section.title))
      .toEqual(['Lately', 'Day by day'])
    expect(memorySections(undefined)).toEqual([])
  })
})

describe('the memorial', () => {
  it('lists the life\'s thoughts and its days, oldest first', () => {
    const memorial = memorialMemories({ gists: [item(1, 'gist', 'Day 1: hatched into a brand-new world.', 1)],
      thoughts: [item(2, 'thought', 'You visit me in the evenings.', 1, 1)] })
    expect(memorial.days.map((line) => `${line.day}: ${line.text}`)).toEqual(['Day 1: hatched into a brand-new world.'])
    expect(memorial.thoughts.map((line) => line.text)).toEqual(['You visit me in the evenings.'])
    expect(memorialMemories(undefined)).toEqual({ thoughts: [], days: [] })
  })
})

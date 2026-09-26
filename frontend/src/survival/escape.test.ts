import { describe, expect, it } from 'vitest'
import { closesOnEscape } from './escape'
import { closesOnKey } from './talk'

describe('Escape', () => {
  it('closes every panel, the talk panel among them (Bond final fix wave)', () => {
    expect(closesOnEscape('Escape')).toBe(true)
    expect(closesOnEscape('Enter')).toBe(false)
    expect(closesOnKey('Escape')).toBe(true)
  })
})

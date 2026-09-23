import { describe, expect, it } from 'vitest'
import { shouldReplace } from './poll'
import type { EggResponse } from './types'

const at = (server_time: number): EggResponse => ({ phase: 'egg', egg: {} as EggResponse['egg'], last_life: null, server_time })

describe('shouldReplace', () => {
  it('accepts the first response when nothing has loaded yet', () => {
    expect(shouldReplace(null, at(10))).toBe(true)
  })

  it('replaces with a newer server_time', () => {
    expect(shouldReplace(at(10), at(20))).toBe(true)
  })

  it('drops an older server_time, so a stalled request cannot undo a newer one', () => {
    expect(shouldReplace(at(20), at(10))).toBe(false)
  })

  it('accepts an equal server_time', () => {
    expect(shouldReplace(at(10), at(10))).toBe(true)
  })
})

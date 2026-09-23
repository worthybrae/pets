import { describe, expect, it } from 'vitest'
import { pickScreen } from './screens'
import type { AliveResponse, EggResponse, LifeSummary } from './types'

const receivedAt = 1000

const alive = { phase: 'alive', life: { id: 7 } } as unknown as AliveResponse
const eggNoLast = { phase: 'egg', egg: {}, last_life: null, server_time: 0 } as unknown as EggResponse

const deadSurvivalLife = { id: 42, kind: 'survival', alive: false } as unknown as LifeSummary
const eggWithDeadSurvival = { phase: 'egg', egg: {}, last_life: deadSurvivalLife, server_time: 0 } as unknown as EggResponse

const retiredLegacyLife = { id: 1, kind: 'legacy', alive: false } as unknown as LifeSummary
const eggWithRetiredLegacy = { phase: 'egg', egg: {}, last_life: retiredLegacyLife, server_time: 0 } as unknown as EggResponse

describe('pickScreen', () => {
  it('shows the archive when a life is open, no matter what else is happening', () => {
    expect(pickScreen({
      received: { data: alive, receivedAt },
      hatching: true,
      openLife: 42,
      memorialDismissed: null,
    })).toBe('archive')
  })

  it('shows connecting when nothing has loaded yet', () => {
    expect(pickScreen({ received: null, hatching: false, openLife: null, memorialDismissed: null }))
      .toBe('connecting')
  })

  it('keeps the egg on screen while hatching, even once a poll reports the pet alive', () => {
    expect(pickScreen({
      received: { data: alive, receivedAt },
      hatching: true,
      openLife: null,
      memorialDismissed: null,
    })).toBe('egg')
  })

  it('shows the alive world once hatching finishes', () => {
    expect(pickScreen({
      received: { data: alive, receivedAt },
      hatching: false,
      openLife: null,
      memorialDismissed: null,
    })).toBe('alive')
  })

  it('shows the memorial for a dead survival life that has not been dismissed', () => {
    expect(pickScreen({
      received: { data: eggWithDeadSurvival, receivedAt },
      hatching: false,
      openLife: null,
      memorialDismissed: null,
    })).toBe('memorial')
  })

  it('skips the memorial once its life id has been dismissed', () => {
    expect(pickScreen({
      received: { data: eggWithDeadSurvival, receivedAt },
      hatching: false,
      openLife: null,
      memorialDismissed: 42,
    })).toBe('egg')
  })

  it('shows the egg for a retired legacy life instead of a memorial', () => {
    expect(pickScreen({
      received: { data: eggWithRetiredLegacy, receivedAt },
      hatching: false,
      openLife: null,
      memorialDismissed: null,
    })).toBe('egg')
  })

  it('shows the egg when there is no last life at all', () => {
    expect(pickScreen({
      received: { data: eggNoLast, receivedAt },
      hatching: false,
      openLife: null,
      memorialDismissed: null,
    })).toBe('egg')
  })
})

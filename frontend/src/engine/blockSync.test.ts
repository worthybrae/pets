import { describe, expect, it } from 'vitest'
import { BlockSync, type BlocksPage } from './blockSync'
import type { PlacedBlock } from './worldStore'

function setup(pages: Record<number, BlocksPage>) {
  const calls: number[] = []
  const applied: { changes: PlacedBlock[]; reset: boolean }[] = []
  const sync = new BlockSync(async (since) => {
    calls.push(since)
    const page = pages[since]
    if (!page) throw new Error('offline')
    return page
  }, (changes, reset) => { applied.push({ changes, reset }) })
  return { sync, calls, applied }
}

const stone = (x: number): PlacedBlock => ({ x, y: 30, z: 0, material: 'stone' })

describe('BlockSync', () => {
  it('pages until the server says there is no more', async () => {
    const { sync, calls, applied } = setup({
      0: { seq: 2, changes: [stone(1), stone(2)], more: true },
      2: { seq: 3, changes: [stone(3)], more: false },
    })
    expect(await sync.syncTo(3)).toBe(true)
    expect(calls).toEqual([0, 2])
    expect(applied.flatMap((batch) => batch.changes.map((change) => change.x))).toEqual([1, 2, 3])
    expect(sync.seq).toBe(3)
  })

  it('does nothing when already in sync', async () => {
    const { sync, calls } = setup({})
    expect(await sync.syncTo(0)).toBe(false)
    expect(calls).toEqual([])
  })

  it('resyncs from zero with a reset when the server seq goes backwards', async () => {
    const { sync, applied } = setup({
      0: { seq: 5, changes: [stone(1)], more: false },
    })
    sync.seq = 9
    await sync.syncTo(5)
    expect(applied).toEqual([{ changes: [stone(1)], reset: true }])
    expect(sync.seq).toBe(5)
  })

  it('keeps its place and its pending reset when a fetch fails', async () => {
    const pages: Record<number, BlocksPage> = {}
    const { sync, applied } = setup(pages)
    sync.seq = 9
    await expect(sync.syncTo(5)).rejects.toThrow('offline')
    expect(sync.seq).toBe(0)
    pages[0] = { seq: 5, changes: [], more: false }
    await sync.syncTo(5)
    expect(applied).toEqual([{ changes: [], reset: true }])
  })

  it('skips a call while another sync is running', async () => {
    let release: (page: BlocksPage) => void = () => {}
    const sync = new BlockSync(() => new Promise<BlocksPage>((resolve) => { release = resolve }), () => {})
    const first = sync.syncTo(1)
    expect(await sync.syncTo(1)).toBe(false)
    release({ seq: 1, changes: [], more: false })
    expect(await first).toBe(true)
  })
})

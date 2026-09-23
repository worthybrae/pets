import { afterEach, describe, expect, it, vi } from 'vitest'
import { blocksPath, request } from './api'

afterEach(() => { vi.unstubAllGlobals() })

describe('blocksPath', () => {
  it('pages the active life or an archived one', () => {
    expect(blocksPath(null, 12)).toBe('/api/mimo/blocks?since=12')
    expect(blocksPath(1, 0)).toBe('/api/lives/1/blocks?since=0')
  })
})

describe('request', () => {
  it('returns the JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ phase: 'egg' }), { status: 200 })))
    await expect(request('/api/mimo')).resolves.toEqual({ phase: 'egg' })
  })

  it("throws the server's detail message", async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ detail: 'No snack left today.' }), { status: 409 })))
    await expect(request('/api/mimo/care')).rejects.toThrow('No snack left today.')
  })

  it('falls back to the status code when the body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('oops', { status: 503 })))
    await expect(request('/api/mimo')).rejects.toThrow('Server returned 503')
  })
})

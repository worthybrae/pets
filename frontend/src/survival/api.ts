import type { BlocksPage } from '../engine/blockSync'
import type { AliveResponse, CareKind, CareRemaining, LifeDetail, LifeRow, MimoResponse, Vitals } from './types'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** Fetch JSON from the API. A failed request throws the server's `detail` message when it has one. */
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init)
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body && typeof body === 'object' && 'detail' in body ? body.detail : null
    throw new Error(typeof detail === 'string' ? detail : `Server returned ${response.status}`)
  }
  return body as T
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

/** Block pages for the active life (lifeId null) or any archived life. */
export function blocksPath(lifeId: number | null, since: number): string {
  return lifeId === null ? `/api/mimo/blocks?since=${since}` : `/api/lives/${lifeId}/blocks?since=${since}`
}

export const fetchMimo = () => request<MimoResponse>('/api/mimo')
export const hatchEgg = () => post<{ life: LifeRow; state: AliveResponse }>('/api/lives/hatch')
export const giveCare = (kind: CareKind) =>
  post<{ kind: CareKind; vitals: Vitals; remaining: CareRemaining }>('/api/mimo/care', { kind })
export const sayHello = () => post<{ mood: number; noticed_at: number }>('/api/mimo/hello')
export const helpMimo = (action: string, item: string) =>
  post<{ message: string; inventory: Record<string, number> }>('/api/mimo/action', { action, item })
export const fetchLives = () => request<LifeRow[]>('/api/lives')
export const fetchLife = (id: number) => request<LifeDetail>(`/api/lives/${id}`)
export const blocksFetcher = (lifeId: number | null) => (since: number) => request<BlocksPage>(blocksPath(lifeId, since))

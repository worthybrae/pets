import { useCallback, useEffect, useState } from 'react'
import { fetchMimo } from '../survival/api'
import SurvivalWorld from '../survival/SurvivalWorld'
import type { MimoResponse } from '../survival/types'

interface Received {
  data: MimoResponse
  /** Local time in seconds when the response arrived. */
  receivedAt: number
}

/** /preview: the living pet. The egg screen, memorial and archive arrive in later tasks. */
export default function WorldPreview() {
  const [received, setReceived] = useState<Received | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMimo()
      setReceived({ data, receivedAt: Date.now() / 1000 })
      setError('')
    } catch (failure) {
      setError(failure instanceof Error && !failure.message.startsWith('Server returned')
        ? failure.message : 'The server is unavailable. The world will appear when it is running.')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => { void refresh() }, 0)
    const timer = window.setInterval(() => { void refresh() }, 1000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [refresh])

  if (!received) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )

  const { data, receivedAt } = received
  if (data.phase === 'alive') {
    return <SurvivalWorld key={data.life.id} state={data} receivedAt={receivedAt} arrival={false}
      connectionError={error} onChanged={refresh} />
  }
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <p className="max-w-sm text-xl font-semibold">No pet is alive yet. Hatch the egg with POST /api/lives/hatch.</p>
    </main>
  )
}

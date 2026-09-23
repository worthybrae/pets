import { useCallback, useEffect, useState } from 'react'
import { fetchMimo } from '../survival/api'
import ArchiveBrowser from '../survival/ArchiveBrowser'
import ArchiveWorld from '../survival/ArchiveWorld'
import SurvivalWorld from '../survival/SurvivalWorld'
import type { MimoResponse } from '../survival/types'

interface Received {
  data: MimoResponse
  /** Local time in seconds when the response arrived. */
  receivedAt: number
}

/** /preview: the living pet and the archive of every life. The egg screen arrives in the next task. */
export default function WorldPreview() {
  const [received, setReceived] = useState<Received | null>(null)
  const [error, setError] = useState('')
  const [showLives, setShowLives] = useState(false)
  const [openLife, setOpenLife] = useState<number | null>(null)

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

  if (openLife !== null) return <ArchiveWorld key={openLife} lifeId={openLife} onBack={() => setOpenLife(null)} />

  if (!received) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )

  const { data, receivedAt } = received
  const openLives = () => setShowLives(true)
  const screen = data.phase === 'alive'
    ? <SurvivalWorld key={data.life.id} state={data} receivedAt={receivedAt} arrival={false}
      connectionError={error} onChanged={refresh} onOpenLives={openLives} />
    : (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[#dce9eb] px-6 text-center text-[#315e58]">
        <p className="max-w-sm text-xl font-semibold">No pet is alive yet. Hatch the egg with POST /api/lives/hatch.</p>
        <button type="button" onClick={openLives} className="rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Lives</button>
      </main>
    )
  return (
    <>
      {screen}
      {showLives && <ArchiveBrowser onClose={() => setShowLives(false)}
        onOpen={(lifeId) => { setShowLives(false); setOpenLife(lifeId) }} />}
    </>
  )
}

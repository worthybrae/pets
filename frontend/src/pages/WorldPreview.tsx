import { useCallback, useEffect, useState } from 'react'
import { fetchMimo } from '../survival/api'
import ArchiveBrowser from '../survival/ArchiveBrowser'
import ArchiveWorld from '../survival/ArchiveWorld'
import EggHatch from '../survival/EggHatch'
import Memorial from '../survival/Memorial'
import { shouldReplace } from '../survival/poll'
import { pickScreen } from '../survival/screens'
import type { Received } from '../survival/screens'
import SurvivalWorld from '../survival/SurvivalWorld'
import type { LifeSummary, ServerEgg } from '../survival/types'

/** How long the fly-in plays before `arrival` clears itself, so it only ever plays once. */
const ARRIVAL_MS = 3000
/** Gap between the end of one poll and the start of the next. */
const POLL_MS = 1000

/** The egg and last-life props EggHatch was showing at the moment the owner pressed Hatch. */
interface HatchSnapshot {
  egg: ServerEgg
  lastLife: LifeSummary | null
}

/** /preview: the egg, the living pet, the memorial after a death, and the archive of every life. */
export default function WorldPreview() {
  const [received, setReceived] = useState<Received | null>(null)
  const [error, setError] = useState('')
  const [arrival, setArrival] = useState(false)
  const [memorialSeen, setMemorialSeen] = useState<number | null>(null)
  const [showLives, setShowLives] = useState(false)
  const [openLife, setOpenLife] = useState<number | null>(null)
  // Set the instant Hatch is pressed and cleared once the hatch finishes or fails. While set, the
  // egg stays on screen no matter what a poll landing mid-animation reports.
  const [hatchSnapshot, setHatchSnapshot] = useState<HatchSnapshot | null>(null)

  const refresh = useCallback(async () => {
    try {
      const data = await fetchMimo()
      setReceived((current) => (current && !shouldReplace(current.data, data)) ? current : { data, receivedAt: Date.now() / 1000 })
      setError('')
    } catch (failure) {
      setError(failure instanceof Error && !failure.message.startsWith('Server returned')
        ? failure.message : 'The server is unavailable. The world will appear when it is running.')
    }
  }, [])

  // Polls one at a time: the next poll is scheduled only once the current fetch settles, so a
  // stalled request cannot pile up behind another and resolve out of order.
  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    const poll = async () => {
      await refresh()
      if (!cancelled) timer = window.setTimeout(() => { void poll() }, POLL_MS)
    }
    void poll()
    return () => { cancelled = true; if (timer !== undefined) window.clearTimeout(timer) }
  }, [refresh])

  // One-shot: the fly-in plays once per arrival, then this clears it so re-mounting the
  // world (e.g. coming back from the archive) starts at the normal camera angle, not high up.
  useEffect(() => {
    if (!arrival) return
    const timer = window.setTimeout(() => { setArrival(false) }, ARRIVAL_MS)
    return () => window.clearTimeout(timer)
  }, [arrival])

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
  const hatching = hatchSnapshot !== null
  const screenName = pickScreen({ received, hatching, openLife, memorialDismissed: memorialSeen })

  // The hatch API call already finished by the time this runs (it's awaited inside EggHatch
  // before onHatched fires), so refresh now to pick up the freshly alive state before switching.
  const handleHatched = async () => {
    await refresh()
    setArrival(true)
    setHatchSnapshot(null)
  }
  const handleHatchFailed = () => {
    setHatchSnapshot(null)
    void refresh()
  }

  let screen
  if (screenName === 'alive' && data.phase === 'alive') {
    screen = <SurvivalWorld key={data.life.id} state={data} receivedAt={receivedAt} arrival={arrival}
      connectionError={error} onChanged={refresh} onOpenLives={openLives} />
  } else if (screenName === 'memorial' && data.phase === 'egg' && data.last_life) {
    const last = data.last_life
    screen = <Memorial life={last} onViewWorld={() => setOpenLife(last.id)} onNextEgg={() => setMemorialSeen(last.id)} />
  } else {
    // screenName === 'egg': the frozen snapshot while hatching, otherwise the freshly polled egg.
    const shown = hatchSnapshot ?? (data.phase === 'egg' ? { egg: data.egg, lastLife: data.last_life } : null)
    screen = shown && (
      <EggHatch egg={shown.egg} lastLife={shown.lastLife} onOpenLives={openLives}
        onHatchStart={() => { if (!hatchSnapshot) setHatchSnapshot(shown) }}
        onHatched={handleHatched} onHatchFailed={handleHatchFailed} />
    )
  }
  return (
    <>
      {screen}
      {showLives && <ArchiveBrowser onClose={() => setShowLives(false)}
        onOpen={(lifeId) => { setShowLives(false); setOpenLife(lifeId) }} />}
    </>
  )
}

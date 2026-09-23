import { useEffect, useMemo, useState } from 'react'
import { BlockSync } from '../engine/blockSync'
import { WorldStore } from '../engine/worldStore'
import { blocksFetcher, fetchLife } from './api'
import { isLegacyState, legacyOverlay } from './archive'
import { lifeLine } from './hud'
import type { LifeDetail } from './types'
import WorldCanvas from './WorldCanvas'

const PANEL = 'rounded-2xl border border-white/75 bg-[#f5faf7]/90 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md'

function ArchiveScene({ lifeId, detail, onBack }: { lifeId: number; detail: LifeDetail; onBack: () => void }) {
  const { life, state } = detail
  const store = useMemo(() => new WorldStore(state.world_seed), [state.world_seed])
  const [syncError, setSyncError] = useState('')
  const [following, setFollowing] = useState(true)
  const overlay = useMemo(() => isLegacyState(state) ? legacyOverlay(state.plans, state.currentIndex, state.progress) : [],
    [state])

  useEffect(() => {
    const sync = new BlockSync(blocksFetcher(lifeId), (changes, reset) => { store.applyServerChanges(changes, reset) })
    sync.syncTo(state.blocks_seq).catch(() => setSyncError('Some block changes could not be loaded.'))
  }, [store, lifeId, state.blocks_seq])
  useEffect(() => { store.setOverlay(overlay, 'legacy-builds') }, [store, overlay])

  const position = { x: state.position.x, y: state.position.y ?? 1, z: state.position.z }
  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <WorldCanvas store={store} position={position} following={following} onOrbit={() => setFollowing(false)} />
      <section className={`${PANEL} absolute inset-x-4 top-4 z-10 px-4 py-3 sm:inset-x-auto sm:left-8 sm:top-8 sm:w-80`} aria-label={`${life.name}'s life`}>
        <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">Archive · read only</p>
        <p className="mt-1 text-2xl font-semibold tracking-tight">{life.name}</p>
        <p className="mt-1 text-xs text-[#54726e]">{lifeLine(life)}</p>
        {detail.notable_events.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-[#54726e]">
            {detail.notable_events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
        )}
        {syncError && <p className="mt-2 text-xs text-[#a65b50]">{syncError}</p>}
        <div className="mt-3 flex gap-4 text-sm font-medium text-[#315e58]">
          <button type="button" onClick={onBack} className="underline decoration-[#8cafa2] underline-offset-4">Back</button>
          <button type="button" onClick={() => setFollowing(true)} className="underline decoration-[#8cafa2] underline-offset-4">Center on {life.name}</button>
        </div>
      </section>
    </main>
  )
}

/** One life's world, read only. The legacy life shows its builds through the blueprint overlay. */
export default function ArchiveWorld({ lifeId, onBack }: { lifeId: number; onBack: () => void }) {
  const [detail, setDetail] = useState<LifeDetail | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    fetchLife(lifeId).then(
      (loaded) => { if (!cancelled) setDetail(loaded) },
      (failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'This life could not be loaded.') },
    )
    return () => { cancelled = true }
  }, [lifeId])

  if (!detail) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div>
        <p className="text-2xl font-semibold">{error ? 'This world could not be opened' : 'Opening the archive…'}</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        <button type="button" onClick={onBack} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Back</button>
      </div>
    </main>
  )
  return <ArchiveScene lifeId={lifeId} detail={detail} onBack={onBack} />
}

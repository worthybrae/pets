import { useMemo, useState } from 'react'
import EggScene from '../components/hatch/EggScene'
import type { EggProfile, Phase } from '../components/hatch/types'
import { rarityColors } from '../data/rarity'
import { hatchEgg } from './api'
import type { LifeSummary, ServerEgg } from './types'

/** Long enough for EggScene's hatching glow to play before the world appears. */
const HATCH_ANIMATION_MS = 2200

/** The egg the server rolled, its attributes, and the Hatch button. */
export default function EggHatch({ egg, lastLife, onHatched, onOpenLives }: {
  egg: ServerEgg
  lastLife: LifeSummary | null
  onHatched: () => Promise<void>
  onOpenLives: () => void
}) {
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState('')
  // Every poll parses a new egg object. Key on its content so EggScene keeps its materials.
  const eggKey = JSON.stringify(egg)
  const profile = useMemo<EggProfile>(() => ({ ...(JSON.parse(eggKey) as ServerEgg), statRanges: {} }), [eggKey])

  const hatch = async () => {
    setError('')
    setPhase('hatching')
    try {
      await Promise.all([hatchEgg(), new Promise((resolve) => window.setTimeout(resolve, HATCH_ANIMATION_MS))])
      await onHatched()
    } catch (failure) {
      setPhase('idle')
      setError(failure instanceof Error ? failure.message : 'The egg did not hatch. Try again.')
    }
  }

  return (
    <main className="relative grid min-h-screen grid-cols-1 overflow-hidden bg-[#e5e5e5] lg:grid-cols-2">
      <div className="relative order-2 min-h-[50vh] lg:order-1 lg:min-h-screen">
        <div className="absolute inset-0">
          <EggScene phase={phase} egg={profile} revealProgress={0} voxels={[]} />
        </div>
      </div>
      <section className="relative z-10 order-1 flex flex-col justify-center px-6 py-10 sm:px-12 lg:order-2 lg:px-16" aria-label="The egg">
        {lastLife?.kind === 'legacy' && (
          <p className="mb-6 max-w-sm text-sm leading-6 text-neutral-600">
            {lastLife.name} has retired. Its world and everything it built stay in the archive.
          </p>
        )}
        <p className="text-xs font-semibold uppercase tracking-widest text-neutral-500">A new egg</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-neutral-900">{egg.name}</h1>
        <p className="mt-2 text-xs font-semibold uppercase tracking-wider" style={{ color: rarityColors[egg.rarity] }}>
          {egg.rarity} · {egg.totalPoints.toFixed(1)} / 10
        </p>
        <dl className="mt-6 max-w-xs divide-y divide-neutral-200 text-sm">
          {egg.attributes.map((attribute) => (
            <div key={attribute.category} className="flex items-center justify-between gap-3 py-1.5">
              <dt className="w-16 text-[11px] uppercase tracking-wider text-neutral-400">{attribute.category}</dt>
              <dd className="flex-1 font-medium text-neutral-800">{attribute.option.name}</dd>
              <dd className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: rarityColors[attribute.option.tier] }}>
                {attribute.option.tier}
              </dd>
            </div>
          ))}
        </dl>
        <div className="mt-8 flex flex-wrap items-center gap-4">
          <button type="button" disabled={phase !== 'idle'} onClick={() => { void hatch() }}
            className="rounded-xl bg-neutral-900 px-10 py-3.5 text-sm font-medium uppercase tracking-[0.15em] text-white shadow-[0_4px_24px_rgba(0,0,0,0.15)] hover:bg-neutral-800 disabled:opacity-60">
            {phase === 'idle' ? 'Hatch' : 'Hatching…'}
          </button>
          <button type="button" onClick={onOpenLives} className="text-sm font-medium text-neutral-600 underline underline-offset-4">Lives</button>
        </div>
        {error && <p className="mt-4 text-sm text-[#a65b50]" role="alert">{error}</p>}
      </section>
    </main>
  )
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { BlockSync } from '../engine/blockSync'
import { WorldStore } from '../engine/worldStore'
import { blocksFetcher, giveCare, helpMimo, sayHello } from './api'
import { DelayedBlocks } from './blockDelay'
import { isCameraKey, loadCameraMode, nextMode, saveCameraMode, type AutoPick, type CameraMode } from './cameraModes'
import { liveClock } from './clock'
import CraftingPanel from './CraftingPanel'
import JournalPanel from './JournalPanel'
import { workerOnline } from './hud'
import Minimap from './Minimap'
import { isMapKey, loadMapOpen, mapShownByDefault, saveMapOpen } from './overheadMap'
import { serverNow } from './motion'
import SurvivalHud from './SurvivalHud'
import type { AliveResponse, CareKind } from './types'
import WorldCanvas from './WorldCanvas'

const browserStorage = () => window.localStorage

/** The live survival world: terrain and blocks, the pet, day and night, the HUD and owner care. */
export default function SurvivalWorld({ state, receivedAt, arrival, connectionError, onChanged, onOpenLives }: {
  state: AliveResponse
  /** Local time (seconds) when `state` arrived, to run the clock between polls. */
  receivedAt: number
  arrival: boolean
  connectionError: string
  onChanged: () => Promise<void>
  onOpenLives?: () => void
}) {
  // Keyed on the life id too: a new life always needs its own store and sync, even in the
  // unlikely case its world seed matched the previous life's.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const store = useMemo(() => new WorldStore(state.world_seed), [state.world_seed, state.life.id])
  // Block changes wait REPLAY_DELAY before they reach the store, so they land when the replayed
  // pet (drawn that far behind the server) mines or places the block.
  const delayed = useMemo(() => new DelayedBlocks((changes, reset) => { store.applyServerChanges(changes, reset) }),
    [store])
  const sync = useMemo(() => new BlockSync(blocksFetcher(state.life.id), (changes, reset) => {
    delayed.push(changes, reset)
  }), [delayed, state.life.id])
  const [following, setFollowing] = useState(true)
  const [helloCount, setHelloCount] = useState(0)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [syncError, setSyncError] = useState('')
  const [showCrafting, setShowCrafting] = useState(false)
  const [showJournal, setShowJournal] = useState(false)
  const [craftMessage, setCraftMessage] = useState('')
  const [cameraMode, setCameraMode] = useState<CameraMode>(() => loadCameraMode(browserStorage))
  const [autoPick, setAutoPick] = useState<AutoPick | null>(null)
  // Hidden at first on short screens, where it would cover the vitals; M or the Map button shows it.
  const [mapOpen, setMapOpen] = useState(() => loadMapOpen(browserStorage,
    mapShownByDefault(window.innerWidth, window.innerHeight)))

  // Any camera choice, or auto switching, follows Mimo again.
  const chooseCamera = useCallback((mode: CameraMode) => {
    setCameraMode(mode)
    saveCameraMode(browserStorage, mode)
    setFollowing(true)
  }, [])
  const autoPicked = useCallback((pick: AutoPick) => {
    setAutoPick(pick)
    setFollowing(true)
  }, [])

  useEffect(() => {
    const cycle = (event: KeyboardEvent) => {
      if (event.repeat || !isCameraKey(event)) return
      chooseCamera(nextMode(cameraMode))
    }
    window.addEventListener('keydown', cycle)
    return () => window.removeEventListener('keydown', cycle)
  }, [cameraMode, chooseCamera])

  const showMap = useCallback((open: boolean) => {
    setMapOpen(open)
    saveMapOpen(browserStorage, open)
  }, [])

  useEffect(() => {
    const toggle = (event: KeyboardEvent) => {
      if (event.repeat || !isMapKey(event)) return
      showMap(!mapOpen)
    }
    window.addEventListener('keydown', toggle)
    return () => window.removeEventListener('keydown', toggle)
  }, [mapOpen, showMap])

  // Poll-driven: receivedAt changes every second, so a failed delta is retried on the next poll.
  // Once a sync has caught the store up, later changes are held back (see DelayedBlocks).
  useEffect(() => {
    sync.syncTo(state.blocks_seq).then(
      (ran) => {
        if (ran || sync.seq === state.blocks_seq) delayed.goLive()
        setSyncError('')
      },
      () => setSyncError('Some block changes could not be loaded. Retrying.'),
    )
  }, [sync, delayed, state.blocks_seq, receivedAt])

  useEffect(() => {
    const timer = window.setInterval(() => { delayed.flush() }, 100)
    return () => window.clearInterval(timer)
  }, [delayed])

  const seconds = useCallback(() => liveClock(state.clock, receivedAt, Date.now() / 1000).secondsIntoDay,
    [state.clock, receivedAt])
  const serverTime = useCallback(() => serverNow(state.server_time, receivedAt, Date.now() / 1000),
    [state.server_time, receivedAt])
  const stations = useMemo(() => store.materialsNear(state.position.x, state.position.z, 6),
    // Re-read once per poll, after the block delta for that poll has been applied.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [store, receivedAt, state.position.x, state.position.z])

  const run = async (action: () => Promise<unknown>, done?: () => void) => {
    setBusy(true)
    setMessage('')
    try {
      await action()
      done?.()
      await onChanged()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'That did not work. Try again.')
    } finally {
      setBusy(false)
    }
  }

  const minimap = mapOpen
    ? <Minimap store={store} position={state.position} explored={state.explored} structures={state.structures}
        landmarks={state.landmarks} creatures={state.creatures} action={state.action} name={state.life.name}
        onHide={() => showMap(false)} />
    : (
      <button type="button" onClick={() => showMap(true)} title="Show the map (M)"
        className="rounded-xl border border-white/75 bg-[#f5faf7]/90 px-3 py-1.5 text-xs font-medium text-[#315e58] shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md hover:bg-white">
        Map
      </button>
    )

  const care = (kind: CareKind) => { void run(() => giveCare(kind)) }
  const hello = () => { void run(sayHello, () => setHelloCount((count) => count + 1)) }
  const craft = async (action: string, item: string) => {
    try {
      setCraftMessage((await helpMimo(action, item)).message)
      await onChanged()
    } catch (error) {
      setCraftMessage(error instanceof Error ? error.message : 'That action could not be completed.')
    }
  }

  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <WorldCanvas store={store} position={state.position} seconds={seconds} arrival={arrival}
        following={following} onOrbit={() => setFollowing(false)} onPetClick={hello} hopSignal={helloCount}
        action={state.action} recentActions={state.recent_actions} decays={state.decays} structures={state.structures}
        creatures={state.creatures} creatureMoves={state.creature_moves} inventory={state.inventory} hurtAt={state.hurt_at}
        serverTime={serverTime}
        cameraMode={cameraMode} onAutoPick={autoPicked} />
      <SurvivalHud state={state} online={!connectionError && workerOnline(state.server_time, state.last_tick_at)}
        busy={busy} message={message || connectionError || syncError}
        cameraMode={cameraMode} autoPick={autoPick} minimap={minimap} onCameraMode={chooseCamera}
        onCare={care} onHello={hello} onFollow={() => setFollowing(true)}
        onCrafting={() => setShowCrafting(true)} onJournal={() => setShowJournal(true)} onOpenLives={onOpenLives} />
      {showCrafting && (
        <CraftingPanel name={state.life.name} inventory={state.inventory} chests={state.chests} recipes={state.recipes} stations={stations}
          worldSeed={state.world_seed} message={craftMessage} onAction={(action, item) => { void craft(action, item) }}
          onClose={() => setShowCrafting(false)} />
      )}
      {showJournal && <JournalPanel name={state.life.name} journal={state.journal} onClose={() => setShowJournal(false)} />}
    </main>
  )
}

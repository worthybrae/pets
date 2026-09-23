import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import type { OrbitControls as OrbitControlsType } from 'three-stdlib'
import * as THREE from 'three'
import type { BlockEdit } from '../types/world'
import PetEntity from '../components/world/PetEntity'
import WorldManager from '../components/world/WorldManager'
import { previewPet } from '../components/world/previewWorld'
import { applyBlockEdits, ensureTerrainAround, ORBITAL_STATION } from '../components/world/expandingWorld'
import { compileWorldPlan, worldForPlannerState, type WorldPlan } from '../components/world/worldPlanner'
import { DEFAULT_WORLD_SEED, terrainHeight } from '../components/world/worldgen'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WILDERNESS = { x: 260, z: 120 }
interface Point { x: number; y?: number; z: number }
interface MimoEvent { id: number; at: number; kind: string; text: string }
interface LiveMimoState {
  name: string
  world_seed: string
  position: Point
  energy: number
  mood: number
  plans: WorldPlan[]
  currentIndex: number
  progress: number
  status: string
  last_thought: string
  last_observation: string
  last_action_at: number
  last_error: string | null
  worker_last_seen_at: number | null
  fetched_at: number
  block_edits: BlockEdit[]
  catalog: Record<string, { color: number[] }>
  inventory: Record<string, number>
  recipes: Record<string, { ingredients: Record<string, number>; output: Record<string, number>; station?: string }>
  events: MimoEvent[]
}

function BuildCamera({ focus, focusY, initialFocus, initialFocusY, distance, follow, onOrbit, onChunkChange }: {
  focus: Point
  focusY: number
  initialFocus: Point
  initialFocusY: number
  distance: number
  follow: boolean
  onOrbit: () => void
  onChunkChange: (x: number, z: number) => void
}) {
  const controlsRef = useRef<OrbitControlsType>(null)
  const lastChunk = useRef('0,0')
  const { camera } = useThree()

  useFrame((_, delta) => {
    const controls = controlsRef.current
    if (!controls) return
    if (follow) {
      const desired = new THREE.Vector3(focus.x, focusY, focus.z)
      const movement = desired.sub(controls.target).multiplyScalar(1 - Math.exp(-3 * delta))
      controls.target.add(movement)
      camera.position.add(movement)
      const offset = camera.position.clone().sub(controls.target)
      const currentDistance = offset.length()
      camera.position.addScaledVector(offset.normalize(), (distance - currentDistance) * (1 - Math.exp(-2 * delta)))
      controls.update()
    }
    const cx = Math.floor(controls.target.x / 16)
    const cz = Math.floor(controls.target.z / 16)
    const key = `${cx},${cz}`
    if (key !== lastChunk.current) {
      lastChunk.current = key
      onChunkChange(cx, cz)
    }
  })

  return (
    <OrbitControls ref={controlsRef} target={[initialFocus.x, initialFocusY, initialFocus.z]}
      enableDamping dampingFactor={0.08} minDistance={11} maxDistance={130}
      maxPolarAngle={Math.PI / 2.04} onStart={onOrbit} />
  )
}

function LiveWorld({ state, onHello, onAction, connectionError }: {
  state: LiveMimoState
  onHello: () => Promise<void>
  onAction: (action: string, item: string) => Promise<string>
  connectionError: string
}) {
  const worldSeed = state.world_seed || DEFAULT_WORLD_SEED
  const [initialPosition] = useState<Point>(() => ({ ...state.position }))
  const [cameraChunk, setCameraChunk] = useState(() => ({ x: Math.floor(state.position.x / 16), z: Math.floor(state.position.z / 16) }))
  const [following, setFollowing] = useState(true)
  const [viewingStation, setViewingStation] = useState(false)
  const [viewingWilderness, setViewingWilderness] = useState(false)
  const [helloCount, setHelloCount] = useState(0)
  const [showSystems, setShowSystems] = useState(false)
  const [interactionError, setInteractionError] = useState('')
  const [systemMessage, setSystemMessage] = useState('')
  const plan = state.plans[state.currentIndex]
  const project = useMemo(() => compileWorldPlan(plan), [plan])
  const targetStepIndex = Math.floor(project.voxels.length * state.progress / 100)
  const [revealed, setRevealed] = useState(() => ({ projectIndex: state.currentIndex, count: targetStepIndex }))
  const revealedRef = useRef(revealed)
  const stepIndex = revealed.projectIndex === state.currentIndex ? Math.min(revealed.count, targetStepIndex) : targetStepIndex
  const visibleProgress = project.voxels.length ? Math.round(stepIndex / project.voxels.length * 100) : 100
  useEffect(() => { revealedRef.current = revealed }, [revealed])
  useEffect(() => {
    const current = revealedRef.current
    if (current.projectIndex !== state.currentIndex || current.count > targetStepIndex) {
      setRevealed({ projectIndex: state.currentIndex, count: targetStepIndex })
      return
    }
    if (current.count >= targetStepIndex) return
    const startCount = current.count
    const newBlocks = targetStepIndex - startCount
    const startedAt = performance.now()
    let frame = 0
    const revealFrame = (time: number) => {
      const fraction = Math.min(1, (time - startedAt) / 4800)
      const count = startCount + Math.max(1, Math.ceil(newBlocks * fraction))
      setRevealed((previous) => previous.projectIndex === state.currentIndex && count > previous.count
        ? { ...previous, count: Math.min(count, targetStepIndex) } : previous)
      if (fraction < 1) frame = window.requestAnimationFrame(revealFrame)
    }
    frame = window.requestAnimationFrame(revealFrame)
    return () => window.cancelAnimationFrame(frame)
  }, [state.currentIndex, targetStepIndex])
  const chunks = useMemo(() => {
    const viewCenter = { x: cameraChunk.x * 16, z: cameraChunk.z * 16 }
    const built = worldForPlannerState({ plans: state.plans, currentIndex: state.currentIndex, stepIndex },
      viewCenter, 112, worldSeed)
    const nearbyEdits = state.block_edits.filter((edit) =>
      Math.abs(edit.x - viewCenter.x) <= 112 && Math.abs(edit.z - viewCenter.z) <= 112)
    const edited = applyBlockEdits(built, nearbyEdits, state.catalog, worldSeed)
    return ensureTerrainAround(edited, cameraChunk.x * 16, cameraChunk.z * 16, 6, worldSeed)
  }, [state.plans, state.currentIndex, state.block_edits, state.catalog, worldSeed,
    stepIndex, cameraChunk.x, cameraChunk.z])
  const pet = useMemo(() => ({
    ...previewPet, position: { ...previewPet.position, x: initialPosition.x, y: initialPosition.y ?? 1, z: initialPosition.z },
  }), [initialPosition])
  const workerOnline = !connectionError && state.worker_last_seen_at !== null && state.fetched_at - state.worker_last_seen_at < 25
  const activelyLiving = workerOnline && state.status !== 'waiting_for_model'
  const nearbyStations = new Set(state.block_edits.filter((block) =>
    (block.material === 'crafting_table' || block.material === 'furnace') &&
    Math.hypot(block.x - state.position.x, block.z - state.position.z) <= 6
  ).map((block) => block.material))
  const cameraFocus = viewingStation ? ORBITAL_STATION : viewingWilderness ? WILDERNESS : state.progress < 100
    ? { x: (state.position.x + plan.site.x) / 2, z: (state.position.z + plan.site.z) / 2 }
    : state.position
  const cameraY = viewingStation ? ORBITAL_STATION.centerY
    : viewingWilderness ? terrainHeight(WILDERNESS.x, WILDERNESS.z, worldSeed) + 2
      : state.position.y ?? 1

  const sayHello = async () => {
    setInteractionError('')
    try {
      await onHello()
      setHelloCount((count) => count + 1)
    } catch {
      setInteractionError('Mimo could not hear you. The server may be offline.')
    }
  }

  const helpMimo = async (action: string, item: string) => {
    try {
      setSystemMessage(await onAction(action, item))
    } catch (error) {
      setSystemMessage(error instanceof Error ? error.message : 'That action could not be completed.')
    }
  }

  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <div className="absolute inset-0">
        <Canvas camera={{ position: [initialPosition.x + 18, 14, initialPosition.z + 18], fov: 48, near: 0.1, far: 280 }}
          gl={{ antialias: true }} dpr={[1, 2]}>
          <color attach="background" args={['#dce9eb']} />
          <fog attach="fog" args={['#dce9eb', 68, 116]} />
          <ambientLight intensity={0.8} />
          <directionalLight position={[12, 24, 16]} intensity={1.7} />
          <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
          <WorldManager chunks={chunks} cameraChunkX={cameraChunk.x} cameraChunkZ={cameraChunk.z} viewDistance={6} />
          <PetEntity pet={pet} scale={0.31}
            destination={{ x: state.position.x, y: state.position.y, z: state.position.z, token: Math.round(state.last_action_at) }}
            onPetClick={() => { void sayHello() }} hopSignal={helloCount}>
            {[-0.25, 1.25].map((x) => (
              <mesh key={x} position={[x, 3.35, 2.08]}>
                <boxGeometry args={[0.34, 0.38, 0.16]} />
                <meshStandardMaterial color="#39454a" />
              </mesh>
            ))}
            <mesh position={[0.5, 2.58, 2.1]}>
              <boxGeometry args={[0.32, 0.25, 0.18]} />
              <meshStandardMaterial color="#cd8a84" />
            </mesh>
          </PetEntity>
          <BuildCamera focus={cameraFocus} focusY={cameraY} initialFocus={initialPosition} initialFocusY={initialPosition.y ?? 1}
            distance={viewingStation ? 84 : viewingWilderness ? 52 : state.progress < 100 ? 30 : 26} follow={following}
            onOrbit={() => setFollowing(false)}
            onChunkChange={(x, z) => setCameraChunk((current) => current.x === x && current.z === z ? current : { x, z })} />
        </Canvas>
      </div>

      <div className="pointer-events-none absolute left-5 top-20 z-10 max-w-xs sm:left-10 sm:top-24">
        <p className="mb-2 text-sm font-medium text-[#637d79]">Mimo's world</p>
        <h1 className="text-4xl font-semibold leading-[1.04] tracking-[-0.065em] sm:text-6xl">Made by Mimo.</h1>
        <p className="mt-4 max-w-[18rem] text-sm leading-6 text-[#4f6967] sm:text-base">
          Mimo's world and activity are stored on the server. Its worker runs while this page is closed.
        </p>
      </div>

      <div className="absolute right-5 top-5 z-10 max-w-[15rem] rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-4 py-3 text-xs shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md sm:right-10 sm:top-9">
        <p className="font-semibold"><span className={activelyLiving ? 'text-[#3c9a73]' : 'text-[#c76e5c]'}>●</span> {activelyLiving ? 'Mimo is live' : workerOnline ? 'Mimo is paused' : 'Worker offline'}</p>
        <p className="mt-1 text-[#54726e]">{state.status.replaceAll('_', ' ')} · energy {Math.round(state.energy)}%</p>
        <p className="mt-1 text-[#54726e]">Last action {new Date(state.last_action_at * 1000).toLocaleString()}</p>
      </div>

      <div className="absolute bottom-6 left-5 right-5 z-10 flex flex-col gap-4 sm:bottom-9 sm:left-10 sm:right-10 sm:flex-row sm:items-end sm:justify-between">
        <div className="w-[min(100%,21rem)] rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-5 py-4 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f5c0a9] text-xl" aria-hidden="true">✿</div>
            <div>
              <p className="text-base font-semibold leading-tight">Mimo</p>
              <p className="text-xs text-[#65817b]">{state.status.replaceAll('_', ' ')}</p>
            </div>
          </div>
          <p className="mt-4 text-sm font-medium">{stepIndex < project.voxels.length ? 'Building' : 'Finished'} {project.name}</p>
          {stepIndex < project.voxels.length && <p className="mt-1 text-xs text-[#54726e]">{stepIndex} / {project.voxels.length} blocks placed</p>}
          <p className="mt-2 text-xs leading-5 text-[#54726e]">{plan.observation}</p>
          <p className="mt-2 text-xs italic leading-5 text-[#54726e]">“{state.last_thought}”</p>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar"
            aria-valuenow={visibleProgress} aria-valuemin={0} aria-valuemax={100} aria-label={`${project.name} progress`}>
            <div className="h-full rounded-full bg-[#4d8c77] transition-[width] duration-150" style={{ width: `${visibleProgress}%` }} />
          </div>
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={() => { void sayHello() }}
              className="flex-1 rounded-xl bg-[#315e58] px-3 py-2.5 text-sm font-medium text-white hover:bg-[#244b47]">Say hello</button>
            <button type="button" onClick={() => { setViewingStation(false); setViewingWilderness(false); setFollowing(true) }}
              className="flex-1 rounded-xl border border-[#bfd5cd] px-3 py-2.5 text-sm font-medium text-[#315e58] hover:bg-white">Follow Mimo</button>
          </div>
          <button type="button" onClick={() => { setViewingStation(true); setViewingWilderness(false); setFollowing(true) }}
            className="mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4">
            Visit the orbital station
          </button>
          <button type="button" onClick={() => { setViewingStation(false); setViewingWilderness(true); setFollowing(true) }}
            className="ml-4 mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4">
            Explore the wilderness
          </button>
          <button type="button" onClick={() => setShowSystems(true)}
            className="ml-4 mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4">
            Blocks & crafting
          </button>
          {(state.last_error || interactionError) && <p className="mt-3 text-xs text-[#a65b50]">{interactionError || state.last_error}</p>}
        </div>
        <div className="hidden w-64 rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-4 py-4 text-xs shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md md:block">
          <p className="mb-2 font-semibold">Mimo's inventory</p>
          <div className="mb-4 flex flex-wrap gap-1.5 text-[#315e58]">
            {Object.entries(state.inventory).filter(([, amount]) => amount > 0).slice(0, 8).map(([item, amount]) =>
              <span key={item} className="rounded-md bg-[#e1eee7] px-2 py-1">{item.replaceAll('_', ' ')} ×{amount}</span>)}
          </div>
          <p className="mb-2 font-semibold">What Mimo has done</p>
          <ul className="space-y-2 text-[#54726e]">
            {state.events.slice(0, 4).map((event) => <li key={event.id}>{event.text}</li>)}
          </ul>
          <p className="mt-3 text-[#65817b]">Drag to look around · Scroll to zoom</p>
        </div>
      </div>
      {showSystems && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={() => setShowSystems(false)}>
          <section role="dialog" aria-modal="true" aria-label="Mimo's blocks and crafting" onClick={(event) => event.stopPropagation()}
            className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
            <div className="flex items-start justify-between gap-4">
              <div><p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">World systems</p>
                <h2 className="mt-1 text-3xl font-semibold tracking-tight">Blocks & crafting</h2></div>
              <button type="button" onClick={() => setShowSystems(false)} aria-label="Close blocks and crafting" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
            </div>
            <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">Mimo can mine, place, craft, and smelt these materials. You can help with crafting here. Inventory and machines persist when you leave.</p>
            <p className="mt-2 text-xs text-[#54726e]">World seed: <code>{worldSeed}</code></p>
            <h3 className="mt-6 text-sm font-semibold">Mimo's inventory</h3>
            <div className="mt-2 flex flex-wrap gap-2 text-sm">
              {Object.entries(state.inventory).filter(([, amount]) => amount > 0).map(([item, amount]) =>
                <span key={item} className="rounded-lg bg-[#e1eee7] px-3 py-1.5">{item.replaceAll('_', ' ')} ×{amount}</span>)}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" disabled={!state.inventory.crafting_table} onClick={() => { void helpMimo('place_machine', 'crafting_table') }}
                className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place crafting table</button>
              <button type="button" disabled={!state.inventory.furnace} onClick={() => { void helpMimo('place_machine', 'furnace') }}
                className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place furnace</button>
              <button type="button" disabled={!state.inventory.iron_ore || !nearbyStations.has('furnace') || !(state.inventory.coal || state.inventory.planks)} onClick={() => { void helpMimo('smelt', 'iron_ore') }}
                className="rounded-lg border border-[#bfd5cd] px-3 py-2 text-xs font-medium text-[#315e58] disabled:cursor-not-allowed disabled:opacity-35">Smelt iron ore</button>
            </div>
            <p className="mt-2 text-xs text-[#65817b]">Smelting needs a placed furnace and coal or planks for fuel.</p>
            {systemMessage && <p className="mt-3 rounded-lg bg-[#e1eee7] px-3 py-2 text-xs text-[#315e58]" role="status">{systemMessage}</p>}
            <h3 className="mt-6 text-sm font-semibold">{Object.keys(state.catalog).length} block types</h3>
            <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(state.catalog).map(([name, block]) => (
                <div key={name} className="flex items-center gap-2 rounded-lg border border-[#d6e5dc] px-2 py-1.5 text-xs">
                  <span className="h-5 w-5 shrink-0 rounded-sm border border-black/10" style={{ backgroundColor: `rgb(${block.color.join(',')})` }} />
                  {name.replaceAll('_', ' ')}
                </div>
              ))}
            </div>
            <h3 className="mt-6 text-sm font-semibold">Recipes</h3>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {Object.entries(state.recipes).map(([name, recipe]) => (
                <div key={name} className="rounded-xl bg-[#e9f2eb] px-3 py-2 text-xs leading-5">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold">{name.replaceAll('_', ' ')}</p>
                    <button type="button" disabled={Boolean(recipe.station && !nearbyStations.has(recipe.station)) ||
                      Object.entries(recipe.ingredients).some(([item, amount]) => (state.inventory[item] || 0) < amount)}
                      onClick={() => { void helpMimo('craft', name) }}
                      className="rounded-md bg-[#315e58] px-2 py-1 font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-35">Craft</button>
                  </div>
                  <p className="text-[#54726e]">{Object.entries(recipe.ingredients).map(([item, amount]) => `${amount} ${item.replaceAll('_', ' ')}`).join(' + ')}
                    {recipe.station ? ` · needs placed ${recipe.station.replaceAll('_', ' ')}` : ''}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </main>
  )
}

export default function WorldPreview() {
  const [state, setState] = useState<LiveMimoState | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/mimo`)
      if (!response.ok) throw new Error(`Server returned ${response.status}`)
      const next = await response.json() as LiveMimoState
      next.fetched_at = Date.now() / 1000
      setState((previous) => {
        if (previous && JSON.stringify(previous.plans) === JSON.stringify(next.plans)) next.plans = previous.plans
        if (previous && JSON.stringify(previous.block_edits) === JSON.stringify(next.block_edits)) next.block_edits = previous.block_edits
        if (previous && JSON.stringify(previous.catalog) === JSON.stringify(next.catalog)) next.catalog = previous.catalog
        return next
      })
      setError('')
    } catch {
      setError('Mimo’s server is unavailable. Its world will appear when the server is running.')
    }
  }, [])

  useEffect(() => {
    const initial = window.setTimeout(() => { void refresh() }, 0)
    const timer = window.setInterval(() => { void refresh() }, 1000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [refresh])

  const hello = async () => {
    const response = await fetch(`${API_URL}/api/mimo/hello`, { method: 'POST' })
    if (!response.ok) throw new Error('Greeting failed')
    await refresh()
  }

  const act = async (action: string, item: string) => {
    const response = await fetch(`${API_URL}/api/mimo/action`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, item }),
    })
    const result = await response.json() as { message?: string; detail?: string }
    if (!response.ok) throw new Error(result.detail || 'That action could not be completed.')
    await refresh()
    return result.message || 'Done.'
  }

  if (!state) return (
    <main className="flex min-h-screen items-center justify-center bg-[#dce9eb] px-6 text-center text-[#315e58]">
      <div><p className="text-2xl font-semibold">Connecting to Mimo’s world…</p>
        {error && <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{error}</p>}
        {error && <button type="button" onClick={() => { void refresh() }} className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>}
      </div>
    </main>
  )
  return <LiveWorld state={state} onHello={hello} onAction={act} connectionError={error} />
}

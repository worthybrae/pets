import { useCallback, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import BlockWorld, { type ViewStats } from '../engine/BlockWorld'
import { fogRange } from '../engine/fog'
import type { WorldStore } from '../engine/worldStore'
import DayNight, { PetGlow } from './DayNight'
import FollowCamera from './FollowCamera'
import { focusPoint } from './motion'
import { REPLAY_DELAY, replayAt } from './replay'
import { daylightFactor } from './sky'
import ActionEffects from './ActionEffects'
import LeafPuffs from './LeafPuffs'
import { cutawayFor } from './cutaway'
import SurvivalPet from './SurvivalPet'
import type { FinishedAction, LeafDecay, MimoAction } from './types'

const CAMERA_DISTANCE = 26
const DAY_SKY = '#dce9eb'
const NO_ACTIONS: FinishedAction[] = []
const NO_DECAYS: LeafDecay[] = []

/** Phones and low-core devices draw fewer columns. */
function pickViewDistance(): number {
  const small = Math.min(window.innerWidth, window.innerHeight) < 600
  return small || (navigator.hardwareConcurrency ?? 8) <= 4 ? 4 : 6
}

/**
 * The 3D world around one pet: terrain from the store, the pet, and a camera that follows it.
 * With `seconds` (game seconds into the day) the sky, lights and terrain follow day and night;
 * without it the scene stays in daylight. `arrival` starts the camera high so it flies down.
 * `action` and `serverTime` (server seconds now) let the pet walk its path and act out its step.
 * When the pet is underground, the terrain over it is cut away (cutaway.ts).
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, serverTime }: {
  store: WorldStore
  position: { x: number; y: number; z: number }
  seconds?: () => number
  arrival?: boolean
  following: boolean
  onOrbit: () => void
  onPetClick?: () => void
  hopSignal?: number
  action?: MimoAction | null
  recentActions?: FinishedAction[]
  decays?: LeafDecay[]
  serverTime?: () => number
}) {
  const [viewDistance] = useState(pickViewDistance)
  const [debug] = useState(() => new URLSearchParams(window.location.search).has('debug'))
  const [stats, setStats] = useState<ViewStats | null>(null)
  const [engineError, setEngineError] = useState('')
  const [engineKey, setEngineKey] = useState(0)
  const [initial] = useState(() => ({ ...position }))
  const [cameraChunk, setCameraChunk] = useState(() => ({ x: Math.floor(position.x / 16), z: Math.floor(position.z / 16) }))
  const [fogNear, fogFar] = fogRange(viewDistance, CAMERA_DISTANCE)
  // The pet is drawn REPLAY_DELAY seconds behind the server, so a step that started and ended
  // between two polls still plays out. Without a server clock (archives) it stands still.
  const replayTime = useCallback(() => (serverTime ? serverTime() - REPLAY_DELAY : 0), [serverTime])
  // The same interpolated point SurvivalPet renders at, so the camera tracks the walk instead of
  // snapping only when the server's polled position changes.
  const focusAt = useCallback(() => {
    const t = replayTime()
    const { step, rest } = replayAt(action, recentActions, position, t)
    return focusPoint(step, rest, t)
  }, [action, recentActions, position, replayTime])
  // Underground, the terrain over the drawn pet is cut away so the camera can still see it.
  const cutawayAt = useCallback(() => cutawayFor(store, serverTime ? focusAt() : position),
    [store, serverTime, focusAt, position])

  return (
    <>
      <div className="absolute inset-0">
        <Canvas camera={{ position: [initial.x + 18, initial.y + (arrival ? 80 : 13), initial.z + 18], fov: 48, near: 0.1, far: 320 }}
          gl={{ antialias: true }} dpr={[1, 2]}>
          <color attach="background" args={[DAY_SKY]} />
          <fog attach="fog" args={[DAY_SKY, fogNear, fogFar]} />
          {seconds ? <DayNight seconds={seconds} /> : (
            <>
              <ambientLight intensity={0.8} />
              <directionalLight position={[12, 24, 16]} intensity={1.7} />
              <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
            </>
          )}
          <BlockWorld key={engineKey} store={store} centerX={cameraChunk.x * 16 + 8} centerZ={cameraChunk.z * 16 + 8}
            viewDistance={viewDistance} daylight={seconds ? () => daylightFactor(seconds()) : undefined}
            cutaway={cutawayAt}
            onStats={debug ? setStats : undefined} onError={setEngineError} />
          <SurvivalPet action={action} recent={recentActions} position={position} now={replayTime} onPetClick={onPetClick} hopSignal={hopSignal}>
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
            {seconds && <PetGlow seconds={seconds} />}
          </SurvivalPet>
          {serverTime && <ActionEffects store={store} action={action} recent={recentActions} position={position} now={replayTime} />}
          {serverTime && <LeafPuffs decays={decays} now={replayTime} />}
          <FollowCamera focus={position} focusY={position.y} focusAt={serverTime ? focusAt : undefined}
            initialFocus={initial} initialFocusY={initial.y}
            distance={CAMERA_DISTANCE} follow={following} viewDistance={viewDistance} onOrbit={onOrbit}
            onChunkChange={(x, z) => setCameraChunk((current) => current.x === x && current.z === z ? current : { x, z })} />
        </Canvas>
      </div>

      {debug && stats && (
        <div className="pointer-events-none absolute bottom-3 left-3 z-30 rounded-lg bg-black/70 px-3 py-2 font-mono text-[11px] leading-5 text-white">
          {stats.fps} fps · {stats.drawCalls} draws<br />
          {stats.columns} columns · {stats.pending} pending · mesh {stats.lastMeshMs.toFixed(1)} ms
        </div>
      )}

      {engineError && (
        <div className="absolute inset-0 z-40 flex items-center justify-center bg-[#dce9eb]/90 px-6 text-center text-[#315e58]">
          <div>
            <p className="text-2xl font-semibold">The world stopped drawing</p>
            <p className="mx-auto mt-3 max-w-sm text-sm leading-6">{engineError}</p>
            <button type="button" onClick={() => { setEngineError(''); setEngineKey((key) => key + 1) }}
              className="mt-5 rounded-xl bg-[#315e58] px-4 py-2 text-sm text-white">Try again</button>
          </div>
        </div>
      )}
    </>
  )
}

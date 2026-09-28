import { useCallback, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import BlockWorld, { type ViewStats } from '../engine/BlockWorld'
import { fogRange } from '../engine/fog'
import type { WorldStore } from '../engine/worldStore'
import DayNight, { PetGlow } from './DayNight'
import FollowCamera, { type ReplayedStep } from './FollowCamera'
import { focusPoint } from './motion'
import { REPLAY_DELAY, replayAt } from './replay'
import { daylightFactor } from './sky'
import ActionEffects from './ActionEffects'
import CombatEffects from './CombatEffects'
import LeafPuffs from './LeafPuffs'
import { CLOSE_DISTANCE, cutawayFor, type AutoPick, type CameraMode, type ViewMode } from './cameraModes'
import { hidden, holdWallCut, shelterBlocks } from './cutaway'
import SurvivalCreatures from './SurvivalCreatures'
import SurvivalDoors from './SurvivalDoors'
import SurvivalPet from './SurvivalPet'
import { wornCap, wornCloak, wornTunic } from './petGear'
import { easeToward, freezeSeconds, SNOW_EASE_SECONDS } from './seasons'
import WeatherEffects from './WeatherEffects'
import type { Ailments, Built, Creature, CreatureMove, FinishedAction, LeafDecay, MimoAction, Point, SkyView } from './types'

const CAMERA_DISTANCE = 26
const DAY_SKY = '#dce9eb'
const NO_ACTIONS: FinishedAction[] = []
const NO_DECAYS: LeafDecay[] = []
const NO_STRUCTURES: Built[] = []

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
 * When the pet is underground, or a wall or roof of a shelter it built (`structures`) hides it, the
 * terrain over it is cut away (cutaway.ts) as the camera mode says (cameraModes.ts). `cameraMode`
 * defaults to the overview camera (archives). `creatures` and `creatureMoves` (L1) are drawn
 * replaying their moves the same REPLAY_DELAY behind the server as the pet. L2: the doors Mimo
 * built swing open as the drawn pet passes, arrows fly and hostiles burn (CombatEffects), and the
 * pet wears the armor in `inventory` and glows red when a creature hits it (`hurtAt`). W1: it shows what ails it
 * (`ailments`) and a "?" while it has just asked its owner something (`asking`). W2: the season and the
 * weather (`sky`) tint the sky, fog closes in and lightning flashes.
 */
export default function WorldCanvas({ store, position, seconds, arrival = false, following, onOrbit, onPetClick, hopSignal = 0, action = null, recentActions = NO_ACTIONS, decays = NO_DECAYS, structures = NO_STRUCTURES, creatures, creatureMoves, inventory, hurtAt = null, ailments = null, asking = false, sky = null, sheltered = false, timeScale = 1, serverTime, cameraMode = 'overview', onAutoPick, doorsOpen }: {
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
  /** What Mimo built (the snapshot's list); its shelters' walls and roofs may be cut away. */
  structures?: Built[]
  /** Making: the doors a machine holds open ([x, y, z]). */
  doorsOpen?: readonly number[][]
  /** The creatures near Mimo and their last moves (the snapshot's lists). */
  creatures?: Creature[]
  creatureMoves?: CreatureMove[]
  /** What Mimo carries (L2: the armor it wears) and when a creature last hurt it. */
  inventory?: Record<string, number>
  hurtAt?: number | null
  /** W1: what ails Mimo, and whether it has just asked its owner something. */
  ailments?: Ailments | null
  asking?: boolean
  /** W2: the season and the weather (the snapshot's `sky`); whether Mimo stands inside the shelter it built (no rain
   * or snow falls round a camera close to it there); the clock's pace, for how fast the ice comes and goes. */
  sky?: SkyView | null
  sheltered?: boolean
  timeScale?: number
  serverTime?: () => number
  cameraMode?: CameraMode
  /** Called when the auto camera picks overview or close. */
  onAutoPick?: (pick: AutoPick) => void
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
  // The step SurvivalPet plays, so the camera tracks the walk (and turns with it in the close and
  // eyes modes) instead of snapping only when the server's polled position changes.
  const stepAt = useCallback((): ReplayedStep => {
    const t = replayTime()
    return { ...replayAt(action, recentActions, position, t), t }
  }, [action, recentActions, position, replayTime])
  // From FollowCamera each frame: which mode's cut to draw, whether it is inside the pet, how far
  // back the close camera sits (the close cut reaches just past it) and the frame clock.
  const view = useRef<{ cut: ViewMode; petHidden: boolean; closeDistance: number; now: number }>(
    { cut: 'overview', petHidden: false, closeDistance: CLOSE_DISTANCE, now: 0 })
  const onView = useCallback((cut: ViewMode, petHidden: boolean, closeDistance: number, now: number) => {
    view.current.cut = cut
    view.current.petHidden = petHidden
    view.current.closeDistance = closeDistance
    view.current.now = now
  }, [])
  // Only the walls and roofs of a shelter Mimo built count as hiding it, never a natural hill.
  const walls = useMemo(() => shelterBlocks(store, structures), [store, structures])
  // When those walls last hid the drawn pet (frame clock seconds), for the wall cut's hold.
  const wallsLastHid = useRef<number | null>(null)
  // Underground, or hidden behind a wall or roof it built, the terrain over the drawn pet is cut
  // away so the camera can still see it (closer in close mode, not at all from its eyes).
  const cutawayAt = useCallback((camera: Point) => {
    const pose = serverTime ? stepAt() : null
    const at = pose ? focusPoint(pose.step, pose.rest, pose.t) : position
    const held = holdWallCut(hidden(store, at, camera, walls), wallsLastHid.current, view.current.now)
    wallsLastHid.current = held.lastHidden
    return cutawayFor(view.current.cut, store, at, held.on, view.current.closeDistance)
  }, [store, serverTime, stepAt, position, walls])
  const petHidden = useCallback(() => view.current.petHidden, [])
  // W2: the snow cover and the ice drawn on the terrain, eased toward the server's (seasons.ts).
  const cover = useRef({ snow: sky?.snow ?? 0, frozen: sky?.frozen ? 1 : 0 })
  const weatherNow = useCallback((delta: number): [number, number] => {
    const drawn = cover.current
    drawn.snow = easeToward(drawn.snow, sky?.snow ?? 0, delta, SNOW_EASE_SECONDS)
    drawn.frozen = easeToward(drawn.frozen, sky?.frozen ? 1 : 0, delta, freezeSeconds(timeScale))
    return [drawn.snow, drawn.frozen]
  }, [sky, timeScale])
  // Where the drawn pet is, for the doors it opens (L2).
  const petAt = useCallback(() => {
    const pose = stepAt()
    return focusPoint(pose.step, pose.rest, pose.t)
  }, [stepAt])

  return (
    <>
      <div className="absolute inset-0">
        <Canvas camera={{ position: [initial.x + 18, initial.y + (arrival ? 80 : 13), initial.z + 18], fov: 48, near: 0.1, far: 320 }}
          gl={{ antialias: true }} dpr={[1, 2]}>
          <color attach="background" args={[DAY_SKY]} />
          <fog attach="fog" args={[DAY_SKY, fogNear, fogFar]} />
          {seconds ? <DayNight seconds={seconds} sky={sky} now={serverTime ? replayTime : undefined} fog={[fogNear, fogFar]} /> : (
            <>
              <ambientLight intensity={0.8} />
              <directionalLight position={[12, 24, 16]} intensity={1.7} />
              <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
            </>
          )}
          <BlockWorld key={engineKey} store={store} centerX={cameraChunk.x * 16 + 8} centerZ={cameraChunk.z * 16 + 8}
            viewDistance={viewDistance} daylight={seconds ? () => daylightFactor(seconds()) : undefined}
            cutaway={cutawayAt} weather={sky ? weatherNow : undefined}
            onStats={debug ? setStats : undefined} onError={setEngineError} />
          <SurvivalPet action={action} recent={recentActions} position={position} now={replayTime} onPetClick={onPetClick}
            hopSignal={hopSignal} hidden={petHidden} tunic={wornTunic(inventory)}
            cap={wornCap(inventory)} cloak={wornCloak(inventory)} hurtAt={hurtAt} ailments={ailments} asking={asking}>
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
          {serverTime && sky && <WeatherEffects sky={sky} now={replayTime} mode={cameraMode} sheltered={sheltered}
            small={viewDistance < 6} timeScale={timeScale} />}
          {serverTime && <SurvivalCreatures creatures={creatures} moves={creatureMoves} now={replayTime} />}
          {serverTime && <CombatEffects action={action} recent={recentActions} position={position} creatures={creatures}
            now={replayTime} />}
          <SurvivalDoors store={store} focus={position} pet={serverTime ? petAt : undefined} held={doorsOpen} />
          <FollowCamera focus={position} focusY={position.y} stepAt={serverTime ? stepAt : undefined}
            initialFocus={initial} initialFocusY={initial.y} mode={cameraMode} store={store} onView={onView} onAutoPick={onAutoPick}
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

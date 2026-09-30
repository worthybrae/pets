import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { CameraMode } from './cameraModes'
import type { Point, SkyView } from './types'
import {
  BOLT_SEGMENTS, boltPoints, boltsAt, burnedOut, EMBERS_PER_FIRE, emberAt, fallAt, fallShown, keepSmoke,
  particleCount, type Puff, RAIN_STREAKS, SMOKE_GAME_SECONDS, SNOW_FLAKES,
} from './weather'

const MAX_FIRES = 48
const MAX_SMOKE = 24
const SMOKE_BITS = 4
const NO_CELLS: Point[] = []

/**
 * W2: the weather drawn round the camera and the fires in the trees, at replay time `now` (server seconds): rain
 * streaks or snowflakes falling in a box that follows the camera (half as many on a small screen, none under a
 * roof when the camera is close to or in the pet), a lightning bolt for a moment at each strike, embers over the
 * burning cells, and smoke over a tree that burned out for a game minute. Cheap: five instanced meshes, all updated
 * in one useFrame.
 */
export default function WeatherEffects({ sky, now, mode, sheltered, small, timeScale }: {
  sky: SkyView
  now: () => number
  mode: CameraMode
  sheltered: boolean
  small: boolean
  /** Game seconds a server second, for how long smoke lasts. */
  timeScale: number
}) {
  const rain = useRef<THREE.InstancedMesh>(null)
  const snow = useRef<THREE.InstancedMesh>(null)
  const embers = useRef<THREE.InstancedMesh>(null)
  const smoke = useRef<THREE.InstancedMesh>(null)
  const bolt = useRef<THREE.InstancedMesh>(null)
  const scratch = useRef<THREE.Object3D | null>(null)
  const burned = useRef<{ before: Point[]; smoking: Puff[] }>({ before: [], smoking: [] })

  useFrame(({ camera }) => {
    const t = now()
    const dummy = (scratch.current ??= new THREE.Object3D())
    const center = { x: camera.position.x, y: camera.position.y, z: camera.position.z }
    const shown = fallShown(sky.weather, mode, sheltered)
    const falls = [[rain.current, sky.weather === 'rain' || sky.weather === 'storm'], [snow.current, sky.weather === 'snow']] as const
    for (const [mesh, falling] of falls) {
      if (!mesh) continue
      const count = shown && falling ? particleCount(sky.weather, small) : 0
      for (let index = 0; index < count; index++) {
        const at = fallAt(index, t, sky.weather, center)
        dummy.position.set(at.x, at.y, at.z)
        dummy.scale.setScalar(1)
        dummy.updateMatrix()
        mesh.setMatrixAt(index, dummy.matrix)
      }
      mesh.count = count
      mesh.visible = count > 0
      mesh.instanceMatrix.needsUpdate = count > 0
    }
    const flashing = boltsAt(sky.strikes, t)
    const segments = bolt.current
    if (segments) {
      const points = flashing.length > 0 ? boltPoints(flashing[flashing.length - 1]) : []
      for (let k = 0; k + 1 < points.length; k++) {  // each segment a thin bar from one point to the next
        const [from, to] = [points[k], points[k + 1]]
        dummy.position.set((from.x + to.x) / 2, (from.y + to.y) / 2, (from.z + to.z) / 2)
        dummy.scale.set(1, 1, Math.hypot(to.x - from.x, to.y - from.y, to.z - from.z))
        dummy.lookAt(to.x, to.y, to.z)
        dummy.updateMatrix()
        segments.setMatrixAt(k, dummy.matrix)
      }
      segments.count = Math.max(0, points.length - 1)
      segments.visible = points.length > 0
      segments.instanceMatrix.needsUpdate = points.length > 0
      dummy.rotation.set(0, 0, 0)
    }
    const glowing = embers.current
    if (glowing) {
      let shownEmbers = 0
      for (const cell of sky.fires.slice(0, MAX_FIRES)) {
        for (let index = 0; index < EMBERS_PER_FIRE; index++) {
          const { position, scale } = emberAt(cell, index, t)
          dummy.position.set(position.x, position.y, position.z)
          dummy.scale.setScalar(Math.max(0.01, scale))
          dummy.updateMatrix()
          glowing.setMatrixAt(shownEmbers++, dummy.matrix)
        }
      }
      glowing.count = shownEmbers
      glowing.visible = shownEmbers > 0
      glowing.instanceMatrix.needsUpdate = shownEmbers > 0
    }
    const memory = burned.current
    const lasts = SMOKE_GAME_SECONDS / Math.max(timeScale, 1e-6)
    // the burned-out cells are looked for only when the fires change (a new poll), and the list is kept in place
    keepSmoke(memory.smoking, sky.fires === memory.before ? NO_CELLS : burnedOut(memory.before, sky.fires), t, lasts,
      MAX_SMOKE)
    memory.before = sky.fires
    const puffs = smoke.current
    if (puffs) {
      let bits = 0
      for (const puff of memory.smoking) {
        const age = (t - puff.at) / lasts
        for (let index = 0; index < SMOKE_BITS; index++) {
          const rise = ((age * 6 + index / SMOKE_BITS) % 1) * 2.4
          dummy.position.set(puff.cell.x + 0.5 + Math.sin(index * 2.1) * 0.3, puff.cell.y + 0.5 + rise,
            puff.cell.z + 0.5 + Math.cos(index * 2.1) * 0.3)
          dummy.scale.setScalar(0.5 + rise * 0.3)
          dummy.updateMatrix()
          puffs.setMatrixAt(bits++, dummy.matrix)
        }
      }
      puffs.count = bits
      puffs.visible = bits > 0
      puffs.instanceMatrix.needsUpdate = bits > 0
    }
  })

  return (
    <>
      <instancedMesh ref={rain} args={[undefined, undefined, RAIN_STREAKS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.03, 0.75, 0.03]} />
        <meshBasicMaterial color="#aebfd0" transparent opacity={0.55} depthWrite={false} />
      </instancedMesh>
      <instancedMesh ref={snow} args={[undefined, undefined, SNOW_FLAKES]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.1, 0.1, 0.1]} />
        <meshBasicMaterial color="#f7f9fb" />
      </instancedMesh>
      <instancedMesh ref={embers} args={[undefined, undefined, MAX_FIRES * EMBERS_PER_FIRE]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.08, 0.08, 0.08]} />
        <meshBasicMaterial color="#ffb05a" />
      </instancedMesh>
      <instancedMesh ref={smoke} args={[undefined, undefined, MAX_SMOKE * SMOKE_BITS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.5, 0.5, 0.5]} />
        <meshBasicMaterial color="#8d8f93" transparent opacity={0.35} depthWrite={false} />
      </instancedMesh>
      <instancedMesh ref={bolt} args={[undefined, undefined, BOLT_SEGMENTS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.14, 0.14, 1]} />
        <meshBasicMaterial color="#f4f6ff" />
      </instancedMesh>
    </>
  )
}

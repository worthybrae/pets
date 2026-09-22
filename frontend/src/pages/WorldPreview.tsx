import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import type { OrbitControls as OrbitControlsType } from 'three-stdlib'
import * as THREE from 'three'
import PetEntity from '../components/world/PetEntity'
import WorldManager from '../components/world/WorldManager'
import { previewPet } from '../components/world/previewWorld'
import {
  ensureTerrainAround, loadBuildProgress, makeProject, ORBITAL_STATION, placeVoxels,
  saveBuildProgress, worldForProgress,
} from '../components/world/expandingWorld'

interface Point { x: number; z: number }

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
    <OrbitControls
      ref={controlsRef}
      target={[initialFocus.x, initialFocusY, initialFocus.z]}
      enableDamping
      dampingFactor={0.08}
      minDistance={11}
      maxDistance={110}
      maxPolarAngle={Math.PI / 2.04}
      onStart={onOrbit}
    />
  )
}

export default function WorldPreview() {
  const [progress, setProgress] = useState(loadBuildProgress)
  const [chunks, setChunks] = useState(() => worldForProgress(loadBuildProgress()))
  const project = useMemo(() => makeProject(progress.projectIndex), [progress.projectIndex])
  const [initialPosition] = useState<Point>(() => ({ x: project.site.x, z: project.site.z + project.standOff }))
  const [initialCameraFocus] = useState<Point>(() => project.landmark ? project.site : initialPosition)
  const [initialCameraY] = useState(() => project.landmark?.centerY ?? 1)
  const pet = useMemo(() => ({
    ...previewPet,
    position: { ...previewPet.position, x: initialPosition.x, z: initialPosition.z },
  }), [initialPosition])
  const [focus, setFocus] = useState<Point>(initialPosition)
  const [cameraChunk, setCameraChunk] = useState({ x: 0, z: 0 })
  const [following, setFollowing] = useState(true)
  const [viewingStation, setViewingStation] = useState(false)
  const [arrived, setArrived] = useState(false)
  const [helloCount, setHelloCount] = useState(0)
  const [greeted, setGreeted] = useState(false)
  const lastFocusUpdate = useRef(0)

  const sayHello = () => {
    setHelloCount((count) => count + 1)
    setGreeted(true)
  }

  const handlePetPosition = useCallback((position: { x: number; y: number; z: number }) => {
    const now = performance.now()
    if (now - lastFocusUpdate.current < 100) return
    lastFocusUpdate.current = now
    setFocus({ x: position.x, z: position.z })
  }, [])

  const handleChunkChange = useCallback((x: number, z: number) => {
    setCameraChunk({ x, z })
    setChunks((current) => ensureTerrainAround(current, x * 16, z * 16, 5))
  }, [])

  useEffect(() => { saveBuildProgress(progress) }, [progress])

  useEffect(() => {
    if (!arrived) return
    if (progress.stepIndex >= project.voxels.length) {
      const timeout = window.setTimeout(() => {
        setArrived(false)
        const nextProject = makeProject(progress.projectIndex + 1)
        setChunks((current) => ensureTerrainAround(current, nextProject.site.x, nextProject.site.z, 2))
        setProgress({ projectIndex: progress.projectIndex + 1, stepIndex: 0 })
      }, 900)
      return () => window.clearTimeout(timeout)
    }
    const timeout = window.setTimeout(() => {
      const batchSize = Math.max(1, Math.ceil(project.voxels.length / 220))
      const nextStep = Math.min(project.voxels.length, progress.stepIndex + batchSize)
      setChunks((current) => placeVoxels(current, project.voxels.slice(progress.stepIndex, nextStep)))
      setProgress({ projectIndex: progress.projectIndex, stepIndex: nextStep })
      if (progress.stepIndex % (batchSize * 5) === 0) setHelloCount((count) => count + 1)
    }, 260)
    return () => window.clearTimeout(timeout)
  }, [arrived, progress.projectIndex, progress.stepIndex, project])

  const cameraDistance = project.landmark ? 55 : typeof window !== 'undefined' && window.innerWidth < 700 ? 40 : 28
  const targetDistance = viewingStation || project.landmark ? 83 : 38
  const cameraFocus = viewingStation
    ? { x: ORBITAL_STATION.x, z: ORBITAL_STATION.z }
    : project.landmark ? project.site : focus
  const cameraY = viewingStation ? ORBITAL_STATION.centerY : project.landmark?.centerY ?? 1
  const buildSegment = project.landmark
    ? Math.min(19, Math.floor((progress.stepIndex / project.voxels.length) * 20))
    : 0
  const buildAngle = Math.PI / 2 - (buildSegment / 20) * Math.PI * 2
  const destination = project.landmark
    ? {
        x: project.site.x + Math.cos(buildAngle) * project.standOff,
        z: project.site.z + Math.sin(buildAngle) * project.standOff,
        token: progress.projectIndex * 100 + buildSegment,
      }
    : { x: project.site.x, z: project.site.z + project.standOff, token: progress.projectIndex * 100 }
  const percent = Math.round((progress.stepIndex / project.voxels.length) * 100)

  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <div className="absolute inset-0">
        <Canvas
          camera={{
            position: [initialCameraFocus.x + cameraDistance, initialCameraY + cameraDistance * 0.72, initialCameraFocus.z + cameraDistance],
            fov: 48, near: 0.1, far: 260,
          }}
          gl={{ antialias: true }}
          dpr={[1, 2]}
        >
          <color attach="background" args={['#dce9eb']} />
          <fog attach="fog" args={['#dce9eb', 90, 175]} />
          <ambientLight intensity={1.3} />
          <directionalLight position={[12, 24, 16]} intensity={2.4} />
          <directionalLight position={[-10, 8, -12]} intensity={0.8} color="#d5eaff" />
          <WorldManager chunks={chunks} cameraChunkX={cameraChunk.x} cameraChunkZ={cameraChunk.z} viewDistance={5} />
          {project.landmark && progress.stepIndex < project.voxels.length && (
            <mesh position={[project.site.x, project.landmark.centerY, project.site.z]}>
              <sphereGeometry args={[project.landmark.radius + 0.5, 20, 14]} />
              <meshBasicMaterial color="#6f8e90" wireframe transparent opacity={0.12} depthWrite={false} />
            </mesh>
          )}
          <PetEntity
            pet={pet}
            destination={destination}
            onArrive={() => setArrived(true)}
            onPositionChange={handlePetPosition}
            onPetClick={sayHello}
            hopSignal={helloCount}
          >
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
          <BuildCamera focus={cameraFocus} focusY={cameraY} initialFocus={initialCameraFocus} initialFocusY={initialCameraY} distance={targetDistance} follow={following} onOrbit={() => setFollowing(false)} onChunkChange={handleChunkChange} />
        </Canvas>
      </div>

      <div className="pointer-events-none absolute left-5 top-20 z-10 max-w-xs sm:left-10 sm:top-24">
        <p className="mb-2 text-sm font-medium text-[#637d79]">Mimo's world</p>
        <h1 className="text-4xl font-semibold leading-[1.04] tracking-[-0.065em] sm:text-6xl">Made by Mimo.</h1>
        <p className="mt-4 max-w-[18rem] text-sm leading-6 text-[#4f6967] sm:text-base">
          Follow along as Mimo explores and adds new places to the world.
        </p>
      </div>

      <div className="absolute bottom-6 left-5 right-5 z-10 flex flex-col gap-4 sm:bottom-9 sm:left-10 sm:right-10 sm:flex-row sm:items-end sm:justify-between">
        <div className="w-[min(100%,18rem)] rounded-2xl border border-white/75 bg-[#f5faf7]/90 px-5 py-4 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f5c0a9] text-xl" aria-hidden="true">✿</div>
            <div>
              <p className="text-base font-semibold leading-tight">Mimo</p>
              <p className="text-xs text-[#65817b]">{greeted ? 'Happy to see you' : arrived ? 'Busy building' : 'On the way'}</p>
            </div>
          </div>
          <p className="mt-4 text-sm font-medium">{arrived ? 'Building' : 'Heading to'} {project.name}</p>
          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[#d9e8df]" role="progressbar" aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100} aria-label={`${project.name} progress`}>
            <div className="h-full rounded-full bg-[#4d8c77] transition-[width] duration-200" style={{ width: `${percent}%` }} />
          </div>
          <div className="mt-4 flex gap-2">
            <button type="button" onClick={sayHello} className="flex-1 rounded-xl bg-[#315e58] px-3 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#244b47] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#315e58]">Say hello</button>
            <button type="button" onClick={() => { setViewingStation(false); setFollowing(true) }} className="flex-1 rounded-xl border border-[#bfd5cd] px-3 py-2.5 text-sm font-medium text-[#315e58] transition-colors hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#315e58]">{project.landmark ? 'View build' : 'Follow Mimo'}</button>
          </div>
          {progress.projectIndex > 0 && (
            <button type="button" onClick={() => { setViewingStation(true); setFollowing(true) }} className="mt-3 text-sm font-medium text-[#315e58] underline decoration-[#8cafa2] underline-offset-4 hover:text-[#244b47] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#315e58]">
              Visit the orbital station
            </button>
          )}
        </div>
        <p className="max-w-[14rem] text-xs leading-5 text-[#54726e] sm:text-right">Drag to look around<br />Scroll to zoom in</p>
      </div>
    </main>
  )
}

import { useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import PetEntity from '../components/world/PetEntity'
import WorldManager from '../components/world/WorldManager'
import { previewChunks, previewPet } from '../components/world/previewWorld'

export default function WorldPreview() {
  const [helloCount, setHelloCount] = useState(0)
  const [greeted, setGreeted] = useState(false)

  const sayHello = () => {
    setHelloCount((count) => count + 1)
    setGreeted(true)
  }

  const cameraDistance = typeof window !== 'undefined' && window.innerWidth < 700 ? 39 : 25

  return (
    <main className="relative h-screen min-h-[540px] overflow-hidden bg-[#dce9eb] text-[#243e3d]">
      <div className="absolute inset-0">
        <Canvas
          camera={{ position: [cameraDistance, cameraDistance * 0.72, cameraDistance], fov: 48, near: 0.1, far: 150 }}
          gl={{ antialias: true }}
          dpr={[1, 2]}
        >
          <color attach="background" args={['#dce9eb']} />
          <fog attach="fog" args={['#dce9eb', 65, 105]} />
          <ambientLight intensity={1.3} />
          <directionalLight position={[12, 24, 16]} intensity={2.4} />
          <directionalLight position={[-10, 8, -12]} intensity={0.8} color="#d5eaff" />
          <WorldManager chunks={previewChunks} />
          <PetEntity pet={previewPet} wanderRadius={2.2} onPetClick={sayHello} hopSignal={helloCount}>
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
          <OrbitControls
            target={[0, 1, 0]}
            enableDamping
            dampingFactor={0.08}
            minDistance={18}
            maxDistance={75}
            maxPolarAngle={Math.PI / 2.05}
          />
        </Canvas>
      </div>

      <div className="pointer-events-none absolute left-5 top-20 z-10 max-w-xs sm:left-10 sm:top-24">
        <p className="mb-2 text-sm font-medium text-[#637d79]">A little world, just for Mimo</p>
        <h1 className="text-4xl font-semibold leading-[1.04] tracking-[-0.065em] sm:text-6xl">
          Meet Mimo.
        </h1>
        <p className="mt-4 max-w-[17rem] text-sm leading-6 text-[#4f6967] sm:text-base">
          Mimo has a home, a pond, and plenty of room to explore.
        </p>
      </div>

      <div className="absolute bottom-6 left-5 right-5 z-10 flex flex-col gap-4 sm:bottom-9 sm:left-10 sm:right-10 sm:flex-row sm:items-end sm:justify-between">
        <div className="w-fit rounded-2xl border border-white/75 bg-[#f5faf7]/85 px-5 py-4 shadow-[0_14px_40px_rgba(57,95,91,0.12)] backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#f5c0a9] text-xl" aria-hidden="true">✿</div>
            <div>
              <p className="text-base font-semibold leading-tight">Mimo</p>
              <p className="text-xs text-[#65817b]">{greeted ? 'Happy to see you' : 'Out exploring'}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={sayHello}
            className="mt-4 w-full rounded-xl bg-[#315e58] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#244b47] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#315e58]"
          >
            Say hello
          </button>
        </div>
        <p className="max-w-[14rem] text-xs leading-5 text-[#54726e] sm:text-right">
          Drag to look around<br />Scroll to zoom in
        </p>
      </div>
    </main>
  )
}

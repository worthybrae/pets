import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { rarityColors } from '../data/rarity'
import type { Rarity } from '../data/rarity'

interface HatchProps {
  onHatch: (name: string, initialCuriosity: string) => Promise<any>
  onComplete: (petData: any) => void
}

interface PetData {
  id: string
  name: string
  rarity: Rarity
  stats: Record<string, number>
  backstory: string
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}

type Phase = 'input' | 'hatching' | 'reveal' | 'backstory'

// ============ 3D Components ============

function EggVoxels({ phase, progress }: { phase: Phase; progress: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)
  const fragmentsRef = useRef<{ pos: THREE.Vector3; vel: THREE.Vector3 }[]>([])

  // Egg shape: roughly ovoid, made of voxels
  const eggVoxels = useMemo(() => {
    const voxels: { x: number; y: number; z: number }[] = []
    for (let y = -2; y <= 3; y++) {
      let radius: number
      if (y <= -1) radius = 1
      else if (y === 0) radius = 1.5
      else if (y === 1) radius = 1.5
      else if (y === 2) radius = 1
      else radius = 0.5

      for (let x = -Math.floor(radius); x <= Math.floor(radius); x++) {
        for (let z = -Math.floor(radius); z <= Math.floor(radius); z++) {
          if (Math.sqrt(x * x + z * z) <= radius) {
            voxels.push({ x, y, z })
          }
        }
      }
    }
    return voxels
  }, [])

  // Initialize fragments for explosion
  useEffect(() => {
    if (phase === 'hatching' && progress > 0.6) {
      fragmentsRef.current = eggVoxels.map((v) => ({
        pos: new THREE.Vector3(v.x, v.y, v.z),
        vel: new THREE.Vector3(
          (Math.random() - 0.5) * 8,
          Math.random() * 6 + 2,
          (Math.random() - 0.5) * 8
        ),
      }))
    }
  }, [phase, progress > 0.6, eggVoxels])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (!meshRef.current || !groupRef.current) return

    const mesh = meshRef.current
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()

    if (phase === 'hatching' && progress > 0.7) {
      // Explosion phase: fragments fly outward
      const explosionTime = (progress - 0.7) / 0.3
      fragmentsRef.current.forEach((frag, i) => {
        if (i >= eggVoxels.length) return
        const pos = frag.pos.clone().add(frag.vel.clone().multiplyScalar(explosionTime * 2))
        pos.y -= explosionTime * explosionTime * 5 // gravity
        dummy.position.copy(pos)
        dummy.scale.setScalar(Math.max(0, 1 - explosionTime * 1.5))
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(1, 1, 1)
        color.multiplyScalar(Math.max(0, 1 - explosionTime))
        mesh.setColorAt(i, color)
      })
    } else if (phase === 'hatching') {
      // Pulsing / cracking phase
      const pulse = Math.sin(timeRef.current * 6) * 0.15
      const shake = progress > 0.3 ? Math.sin(timeRef.current * 20) * 0.05 * progress : 0

      for (let i = 0; i < eggVoxels.length; i++) {
        const v = eggVoxels[i]
        dummy.position.set(v.x + shake, v.y, v.z + shake * 0.5)
        dummy.scale.setScalar(1 + pulse)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)

        const brightness = 0.3 + pulse * 2 + progress * 0.5
        color.setRGB(brightness, brightness, brightness)
        mesh.setColorAt(i, color)
      }

      // Cracks appear as progress advances
      if (progress > 0.4) {
        const crackCount = Math.floor((progress - 0.4) / 0.1 * 3)
        for (let i = 0; i < Math.min(crackCount, eggVoxels.length); i++) {
          const crackIdx = (i * 7) % eggVoxels.length
          color.setRGB(0.8, 0.6, 0.2)
          mesh.setColorAt(crackIdx, color)
        }
      }
    } else {
      // Idle egg (input phase)
      const pulse = Math.sin(timeRef.current * 2) * 0.05
      for (let i = 0; i < eggVoxels.length; i++) {
        const v = eggVoxels[i]
        dummy.position.set(v.x, v.y, v.z)
        dummy.scale.setScalar(1 + pulse)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(0.2, 0.2, 0.22)
        mesh.setColorAt(i, color)
      }
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

    // Gentle rotation
    groupRef.current.rotation.y += delta * 0.3
  })

  if (phase === 'reveal' || phase === 'backstory') return null

  return (
    <group ref={groupRef}>
      <pointLight color="#ffffff" intensity={phase === 'hatching' ? 3 + progress * 5 : 1} distance={20} decay={2} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, eggVoxels.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshStandardMaterial vertexColors toneMapped={false} />
      </instancedMesh>
    </group>
  )
}

function Particles({ active, intensity }: { active: boolean; intensity: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const particlesRef = useRef<{ pos: THREE.Vector3; vel: THREE.Vector3; life: number }[]>([])
  const timeRef = useRef(0)

  const PARTICLE_COUNT = 80

  useEffect(() => {
    particlesRef.current = Array.from({ length: PARTICLE_COUNT }, () => ({
      pos: new THREE.Vector3(
        (Math.random() - 0.5) * 2,
        (Math.random() - 0.5) * 2,
        (Math.random() - 0.5) * 2
      ),
      vel: new THREE.Vector3(
        (Math.random() - 0.5) * 3,
        Math.random() * 4 + 1,
        (Math.random() - 0.5) * 3
      ),
      life: Math.random(),
    }))
  }, [])

  useFrame((_, delta) => {
    if (!meshRef.current || !active) return
    timeRef.current += delta

    const mesh = meshRef.current
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()

    particlesRef.current.forEach((p, i) => {
      p.life -= delta * (0.5 + intensity * 0.5)
      if (p.life <= 0) {
        p.pos.set(
          (Math.random() - 0.5) * 2,
          (Math.random() - 0.5) * 2,
          (Math.random() - 0.5) * 2
        )
        p.vel.set(
          (Math.random() - 0.5) * (3 + intensity * 4),
          Math.random() * (4 + intensity * 4) + 1,
          (Math.random() - 0.5) * (3 + intensity * 4)
        )
        p.life = 1
      }

      p.pos.add(p.vel.clone().multiplyScalar(delta))
      p.vel.y -= delta * 2

      dummy.position.copy(p.pos)
      const scale = p.life * 0.3 * intensity
      dummy.scale.setScalar(scale)
      dummy.updateMatrix()
      mesh.setMatrixAt(i, dummy.matrix)

      const brightness = p.life * intensity
      color.setRGB(brightness, brightness * 0.9, brightness * 0.7)
      mesh.setColorAt(i, color)
    })

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  })

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, PARTICLE_COUNT]} frustumCulled={false}>
      <boxGeometry args={[0.2, 0.2, 0.2]} />
      <meshBasicMaterial vertexColors toneMapped={false} transparent opacity={0.8} />
    </instancedMesh>
  )
}

function PetReveal({ voxels, progress }: { voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]; progress: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)

  const centeredVoxels = useMemo(() => {
    if (voxels.length === 0) return voxels
    const cx = voxels.reduce((s, v) => s + v.x, 0) / voxels.length
    const cy = voxels.reduce((s, v) => s + v.y, 0) / voxels.length
    const cz = voxels.reduce((s, v) => s + v.z, 0) / voxels.length
    return voxels.map((v) => ({ ...v, x: v.x - cx, y: v.y - cy, z: v.z - cz }))
  }, [voxels])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (!meshRef.current || !groupRef.current) return

    const mesh = meshRef.current
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    const voxelsToShow = Math.floor(progress * centeredVoxels.length)

    for (let i = 0; i < centeredVoxels.length; i++) {
      const v = centeredVoxels[i]
      if (i < voxelsToShow) {
        const localProgress = Math.min(1, (progress * centeredVoxels.length - i) / 3)
        const popScale = localProgress < 0.5
          ? localProgress * 2 * 1.3
          : 1 + (1 - localProgress) * 0.3
        dummy.position.set(v.x, v.y, v.z)
        dummy.scale.setScalar(popScale)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)

        // Use actual voxel colors
        color.setRGB(v.r / 255, v.g / 255, v.b / 255)
        mesh.setColorAt(i, color)
      } else {
        dummy.position.set(0, 0, 0)
        dummy.scale.setScalar(0)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(0, 0, 0)
        mesh.setColorAt(i, color)
      }
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

    // Gentle rotation
    groupRef.current.rotation.y += delta * 0.5
  })

  if (centeredVoxels.length === 0) return null

  return (
    <group ref={groupRef} position={[0, 2, 0]}>
      <pointLight color="#ffffff" intensity={4} distance={25} decay={2} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, centeredVoxels.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshBasicMaterial vertexColors toneMapped={false} />
      </instancedMesh>
    </group>
  )
}

function HatchScene({ phase, hatchProgress, revealProgress, voxels }: {
  phase: Phase
  hatchProgress: number
  revealProgress: number
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}) {
  return (
    <Canvas
      camera={{ position: [0, 2, 12], fov: 40, near: 0.1, far: 100 }}
      gl={{ antialias: true }}
      className="!absolute inset-0"
    >
      <color attach="background" args={['#000000']} />
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 10, 5]} intensity={0.6} />
      <directionalLight position={[-5, 5, -5]} intensity={0.3} />

      <EggVoxels phase={phase} progress={hatchProgress} />
      <Particles active={phase === 'hatching'} intensity={hatchProgress} />
      {(phase === 'reveal' || phase === 'backstory') && voxels.length > 0 && (
        <PetReveal voxels={voxels} progress={revealProgress} />
      )}
    </Canvas>
  )
}

// ============ Stat Display Components ============

function getStatColor(value: number): string {
  if (value >= 9) return '#fbbf24' // gold
  if (value >= 7) return '#60a5fa' // blue
  if (value >= 5) return '#a78bfa' // purple
  if (value >= 3) return '#6ee7b7' // green
  return '#9ca3af' // gray
}

function StatBar({ name, value, delay, revealed }: { name: string; value: number; delay: number; revealed: boolean }) {
  const [active, setActive] = useState(false)
  const [filled, setFilled] = useState(false)
  const [showValue, setShowValue] = useState(false)
  const barColor = getStatColor(value)

  useEffect(() => {
    if (!revealed) return

    const t1 = setTimeout(() => setActive(true), delay)
    const t2 = setTimeout(() => setFilled(true), delay + 50)
    const t3 = setTimeout(() => setShowValue(true), delay + 500)

    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(t3)
    }
  }, [revealed, delay])

  return (
    <div
      className="flex items-center gap-3 text-sm"
      style={{
        opacity: active ? 1 : 0,
        transform: active ? 'translateX(0)' : 'translateX(-8px)',
        transition: 'opacity 0.3s ease-out, transform 0.3s ease-out',
      }}
    >
      <span className="text-gray-400 w-24 capitalize">{name}</span>
      <div className="flex-1 h-2.5 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{
            width: filled ? `${value * 10}%` : '0%',
            backgroundColor: barColor,
            boxShadow: filled && value >= 7 ? `0 0 8px ${barColor}60` : 'none',
            transition: 'width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
          }}
        />
      </div>
      <span
        className="w-6 text-right font-mono font-bold"
        style={{
          color: showValue ? barColor : 'transparent',
          transition: 'color 0.2s ease-out',
        }}
      >
        {value}
      </span>
    </div>
  )
}

function TotalReveal({ total, visible }: { total: number; visible: boolean }) {
  const [displayTotal, setDisplayTotal] = useState(0)

  useEffect(() => {
    if (!visible) return
    const duration = 600
    const start = Date.now()
    const animate = () => {
      const elapsed = Date.now() - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setDisplayTotal(Math.round(eased * total))
      if (progress < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [visible, total])

  if (!visible) return null

  return (
    <div
      className="flex justify-between items-center pt-2 border-t border-white/10"
      style={{ animation: 'fade-in 0.3s ease-out both' }}
    >
      <span className="text-gray-500 text-sm">Total</span>
      <span className="text-white font-mono font-bold text-lg">{displayTotal}</span>
    </div>
  )
}

function RarityBadge({ rarity, visible }: { rarity: Rarity; visible: boolean }) {
  const [show, setShow] = useState(false)
  const color = rarityColors[rarity]
  const isMythic = rarity === 'mythic'
  const isLegendary = rarity === 'legendary'

  useEffect(() => {
    if (visible) {
      const t = setTimeout(() => setShow(true), 50)
      return () => clearTimeout(t)
    }
  }, [visible])

  if (!visible) return null

  return (
    <div className="relative inline-block">
      {(isLegendary || isMythic) && show && (
        <div
          className="absolute inset-0 rounded-full blur-xl animate-pulse"
          style={{ backgroundColor: `${color}30` }}
        />
      )}
      <div
        className={`relative inline-block px-5 py-2 rounded-full text-sm font-bold uppercase tracking-widest ${
          isMythic ? 'mythic-badge' : ''
        }`}
        style={{
          ...(isMythic ? {} : { backgroundColor: `${color}20`, color, border: `1px solid ${color}50` }),
          opacity: show ? 1 : 0,
          transform: show ? 'scale(1)' : 'scale(0.3)',
          transition: 'all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
        }}
      >
        {rarity}
      </div>
    </div>
  )
}

// ============ Main Hatch Component ============

export default function Hatch({ onHatch, onComplete }: HatchProps) {
  const [name, setName] = useState('')
  const [curiosity, setCuriosity] = useState('')
  const [phase, setPhase] = useState<Phase>('input')
  const [hatchProgress, setHatchProgress] = useState(0)
  const [revealProgress, setRevealProgress] = useState(0)
  const [petData, setPetData] = useState<PetData | null>(null)
  const [fullPetResponse, setFullPetResponse] = useState<any>(null)
  const [statsRevealed, setStatsRevealed] = useState(false)
  const [rarityVisible, setRarityVisible] = useState(false)
  const [backstoryText, setBackstoryText] = useState('')
  const [showBeginButton, setShowBeginButton] = useState(false)
  const [flashActive, setFlashActive] = useState(false)
  const hatchStartRef = useRef<number>(0)
  const animFrameRef = useRef<number>(0)

  // Hatching animation loop
  const startHatchAnimation = useCallback(() => {
    hatchStartRef.current = Date.now()
    const HATCH_DURATION = 8000 // 8 seconds to cover LLM latency

    const animate = () => {
      const elapsed = Date.now() - hatchStartRef.current
      const progress = Math.min(elapsed / HATCH_DURATION, 1)
      setHatchProgress(progress)

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(animate)
      } else {
        // Flash!
        setFlashActive(true)
        setTimeout(() => setFlashActive(false), 400)
        // Transition to reveal
        setTimeout(() => {
          setPhase('reveal')
          startRevealAnimation()
        }, 300)
      }
    }

    animFrameRef.current = requestAnimationFrame(animate)
  }, [])

  // Reveal animation loop
  const startRevealAnimation = useCallback(() => {
    const REVEAL_DURATION = 3000
    const revealStart = Date.now()

    const animate = () => {
      const elapsed = Date.now() - revealStart
      const progress = Math.min(elapsed / REVEAL_DURATION, 1)
      setRevealProgress(progress)

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(animate)
      } else {
        // Sequential reveal: name → stats → rarity
        setTimeout(() => setStatsRevealed(true), 800)
        // Rarity comes last (after all 7 stats finish)
        // Stats take 800ms start + 7*250ms stagger + 600ms fill = ~3.5s
        setTimeout(() => setRarityVisible(true), 3500)
      }
    }

    animFrameRef.current = requestAnimationFrame(animate)
  }, [])

  // Backstory typewriter effect
  useEffect(() => {
    if (phase !== 'backstory' || !petData) return

    const fullText = petData.backstory
    let index = 0
    const interval = setInterval(() => {
      index++
      setBackstoryText(fullText.slice(0, index))
      if (index >= fullText.length) {
        clearInterval(interval)
        setTimeout(() => setShowBeginButton(true), 500)
      }
    }, 30)

    return () => clearInterval(interval)
  }, [phase, petData])

  // Cleanup animation frames
  useEffect(() => {
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    // Start hatching animation immediately
    setPhase('hatching')
    startHatchAnimation()

    // Call backend in parallel
    const response = await onHatch(name.trim(), curiosity.trim())

    if (response) {
      setFullPetResponse(response)
      setPetData({
        id: response.id,
        name: response.name,
        rarity: response.rarity,
        stats: response.stats,
        backstory: response.backstory,
        voxels: response.voxels || [],
      })
    } else {
      setPetData({
        id: 'fallback',
        name: name.trim(),
        rarity: 'common',
        stats: { curiosity: 5, creativity: 5, social: 5, focus: 5, energy: 5, resilience: 5, humor: 5 },
        backstory: `${name.trim()} emerged from the void with wonder in their eyes.`,
        voxels: [{ x: 0, y: 0, z: 0, r: 255, g: 255, b: 255 }],
      })
    }
  }

  const handleBeginJourney = () => {
    if (fullPetResponse) {
      onComplete(fullPetResponse)
    } else if (petData) {
      onComplete(petData)
    }
  }

  const handleContinueToBackstory = () => {
    setPhase('backstory')
  }

  return (
    <div className="min-h-screen bg-black flex items-center justify-center relative overflow-hidden">
      {/* 3D Scene (background layer) */}
      <div className="absolute inset-0 z-0">
        <HatchScene
          phase={phase}
          hatchProgress={hatchProgress}
          revealProgress={revealProgress}
          voxels={petData?.voxels || []}
        />
      </div>

      {/* Screen flash */}
      {flashActive && (
        <div className="absolute inset-0 z-40 bg-white animate-[flash_0.4s_ease-out_forwards]" />
      )}

      {/* UI Overlay */}
      <div className="relative z-10 w-full max-w-lg px-6">

        {/* Phase 1: Input */}
        {phase === 'input' && (
          <div className="animate-[fade-in_0.5s_ease-out]">
            <div className="text-center mb-10">
              <h1 className="text-3xl font-light text-white mb-2">A new life awaits</h1>
              <p className="text-gray-500 text-sm">Name your pet and describe what fascinates them</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-xs text-gray-500 mb-2 uppercase tracking-wider">Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Give them a name"
                  maxLength={20}
                  autoFocus
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white text-lg placeholder-gray-600 focus:outline-none focus:border-white/30 transition-colors"
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-xs text-gray-500 uppercase tracking-wider">Initial Curiosity</label>
                  <span className="text-xs text-gray-600">{curiosity.length}/250</span>
                </div>
                <textarea
                  value={curiosity}
                  onChange={(e) => setCuriosity(e.target.value.slice(0, 250))}
                  placeholder="Describe what fascinates your pet... deep ocean creatures, ancient mathematics, the patterns in clouds, bioluminescent organisms in cave systems..."
                  maxLength={250}
                  rows={4}
                  className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder-gray-600 focus:outline-none focus:border-white/30 transition-colors resize-none leading-relaxed"
                />
              </div>

              <button
                type="submit"
                disabled={!name.trim()}
                className="w-full px-6 py-3.5 bg-white text-black font-medium rounded-lg hover:bg-gray-100 transition-all disabled:opacity-20 disabled:cursor-not-allowed active:scale-[0.98]"
              >
                Hatch
              </button>
            </form>
          </div>
        )}

        {/* Phase 2: Hatching */}
        {phase === 'hatching' && (
          <div className="text-center animate-[fade-in_0.3s_ease-out]">
            <p className="text-gray-400 text-sm animate-pulse mt-40">
              {hatchProgress < 0.2 ? 'Something stirs...' :
               hatchProgress < 0.4 ? 'A pulse of light...' :
               hatchProgress < 0.6 ? 'Cracking...' :
               hatchProgress < 0.8 ? 'Almost there...' :
               'Breaking free!'}
            </p>
          </div>
        )}

        {/* Waiting for data (animation done but API still loading) */}
        {phase === 'reveal' && !petData && (
          <div className="text-center animate-pulse mt-40">
            <p className="text-gray-400 text-sm">Shaping your pet...</p>
          </div>
        )}

        {/* Phase 3: Reveal */}
        {phase === 'reveal' && petData && (
          <div className="animate-[fade-in_0.5s_ease-out] mt-32">
            <div className="bg-black/70 backdrop-blur-md rounded-2xl border border-white/10 p-6 space-y-5">
              {/* Name */}
              <div className="text-center space-y-3">
                <h2 className="text-2xl font-medium text-white">{petData.name}</h2>
              </div>

              {/* Stats */}
              <div className="space-y-3 pt-2">
                {Object.entries(petData.stats).map(([statName, value], idx) => (
                  <StatBar
                    key={statName}
                    name={statName}
                    value={value}
                    delay={idx * 250}
                    revealed={statsRevealed}
                  />
                ))}
              </div>

              {/* Total */}
              <TotalReveal
                total={Object.values(petData.stats).reduce((a, b) => a + b, 0)}
                visible={rarityVisible}
              />

              {/* Rarity badge */}
              <div className="text-center pt-1">
                <RarityBadge rarity={petData.rarity as Rarity} visible={rarityVisible} />
              </div>

              {/* Continue button */}
              {rarityVisible && (
                <button
                  onClick={handleContinueToBackstory}
                  className="w-full px-6 py-3 bg-white/10 border border-white/20 text-white rounded-lg hover:bg-white/20 transition-all mt-2"
                  style={{
                    animation: 'fade-in 0.4s ease-out 0.6s both',
                  }}
                >
                  Continue
                </button>
              )}
            </div>
          </div>
        )}

        {/* Phase 4: Backstory */}
        {phase === 'backstory' && petData && (
          <div className="animate-[fade-in_0.5s_ease-out] mt-32">
            <div className="bg-black/60 backdrop-blur-sm rounded-2xl border border-white/10 p-6 space-y-6">
              <div className="text-center">
                <h2 className="text-xl font-medium text-white">{petData.name}</h2>
              </div>

              <div className="min-h-[120px]">
                <p className="text-gray-300 text-sm leading-relaxed">
                  {backstoryText}
                  <span className="animate-pulse">|</span>
                </p>
              </div>

              {showBeginButton && (
                <button
                  onClick={handleBeginJourney}
                  className="w-full px-6 py-3.5 bg-white text-black font-medium rounded-lg hover:bg-gray-100 transition-all animate-[fade-in_0.5s_ease-out] active:scale-[0.98]"
                >
                  Begin Journey
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fade-in {
          0% { opacity: 0; transform: translateY(10px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        @keyframes scale-in {
          0% { opacity: 0; transform: scale(0.5); }
          50% { transform: scale(1.1); }
          100% { opacity: 1; transform: scale(1); }
        }
        @keyframes flash {
          0% { opacity: 0.9; }
          100% { opacity: 0; }
        }
        .mythic-badge {
          background: linear-gradient(90deg, #ec4899, #8b5cf6, #3b82f6, #22c55e, #eab308, #ec4899);
          background-size: 300% 100%;
          animation: rainbow-shift 3s linear infinite;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          border: 1px solid rgba(236, 72, 153, 0.4);
        }
        @keyframes rainbow-shift {
          0% { background-position: 0% 50%; }
          100% { background-position: 300% 50%; }
        }
      `}</style>
    </div>
  )
}

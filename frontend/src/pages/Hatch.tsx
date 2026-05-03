import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { petShapes, rarityColors, speciesByRarity } from '../data/petShapes'
import type { Species, Rarity } from '../data/petShapes'

interface HatchProps {
  onHatch: (name: string, initialCuriosity: string) => Promise<any>
}

interface PetData {
  id: string
  name: string
  rarity: Rarity
  species: Species
  stats: Record<string, number>
  backstory: string
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
    // Build a simple egg shape (wider in middle, narrower top/bottom)
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
          const crackIdx = (i * 7) % eggVoxels.length // Pseudo-random crack positions
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
        // Respawn
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
      p.vel.y -= delta * 2 // slight gravity

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

function PetReveal({ species, progress }: { species: Species; progress: number }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)

  const shape = useMemo(() => petShapes[species] || petShapes.cat, [species])

  // Center the shape
  const centeredShape = useMemo(() => {
    if (shape.length === 0) return shape
    const cx = shape.reduce((s, v) => s + v.x, 0) / shape.length
    const cy = shape.reduce((s, v) => s + v.y, 0) / shape.length
    const cz = shape.reduce((s, v) => s + v.z, 0) / shape.length
    return shape.map((v) => ({ ...v, x: v.x - cx, y: v.y - cy, z: v.z - cz }))
  }, [shape])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (!meshRef.current || !groupRef.current) return

    const mesh = meshRef.current
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    const voxelsToShow = Math.floor(progress * centeredShape.length)

    for (let i = 0; i < centeredShape.length; i++) {
      const v = centeredShape[i]
      if (i < voxelsToShow) {
        // Materialize with a pop effect
        const localProgress = Math.min(1, (progress * centeredShape.length - i) / 3)
        const popScale = localProgress < 0.5
          ? localProgress * 2 * 1.3
          : 1 + (1 - localProgress) * 0.3
        dummy.position.set(v.x, v.y, v.z)
        dummy.scale.setScalar(popScale)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)

        const glow = Math.sin(timeRef.current * 3 + i * 0.5) * 0.1
        color.setRGB(0.9 + glow, 0.9 + glow, 0.95 + glow)
        mesh.setColorAt(i, color)
      } else {
        // Hidden
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

  return (
    <group ref={groupRef}>
      <pointLight color="#ffffff" intensity={3} distance={20} decay={2} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, centeredShape.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshStandardMaterial vertexColors toneMapped={false} emissive="#222222" emissiveIntensity={0.5} />
      </instancedMesh>
    </group>
  )
}

function HatchScene({ phase, hatchProgress, revealProgress, species }: {
  phase: Phase
  hatchProgress: number
  revealProgress: number
  species: Species
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
      {(phase === 'reveal' || phase === 'backstory') && (
        <PetReveal species={species} progress={revealProgress} />
      )}
    </Canvas>
  )
}

// ============ Stat Display Components ============

function StatBar({ name, value, delay, revealed }: { name: string; value: number; delay: number; revealed: boolean }) {
  const [displayValue, setDisplayValue] = useState(0)
  const [rolling, setRolling] = useState(false)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!revealed) return

    const timeout = setTimeout(() => {
      setRolling(true)
      let ticks = 0
      const maxTicks = 15
      intervalRef.current = setInterval(() => {
        ticks++
        if (ticks >= maxTicks) {
          setDisplayValue(value)
          setRolling(false)
          if (intervalRef.current) clearInterval(intervalRef.current)
        } else {
          setDisplayValue(Math.floor(Math.random() * 10) + 1)
        }
      }, 60)
    }, delay)

    return () => {
      clearTimeout(timeout)
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [revealed, value, delay])

  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-gray-400 w-24 capitalize">{name}</span>
      <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-white/80 rounded-full transition-all duration-300"
          style={{ width: `${(rolling ? displayValue : (revealed ? value : 0)) * 10}%` }}
        />
      </div>
      <span className={`w-6 text-right font-mono ${rolling ? 'text-white animate-pulse' : 'text-white/70'}`}>
        {revealed ? displayValue : '-'}
      </span>
    </div>
  )
}

function RarityBadge({ rarity, visible }: { rarity: Rarity; visible: boolean }) {
  if (!visible) return null

  const color = rarityColors[rarity]
  const isMythic = rarity === 'mythic'

  return (
    <div
      className={`inline-block px-4 py-1.5 rounded-full text-sm font-bold uppercase tracking-wider animate-[scale-in_0.4s_ease-out] ${
        isMythic ? 'mythic-badge' : ''
      }`}
      style={isMythic ? {} : { backgroundColor: `${color}20`, color, border: `1px solid ${color}40` }}
    >
      {rarity}
    </div>
  )
}

// ============ Main Hatch Component ============

export default function Hatch({ onHatch }: HatchProps) {
  const [name, setName] = useState('')
  const [curiosity, setCuriosity] = useState('')
  const [phase, setPhase] = useState<Phase>('input')
  const [hatchProgress, setHatchProgress] = useState(0)
  const [revealProgress, setRevealProgress] = useState(0)
  const [petData, setPetData] = useState<PetData | null>(null)
  const [statsRevealed, setStatsRevealed] = useState(false)
  const [rarityVisible, setRarityVisible] = useState(false)
  const [speciesVisible, setSpeciesVisible] = useState(false)
  const [backstoryText, setBackstoryText] = useState('')
  const [showBeginButton, setShowBeginButton] = useState(false)
  const [flashActive, setFlashActive] = useState(false)
  const hatchStartRef = useRef<number>(0)
  const animFrameRef = useRef<number>(0)

  // Generate local random pet data (used for animation, overridden by backend response)
  const generateLocalPet = useCallback((): PetData => {
    const rarityRoll = Math.random() * 100
    let rarity: Rarity
    if (rarityRoll < 1) rarity = 'mythic'
    else if (rarityRoll < 5) rarity = 'legendary'
    else if (rarityRoll < 15) rarity = 'rare'
    else if (rarityRoll < 40) rarity = 'uncommon'
    else rarity = 'common'

    const speciesPool = speciesByRarity[rarity]
    const species = speciesPool[Math.floor(Math.random() * speciesPool.length)]

    const stats: Record<string, number> = {}
    const statNames = ['curiosity', 'creativity', 'social', 'focus', 'energy', 'resilience']
    statNames.forEach((s) => {
      stats[s] = Math.floor(Math.random() * 10) + 1
    })

    return {
      id: 'local',
      name: name.trim(),
      rarity,
      species,
      stats,
      backstory: `Born from curiosity about ${curiosity || 'the mysteries of the world'}, ${name.trim()} emerged with an insatiable desire to explore.`,
    }
  }, [name, curiosity])

  // Hatching animation loop
  const startHatchAnimation = useCallback(() => {
    hatchStartRef.current = Date.now()
    const HATCH_DURATION = 3500 // 3.5 seconds

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
    const REVEAL_DURATION = 4000 // 4 seconds for pet to materialize
    const revealStart = Date.now()

    const animate = () => {
      const elapsed = Date.now() - revealStart
      const progress = Math.min(elapsed / REVEAL_DURATION, 1)
      setRevealProgress(progress)

      if (progress < 1) {
        animFrameRef.current = requestAnimationFrame(animate)
      } else {
        // Show stats rolling
        setTimeout(() => setStatsRevealed(true), 500)
        // Show species name
        setTimeout(() => setSpeciesVisible(true), 800)
        // Show rarity badge
        setTimeout(() => setRarityVisible(true), 2500)
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
      // Use real backend data
      setPetData({
        id: response.id,
        name: response.name,
        rarity: response.rarity,
        species: response.species,
        stats: response.stats,
        backstory: response.backstory,
      })
    } else {
      // Fallback to locally generated data
      setPetData(generateLocalPet())
    }
  }

  const handleBeginJourney = () => {
    // Navigate will happen via App.tsx state change (pet is now set)
    window.location.href = '/world'
  }

  const handleContinueToBackstory = () => {
    setPhase('backstory')
  }

  const species = petData?.species || 'cat'

  return (
    <div className="min-h-screen bg-black flex items-center justify-center relative overflow-hidden">
      {/* 3D Scene (background layer) */}
      <div className="absolute inset-0 z-0">
        <HatchScene
          phase={phase}
          hatchProgress={hatchProgress}
          revealProgress={revealProgress}
          species={species as Species}
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

        {/* Phase 2: Hatching (minimal UI - let the 3D scene do the work) */}
        {phase === 'hatching' && (
          <div className="text-center animate-[fade-in_0.3s_ease-out]">
            <p className="text-gray-400 text-sm animate-pulse mt-40">
              {hatchProgress < 0.3 ? 'Something stirs...' :
               hatchProgress < 0.6 ? 'Cracking...' :
               'Breaking free!'}
            </p>
          </div>
        )}

        {/* Phase 3: Reveal */}
        {phase === 'reveal' && petData && (
          <div className="animate-[fade-in_0.5s_ease-out] mt-32">
            <div className="bg-black/60 backdrop-blur-sm rounded-2xl border border-white/10 p-6 space-y-5">
              {/* Species & Name */}
              <div className="text-center space-y-2">
                {speciesVisible && (
                  <p className="text-gray-400 text-xs uppercase tracking-widest animate-[fade-in_0.3s_ease-out]">
                    {petData.species}
                  </p>
                )}
                <h2 className="text-2xl font-medium text-white">{petData.name}</h2>
                <RarityBadge rarity={petData.rarity as Rarity} visible={rarityVisible} />
              </div>

              {/* Stats */}
              <div className="space-y-2.5 pt-2">
                {Object.entries(petData.stats).map(([statName, value], idx) => (
                  <StatBar
                    key={statName}
                    name={statName}
                    value={value}
                    delay={idx * 300}
                    revealed={statsRevealed}
                  />
                ))}
              </div>

              {/* Total */}
              {statsRevealed && (
                <div className="flex justify-between items-center pt-2 border-t border-white/10 animate-[fade-in_0.3s_ease-out]">
                  <span className="text-gray-500 text-sm">Total</span>
                  <span className="text-white font-mono">
                    {Object.values(petData.stats).reduce((a, b) => a + b, 0)}
                  </span>
                </div>
              )}

              {/* Continue button */}
              {rarityVisible && (
                <button
                  onClick={handleContinueToBackstory}
                  className="w-full px-6 py-3 bg-white/10 border border-white/20 text-white rounded-lg hover:bg-white/20 transition-all animate-[fade-in_0.5s_ease-out] mt-4"
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
                <p className="text-gray-400 text-xs uppercase tracking-widest mb-1">{petData.species}</p>
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

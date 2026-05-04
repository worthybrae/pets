import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { EGG_VERT, EGG_FRAG, EGG_GLOW_VERT, EGG_GLOW_FRAG, SHADOW_VERT, SHADOW_FRAG } from './eggShaders'
import PetReveal from './PetReveal'
import type { Phase, EggProfile } from './types'

// ── Color map for egg color attribute ──

const COLOR_MAP: Record<string, { base: [number, number, number]; core: [number, number, number]; spec: [number, number, number] }> = {
  Stone:      { base: [0.55, 0.52, 0.48], core: [0.65, 0.6, 0.55],  spec: [0.9, 0.88, 0.85] },
  Moss:       { base: [0.42, 0.55, 0.38], core: [0.3, 0.6, 0.25],   spec: [0.8, 0.9, 0.75] },
  Amber:      { base: [0.78, 0.58, 0.32], core: [0.85, 0.55, 0.12], spec: [1.0, 0.9, 0.7] },
  Cobalt:     { base: [0.32, 0.48, 0.72], core: [0.22, 0.38, 0.82], spec: [0.7, 0.8, 1.0] },
  Crimson:    { base: [0.75, 0.28, 0.25], core: [0.85, 0.18, 0.12], spec: [1.0, 0.7, 0.7] },
  Violet:     { base: [0.55, 0.35, 0.68], core: [0.55, 0.22, 0.75], spec: [0.85, 0.7, 1.0] },
  Obsidian:   { base: [0.15, 0.14, 0.18], core: [0.3, 0.25, 0.4],   spec: [0.6, 0.55, 0.7] },
  Iridescent: { base: [0.6, 0.5, 0.65],   core: [0.7, 0.4, 0.8],   spec: [1.0, 0.9, 1.0] },
}

const SIZE_SCALE_MAP: Record<string, number> = {
  Tiny: 0.6, Small: 0.8, Standard: 1.0, Large: 1.2, Massive: 1.4, Colossal: 1.7,
}

function getEggUniforms(egg: EggProfile) {
  const colorAttr = egg.attributes.find(a => a.category === 'color')
  const colors = COLOR_MAP[colorAttr?.option.name || 'Stone'] || COLOR_MAP.Stone
  const shapeAttr = egg.attributes.find(a => a.category === 'shape')
  const scaleAttr = egg.attributes.find(a => a.category === 'scales')
  const sizeAttr = egg.attributes.find(a => a.category === 'size')
  const mistAttr = egg.attributes.find(a => a.category === 'mist')

  return {
    shapeType: shapeAttr?.option.value ?? 0,
    scaleType: scaleAttr?.option.value ?? 0,
    sizeScale: SIZE_SCALE_MAP[sizeAttr?.option.name || 'Standard'] || 1.0,
    mistIntensity: mistAttr?.option.value ?? 0,
    baseColor: colors.base,
    coreColor: colors.core,
    specColor: colors.spec,
  }
}

// ── Glow Halo ──

function GlowHalo({ phase, glowColor, mistIntensity }: { phase: Phase; glowColor: [number, number, number]; mistIntensity: number }) {
  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uGrowth: { value: 0 },
      uDissolve: { value: 0 },
      uGlowColor: { value: new THREE.Vector3(...glowColor) },
      uMistIntensity: { value: mistIntensity },
    },
    vertexShader: EGG_GLOW_VERT,
    fragmentShader: EGG_GLOW_FRAG,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  }), [glowColor, mistIntensity])

  useFrame((_, dt) => {
    mat.uniforms.uTime.value += dt
    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    mat.uniforms.uGrowth.value += (targetGrowth - mat.uniforms.uGrowth.value) * 0.03
    if (phase === 'reveal') {
      mat.uniforms.uDissolve.value = Math.min(1, mat.uniforms.uDissolve.value + dt * 0.7)
    }
  })

  return (
    <mesh position={[0, 0, -0.5]} material={mat}>
      <planeGeometry args={[6, 6]} />
    </mesh>
  )
}

// ── Egg Mesh ──

function EggMesh({ phase, egg, mouseRef }: {
  phase: Phase
  egg: EggProfile
  mouseRef: React.MutableRefObject<{ x: number; y: number }>
}) {
  const groupRef = useRef<THREE.Group>(null)
  const dissolveRef = useRef(0)
  const timeRef = useRef(0)
  const growthRef = useRef(0)

  const uniforms = useMemo(() => getEggUniforms(egg), [egg])

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uGrowth: { value: 0 },
      uDissolve: { value: 0 },
      uBeat: { value: 0 },
      uSeed: { value: Math.random() * 100 },
      uShapeType: { value: uniforms.shapeType },
      uScaleType: { value: uniforms.scaleType },
      uSizeScale: { value: uniforms.sizeScale },
      uMistIntensity: { value: uniforms.mistIntensity },
      uBaseColor: { value: new THREE.Vector3(...uniforms.baseColor) },
      uCoreColor: { value: new THREE.Vector3(...uniforms.coreColor) },
      uSpecColor: { value: new THREE.Vector3(...uniforms.specColor) },
    },
    vertexShader: EGG_VERT,
    fragmentShader: EGG_FRAG,
    transparent: true,
  }), [uniforms])

  useFrame((_, dt) => {
    timeRef.current += dt
    const t = timeRef.current
    mat.uniforms.uTime.value = t

    let targetGrowth = 0
    if (phase === 'idle') targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    growthRef.current += (targetGrowth - growthRef.current) * 0.03
    mat.uniforms.uGrowth.value = growthRef.current

    if (phase === 'reveal') {
      dissolveRef.current = Math.min(1, dissolveRef.current + dt * 0.5)
    }
    mat.uniforms.uDissolve.value = dissolveRef.current

    const beatSpeed = 1.0 + growthRef.current * 1.5
    const pulse = Math.pow(Math.max(0, Math.sin(t * beatSpeed)), 8.0)
    mat.uniforms.uBeat.value = pulse

    const beatAmp = 0.08 + growthRef.current * 0.06
    const scale = 1.0 + pulse * beatAmp

    if (groupRef.current) {
      groupRef.current.scale.setScalar(scale)
      groupRef.current.rotation.y += dt * 0.15 + mouseRef.current.x * 0.01
      groupRef.current.rotation.x = mouseRef.current.y * 0.1
    }
  })

  if (dissolveRef.current >= 0.99) return null

  return (
    <group ref={groupRef}>
      <mesh material={mat}>
        <sphereGeometry args={[1, 64, 64]} />
      </mesh>
    </group>
  )
}

// ── Ground Shadow ──

function GroundShadow() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.2, 0]}>
      <circleGeometry args={[1.5, 64]} />
      <shaderMaterial
        vertexShader={SHADOW_VERT}
        fragmentShader={SHADOW_FRAG}
        transparent
        depthWrite={false}
      />
    </mesh>
  )
}

// ── Camera ──

function SceneCamera({ phase }: { phase: Phase }) {
  const { camera } = useThree()
  const timeRef = useRef(0)

  useFrame((_, dt) => {
    timeRef.current += dt
    const t = timeRef.current

    if (phase === 'idle' || phase === 'hatching' || phase === 'stats') {
      const cx = Math.sin(t * 0.08) * 0.3
      const cy = 0.5 + Math.sin(t * 0.06) * 0.2
      const cz = phase === 'idle' ? 5 : 4
      camera.position.lerp(new THREE.Vector3(cx, cy, cz), 0.02)
      camera.lookAt(0, 0, 0)
    } else if (phase === 'generating') {
      const cx = Math.sin(t * 0.1) * 0.4
      const cy = 0.3 + Math.sin(t * 0.08) * 0.3
      camera.position.lerp(new THREE.Vector3(cx, cy, 3.5), 0.02)
      camera.lookAt(0, 0, 0)
    } else if (phase === 'reveal') {
      camera.position.lerp(new THREE.Vector3(0, 3, 11), 0.03)
      camera.lookAt(0, 1, 0)
    }
  })

  return null
}

// ── Main Scene (exported) ──

export default function EggScene({ phase, egg, revealProgress, voxels }: {
  phase: Phase
  egg: EggProfile
  revealProgress: number
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}) {
  const mouseRef = useRef({ x: 0, y: 0 })
  const uniforms = useMemo(() => getEggUniforms(egg), [egg])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mouseRef.current.x = (e.clientX / window.innerWidth) * 2 - 1
      mouseRef.current.y = (e.clientY / window.innerHeight) * 2 - 1
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  return (
    <Canvas
      camera={{ position: [0, 0.5, 5], fov: 35, near: 0.1, far: 100 }}
      gl={{ antialias: true, alpha: false }}
      className="!absolute inset-0"
    >
      <color attach="background" args={['#0a0a0f']} />
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={0.5} />

      <SceneCamera phase={phase} />
      <GlowHalo phase={phase} glowColor={uniforms.coreColor} mistIntensity={uniforms.mistIntensity} />
      <EggMesh phase={phase} egg={egg} mouseRef={mouseRef} />
      <GroundShadow />

      {phase === 'reveal' && voxels.length > 0 && (
        <PetReveal voxels={voxels} progress={revealProgress} />
      )}
    </Canvas>
  )
}

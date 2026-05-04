import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { EGG_VERT, EGG_FRAG, EGG_GLOW_VERT, EGG_GLOW_FRAG, SHADOW_VERT, SHADOW_FRAG } from './eggShaders'
import PetReveal from './PetReveal'
import type { Phase, EggProfile } from './types'

// ── Color map for egg color attribute ──

const COLOR_MAP: Record<string, { base: [number, number, number]; core: [number, number, number]; spec: [number, number, number] }> = {
  // Deep rich tones — designed for gem-like rendering with color variation
  Stone:      { base: [0.38, 0.35, 0.32], core: [0.75, 0.6, 0.4],   spec: [1.0, 0.95, 0.85] },
  Moss:       { base: [0.15, 0.35, 0.12], core: [0.2, 0.75, 0.15],  spec: [0.6, 1.0, 0.5] },
  Amber:      { base: [0.6, 0.35, 0.08],  core: [1.0, 0.65, 0.05],  spec: [1.0, 0.95, 0.5] },
  Cobalt:     { base: [0.1, 0.22, 0.55],  core: [0.1, 0.4, 1.0],    spec: [0.5, 0.75, 1.0] },
  Crimson:    { base: [0.55, 0.08, 0.08], core: [1.0, 0.12, 0.05],  spec: [1.0, 0.5, 0.4] },
  Violet:     { base: [0.35, 0.12, 0.55], core: [0.65, 0.1, 0.95],  spec: [0.8, 0.5, 1.0] },
  Obsidian:   { base: [0.06, 0.05, 0.1],  core: [0.2, 0.15, 0.5],   spec: [0.45, 0.4, 0.7] },
  Iridescent: { base: [0.4, 0.3, 0.5],    core: [0.8, 0.3, 0.9],    spec: [1.0, 0.8, 1.0] },
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

function GlowHalo({ phase, glowColor, mistIntensity, eggScaleRef }: { phase: Phase; glowColor: [number, number, number]; mistIntensity: number; eggScaleRef: React.MutableRefObject<number> }) {
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
    // Mist shows as soon as egg has grown in
    let targetGrowth = eggScaleRef.current * 0.5
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    mat.uniforms.uGrowth.value += (targetGrowth - mat.uniforms.uGrowth.value) * 0.03
    // Fade in mist intensity with egg intro
    mat.uniforms.uMistIntensity.value = mistIntensity * eggScaleRef.current
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

const INTRO_DURATION = 5.0 // seconds for black sphere → full egg
const MAX_EGG_SCALE = 0.3 // tuned for detail visibility

function EggMesh({ phase, egg, mouseRef, onIntroComplete, eggScaleRef, seed }: {
  phase: Phase
  egg: EggProfile
  mouseRef: React.MutableRefObject<{ x: number; y: number }>
  onIntroComplete: () => void
  eggScaleRef: React.MutableRefObject<number>
  seed: number
}) {
  const groupRef = useRef<THREE.Group>(null)
  const dissolveRef = useRef(0)
  const timeRef = useRef(0)
  const growthRef = useRef(0)
  const introRef = useRef(0) // 0→1 over INTRO_DURATION
  const introCompleteRef = useRef(false)
  const nextBeatRef = useRef(0) // time of next random beat
  const beatDecayRef = useRef(0) // current beat decay value

  const uniforms = useMemo(() => getEggUniforms(egg), [egg])

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uGrowth: { value: 0 },
      uDissolve: { value: 0 },
      uBeat: { value: 0 },
      uSeed: { value: seed },
      uShapeType: { value: uniforms.shapeType },
      uScaleType: { value: uniforms.scaleType },
      uSizeScale: { value: 0.08 },
      uMorph: { value: 0 },
      uMistIntensity: { value: 0 },
      uBaseColor: { value: new THREE.Vector3(0.02, 0.02, 0.03) },
      uCoreColor: { value: new THREE.Vector3(0.05, 0.05, 0.08) },
      uSpecColor: { value: new THREE.Vector3(0.1, 0.1, 0.1) },
    },
    vertexShader: EGG_VERT,
    fragmentShader: EGG_FRAG,
    transparent: true,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [uniforms.shapeType, uniforms.scaleType, seed])

  useFrame((_, dt) => {
    timeRef.current += dt
    const t = timeRef.current
    mat.uniforms.uTime.value = t

    // ── Intro animation: black sphere → colored egg ──
    if (introRef.current < 1) {
      introRef.current = Math.min(1, introRef.current + dt / INTRO_DURATION)
      const p = introRef.current
      // Spurt easing: grows in distinct bursts with brief pauses
      const burstCount = 5
      const raw = p * burstCount
      const burst = Math.floor(Math.min(raw, burstCount - 0.001))
      const within = raw - burst
      // Each burst: active growth then a brief pause
      const burstEase = within < 0.6
        ? 0.5 * (1 - Math.cos(Math.PI * within / 0.6))
        : 1.0
      const ease = Math.min(1, (burst + burstEase) / burstCount)

      // Pulse the core on each growth burst
      if (within < 0.3) {
        mat.uniforms.uBeat.value = Math.pow(1 - within / 0.3, 3)
      } else {
        mat.uniforms.uBeat.value = 0
      }

      // Schedule first random beat after intro completes
      if (burst === burstCount - 1) {
        nextBeatRef.current = t + 1.5 + Math.random() * 2.0
      }

      // Write current progress to shared ref for shadow sync
      eggScaleRef.current = ease

      // Lerp size from tiny to final
      const finalSize = uniforms.sizeScale * MAX_EGG_SCALE
      const currentSize = 0.08 + (finalSize - 0.08) * ease
      mat.uniforms.uSizeScale.value = currentSize
      // Morph from sphere to egg shape smoothly
      mat.uniforms.uMorph.value = ease

      // Lerp colors from black to actual
      const base = mat.uniforms.uBaseColor.value as THREE.Vector3
      base.set(
        0.02 + (uniforms.baseColor[0] - 0.02) * ease,
        0.02 + (uniforms.baseColor[1] - 0.02) * ease,
        0.03 + (uniforms.baseColor[2] - 0.03) * ease
      )
      const core = mat.uniforms.uCoreColor.value as THREE.Vector3
      core.set(
        0.05 + (uniforms.coreColor[0] - 0.05) * ease,
        0.05 + (uniforms.coreColor[1] - 0.05) * ease,
        0.08 + (uniforms.coreColor[2] - 0.08) * ease
      )
      const spec = mat.uniforms.uSpecColor.value as THREE.Vector3
      spec.set(
        0.1 + (uniforms.specColor[0] - 0.1) * ease,
        0.1 + (uniforms.specColor[1] - 0.1) * ease,
        0.1 + (uniforms.specColor[2] - 0.1) * ease
      )

      // Mist fades in last
      const mistP = Math.max(0, (p - 0.7) / 0.3)
      mat.uniforms.uMistIntensity.value = uniforms.mistIntensity * mistP

      // Fire callback when done
      if (p >= 1 && !introCompleteRef.current) {
        introCompleteRef.current = true
        onIntroComplete()
      }
    }

    // ── Phase-based growth (post-intro) ──
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

    // ── Random beats (post-intro) ──
    if (introRef.current >= 1) {
      beatDecayRef.current = Math.max(0, beatDecayRef.current - dt * 4.0)
      if (t >= nextBeatRef.current) {
        beatDecayRef.current = 1.0
        // Schedule next beat at random interval (1.5–4.5s)
        nextBeatRef.current = t + 1.5 + Math.random() * 3.0
      }
      mat.uniforms.uBeat.value = Math.pow(beatDecayRef.current, 3)
    }

    const scale = 1.0

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

function GroundShadow({ phase, eggScaleRef }: { phase: Phase; eggScaleRef: React.MutableRefObject<number> }) {
  const meshRef = useRef<THREE.Mesh>(null)

  const growthRef = useRef(0)
  useFrame((_, dt) => {
    if (!meshRef.current) return

    // Track the growth uniform smoothly
    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    growthRef.current += (targetGrowth - growthRef.current) * 0.03

    // Shadow scales with intro progress AND post-intro growth
    const growthScale = 0.8 + growthRef.current * 0.6 // matches shader: uSizeScale * (0.8 + uGrowth * 0.6)
    let scale = eggScaleRef.current * growthScale
    if (phase === 'reveal') scale *= Math.max(0, 1 - growthRef.current * 0.3)

    meshRef.current.scale.setScalar(scale)
  })

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.85, 0]} scale={0}>
      <circleGeometry args={[1.0, 64]} />
      <shaderMaterial
        vertexShader={SHADOW_VERT}
        fragmentShader={SHADOW_FRAG}
        transparent
        depthWrite={false}
      />
    </mesh>
  )
}

// ── Mist Cloud — 3D volumetric fog ellipsoid ──

function MistCloud({ mistIntensity, color, eggScaleRef, phase }: {
  mistIntensity: number
  color: [number, number, number]
  eggScaleRef: React.MutableRefObject<number>
  phase: Phase
}) {
  const meshRef = useRef<THREE.Mesh>(null)

  const material = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Vector3(...color) },
      uOpacity: { value: 0 },
    },
    vertexShader: /* glsl */ `
      varying vec3 vNormal;
      varying vec3 vViewDir;
      void main() {
        vec4 worldPos = modelMatrix * vec4(position, 1.0);
        vNormal = normalize(normalMatrix * normal);
        vViewDir = normalize(cameraPosition - worldPos.xyz);
        gl_Position = projectionMatrix * viewMatrix * worldPos;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uTime;
      uniform vec3 uColor;
      uniform float uOpacity;
      varying vec3 vNormal;
      varying vec3 vViewDir;

      void main() {
        float facing = abs(dot(normalize(vNormal), normalize(vViewDir)));
        // pow 0.8 → visible from shallow camera angle, soft fade at edges
        float thickness = pow(facing, 0.8);
        // Kill the hard mesh boundary
        float edgeFade = smoothstep(0.0, 0.15, facing);
        thickness *= edgeFade;

        float breathe = 1.0 + sin(uTime * 0.7) * 0.05 + sin(uTime * 0.4) * 0.03;

        float alpha = thickness * uOpacity * breathe;

        // Tinted enough to distinguish from gray background
        vec3 col = uColor * 0.5 + vec3(0.4);

        if (alpha < 0.003) discard;
        gl_FragColor = vec4(col, alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    side: THREE.BackSide,
  }), [color])

  const growthRef = useRef(0)
  useFrame((_, dt) => {
    if (!material || !meshRef.current) return
    material.uniforms.uTime.value += dt

    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    growthRef.current += (targetGrowth - growthRef.current) * 0.03

    const growthScale = 0.8 + growthRef.current * 0.6
    const eggScale = eggScaleRef.current * growthScale

    // Pillow shape: ~2x egg width, visible depth
    const w = eggScale * 1.0
    const h = eggScale * 0.2
    meshRef.current.scale.set(w, h, w)

    // Opacity
    const opTarget = phase === 'reveal' ? 0 : 0.4 + mistIntensity * 0.12
    const eggFade = Math.min(1, eggScaleRef.current * 2)
    const cur = material.uniforms.uOpacity.value
    material.uniforms.uOpacity.value += (opTarget * eggFade - cur) * dt * 1.5

    // Sit at egg base
    meshRef.current.position.y = -eggScale * 0.2
  })

  return (
    <mesh ref={meshRef} position={[0, 0, 0]}>
      <sphereGeometry args={[1, 32, 16]} />
      <primitive object={material} attach="material" />
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

export default function EggScene({ phase, egg, revealProgress, voxels, onIntroComplete }: {
  phase: Phase
  egg: EggProfile
  revealProgress: number
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  onIntroComplete?: () => void
}) {
  const mouseRef = useRef({ x: 0, y: 0 })
  const eggScaleRef = useRef(0) // shared: intro progress (0→1)
  const uniforms = useMemo(() => getEggUniforms(egg), [egg])
  const seed = useMemo(() => Math.random() * 100, [])

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
      <color attach="background" args={['#e5e5e5']} />
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={0.5} />

      <SceneCamera phase={phase} />
      <GlowHalo phase={phase} glowColor={uniforms.coreColor} mistIntensity={uniforms.mistIntensity} eggScaleRef={eggScaleRef} />
      <EggMesh phase={phase} egg={egg} mouseRef={mouseRef} onIntroComplete={onIntroComplete || (() => {})} eggScaleRef={eggScaleRef} seed={seed} />
      <GroundShadow phase={phase} eggScaleRef={eggScaleRef} />
      {uniforms.mistIntensity > 0 && (
        <MistCloud mistIntensity={uniforms.mistIntensity} color={uniforms.coreColor} eggScaleRef={eggScaleRef} phase={phase} />
      )}

      {phase === 'reveal' && voxels.length > 0 && (
        <PetReveal voxels={voxels} progress={revealProgress} />
      )}
    </Canvas>
  )
}

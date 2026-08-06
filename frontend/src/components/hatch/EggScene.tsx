import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { Environment } from '@react-three/drei'
import { EffectComposer, N8AO, Bloom, Vignette, ToneMapping } from '@react-three/postprocessing'
import { ToneMappingMode } from 'postprocessing'
import VoxelEgg from './VoxelEgg'
import PetReveal from './PetReveal'
import type { Phase, EggProfile } from './types'

// ── Color map for egg color attribute (0-255 for VoxelEgg) ──

const COLOR_MAP: Record<string, { base: [number, number, number]; core: [number, number, number]; spec: [number, number, number] }> = {
  Stone:      { base: [97, 89, 82],    core: [191, 153, 102],  spec: [255, 242, 217] },
  Moss:       { base: [38, 89, 31],    core: [51, 191, 38],    spec: [153, 255, 128] },
  Amber:      { base: [153, 89, 20],   core: [255, 166, 13],   spec: [255, 242, 128] },
  Cobalt:     { base: [26, 56, 140],   core: [26, 102, 255],   spec: [128, 191, 255] },
  Crimson:    { base: [140, 20, 20],   core: [255, 31, 13],    spec: [255, 128, 102] },
  Violet:     { base: [89, 31, 140],   core: [166, 26, 242],   spec: [204, 128, 255] },
  Obsidian:   { base: [15, 13, 26],    core: [51, 38, 128],    spec: [115, 102, 179] },
  Iridescent: { base: [102, 77, 128],  core: [204, 77, 230],   spec: [255, 204, 255] },
}

const SIZE_SCALE_MAP: Record<string, number> = {
  Tiny: 0.6, Small: 0.8, Standard: 1.0, Large: 1.2, Massive: 1.4, Colossal: 1.7,
}

function getEggProps(egg: EggProfile) {
  const colorAttr = egg.attributes.find(a => a.category === 'color')
  const colors = COLOR_MAP[colorAttr?.option.name || 'Stone'] || COLOR_MAP.Stone
  const shapeAttr = egg.attributes.find(a => a.category === 'shape')
  const scaleAttr = egg.attributes.find(a => a.category === 'scales')
  const sizeAttr = egg.attributes.find(a => a.category === 'size')

  return {
    shape: shapeAttr?.option.value ?? 0,
    scalePattern: scaleAttr?.option.value ?? 0,
    size: SIZE_SCALE_MAP[sizeAttr?.option.name || 'Standard'] || 1.0,
    baseColor: colors.base as [number, number, number],
    coreColor: colors.core as [number, number, number],
    specColor: colors.spec as [number, number, number],
  }
}


// ── Ground Plane ──

function GroundPlane() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]} receiveShadow>
      <planeGeometry args={[40, 40]} />
      <meshStandardMaterial color="#d4d0cc" roughness={0.9} metalness={0} />
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
      camera.position.lerp(new THREE.Vector3(cx, cy, 4.5), 0.02)
      camera.lookAt(0, 0, 0)
    } else if (phase === 'reveal') {
      camera.position.lerp(new THREE.Vector3(0, 3, 11), 0.03)
      camera.lookAt(0, 1, 0)
    }
  })

  return null
}

// ── Main Scene (exported) ──

export default function EggScene({ phase, egg, revealProgress, voxels, onIntroComplete, onHover }: {
  phase: Phase
  egg: EggProfile
  revealProgress: number
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  onIntroComplete?: () => void
  onHover?: (hovered: boolean) => void
}) {
  const mouseRef = useRef({ x: 0, y: 0 })
  const eggScaleRef = useRef(0)
  const props = useMemo(() => getEggProps(egg), [egg])

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
      gl={{ antialias: true, alpha: false, toneMapping: THREE.NoToneMapping }}
      className="!absolute inset-0"
    >
      <color attach="background" args={['#e8e4e0']} />

      {/* HDR environment for realistic reflections on clearcoat */}
      <Environment preset="studio" environmentIntensity={0.6} />

      {/* 3-point lighting — key/fill/rim for a product-shot look */}
      <ambientLight intensity={0.3} />
      <directionalLight position={[3, 6, 4]} intensity={1.4} castShadow shadow-mapSize={1024} />
      <directionalLight position={[-4, 2, -2]} intensity={0.5} />
      <directionalLight position={[0, -1, -4]} intensity={0.2} />
      <pointLight position={[0, 3, 2]} intensity={0.8} distance={12} decay={2} />

      <SceneCamera phase={phase} />
      <GroundPlane />

      <VoxelEgg
        color={{ base: props.baseColor, core: props.coreColor }}
        shape={props.shape}
        size={props.size}
        scalePattern={props.scalePattern}
        phase={phase}
        eggScaleRef={eggScaleRef}
        onIntroComplete={onIntroComplete || (() => {})}
        mouseRef={mouseRef}
        onHover={onHover}
      />

      {phase === 'reveal' && voxels.length > 0 && (
        <PetReveal voxels={voxels} progress={revealProgress} fallbackColor={[props.coreColor[0] / 255, props.coreColor[1] / 255, props.coreColor[2] / 255]} />
      )}

      {/* Post-processing: SSAO + Bloom + Vignette + ACES tone mapping */}
      <EffectComposer multisampling={4}>
        <N8AO
          aoRadius={0.5}
          intensity={2.5}
          aoSamples={16}
          denoiseSamples={8}
          distanceFalloff={0.5}
          quality="high"
          halfRes={false}
        />
        <Bloom
          luminanceThreshold={0.8}
          luminanceSmoothing={0.4}
          intensity={0.35}
          mipmapBlur
        />
        <Vignette offset={0.3} darkness={0.6} />
        <ToneMapping mode={ToneMappingMode.ACES_FILMIC} />
      </EffectComposer>
    </Canvas>
  )
}

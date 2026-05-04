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

// Width scale per shape type (matches widthScale in eggShaders vertex shader)
const SHAPE_WIDTH: Record<number, number> = {
  0: 1.05,  // Round
  1: 0.95,  // Oval
  2: 1.15,  // Squat
  3: 0.82,  // Elongated
  4: 1.0,   // Teardrop
  5: 1.12,  // Bulbous
  6: 0.98,  // Gourd
  7: 0.72,  // Spire
}

function getEggUniforms(egg: EggProfile) {
  const colorAttr = egg.attributes.find(a => a.category === 'color')
  const colors = COLOR_MAP[colorAttr?.option.name || 'Stone'] || COLOR_MAP.Stone
  const shapeAttr = egg.attributes.find(a => a.category === 'shape')
  const scaleAttr = egg.attributes.find(a => a.category === 'scales')
  const sizeAttr = egg.attributes.find(a => a.category === 'size')
  const mistAttr = egg.attributes.find(a => a.category === 'mist')
  const shapeType = shapeAttr?.option.value ?? 0

  return {
    shapeType,
    scaleType: scaleAttr?.option.value ?? 0,
    sizeScale: SIZE_SCALE_MAP[sizeAttr?.option.name || 'Standard'] || 1.0,
    widthScale: SHAPE_WIDTH[shapeType] ?? 1.0,
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
    if (phase === 'generating') targetGrowth = 1.3
    mat.uniforms.uGrowth.value += (targetGrowth - mat.uniforms.uGrowth.value) * 0.03
    // Fade in mist intensity with egg intro
    mat.uniforms.uMistIntensity.value = mistIntensity * eggScaleRef.current
    if (phase === 'reveal') {
      mat.uniforms.uDissolve.value = Math.min(1, mat.uniforms.uDissolve.value + dt * 0.7)
    }
  })

  return (
    <mesh position={[0, 0, -0.5]} material={mat}>
      <planeGeometry args={[10, 10]} />
    </mesh>
  )
}

// ── Egg Mesh ──

const MAX_EGG_SCALE = 0.3 // tuned for detail visibility

function EggMesh({ phase, egg, mouseRef, onIntroComplete, eggScaleRef, seed, onHover }: {
  phase: Phase
  egg: EggProfile
  mouseRef: React.MutableRefObject<{ x: number; y: number }>
  onIntroComplete: () => void
  eggScaleRef: React.MutableRefObject<number>
  seed: number
  onHover?: (hovered: boolean) => void
}) {
  const groupRef = useRef<THREE.Group>(null)
  const meshRef = useRef<THREE.Mesh>(null)
  const dissolveRef = useRef(0)
  const timeRef = useRef(0)
  const growthRef = useRef(0)
  const shakeRef = useRef(0) // shake intensity ramps up during generating
  const nextBeatRef = useRef(1.5 + Math.random() * 2.0)
  const beatDecayRef = useRef(0)
  const visualRadiusRef = useRef(0.08)

  const uniforms = useMemo(() => getEggUniforms(egg), [egg])

  const finalSize = uniforms.sizeScale * MAX_EGG_SCALE

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uGrowth: { value: 0 },
      uDissolve: { value: 0 },
      uBeat: { value: 0 },
      uSeed: { value: seed },
      uShapeType: { value: uniforms.shapeType },
      uScaleType: { value: uniforms.scaleType },
      uSizeScale: { value: finalSize },
      uMorph: { value: 1 },
      uMistIntensity: { value: uniforms.mistIntensity },
      uBaseColor: { value: new THREE.Vector3(...uniforms.baseColor) },
      uCoreColor: { value: new THREE.Vector3(...uniforms.coreColor) },
      uSpecColor: { value: new THREE.Vector3(...uniforms.specColor) },
    },
    vertexShader: EGG_VERT,
    fragmentShader: EGG_FRAG,
    transparent: true,
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [uniforms.shapeType, uniforms.scaleType, seed])

  // Egg exists immediately — no intro animation
  useEffect(() => {
    eggScaleRef.current = 1
    onIntroComplete()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Override raycast to match visual egg size (shader scales geometry down)
  useEffect(() => {
    const mesh = meshRef.current
    if (!mesh) return
    const _sphere = new THREE.Sphere(new THREE.Vector3(), 1)
    const _target = new THREE.Vector3()
    mesh.raycast = (raycaster: THREE.Raycaster, intersects: THREE.Intersection[]) => {
      mesh.getWorldPosition(_sphere.center)
      _sphere.radius = visualRadiusRef.current
      if (raycaster.ray.intersectSphere(_sphere, _target)) {
        const dist = raycaster.ray.origin.distanceTo(_target)
        if (dist >= raycaster.near && dist <= raycaster.far) {
          intersects.push({ distance: dist, point: _target.clone(), object: mesh } as THREE.Intersection)
        }
      }
    }
  }, [])

  useFrame((_, dt) => {
    timeRef.current += dt
    const t = timeRef.current
    mat.uniforms.uTime.value = t

    // ── Phase-based growth ──
    let targetGrowth = 0
    if (phase === 'idle') targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 1.2
    growthRef.current += (targetGrowth - growthRef.current) * 0.03
    mat.uniforms.uGrowth.value = growthRef.current
    visualRadiusRef.current = finalSize * (0.8 + growthRef.current * 0.6)

    if (phase === 'reveal') {
      dissolveRef.current = Math.min(1, dissolveRef.current + dt * 0.8)
    }
    mat.uniforms.uDissolve.value = dissolveRef.current

    // ── Shake during generating — builds gradually ──
    if (phase === 'generating') {
      shakeRef.current = Math.min(1, shakeRef.current + dt * 0.03)
    } else if (phase === 'reveal') {
      shakeRef.current = Math.max(0, shakeRef.current - dt * 3)
    } else {
      shakeRef.current = 0
    }

    // ── Gentle core glow — slow smooth pulse ──
    // Beat faster during generating (egg is agitated)
    const beatSpeed = phase === 'generating' ? 1.5 : 0.8
    const beatInterval = phase === 'generating' ? 0.8 + Math.random() * 0.5 : 3.0 + Math.random() * 3.0
    beatDecayRef.current = Math.max(0, beatDecayRef.current - dt * beatSpeed)
    if (t >= nextBeatRef.current) {
      beatDecayRef.current = 1.0
      nextBeatRef.current = t + beatInterval
    }
    const b = beatDecayRef.current
    const beatStrength = phase === 'generating' ? 0.9 : 0.6
    mat.uniforms.uBeat.value = Math.sin(b * Math.PI) * beatStrength

    if (groupRef.current) {
      const shake = shakeRef.current
      const shakeX = shake * Math.sin(t * 35) * 0.02
      const shakeZ = shake * Math.cos(t * 28) * 0.015
      groupRef.current.rotation.y += dt * 0.15 + mouseRef.current.x * 0.01
      groupRef.current.rotation.x = mouseRef.current.y * 0.1 + shakeX
      groupRef.current.position.x = shakeZ
    }
  })

  if (dissolveRef.current >= 0.99) return null

  return (
    <group ref={groupRef}>
      <mesh ref={meshRef} material={mat} onPointerOver={() => onHover?.(true)} onPointerOut={() => onHover?.(false)}>
        <sphereGeometry args={[1, 64, 64]} />
      </mesh>
    </group>
  )
}

// ── Ground Shadow ──

function GroundShadow({ phase, eggScaleRef, color }: { phase: Phase; eggScaleRef: React.MutableRefObject<number>; color: [number, number, number] }) {
  const meshRef = useRef<THREE.Mesh>(null)

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: new THREE.Vector3(...color) },
    },
    vertexShader: SHADOW_VERT,
    fragmentShader: SHADOW_FRAG,
    transparent: true,
    depthWrite: false,
  }), [color])

  const growthRef = useRef(0)
  useFrame((_, dt) => {
    if (!meshRef.current) return

    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 1.2
    growthRef.current += (targetGrowth - growthRef.current) * 0.03

    const growthScale = 0.8 + growthRef.current * 0.6
    let scale = eggScaleRef.current * growthScale
    if (phase === 'reveal') scale *= Math.max(0, 1 - growthRef.current * 0.3)

    meshRef.current.scale.setScalar(scale)
  })

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.85, 0]} scale={0} material={mat}>
      <circleGeometry args={[1.0, 64]} />
    </mesh>
  )
}

// ── Mist — soft fog bed beneath egg ──

const MIST_NOISE = /* glsl */ `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1./6.,1./3.);
  const vec4 D=vec4(0.,.5,1.,2.);
  vec3 i=floor(v+dot(v,C.yyy));
  vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz);
  vec3 l=1.-g;
  vec3 i1=min(g.xyz,l.zxy);
  vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx;
  vec3 x2=x0-i2+C.yyy;
  vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(
    i.z+vec4(0.,i1.z,i2.z,1.))
    +i.y+vec4(0.,i1.y,i2.y,1.))
    +i.x+vec4(0.,i1.x,i2.x,1.));
  float n_=.142857142857;
  vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z);
  vec4 y_=floor(j-7.*x_);
  vec4 x=x_*ns.x+ns.yyyy;
  vec4 y=y_*ns.x+ns.yyyy;
  vec4 h=1.-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy);
  vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.+1.;
  vec4 s1=floor(b1)*2.+1.;
  vec4 sh=-step(h,vec4(0.));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
  vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x);
  vec3 p1=vec3(a0.zw,h.y);
  vec3 p2=vec3(a1.xy,h.z);
  vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);
  m=m*m;
  return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
`

function MistCloud({ mistIntensity, color, eggScaleRef, phase, eggSize, widthScale }: {
  mistIntensity: number
  color: [number, number, number]
  eggScaleRef: React.MutableRefObject<number>
  phase: Phase
  eggSize: number
  widthScale: number
}) {
  const meshRef = useRef<THREE.Mesh>(null)

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Vector3(...color) },
      uOpacity: { value: 0 },
      uRadius: { value: 0.5 },
      uMistIntensity: { value: mistIntensity },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uTime;
      uniform vec3 uColor;
      uniform float uOpacity;
      uniform float uRadius;
      uniform float uMistIntensity;
      varying vec2 vUv;

      ${MIST_NOISE}

      void main() {
        vec2 center = vUv - 0.5;
        float d = length(center) * 2.0;

        // Soft radial falloff
        float radial = 1.0 - smoothstep(0.2, 0.9, d);
        radial *= radial;

        // Layered animated noise — slow drift
        vec3 noisePos = vec3(center * 4.0, uTime * 0.1);
        float n1 = snoise(noisePos) * 0.5 + 0.5;
        float n2 = snoise(noisePos * 2.0 + vec3(100.0)) * 0.5 + 0.5;
        float fog = n1 * 0.6 + n2 * 0.4;

        // Gentle shaping — avoid hard bright/dark contrast
        fog = smoothstep(0.3, 0.65, fog) * 0.6 + 0.2;
        float alpha = radial * fog * uOpacity;

        // Rarer mist is slightly denser
        alpha *= 0.25 + uMistIntensity * 0.08;

        if (alpha < 0.005) discard;
        // Darken the color slightly so it reads as shadow+mist, not a bright glow
        vec3 mistColor = uColor * 0.5;
        gl_FragColor = vec4(mistColor, alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  }), [color, mistIntensity])

  const growthRef = useRef(0)
  useFrame((_, dt) => {
    if (!mat || !meshRef.current) return
    mat.uniforms.uTime.value += dt

    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 1.2
    growthRef.current += (targetGrowth - growthRef.current) * 0.03

    const eggFade = Math.min(1, eggScaleRef.current * 2)

    // Mist grows only slightly with phase, not as aggressively as the egg
    const mistGrowth = 1.0 + growthRef.current * 0.15
    const radius = eggSize * widthScale * (1.2 + mistIntensity * 0.3) * mistGrowth
    meshRef.current.scale.set(radius, radius, 1)

    const opTarget = phase === 'reveal' ? 0 : 1.0
    const cur = mat.uniforms.uOpacity.value
    mat.uniforms.uOpacity.value += (opTarget * eggFade - cur) * dt * 1.5
  })

  return (
    <mesh ref={meshRef} rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.85, 0]} material={mat}>
      <planeGeometry args={[1, 1]} />
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
      <EggMesh phase={phase} egg={egg} mouseRef={mouseRef} onIntroComplete={onIntroComplete || (() => {})} eggScaleRef={eggScaleRef} seed={seed} onHover={onHover} />
      {uniforms.mistIntensity > 0 ? (
        <MistCloud mistIntensity={uniforms.mistIntensity} color={uniforms.coreColor} eggScaleRef={eggScaleRef} phase={phase} eggSize={uniforms.sizeScale * MAX_EGG_SCALE} widthScale={uniforms.widthScale} />
      ) : (
        <GroundShadow phase={phase} eggScaleRef={eggScaleRef} color={uniforms.coreColor} />
      )}

      {phase === 'reveal' && voxels.length > 0 && (
        <PetReveal voxels={voxels} progress={revealProgress} fallbackColor={uniforms.coreColor} />
      )}
    </Canvas>
  )
}

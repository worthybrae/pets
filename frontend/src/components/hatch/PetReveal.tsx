import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

// Minimum per-voxel brightness (0-1 avg channel). Below this, blend toward fallback.
const MIN_BRIGHTNESS = 0.25

export default function PetReveal({ voxels, progress, fallbackColor }: {
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  progress: number
  fallbackColor?: [number, number, number]
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)

  const centered = useMemo(() => {
    if (voxels.length === 0) return voxels
    const cx = voxels.reduce((s, v) => s + v.x, 0) / voxels.length
    const cy = voxels.reduce((s, v) => s + v.y, 0) / voxels.length
    const cz = voxels.reduce((s, v) => s + v.z, 0) / voxels.length
    return voxels.map(v => ({ ...v, x: v.x - cx, y: v.y - cy, z: v.z - cz }))
  }, [voxels])

  // Pre-compute corrected colors (0-1 range, dark voxels blended with fallback)
  const correctedColors = useMemo(() => {
    if (voxels.length === 0) return []
    // Debug
    const avgBright = voxels.reduce((s, v) => s + v.r + v.g + v.b, 0) / voxels.length
    console.log('[PetReveal] voxels:', voxels.length,
      '| avgBrightness(0-765):', avgBright.toFixed(1),
      '| fallback:', fallbackColor,
      '| samples:', voxels.slice(0, 3).map(v => `(${v.r},${v.g},${v.b})`).join(' '))

    return centered.map(v => {
      // Normalize to 0-1
      let rr = v.r > 1 ? v.r / 255 : v.r
      let gg = v.g > 1 ? v.g / 255 : v.g
      let bb = v.b > 1 ? v.b / 255 : v.b

      const brightness = (rr + gg + bb) / 3

      if (brightness < MIN_BRIGHTNESS && fallbackColor) {
        // Compute position-based fallback color for depth variation
        const height = (v.y + 10) / 20
        const variation = 0.7 + height * 0.6
        const fr = fallbackColor[0] * variation
        const fg = fallbackColor[1] * variation
        const fb = fallbackColor[2] * variation

        // Blend: fully fallback at black, full original at threshold
        const t = brightness / MIN_BRIGHTNESS
        rr = rr * t + fr * (1 - t)
        gg = gg * t + fg * (1 - t)
        bb = bb * t + fb * (1 - t)
      }

      return { r: rr, g: gg, b: bb }
    })
  }, [voxels, centered, fallbackColor])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (!meshRef.current || !groupRef.current) return
    const mesh = meshRef.current
    const obj = new THREE.Object3D()
    const col = new THREE.Color()
    const show = Math.floor(progress * centered.length)

    for (let i = 0; i < centered.length; i++) {
      const v = centered[i]
      if (i < show) {
        const localP = Math.min(1, (progress * centered.length - i) / 5)
        const ease = 1 - Math.pow(1 - localP, 3)
        obj.position.set(
          v.x * 3 * (1 - ease) + v.x * ease,
          v.y * 3 * (1 - ease) + 5 * (1 - ease) + v.y * ease,
          v.z * 3 * (1 - ease) + v.z * ease
        )
        const scale = ease * (localP < 0.3 ? localP / 0.3 : 1)
        obj.scale.setScalar(scale)
        obj.updateMatrix()
        mesh.setMatrixAt(i, obj.matrix)
        const cb = Math.min(1, localP * 2)
        const glow = (1 - cb) * 2
        const cc = correctedColors[i] || { r: 0.6, g: 0.6, b: 0.6 }
        col.setRGB(
          cc.r * cb + glow,
          cc.g * cb + glow,
          cc.b * cb + glow,
          THREE.SRGBColorSpace
        )
        mesh.setColorAt(i, col)
      } else {
        obj.scale.setScalar(0)
        obj.updateMatrix()
        mesh.setMatrixAt(i, obj.matrix)
      }
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    groupRef.current.rotation.y += delta * 0.4
  })

  if (centered.length === 0) return null

  // Auto-scale to fit scene based on bounding box
  const scale = useMemo(() => {
    if (centered.length === 0) return 1
    let maxDim = 0
    for (const v of centered) {
      maxDim = Math.max(maxDim, Math.abs(v.x), Math.abs(v.y), Math.abs(v.z))
    }
    return maxDim > 0 ? 2.5 / maxDim : 1
  }, [centered])

  return (
    <group ref={groupRef} position={[0, 1.5, 0]} scale={scale}>
      <ambientLight intensity={Math.PI} />
      <directionalLight position={[5, 8, 5]} intensity={Math.PI * 1.5} />
      <directionalLight position={[-3, 2, -3]} intensity={Math.PI * 0.5} />
      <pointLight position={[0, 5, 5]} intensity={Math.PI * 2} distance={20} decay={1} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, centered.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshStandardMaterial roughness={0.4} metalness={0.1} />
      </instancedMesh>
    </group>
  )
}

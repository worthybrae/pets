import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

function buildHorse(): { x: number; y: number; z: number; r: number; g: number; b: number }[] {
  const v: { x: number; y: number; z: number; r: number; g: number; b: number }[] = []
  const body = [180, 120, 60]
  const dark = [140, 90, 45]
  const belly = [210, 170, 120]
  const mane = [80, 50, 30]
  const eye = [255, 255, 255]
  const hoof = [90, 90, 90]

  const add = (x: number, y: number, z: number, c: number[]) =>
    v.push({ x, y, z, r: c[0], g: c[1], b: c[2] })

  for (let y = 0; y < 3; y++) { add(-2, y, 0, y === 0 ? hoof : dark); add(-2, y, 1, y === 0 ? hoof : dark) }
  for (let y = 0; y < 3; y++) { add(2, y, 0, y === 0 ? hoof : dark); add(2, y, 1, y === 0 ? hoof : dark) }
  for (let y = 0; y < 3; y++) { add(-2, y, 4, y === 0 ? hoof : dark); add(-2, y, 5, y === 0 ? hoof : dark) }
  for (let y = 0; y < 3; y++) { add(2, y, 4, y === 0 ? hoof : dark); add(2, y, 5, y === 0 ? hoof : dark) }

  for (let x = -2; x <= 2; x++) {
    for (let z = 0; z <= 5; z++) {
      add(x, 3, z, x >= -1 && x <= 1 ? belly : body)
      add(x, 4, z, body)
      if (x >= -1 && x <= 1) add(x, 5, z, body)
    }
  }

  for (let y = 5; y <= 8; y++) {
    add(-1, y, -1, body); add(0, y, -1, body); add(1, y, -1, body)
    add(-1, y, 0, body); add(0, y, 0, body); add(1, y, 0, body)
  }

  for (let x = -1; x <= 1; x++) {
    add(x, 9, -2, body); add(x, 9, -1, body); add(x, 9, 0, body)
    add(x, 8, -2, body); add(x, 8, -1, body)
    add(x, 10, -2, body); add(x, 10, -1, body)
  }
  add(0, 8, -3, belly); add(0, 9, -3, belly)
  add(-1, 8, -3, belly); add(1, 8, -3, belly)
  add(-1, 10, -2, eye); add(1, 10, -2, eye)
  add(-1, 11, -1, dark); add(1, 11, -1, dark)
  for (let y = 6; y <= 10; y++) add(0, y, 1, mane)
  for (let z = 6; z <= 8; z++) { add(0, 5, z, mane); if (z > 6) add(0, 4, z, mane) }

  return v
}

function VoxelModel({ voxels }: { voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[] }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const readyRef = useRef(false)

  const centered = useMemo(() => {
    const cx = voxels.reduce((s, v) => s + v.x, 0) / voxels.length
    const cy = voxels.reduce((s, v) => s + v.y, 0) / voxels.length
    const cz = voxels.reduce((s, v) => s + v.z, 0) / voxels.length
    return voxels.map(v => ({ ...v, x: v.x - cx, y: v.y - cy, z: v.z - cz }))
  }, [voxels])

  const scale = useMemo(() => {
    let maxDim = 0
    for (const v of centered) maxDim = Math.max(maxDim, Math.abs(v.x), Math.abs(v.y), Math.abs(v.z))
    return maxDim > 0 ? 2.5 / maxDim : 1
  }, [centered])

  useFrame((_, delta) => {
    if (!meshRef.current || !groupRef.current) return
    const mesh = meshRef.current

    if (!readyRef.current) {
      readyRef.current = true
      const obj = new THREE.Object3D()
      const col = new THREE.Color()
      for (let i = 0; i < centered.length; i++) {
        const v = centered[i]
        obj.position.set(v.x, v.y, v.z)
        obj.scale.setScalar(1)
        obj.updateMatrix()
        mesh.setMatrixAt(i, obj.matrix)

        // Try explicit color setting
        col.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, col)

        // Debug first voxel
        if (i === 0) {
          console.log('[VoxelTest] input rgb:', v.r, v.g, v.b)
          console.log('[VoxelTest] after setRGB:', col.r, col.g, col.b)
          console.log('[VoxelTest] color hex:', col.getHexString())
        }
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
      console.log('[VoxelTest] instanceColor exists:', !!mesh.instanceColor)
    }

    groupRef.current.rotation.y += delta * 0.5
  })

  return (
    <group ref={groupRef} scale={scale}>
      <instancedMesh ref={meshRef} args={[undefined, undefined, centered.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshStandardMaterial roughness={0.4} metalness={0.1} />
      </instancedMesh>
    </group>
  )
}

// Control: plain colored cube (no instancing) to verify Canvas renders color
function ControlCube() {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((_, dt) => { if (ref.current) ref.current.rotation.y += dt })
  return (
    <mesh ref={ref} position={[-4, 0, 0]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial color="#b47a3c" />
    </mesh>
  )
}

export default function VoxelTest() {
  const horse = useMemo(() => buildHorse(), [])

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#e5e5e5' }}>
      <div style={{ position: 'absolute', top: 20, left: 20, zIndex: 10, fontFamily: 'monospace', fontSize: 14 }}>
        <h2>Voxel Test — {horse.length} voxels</h2>
        <p>Brown control cube on left, instanced horse on right</p>
        <p>Sample: {horse.slice(0, 3).map(v => `rgb(${v.r},${v.g},${v.b})`).join(', ')}</p>
        <p style={{ color: '#999' }}>Check console for color debug info</p>
      </div>
      <Canvas camera={{ position: [0, 2, 12], fov: 35 }} gl={{ antialias: true, toneMapping: THREE.NoToneMapping }}>
        <color attach="background" args={['#e5e5e5']} />
        <ambientLight intensity={Math.PI} />
        <directionalLight position={[5, 8, 5]} intensity={Math.PI} />
        <ControlCube />
        <VoxelModel voxels={horse} />
      </Canvas>
    </div>
  )
}

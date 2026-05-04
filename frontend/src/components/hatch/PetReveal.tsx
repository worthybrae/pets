import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

export default function PetReveal({ voxels, progress }: {
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  progress: number
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
        col.setRGB(
          (v.r / 255) * cb + glow,
          (v.g / 255) * cb + glow,
          (v.b / 255) * cb + glow
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

  return (
    <group ref={groupRef} position={[0, 3, 0]}>
      <pointLight color="#ffffff" intensity={8} distance={25} decay={2} />
      <pointLight color="#999999" intensity={4} distance={20} decay={2} position={[0, -3, 0]} />
      <pointLight color="#ffffff" intensity={3} distance={15} decay={2} position={[0, 5, 5]} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, centered.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshBasicMaterial vertexColors toneMapped={false} fog={false} />
      </instancedMesh>
    </group>
  )
}

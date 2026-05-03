import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'

export default function World() {
  return (
    <div className="h-screen w-screen">
      <Canvas camera={{ position: [10, 10, 10], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <Grid
          infiniteGrid
          cellSize={1}
          sectionSize={4}
          fadeDistance={50}
        />
        <OrbitControls />
        {/* Placeholder voxel */}
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[1, 1, 1]} />
          <meshStandardMaterial color="#8b5cf6" />
        </mesh>
      </Canvas>
    </div>
  )
}

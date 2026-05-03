import { Canvas } from '@react-three/fiber'
import type { Chunk, PetEntity as PetEntityType } from '../../types/world'
import WorldManager from './WorldManager'
import PetEntity from './PetEntity'
import CameraController from './CameraController'

interface WorldSceneProps {
  chunks: Chunk[]
  pet: PetEntityType
  onVoxelClick?: (metadataId: string) => void
}

export default function WorldScene({ chunks, pet, onVoxelClick }: WorldSceneProps) {
  return (
    <div className="h-screen w-screen bg-black">
      <Canvas
        camera={{ position: [10, 8, 10], fov: 50, near: 0.1, far: 500 }}
        gl={{ antialias: true }}
        scene={{ background: undefined }}
      >
        {/* Black void background */}
        <color attach="background" args={['#000000']} />

        {/* Lighting */}
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[20, 30, 10]}
          intensity={0.8}
          castShadow={false}
        />
        <directionalLight
          position={[-10, 10, -10]}
          intensity={0.3}
        />

        {/* Fog to fade distant chunks */}
        <fog attach="fog" args={['#000000', 40, 80]} />

        {/* World chunks */}
        <WorldManager
          chunks={chunks}
          onVoxelClick={onVoxelClick}
        />

        {/* Pet */}
        <PetEntity pet={pet} />

        {/* Camera */}
        <CameraController petPosition={pet.position} />
      </Canvas>
    </div>
  )
}

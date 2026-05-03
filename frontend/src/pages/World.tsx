import WorldScene from '../components/world/WorldScene'
import { demoChunks, demoPet } from '../components/world/demoData'

export default function World() {
  const handleVoxelClick = (metadataId: string) => {
    console.log('Artifact clicked:', metadataId)
  }

  return (
    <WorldScene
      chunks={demoChunks}
      pet={demoPet}
      onVoxelClick={handleVoxelClick}
    />
  )
}

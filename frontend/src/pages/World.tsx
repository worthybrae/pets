import { useState, useCallback, useMemo, useEffect } from 'react'
import WorldScene from '../components/world/WorldScene'
import AppLayout from '../components/layout/AppLayout'
import { useChat } from '../hooks/useChat'
import type { VoxelUpdate, Position } from '../hooks/useWebSocket'
import type { Chunk, PetEntity as PetEntityType, Voxel } from '../types/world'
import type { AgendaTask } from '../components/ui/SchedulePanel'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Pet {
  id: string
  name: string
  seed_curiosity: string
  food_balance: number
  rarity?: string
  stats?: Record<string, number>
  backstory?: string
  initial_curiosity?: string
  voxels?: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  world_voxels?: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}

interface ScheduleInfo {
  nextTaskTime: number | null
  nextTaskName: string | null
  status: string
  tasks: AgendaTask[]
}

function getPetVoxels(pet: Pet): Voxel[] {
  if (pet.voxels && pet.voxels.length > 0) {
    return pet.voxels.map((v) => ({
      x: v.x,
      y: v.y,
      z: v.z,
      r: v.r,
      g: v.g,
      b: v.b,
      a: 255,
    }))
  }
  return [{ x: 0, y: 0, z: 0, r: 255, g: 255, b: 255, a: 255 }]
}

function getInitialChunks(pet: Pet): Chunk[] {
  if (pet.world_voxels && pet.world_voxels.length > 0) {
    const voxels: Voxel[] = pet.world_voxels.map((v) => ({
      x: v.x,
      y: v.y,
      z: v.z,
      r: v.r,
      g: v.g,
      b: v.b,
      a: 255,
    }))
    return [{ chunk_x: 0, chunk_y: 0, chunk_z: 0, voxels }]
  }
  return []
}

export default function World({
  pet,
  onFoodUpdate,
  onScheduleUpdate,
}: {
  pet: Pet
  onFoodUpdate?: (balance: number) => void
  onScheduleUpdate?: (info: ScheduleInfo) => void
}) {
  const petVoxels = useMemo(() => getPetVoxels(pet), [pet])
  const initialChunks = useMemo(() => getInitialChunks(pet), [pet])

  const [currentTime, setCurrentTime] = useState<Date>(new Date())
  const [chunks, setChunks] = useState<Chunk[]>(initialChunks)
  const [petEntity, setPetEntity] = useState<PetEntityType>({
    position: { x: 0, y: 0, z: 0 },
    voxels: petVoxels,
  })
  const [, setFoodBalance] = useState(pet.food_balance)
  const [scheduleTasks, setScheduleTasks] = useState<AgendaTask[]>([])
  const [nextTaskTime, setNextTaskTime] = useState<number | null>(null)

  // Fetch schedule + agenda data
  useEffect(() => {
    let cancelled = false

    const fetchSchedule = async () => {
      try {
        const [schedRes, agendaRes] = await Promise.all([
          fetch(`${API_URL}/api/pets/${pet.id}/schedule`),
          fetch(`${API_URL}/api/pets/${pet.id}/agenda`),
        ])

        if (cancelled) return

        const schedData = await schedRes.json()
        const agendaData = await agendaRes.json()

        const tasks: AgendaTask[] = agendaData?.plan?.tasks || []
        const ntt = schedData?.next_tick || null
        const status = schedData?.status || 'unknown'
        const nextTask = schedData?.next_task || null

        setScheduleTasks(tasks)
        setNextTaskTime(ntt)

        onScheduleUpdate?.({
          nextTaskTime: ntt,
          nextTaskName: nextTask,
          status,
          tasks,
        })
      } catch {
        // Silently fail — schedule display is non-critical
      }
    }

    fetchSchedule()
    const interval = setInterval(fetchSchedule, 30000) // Refresh every 30s
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [pet.id, onScheduleUpdate])

  const handleVoxelUpdate = useCallback((update: VoxelUpdate) => {
    setChunks((prevChunks) => {
      const newChunks = [...prevChunks]
      if (update.action === 'place') {
        const newVoxels: Voxel[] = update.voxels.map((v) => ({
          x: v.x, y: v.y, z: v.z,
          r: v.r ?? 255, g: v.g ?? 255, b: v.b ?? 255, a: v.a ?? 255,
        }))
        if (newChunks.length > 0) {
          newChunks[0] = { ...newChunks[0], voxels: [...newChunks[0].voxels, ...newVoxels] }
        } else {
          newChunks.push({ chunk_x: 0, chunk_y: 0, chunk_z: 0, voxels: newVoxels })
        }
      } else if (update.action === 'remove') {
        const removeSet = new Set(update.voxels.map((v) => `${v.x},${v.y},${v.z}`))
        for (let i = 0; i < newChunks.length; i++) {
          newChunks[i] = {
            ...newChunks[i],
            voxels: newChunks[i].voxels.filter((v) => !removeSet.has(`${v.x},${v.y},${v.z}`)),
          }
        }
      }
      return newChunks
    })
  }, [])

  const handlePetMoved = useCallback((position: Position) => {
    setPetEntity((prev) => ({ ...prev, position }))
  }, [])

  const handleFoodUpdate = useCallback((balance: number) => {
    setFoodBalance(balance)
    onFoodUpdate?.(balance)
  }, [onFoodUpdate])

  const { messages, sendMessage, isConnected } = useChat({
    petId: pet.id,
    petName: pet.name,
    onVoxelUpdate: handleVoxelUpdate,
    onPetMoved: handlePetMoved,
    onFoodUpdate: handleFoodUpdate,
  })

  const handleVoxelClick = (metadataId: string) => {
    console.log('Artifact clicked:', metadataId)
  }

  return (
    <AppLayout
      petName={pet.name}
      messages={messages}
      onSendMessage={sendMessage}
      onTimeChange={setCurrentTime}
      currentTime={currentTime}
      scheduleTasks={scheduleTasks}
      nextTaskTime={nextTaskTime}
    >
      <WorldScene chunks={chunks} pet={petEntity} onVoxelClick={handleVoxelClick} onPetPositionChange={handlePetMoved} />
      <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`} />
        <span className="text-xs text-white/40">
          {isConnected ? 'Live' : 'Offline'}
        </span>
      </div>
    </AppLayout>
  )
}

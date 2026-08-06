import { useState, useCallback, useMemo, useEffect } from 'react'
import WorldScene from '../components/world/WorldScene'
import AppLayout from '../components/layout/AppLayout'
import { useChat } from '../hooks/useChat'
import { generateBaseWorld, type BaseWorldData } from '../components/world/baseWorld'
import { buildCollider, type WorldCollider } from '../components/world/physics'
import type { VoxelUpdate, Position, PetThought, PetBodyVoxel } from '../hooks/useWebSocket'
import type { Chunk, PetEntity as PetEntityType, Voxel } from '../types/world'
import { CHUNK_SIZE } from '../types/world'
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

  // Generate base world template (used to seed DB on first load)
  const baseWorld = useMemo<BaseWorldData>(() => generateBaseWorld(), [])

  const [currentTime, setCurrentTime] = useState<Date>(new Date())
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [worldLoaded, setWorldLoaded] = useState(false)

  // Physics collider — rebuilds when world changes (place/remove voxels)
  const collider = useMemo<WorldCollider>(() => buildCollider(chunks), [chunks])
  const [petEntity, setPetEntity] = useState<PetEntityType>({
    position: { x: 8, y: 2, z: 8 },
    voxels: petVoxels,
  })
  const [, setFoodBalance] = useState(pet.food_balance)
  const [scheduleTasks, setScheduleTasks] = useState<AgendaTask[]>([])
  const [nextTaskTime, setNextTaskTime] = useState<number | null>(null)
  const [petThought, setPetThought] = useState<string | null>(null)

  // Load world + body from API (or seed world if empty)
  useEffect(() => {
    let cancelled = false

    const loadWorld = async () => {
      try {
        // Fetch persisted world chunks and body voxels in parallel
        const [worldRes, bodyRes] = await Promise.all([
          fetch(`${API_URL}/api/pets/${pet.id}/world`),
          fetch(`${API_URL}/api/pets/${pet.id}/body`),
        ])
        const worldData = await worldRes.json()
        const bodyData = await bodyRes.json()

        if (cancelled) return

        // If the pet has a persisted body, use it instead of creation voxels
        if (bodyData?.voxels && bodyData.voxels.length > 0) {
          const bodyVoxels: Voxel[] = bodyData.voxels.map((v: PetBodyVoxel) => ({
            x: v.x, y: v.y, z: v.z,
            r: v.r, g: v.g, b: v.b, a: v.a ?? 255,
          }))
          setPetEntity((prev) => ({ ...prev, voxels: bodyVoxels }))
        }

        // Restore persisted position (from last AI move_self call)
        if (bodyData?.position) {
          setPetEntity((prev) => ({ ...prev, position: bodyData.position }))
        }

        // Real-time overlay: chunk at offset (0,0,0) for WebSocket voxel updates.
        // AI voxels arrive with world coords; offset 0 means they render correctly.
        const overlay: Chunk = { chunk_x: 0, chunk_y: 0, chunk_z: 0, voxels: [] }

        // The base world has 25+ chunks (5x5 grid of terrain).
        // If DB has fewer, the base world hasn't been seeded yet.
        const baseWorldSeeded = worldData && worldData.length >= 20

        if (baseWorldSeeded) {
          // Full world in DB — use it directly
          setChunks([overlay, ...worldData])
        } else {
          // Base world not seeded yet — generate, seed, and show locally.
          // Any existing DB data (creation voxels, birth burst) is merged in.
          const seedChunks = baseWorld.chunks.map((c) => ({
            chunk_x: c.chunk_x,
            chunk_y: c.chunk_y,
            chunk_z: c.chunk_z,
            voxels: c.voxels,
          }))
          fetch(`${API_URL}/api/pets/${pet.id}/world/seed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chunks: seedChunks }),
          }).catch(() => {})  // Fire-and-forget seed

          // Show base world + any existing DB voxels (creation landmark, etc.)
          setChunks([overlay, ...baseWorld.chunks, ...(worldData || [])])
        }
      } catch {
        // Fallback: use local base world if API fails
        const overlay: Chunk = { chunk_x: 0, chunk_y: 0, chunk_z: 0, voxels: [] }
        setChunks([overlay, ...baseWorld.chunks])
      } finally {
        if (!cancelled) setWorldLoaded(true)
      }
    }

    loadWorld()
    return () => { cancelled = true }
  }, [pet.id, baseWorld])

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
        // Convert world coords to each chunk's local coords for matching
        for (let i = 0; i < newChunks.length; i++) {
          const c = newChunks[i]
          const localSet = new Set(
            update.voxels.map((v) =>
              `${v.x - c.chunk_x * CHUNK_SIZE},${v.y - c.chunk_y * CHUNK_SIZE},${v.z - c.chunk_z * CHUNK_SIZE}`
            )
          )
          newChunks[i] = {
            ...c,
            voxels: c.voxels.filter((v) => !localSet.has(`${v.x},${v.y},${v.z}`)),
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

  const handlePetThought = useCallback((t: PetThought) => {
    setPetThought(t.thought)
  }, [])

  const handlePetBodyUpdated = useCallback((voxels: PetBodyVoxel[]) => {
    const mapped: Voxel[] = voxels.map((v) => ({
      x: v.x, y: v.y, z: v.z,
      r: v.r, g: v.g, b: v.b, a: v.a ?? 255,
    }))
    setPetEntity((prev) => ({ ...prev, voxels: mapped }))
  }, [])

  const { messages, sendMessage, isConnected } = useChat({
    petId: pet.id,
    petName: pet.name,
    onVoxelUpdate: handleVoxelUpdate,
    onPetMoved: handlePetMoved,
    onFoodUpdate: handleFoodUpdate,
    onPetThought: handlePetThought,
    onPetBodyUpdated: handlePetBodyUpdated,
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
      <WorldScene chunks={chunks} pet={petEntity} petThought={petThought} collider={collider} onVoxelClick={handleVoxelClick} onPetPositionChange={handlePetMoved} />
      <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`} />
        <span className="text-xs text-white/40">
          {isConnected ? 'Live' : 'Offline'}
        </span>
      </div>
    </AppLayout>
  )
}

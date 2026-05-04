import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { supabase } from './lib/supabase'
import HeaderBar from './components/ui/HeaderBar'
import World from './pages/World'
import Hatch from './pages/Hatch'
import Guide from './pages/Guide'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Pet {
  id: string
  name: string
  seed_curiosity: string
  food_balance: number
  rarity: string
  stats: Record<string, number>
  backstory: string
  initial_curiosity: string
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  soul: string
  world_voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}

function App() {
  const [session, setSession] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [pet, setPet] = useState<Pet | null>(null)
  const [petLoading, setPetLoading] = useState(false)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => subscription.unsubscribe()
  }, [])

  // Check if user has a pet
  useEffect(() => {
    if (!session) {
      setPet(null)
      return
    }

    setPetLoading(true)
    fetch(`${API_URL}/api/pets/by-owner/${session.user.id}`)
      .then((r) => r.json())
      .then((data) => {
        if (data && data.id) {
          setPet(data)
        } else {
          setPetLoading(false)
        }
      })
      .catch(() => {})
      .finally(() => setPetLoading(false))
  }, [session])

  const handleHatch = useCallback(
    async (stats: Record<string, number>, rarity: string) => {
      if (!session) return
      try {
        const res = await fetch(`${API_URL}/api/pets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            owner_id: session.user.id,
            stats,
            rarity,
          }),
        })
        const data = await res.json()
        return data
      } catch (e) {
        console.error('Failed to create pet:', e)
        return null
      }
    },
    [session]
  )

  const handleHatchComplete = useCallback((petData: Pet) => {
    setPet(petData)
  }, [])

  const handleFoodUpdate = useCallback((balance: number) => {
    setPet((prev) => prev ? { ...prev, food_balance: balance } : prev)
  }, [])

  if (loading || petLoading) {
    return <div className="min-h-screen bg-[#0a0a0f]" />
  }

  return (
    <BrowserRouter>
      <HeaderBar
        isLoggedIn={!!session}
        hasPet={!!pet}
        foodBalance={pet?.food_balance}
        maxFood={100}
      />
      <Routes>
        <Route
          path="/"
          element={<Navigate to={pet ? '/world' : '/hatch'} />}
        />
        <Route
          path="/hatch"
          element={
            pet ? <Navigate to="/world" /> : <Hatch onHatch={handleHatch} onComplete={handleHatchComplete} session={session} />
          }
        />
        <Route path="/guide" element={<Guide />} />
        <Route
          path="/world"
          element={
            session
              ? (pet ? <World pet={pet} onFoodUpdate={handleFoodUpdate} /> : <Navigate to="/hatch" />)
              : <Navigate to="/hatch" />
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App

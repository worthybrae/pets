import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect, useState, useCallback } from 'react'
import { supabase } from './lib/supabase'
import Landing from './pages/Landing'
import World from './pages/World'
import Hatch from './pages/Hatch'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Pet {
  id: string
  name: string
  seed_curiosity: string
  food_balance: number
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
        }
      })
      .catch(() => {})
      .finally(() => setPetLoading(false))
  }, [session])

  const handleHatch = useCallback(
    async (name: string) => {
      if (!session) return
      try {
        const res = await fetch(`${API_URL}/api/pets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ owner_id: session.user.id, name }),
        })
        const data = await res.json()
        setPet(data)
      } catch (e) {
        console.error('Failed to create pet:', e)
      }
    },
    [session]
  )

  if (loading || petLoading) {
    return <div className="min-h-screen bg-black" />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            session
              ? <Navigate to={pet ? '/world' : '/hatch'} />
              : <Landing />
          }
        />
        <Route
          path="/hatch"
          element={
            session
              ? (pet ? <Navigate to="/world" /> : <Hatch onHatch={handleHatch} />)
              : <Navigate to="/" />
          }
        />
        <Route
          path="/world"
          element={
            session
              ? (pet ? <World pet={pet} /> : <Navigate to="/hatch" />)
              : <Navigate to="/" />
          }
        />
      </Routes>
    </BrowserRouter>
  )
}

export default App

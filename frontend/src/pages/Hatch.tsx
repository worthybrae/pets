import { useState, useEffect, useRef, useCallback } from 'react'
import { supabase } from '../lib/supabase'
import EggScene from '../components/hatch/EggScene'
import EggTooltip from '../components/hatch/EggTooltip'
import { StatBar, TotalReveal, RarityBadge, QualityBadge } from '../components/hatch/StatsCard'
import { rollEgg, rollStatsFromEgg, computeQuality, GEN_STATUS, readPendingEgg, STAT_NAMES } from '../components/hatch/gameLogic'
import type { Phase, PetData, HatchProps, EggProfile, QualityTier } from '../components/hatch/types'

export default function Hatch({ onHatch, onComplete, session }: HatchProps) {
  // ── Egg state ──
  const [egg, setEgg] = useState<EggProfile>(() => rollEgg())
  const [phase, setPhase] = useState<Phase>('idle')
  const [hovering, setHovering] = useState(false)
  const [eggReady, setEggReady] = useState(false) // true after intro animation

  // ── Stats state ──
  const [rolledStats, setRolledStats] = useState<Record<string, number> | null>(null)
  const [quality, setQuality] = useState<QualityTier>('neutral')
  const [statsRevealed, setStatsRevealed] = useState(false)

  // ── Reveal state ──
  const [revealProgress, setRevealProgress] = useState(0)
  const [petData, setPetData] = useState<PetData | null>(null)
  const [fullPetResponse, setFullPetResponse] = useState<any>(null)
  const [backstoryText, setBackstoryText] = useState('')
  const [showBeginButton, setShowBeginButton] = useState(false)
  const [flashActive, setFlashActive] = useState(false)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })

  // ── Generating state ──
  const [genElapsed, setGenElapsed] = useState(0)
  const genStartRef = useRef(0)
  const genFrameRef = useRef(0)
  const revealFrameRef = useRef(0)

  // ── Phase: Idle → Hatching ──
  const startHatching = useCallback(() => {
    const stats = rollStatsFromEgg(egg)
    const q = computeQuality(stats, egg)
    setRolledStats(stats)
    setQuality(q)
    setPhase('hatching')

    // After growth animation, show stats
    setTimeout(() => {
      setPhase('stats')
      setStatsRevealed(true)
    }, 2000)
  }, [egg])

  // ── Phase: Stats → Generating (after sign-in) ──
  const startGenerating = useCallback(async () => {
    if (!rolledStats) return
    setPhase('generating')
    genStartRef.current = Date.now()

    const colorAttr = egg.attributes.find(a => a.category === 'color')
    const response = await onHatch(rolledStats, egg.rarity, colorAttr?.option.name)
    if (response) {
      setFullPetResponse(response)
      setPetData({
        id: response.id, name: response.name, rarity: response.rarity,
        stats: response.stats, backstory: response.backstory, voxels: response.voxels || [],
      })
    } else {
      setPetData({
        id: 'fallback', name: 'Unknown', rarity: egg.rarity,
        stats: rolledStats,
        backstory: 'A creature emerged from the void with wonder in its eyes.',
        voxels: [{ x: 0, y: 0, z: 0, r: 255, g: 255, b: 255 }],
      })
    }

    // Trigger reveal
    setFlashActive(true)
    setTimeout(() => setFlashActive(false), 800)
    setTimeout(() => {
      setPhase('reveal')
      const start = Date.now()
      const animate = () => {
        const p = Math.min((Date.now() - start) / 4000, 1)
        setRevealProgress(p)
        if (p < 1) {
          revealFrameRef.current = requestAnimationFrame(animate)
        } else {
          setTimeout(() => setStatsRevealed(true), 600)
        }
      }
      revealFrameRef.current = requestAnimationFrame(animate)
    }, 500)
  }, [rolledStats, egg, onHatch])

  // ── Auto-generate if signed in during stats phase ──
  useEffect(() => {
    if (phase !== 'stats' || !session || !rolledStats) return
    const timer = setTimeout(() => startGenerating(), 1500)
    return () => clearTimeout(timer)
  }, [phase, session, rolledStats, startGenerating])

  // ── Sign-in with pending egg ──
  const signInWithGoogle = async () => {
    if (rolledStats) {
      localStorage.setItem('pendingEgg', JSON.stringify({ egg, stats: rolledStats, quality }))
    }
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/hatch' },
    })
  }

  // ── OAuth return with pending egg ──
  useEffect(() => {
    if (!session) return
    const pending = readPendingEgg()
    if (pending) {
      localStorage.removeItem('pendingEgg')
      setEgg(pending.egg)
      setRolledStats(pending.stats)
      setQuality(pending.quality as QualityTier)
      setPhase('stats')
      setStatsRevealed(true)
      setTimeout(() => startGenerating(), 500)
    }
  }, [session, startGenerating])

  // ── Generating elapsed timer ──
  useEffect(() => {
    if (phase !== 'generating') return
    genStartRef.current = Date.now()
    const tick = () => {
      setGenElapsed((Date.now() - genStartRef.current) / 1000)
      genFrameRef.current = requestAnimationFrame(tick)
    }
    genFrameRef.current = requestAnimationFrame(tick)
    return () => { if (genFrameRef.current) cancelAnimationFrame(genFrameRef.current) }
  }, [phase])

  // ── Backstory typewriter ──
  useEffect(() => {
    if (phase !== 'reveal' || !petData) return
    const delay = STAT_NAMES.length * 200 + 2000
    const startTimer = setTimeout(() => {
      let i = 0
      const iv = setInterval(() => {
        i++
        setBackstoryText(petData.backstory.slice(0, i))
        if (i >= petData.backstory.length) { clearInterval(iv); setTimeout(() => setShowBeginButton(true), 500) }
      }, 25)
      return () => clearInterval(iv)
    }, delay)
    return () => clearTimeout(startTimer)
  }, [phase, petData])

  // ── Cleanup ──
  useEffect(() => {
    return () => {
      if (genFrameRef.current) cancelAnimationFrame(genFrameRef.current)
      if (revealFrameRef.current) cancelAnimationFrame(revealFrameRef.current)
    }
  }, [])

  const genStatusText = GEN_STATUS.reduce((msg, s) => genElapsed >= s.t ? s.text : msg, GEN_STATUS[0].text)
  const statEntries = rolledStats ? Object.entries(rolledStats) : []
  const total = rolledStats ? Object.values(rolledStats).reduce((a, b) => a + b, 0) : 0

  return (
    <div
      className="min-h-screen bg-[#e5e5e5] relative overflow-hidden grid grid-cols-1 lg:grid-cols-2"
    >
      {/* ── Right: Text / Controls ── */}
      <div className="relative z-10 flex flex-col justify-center px-8 sm:px-12 lg:px-16 py-12 min-h-[50vh] lg:min-h-screen order-1 lg:order-2">
        {/* Egg info */}
        {phase !== 'reveal' && (
          <div className="mb-8" style={{ animation: 'fadeUp 0.6s ease-out' }}>
            <h2 className="text-2xl sm:text-3xl font-semibold text-neutral-900 tracking-tight">{egg.name}</h2>
            <div className="mt-3 flex items-center gap-3">
              <RarityBadge rarity={egg.rarity} visible={true} />
              <span className="text-neutral-500 text-xs font-medium">{egg.totalPoints.toFixed(1)} / 10</span>
            </div>
          </div>
        )}

        {/* Idle: Hatch button */}
        {phase === 'idle' && (
          <div style={{ animation: 'fadeUp 0.6s ease-out 0.3s both' }}>
            <button
              onClick={startHatching}
              className="group px-12 py-4 bg-neutral-900 text-white text-sm font-medium tracking-[0.15em] uppercase
                rounded-xl hover:bg-neutral-800 transition-all active:scale-[0.97]
                shadow-[0_4px_24px_rgba(0,0,0,0.15)] hover:shadow-[0_8px_32px_rgba(0,0,0,0.25)]"
            >
              <span className="inline-flex items-center gap-2">
                Hatch
                <svg className="w-4 h-4 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </span>
            </button>
          </div>
        )}

        {/* Stats phase: stats card */}
        {(phase === 'stats' || phase === 'generating') && rolledStats && (
          <div
            className="w-full max-w-md"
            style={{ animation: 'fadeUp 0.6s ease-out' }}
          >
            <div
              className="rounded-[24px] p-6 space-y-3"
              style={{
                background: 'rgba(255, 255, 255, 0.85)',
                backdropFilter: 'blur(40px)',
                WebkitBackdropFilter: 'blur(40px)',
                border: '1px solid rgba(0, 0, 0, 0.08)',
                boxShadow: '0 16px 48px rgba(0, 0, 0, 0.1)',
              }}
            >
              <div className="space-y-2">
                {statEntries.map(([name, value], i) => (
                  <StatBar key={name} name={name} value={value} delay={i * 200} revealed={statsRevealed} />
                ))}
              </div>

              <TotalReveal total={total} visible={statsRevealed} />
              <QualityBadge quality={quality} visible={statsRevealed} />

              {/* Sign-in button (if not signed in) */}
              {phase === 'stats' && !session && (
                <div className="pt-3 space-y-3" style={{ animation: 'fadeUp 0.5s ease-out 1.5s both' }}>
                  <p className="text-center text-neutral-400 text-xs tracking-wide">
                    sign in to hatch your egg
                  </p>
                  <button
                    onClick={signInWithGoogle}
                    className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white text-black text-sm font-medium tracking-wide rounded-xl hover:bg-gray-100 transition-colors"
                  >
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                    </svg>
                    Continue with Google
                  </button>
                </div>
              )}

              {/* Generating status */}
              {phase === 'generating' && (
                <div className="text-center pt-2">
                  <p className="text-neutral-400 text-xs tracking-[0.2em] uppercase animate-pulse">{genStatusText}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Reveal: creature card */}
        {phase === 'reveal' && petData && (
          <div
            className="w-full max-w-lg"
            style={{ animation: 'fadeUp 0.8s ease-out 2s both' }}
          >
            <div
              className="rounded-[24px] p-6 space-y-4"
              style={{
                background: 'rgba(255, 255, 255, 0.85)',
                backdropFilter: 'blur(40px)',
                WebkitBackdropFilter: 'blur(40px)',
                border: '1px solid rgba(0, 0, 0, 0.08)',
                boxShadow: '0 16px 48px rgba(0, 0, 0, 0.1)',
              }}
            >
              <div className="space-y-2">
                <h2 className="text-2xl font-light text-neutral-800 tracking-wide">{petData.name}</h2>
                <RarityBadge rarity={petData.rarity} visible={true} />
              </div>

              <div className="space-y-2 pt-2 border-t border-neutral-200">
                {Object.entries(petData.stats).map(([s, v], i) => (
                  <StatBar key={s} name={s} value={v} delay={i * 200 + 500} revealed={statsRevealed} />
                ))}
              </div>

              <TotalReveal
                total={Object.values(petData.stats).reduce((a, b) => a + b, 0)}
                visible={statsRevealed}
              />

              {backstoryText && (
                <div className="pt-2 border-t border-neutral-200">
                  <p className="text-neutral-500 text-sm leading-relaxed font-light">
                    {backstoryText}
                    {backstoryText.length < petData.backstory.length && (
                      <span className="text-neutral-300 animate-pulse">|</span>
                    )}
                  </p>
                </div>
              )}

              {showBeginButton && (
                <button
                  onClick={() => fullPetResponse ? onComplete(fullPetResponse) : onComplete(petData)}
                  className="w-full py-3 bg-neutral-900 text-white font-medium rounded-xl
                    hover:bg-neutral-800 transition-all text-sm tracking-wider uppercase active:scale-[0.98]"
                  style={{ animation: 'fadeUp 0.5s ease-out' }}
                >
                  Begin Journey
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Left: 3D Egg Scene ── */}
      <div
        className="relative min-h-[50vh] lg:min-h-screen order-2 lg:order-1"
        onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
      >
        <div className="absolute inset-0">
          <EggScene
            phase={phase}
            egg={egg}
            revealProgress={revealProgress}
            voxels={petData?.voxels || []}
            onIntroComplete={() => setEggReady(true)}
            onHover={setHovering}
          />
        </div>

        {/* Flash */}
        {flashActive && (
          <div className="absolute inset-0 z-50 bg-white/30" style={{ animation: 'flashOut 0.8s ease-out forwards' }} />
        )}
      </div>

      {/* Tooltip follows cursor over egg */}
      <EggTooltip egg={egg} visible={hovering && (phase === 'idle' || phase === 'hatching')} mousePos={mousePos} />

      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes flashOut {
          0% { opacity: 1; }
          100% { opacity: 0; }
        }
        .stat-shimmer {
          animation: shimmerSweep 0.6s ease-out forwards;
        }
        @keyframes shimmerSweep {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        .mythic-badge {
          background: linear-gradient(90deg, #ec4899, #8b5cf6, #3b82f6, #22c55e, #eab308, #ec4899);
          background-size: 300% 100%;
          animation: rainbow 3s linear infinite;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          border: 1px solid rgba(236, 72, 153, 0.3);
        }
        @keyframes rainbow {
          from { background-position: 0% 50%; }
          to { background-position: 300% 50%; }
        }
      `}</style>
    </div>
  )
}

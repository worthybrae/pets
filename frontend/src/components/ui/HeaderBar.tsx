import { useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface HeaderBarProps {
  isLoggedIn: boolean
  hasPet: boolean
  foodBalance?: number
  maxFood?: number
  nextTaskTime?: number | null
  nextTaskName?: string | null
  petStatus?: string
  onFeed?: () => void
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return 'now'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export default function HeaderBar({
  isLoggedIn,
  hasPet,
  foodBalance = 0,
  maxFood = 1,
  nextTaskTime,
  nextTaskName,
  petStatus,
  onFeed,
}: HeaderBarProps) {
  const navigate = useNavigate()
  const percentage = maxFood > 0 ? Math.min(100, Math.round((foodBalance / maxFood) * 100)) : 0
  const [countdown, setCountdown] = useState<number | null>(null)

  useEffect(() => {
    if (!nextTaskTime) {
      setCountdown(null)
      return
    }

    const update = () => {
      const remaining = nextTaskTime - Date.now() / 1000
      setCountdown(remaining > 0 ? remaining : 0)
    }
    update()
    const interval = setInterval(update, 1000)
    return () => clearInterval(interval)
  }, [nextTaskTime])

  const isSleeping = petStatus === 'sleeping' && countdown !== null && countdown > 0
  const isOutOfFood = foodBalance < 0.0001
  const isLowFood = foodBalance < 0.1

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3">
      <button
        onClick={() => navigate('/')}
        className="text-neutral-800 font-medium text-lg tracking-[0.15em] hover:text-neutral-600 transition-colors"
      >
        cradl
      </button>
      <div className="flex items-center gap-4">
        {isLoggedIn && hasPet && (
          <>
            {/* Sleep timer */}
            <div className="flex items-center gap-1.5" title={nextTaskName ? `Next: ${nextTaskName}` : undefined}>
              {isOutOfFood ? (
                <>
                  <svg className="w-3.5 h-3.5 text-red-400" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M21.64 13a1 1 0 00-1.05-.14 8.05 8.05 0 01-3.37.73A8.15 8.15 0 019.08 5.49a8.59 8.59 0 01.25-2A1 1 0 008 2.36 10.14 10.14 0 1022 14.05a1 1 0 00-.36-1.05z" />
                  </svg>
                  <span className="text-red-400 text-xs font-mono">
                    starving
                  </span>
                </>
              ) : isSleeping ? (
                <>
                  <svg className="w-3.5 h-3.5 text-indigo-400" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M21.64 13a1 1 0 00-1.05-.14 8.05 8.05 0 01-3.37.73A8.15 8.15 0 019.08 5.49a8.59 8.59 0 01.25-2A1 1 0 008 2.36 10.14 10.14 0 1022 14.05a1 1 0 00-.36-1.05z" />
                  </svg>
                  <span className="text-indigo-300 text-xs font-mono tracking-wide">
                    {formatCountdown(countdown!)}
                  </span>
                </>
              ) : (
                <>
                  <svg className="w-3.5 h-3.5 text-amber-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <circle cx="12" cy="12" r="5" />
                    <line x1="12" y1="1" x2="12" y2="3" />
                    <line x1="12" y1="21" x2="12" y2="23" />
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                    <line x1="1" y1="12" x2="3" y2="12" />
                    <line x1="21" y1="12" x2="23" y2="12" />
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                  </svg>
                  <span className="text-amber-400/70 text-xs font-mono">
                    awake
                  </span>
                </>
              )}
            </div>

            <div className="w-px h-4 bg-neutral-300" />

            {/* Food balance + feed button */}
            <div className="flex items-center gap-2">
              <svg
                className={`w-4 h-4 ${isOutOfFood ? 'text-red-400' : 'text-neutral-500'}`}
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M18 8h1a4 4 0 010 8h-1M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8zM6 1v3M10 1v3M14 1v3" />
              </svg>
              <div className="w-20 h-2 bg-neutral-300 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    isOutOfFood ? 'bg-red-400' : isLowFood ? 'bg-amber-400' : 'bg-green-500'
                  }`}
                  style={{ width: `${Math.max(percentage, 1)}%` }}
                />
              </div>
              <span className={`text-xs font-mono tracking-wide ${isOutOfFood ? 'text-red-400' : 'text-neutral-500'}`}>
                ${foodBalance.toFixed(4)}
              </span>

              {/* Feed button — always visible, pulses when starving */}
              {onFeed && (
                <button
                  onClick={onFeed}
                  className={`ml-1 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all ${
                    isOutOfFood
                      ? 'bg-green-500 text-white animate-pulse hover:bg-green-600'
                      : isLowFood
                        ? 'bg-green-500/80 text-white hover:bg-green-600'
                        : 'bg-neutral-200 text-neutral-600 hover:bg-neutral-300'
                  }`}
                  title="Add $1.00 food"
                >
                  +$1
                </button>
              )}
            </div>
          </>
        )}
        <button
          onClick={() => navigate('/guide')}
          className="w-7 h-7 flex items-center justify-center text-neutral-400 hover:text-neutral-600 transition-colors"
          aria-label="How it works"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
        </button>
      </div>
    </header>
  )
}

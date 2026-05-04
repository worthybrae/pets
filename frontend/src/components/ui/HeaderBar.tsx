import { useNavigate } from 'react-router-dom'

interface HeaderBarProps {
  isLoggedIn: boolean
  hasPet: boolean
  foodBalance?: number
  maxFood?: number
}

export default function HeaderBar({ isLoggedIn, hasPet, foodBalance = 0, maxFood = 100 }: HeaderBarProps) {
  const navigate = useNavigate()
  const percentage = maxFood > 0 ? Math.round((foodBalance / maxFood) * 100) : 0

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3">
      <button
        onClick={() => navigate('/')}
        className="text-neutral-800 font-medium text-lg tracking-[0.15em] hover:text-neutral-600 transition-colors"
      >
        cradl
      </button>
      <div className="flex items-center gap-3">
        {isLoggedIn && hasPet && (
          <div className="flex items-center gap-2">
            <svg
              className="w-4 h-4 text-neutral-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M18 8h1a4 4 0 010 8h-1M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8zM6 1v3M10 1v3M14 1v3" />
            </svg>
            <div className="w-24 h-2 bg-neutral-300 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full transition-all duration-300"
                style={{ width: `${percentage}%` }}
              />
            </div>
            <span className="text-neutral-500 text-xs font-medium tracking-wide">
              {(foodBalance ?? 0).toFixed(0)}/{(maxFood ?? 100).toFixed(0)}
            </span>
          </div>
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

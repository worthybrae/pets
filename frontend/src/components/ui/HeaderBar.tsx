interface HeaderBarProps {
  petName: string
  foodBalance: number
  maxFood: number
}

export default function HeaderBar({ petName, foodBalance = 0, maxFood = 100 }: HeaderBarProps) {
  const percentage = maxFood > 0 ? Math.round((foodBalance / maxFood) * 100) : 0

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3 backdrop-blur-md bg-black/50 border-b border-white/10">
      <div className="text-white font-medium text-lg tracking-wide">
        {petName}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-white/70"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M18 8h1a4 4 0 010 8h-1M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8zM6 1v3M10 1v3M14 1v3" />
          </svg>
          <div className="w-24 h-2 bg-white/20 rounded-full overflow-hidden">
            <div
              className="h-full bg-green-400 rounded-full transition-all duration-300"
              style={{ width: `${percentage}%` }}
            />
          </div>
          <span className="text-white/70 text-sm font-mono">
            {(foodBalance ?? 0).toFixed(0)}/{(maxFood ?? 100).toFixed(0)}
          </span>
        </div>
      </div>
    </header>
  )
}

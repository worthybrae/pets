import { useState, useMemo } from 'react'

interface TimelinePanelProps {
  onTimeChange: (timestamp: Date) => void
  currentTime: Date
  isOpen: boolean
}

export default function TimelinePanel({ onTimeChange, currentTime, isOpen }: TimelinePanelProps) {
  const now = useMemo(() => new Date(), [])
  const sevenDaysAgo = useMemo(() => {
    const d = new Date(now)
    d.setDate(d.getDate() - 7)
    return d
  }, [now])

  const totalRange = now.getTime() - sevenDaysAgo.getTime()
  const currentOffset = now.getTime() - currentTime.getTime()
  const percentage = Math.min(100, Math.max(0, (currentOffset / totalRange) * 100))

  const [isDragging, setIsDragging] = useState(false)

  const dayLabels = useMemo(() => {
    const labels: { label: string; position: number }[] = []
    for (let i = 0; i <= 7; i++) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      const label = i === 0 ? 'Now' : i === 1 ? '1d ago' : `${i}d ago`
      labels.push({ label, position: (i / 7) * 100 })
    }
    return labels
  }, [now])

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value)
    const newTime = new Date(now.getTime() - (value / 100) * totalRange)
    onTimeChange(newTime)
  }

  const handleTrackClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const y = e.clientY - rect.top
    const value = (y / rect.height) * 100
    const newTime = new Date(now.getTime() - (value / 100) * totalRange)
    onTimeChange(newTime)
  }

  return (
    <div
      className={`fixed top-0 right-0 bottom-0 z-40 flex flex-col backdrop-blur-md bg-black/60 border-l border-white/10 transition-transform duration-300 ease-in-out w-full sm:w-[320px] ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      {/* Header */}
      <div className="flex items-center px-4 py-3 border-b border-white/10">
        <h2 className="text-white font-medium">Timeline</h2>
      </div>

      {/* Slider area */}
      <div className="flex-1 flex items-stretch px-8 py-6">
        <div className="relative flex-1 flex">
          {/* Track */}
          <div
            className="absolute left-1/2 top-0 bottom-0 w-1 -translate-x-1/2 bg-white/20 rounded-full cursor-pointer"
            onClick={handleTrackClick}
          >
            {/* Progress fill */}
            <div
              className="absolute top-0 left-0 right-0 bg-green-400/60 rounded-full transition-all duration-150"
              style={{ height: `${percentage}%` }}
            />
            {/* Thumb */}
            <div
              className={`absolute left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-2 border-green-400 shadow-lg transition-all duration-150 ${
                isDragging ? 'scale-125' : ''
              }`}
              style={{ top: `${percentage}%`, marginTop: '-8px' }}
            />
          </div>

          {/* Day labels */}
          <div className="absolute left-1/2 top-0 bottom-0 ml-6">
            {dayLabels.map(({ label, position }) => (
              <div
                key={label}
                className="absolute -translate-y-1/2 text-white/60 text-xs whitespace-nowrap"
                style={{ top: `${position}%` }}
              >
                {label}
              </div>
            ))}
          </div>

          {/* Hidden range input for accessibility */}
          <input
            type="range"
            min="0"
            max="100"
            step="0.1"
            value={percentage}
            onChange={handleSliderChange}
            onMouseDown={() => setIsDragging(true)}
            onMouseUp={() => setIsDragging(false)}
            onTouchStart={() => setIsDragging(true)}
            onTouchEnd={() => setIsDragging(false)}
            className="absolute inset-0 opacity-0 cursor-pointer"
            style={{ writingMode: 'vertical-lr' }}
            aria-label="Timeline scrubber"
          />
        </div>
      </div>

      {/* Current time display */}
      <div className="px-4 py-3 border-t border-white/10 text-center">
        <p className="text-white/60 text-xs">Viewing</p>
        <p className="text-white text-sm font-mono">
          {currentTime.toLocaleString([], {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>
    </div>
  )
}

import { useMemo } from 'react'

export interface AgendaTask {
  task: string
  scheduled_time: string
  duration_minutes: number
  estimated_food: number
  priority: number
  completed?: boolean
}

interface SchedulePanelProps {
  tasks: AgendaTask[]
  isOpen: boolean
  nextTaskTime: number | null
  petName: string
}

function formatTime(hhmm: string): string {
  try {
    const [h, m] = hhmm.split(':').map(Number)
    const period = h >= 12 ? 'PM' : 'AM'
    const hour = h % 12 || 12
    return `${hour}:${m.toString().padStart(2, '0')} ${period}`
  } catch {
    return hhmm
  }
}

function formatFoodCost(cost: number): string {
  if (cost < 0.001) return `$${cost.toFixed(6)}`
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  return `$${cost.toFixed(3)}`
}

export default function SchedulePanel({ tasks, isOpen, nextTaskTime, petName }: SchedulePanelProps) {
  const now = useMemo(() => {
    const d = new Date()
    return `${d.getUTCHours().toString().padStart(2, '0')}:${d.getUTCMinutes().toString().padStart(2, '0')}`
  }, [])

  // Find current task index (first uncompleted)
  const currentIdx = tasks.findIndex(t => !t.completed)

  if (!isOpen) return null

  return (
    <div className="fixed top-16 right-4 z-40 w-80 max-h-[70vh] overflow-y-auto rounded-2xl bg-black/60 backdrop-blur-xl border border-white/10 shadow-2xl">
      <div className="p-4 border-b border-white/10">
        <h3 className="text-white/90 text-sm font-medium tracking-wide">
          {petName}'s Schedule
        </h3>
        <p className="text-white/40 text-xs mt-0.5">
          {tasks.filter(t => t.completed).length}/{tasks.length} completed
        </p>
      </div>

      {tasks.length === 0 ? (
        <div className="p-6 text-center">
          <p className="text-white/30 text-sm">No schedule for today</p>
        </div>
      ) : (
        <div className="p-2">
          {tasks.map((task, i) => {
            const isCurrent = i === currentIdx
            const isPast = task.completed

            return (
              <div
                key={i}
                className={`relative flex items-start gap-3 p-3 rounded-xl transition-colors ${
                  isCurrent
                    ? 'bg-white/10'
                    : 'hover:bg-white/5'
                }`}
              >
                {/* Timeline dot + line */}
                <div className="flex flex-col items-center pt-0.5">
                  <div
                    className={`w-2.5 h-2.5 rounded-full border-2 flex-shrink-0 ${
                      isPast
                        ? 'bg-green-400/80 border-green-400/80'
                        : isCurrent
                          ? 'bg-blue-400 border-blue-400 animate-pulse'
                          : 'bg-transparent border-white/30'
                    }`}
                  />
                  {i < tasks.length - 1 && (
                    <div className={`w-0.5 flex-1 min-h-[24px] mt-1 ${
                      isPast ? 'bg-green-400/30' : 'bg-white/10'
                    }`} />
                  )}
                </div>

                {/* Task content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-xs font-mono ${
                      isPast ? 'text-white/30' : isCurrent ? 'text-blue-300' : 'text-white/50'
                    }`}>
                      {formatTime(task.scheduled_time)}
                    </span>
                    <span className="text-white/20 text-[10px]">
                      {task.duration_minutes}m
                    </span>
                  </div>
                  <p className={`text-sm mt-0.5 leading-snug ${
                    isPast
                      ? 'text-white/30 line-through'
                      : isCurrent
                        ? 'text-white/90'
                        : 'text-white/60'
                  }`}>
                    {task.task}
                  </p>
                  <span className="text-white/20 text-[10px]">
                    {formatFoodCost(task.estimated_food)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

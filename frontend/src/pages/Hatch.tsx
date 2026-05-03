import { useState } from 'react'

interface HatchProps {
  onHatch: (name: string) => void
}

export default function Hatch({ onHatch }: HatchProps) {
  const [name, setName] = useState('')
  const [phase, setPhase] = useState<'name' | 'hatching' | 'born'>('name')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setPhase('hatching')

    // Hatching animation sequence
    setTimeout(() => setPhase('born'), 3000)
    setTimeout(() => onHatch(name.trim()), 4500)
  }

  return (
    <div className="min-h-screen bg-black flex items-center justify-center px-6 relative overflow-hidden">
      {/* Background pulse during hatching */}
      {phase === 'hatching' && (
        <div className="absolute inset-0 animate-[pulse-glow_1.5s_ease-in-out_infinite] bg-[radial-gradient(ellipse_at_center,_rgba(255,255,255,0.05)_0%,_transparent_70%)]" />
      )}

      {phase === 'born' && (
        <div className="absolute inset-0 animate-[birth-flash_1.5s_ease-out_forwards] bg-[radial-gradient(ellipse_at_center,_rgba(255,255,255,0.2)_0%,_transparent_70%)]" />
      )}

      <div className="relative z-10 text-center max-w-sm w-full">
        {phase === 'name' && (
          <div className="animate-[fade-in_0.5s_ease-out]">
            {/* Egg / unhatched voxel */}
            <div className="mb-12 flex justify-center">
              <div className="w-6 h-6 bg-white/20 rounded-sm border border-white/10" />
            </div>

            <h1 className="text-2xl font-medium text-white mb-2">Name your pet</h1>
            <p className="text-sm text-gray-500 mb-8">Give it a name. Everything else, it decides.</p>

            <form onSubmit={handleSubmit}>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter a name"
                maxLength={20}
                autoFocus
                className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white text-center text-lg placeholder-gray-600 focus:outline-none focus:border-white/30 mb-4"
              />
              <button
                type="submit"
                disabled={!name.trim()}
                className="w-full px-6 py-3 bg-white text-black font-medium rounded-lg hover:bg-gray-100 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
              >
                Hatch
              </button>
            </form>
          </div>
        )}

        {phase === 'hatching' && (
          <div className="animate-[fade-in_0.3s_ease-out]">
            {/* Pulsing, cracking voxel */}
            <div className="mb-8 flex justify-center">
              <div className="w-8 h-8 bg-white/40 rounded-sm animate-[hatch-pulse_0.8s_ease-in-out_infinite] shadow-[0_0_30px_rgba(255,255,255,0.3)]" />
            </div>
            <p className="text-sm text-gray-500 animate-pulse">Hatching...</p>
          </div>
        )}

        {phase === 'born' && (
          <div className="animate-[fade-in_0.5s_ease-out]">
            {/* Born — bright single voxel */}
            <div className="mb-8 flex justify-center">
              <div className="w-4 h-4 bg-white rounded-sm shadow-[0_0_40px_rgba(255,255,255,0.6)]" />
            </div>
            <p className="text-lg text-white font-medium">{name}</p>
            <p className="text-sm text-gray-500 mt-2">is alive.</p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse-glow {
          0%, 100% { opacity: 0.3; }
          50% { opacity: 1; }
        }
        @keyframes birth-flash {
          0% { opacity: 1; }
          100% { opacity: 0; }
        }
        @keyframes hatch-pulse {
          0%, 100% { transform: scale(1); opacity: 0.4; }
          50% { transform: scale(1.3); opacity: 1; }
        }
        @keyframes fade-in {
          0% { opacity: 0; transform: translateY(10px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}

import { Link } from 'react-router-dom'

export default function Landing() {
  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center px-6 relative overflow-hidden">
      {/* Subtle background glow */}
      <div className="absolute inset-0 opacity-30 bg-[radial-gradient(ellipse_at_center,_rgba(99,102,241,0.15)_0%,_transparent_70%)]" />

      <div className="relative z-10 text-center max-w-2xl">
        {/* Single floating voxel */}
        <div className="mb-10 flex justify-center">
          <div className="w-4 h-4 bg-white rounded-sm shadow-[0_0_20px_rgba(255,255,255,0.4)] animate-[float_3s_ease-in-out_infinite]" />
        </div>

        <h1 className="text-5xl sm:text-7xl font-bold text-white tracking-tight mb-6">
          AI Pets
        </h1>

        <p className="text-lg text-gray-400 mb-12 max-w-md mx-auto">
          An autonomous AI that builds its own world, develops a personality, and evolves on its own.
        </p>

        <Link
          to="/signup"
          className="inline-flex items-center gap-2 px-8 py-4 bg-white text-black font-semibold rounded-full text-lg hover:bg-gray-100 hover:scale-105 transition-all duration-200"
        >
          Create Your Pet
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>

        <p className="mt-6 text-sm text-gray-600">
          Free to start
        </p>
      </div>

      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-8px); }
        }
      `}</style>
    </div>
  )
}

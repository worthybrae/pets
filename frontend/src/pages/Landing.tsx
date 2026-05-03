import { useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Landing() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [emailSent, setEmailSent] = useState(false)

  const signInWithGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/world' },
    })
  }

  const signInWithEmail = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email) return
    setLoading(true)
    await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin + '/world' },
    })
    setLoading(false)
    setEmailSent(true)
  }

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center px-6 relative overflow-hidden">
      {/* Subtle background glow */}
      <div className="absolute inset-0 opacity-30 bg-[radial-gradient(ellipse_at_center,_rgba(99,102,241,0.15)_0%,_transparent_70%)]" />

      <div className="relative z-10 text-center max-w-sm w-full">
        {/* Single floating voxel */}
        <div className="mb-10 flex justify-center">
          <div className="w-4 h-4 bg-white rounded-sm shadow-[0_0_20px_rgba(255,255,255,0.4)] animate-[float_3s_ease-in-out_infinite]" />
        </div>

        <h1 className="text-5xl sm:text-6xl font-bold text-white tracking-tight mb-4">
          AI Pets
        </h1>

        <p className="text-base text-gray-400 mb-10">
          An autonomous AI that builds its own world.
        </p>

        {/* Auth buttons */}
        <div className="space-y-3 mb-6">
          <button
            onClick={signInWithGoogle}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white text-black font-medium rounded-lg hover:bg-gray-100 transition-colors"
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

        {/* Divider */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1 h-px bg-white/10" />
          <span className="text-xs text-gray-600">or</span>
          <div className="flex-1 h-px bg-white/10" />
        </div>

        {/* Email */}
        {emailSent ? (
          <p className="text-sm text-gray-400">Check your email for a sign-in link.</p>
        ) : (
          <form onSubmit={signInWithEmail} className="flex gap-2">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="flex-1 px-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder-gray-600 text-sm focus:outline-none focus:border-white/20"
            />
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-3 bg-white/10 text-white text-sm font-medium rounded-lg border border-white/10 hover:bg-white/15 transition-colors disabled:opacity-50"
            >
              {loading ? '...' : 'Go'}
            </button>
          </form>
        )}

        <p className="mt-8 text-xs text-gray-700">
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

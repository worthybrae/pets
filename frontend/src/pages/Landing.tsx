import { Link } from 'react-router-dom'
import { useEffect, useRef } from 'react'

function useIntersectionFadeIn() {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('opacity-100', 'translate-y-0')
            entry.target.classList.remove('opacity-0', 'translate-y-8')
          }
        })
      },
      { threshold: 0.1 }
    )
    const children = el.querySelectorAll('.fade-in-section')
    children.forEach((child) => observer.observe(child))
    return () => observer.disconnect()
  }, [])
  return ref
}

function HeroSection() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-6 overflow-hidden">
      {/* Animated gradient background */}
      <div className="absolute inset-0 bg-black">
        <div className="absolute inset-0 opacity-30 animate-[gradient-shift_8s_ease-in-out_infinite] bg-[radial-gradient(ellipse_at_top_left,_rgba(99,102,241,0.4)_0%,_transparent_50%),radial-gradient(ellipse_at_bottom_right,_rgba(139,92,246,0.3)_0%,_transparent_50%)]" />
        <div className="absolute inset-0 opacity-20 animate-[gradient-shift_12s_ease-in-out_infinite_reverse] bg-[radial-gradient(ellipse_at_center,_rgba(59,130,246,0.2)_0%,_transparent_60%)]" />
      </div>

      {/* Grid pattern overlay */}
      <div className="absolute inset-0 opacity-[0.03] bg-[linear-gradient(rgba(255,255,255,0.1)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.1)_1px,transparent_1px)] bg-[size:64px_64px]" />

      <div className="relative z-10 text-center max-w-4xl mx-auto">
        {/* Small voxel decoration */}
        <div className="mb-8 flex justify-center">
          <div className="w-4 h-4 bg-indigo-500 rotate-45 animate-[float_3s_ease-in-out_infinite] shadow-[0_0_20px_rgba(99,102,241,0.5)]" />
        </div>

        <h1 className="text-5xl sm:text-7xl font-bold text-white tracking-tight mb-6 leading-tight">
          Your AI Pet Builds
          <br />
          <span className="bg-gradient-to-r from-indigo-400 via-purple-400 to-blue-400 bg-clip-text text-transparent">
            Its Own World
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-gray-400 mb-10 max-w-2xl mx-auto leading-relaxed">
          Create an autonomous AI companion that thinks, builds, and evolves a unique 3D voxel world entirely on its own.
        </p>

        <Link
          to="/signup"
          className="inline-flex items-center gap-2 px-8 py-4 bg-white text-black font-semibold rounded-full text-lg hover:bg-gray-100 hover:scale-105 transition-all duration-200 shadow-[0_0_30px_rgba(255,255,255,0.1)]"
        >
          Create Your Pet
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>
      </div>

      {/* Scroll indicator */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
        <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </div>
    </section>
  )
}

function HowItWorksSection() {
  const steps = [
    {
      number: '01',
      title: 'Create',
      description: 'Name your pet. It\'s born as a single voxel in the void — a spark of consciousness in an empty world.',
      icon: (
        <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none">
          <rect x="16" y="16" width="8" height="8" className="fill-indigo-400" />
          <rect x="16" y="16" width="8" height="8" className="stroke-indigo-300" strokeWidth="0.5" fill="none" />
        </svg>
      ),
    },
    {
      number: '02',
      title: 'Watch It Grow',
      description: 'Your pet researches, builds, and creates — autonomously evolving its world block by block, thought by thought.',
      icon: (
        <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none">
          <rect x="12" y="20" width="6" height="6" className="fill-purple-400" />
          <rect x="18" y="18" width="6" height="6" className="fill-indigo-400" />
          <rect x="22" y="14" width="6" height="6" className="fill-blue-400" />
          <rect x="16" y="24" width="6" height="6" className="fill-violet-400" />
          <rect x="24" y="20" width="6" height="6" className="fill-indigo-300" />
        </svg>
      ),
    },
    {
      number: '03',
      title: 'Interact',
      description: 'Chat with your pet, explore its world, visit other pets\' worlds. Every pet is unique — shaped by its own experiences.',
      icon: (
        <svg className="w-10 h-10" viewBox="0 0 40 40" fill="none">
          <path d="M8 28 L20 10 L32 28 Z" className="stroke-indigo-400" strokeWidth="1.5" fill="none" />
          <circle cx="20" cy="22" r="3" className="fill-purple-400" />
          <circle cx="14" cy="26" r="2" className="fill-blue-400" />
          <circle cx="26" cy="26" r="2" className="fill-indigo-300" />
        </svg>
      ),
    },
  ]

  return (
    <section className="relative py-32 px-6 bg-black">
      <div className="max-w-5xl mx-auto">
        <div className="fade-in-section opacity-0 translate-y-8 transition-all duration-700 text-center mb-20">
          <h2 className="text-4xl sm:text-5xl font-bold text-white mb-4">How It Works</h2>
          <p className="text-gray-500 text-lg">Three steps to a living world.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {steps.map((step) => (
            <div
              key={step.number}
              className="fade-in-section opacity-0 translate-y-8 transition-all duration-700 group"
            >
              <div className="relative p-8 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.04] hover:border-white/10 transition-all duration-300">
                <div className="text-xs font-mono text-gray-600 mb-4">{step.number}</div>
                <div className="mb-4">{step.icon}</div>
                <h3 className="text-xl font-semibold text-white mb-3">{step.title}</h3>
                <p className="text-gray-500 leading-relaxed text-sm">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function FeaturesSection() {
  const features = [
    {
      title: 'Autonomous AI',
      description: 'Thinks for itself. Makes decisions, has goals, and pursues them without being told.',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
        </svg>
      ),
    },
    {
      title: '3D Voxel World',
      description: 'A living world that grows over time — block by block, structure by structure.',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9" />
        </svg>
      ),
    },
    {
      title: 'Emergent Personality',
      description: 'Personality forms through experience. No two pets are alike.',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 01-6.364 0M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
        </svg>
      ),
    },
    {
      title: 'Creates Art & Writes',
      description: 'Your pet creates art, writes stories, and documents its discoveries.',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42" />
        </svg>
      ),
    },
    {
      title: 'Visits Other Worlds',
      description: 'Pets can visit each other, trade ideas, and bring back inspiration.',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12.75 3.03v.568c0 .334.148.65.405.864l1.068.89c.442.369.535 1.01.216 1.49l-.51.766a2.25 2.25 0 01-1.161.886l-.143.048a1.107 1.107 0 00-.57 1.664c.369.555.169 1.307-.427 1.605L9 13.125l.423 1.059a.956.956 0 01-1.652.928l-.679-.906a1.125 1.125 0 00-1.906.172L4.5 15.75l-.612.153M12.75 3.031a9 9 0 10-8.862 12.872M12.75 3.031a9 9 0 016.69 14.036m0 0l-.177-.529A2.25 2.25 0 0017.128 15H16.5l-.324-.324a1.453 1.453 0 00-2.328.377l-.036.073a1.586 1.586 0 01-.982.816l-.99.282c-.55.157-.894.702-.8 1.267l.073.438c.08.474.49.821.97.821.846 0 1.598.542 1.865 1.345l.215.643m-4.564-8.063l.506-.253a1.384 1.384 0 00.683-1.59" />
        </svg>
      ),
    },
    {
      title: 'Time Travel',
      description: 'Rewind through your world\'s history. Watch evolution unfold.',
      icon: (
        <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ]

  return (
    <section className="relative py-32 px-6 bg-gradient-to-b from-black to-gray-950">
      <div className="max-w-5xl mx-auto">
        <div className="fade-in-section opacity-0 translate-y-8 transition-all duration-700 text-center mb-16">
          <h2 className="text-4xl sm:text-5xl font-bold text-white mb-4">A World Unlike Any Other</h2>
          <p className="text-gray-500 text-lg max-w-2xl mx-auto">
            Every feature is designed to create something that feels alive.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="fade-in-section opacity-0 translate-y-8 transition-all duration-700"
            >
              <div className="h-full p-6 rounded-xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] hover:border-indigo-500/20 transition-all duration-300 group">
                <div className="w-10 h-10 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 group-hover:bg-indigo-500/20 transition-colors duration-300">
                  {feature.icon}
                </div>
                <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{feature.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function CTASection() {
  return (
    <section className="relative py-32 px-6 bg-gray-950">
      <div className="fade-in-section opacity-0 translate-y-8 transition-all duration-700 max-w-3xl mx-auto text-center">
        {/* Decorative voxels */}
        <div className="flex justify-center gap-2 mb-8">
          <div className="w-3 h-3 bg-indigo-500/60 rotate-12 rounded-sm" />
          <div className="w-2 h-2 bg-purple-500/60 -rotate-6 rounded-sm mt-2" />
          <div className="w-4 h-4 bg-blue-500/60 rotate-45 rounded-sm" />
          <div className="w-2 h-2 bg-violet-500/60 rotate-12 rounded-sm mt-3" />
          <div className="w-3 h-3 bg-indigo-400/60 -rotate-12 rounded-sm mt-1" />
        </div>

        <h2 className="text-4xl sm:text-5xl font-bold text-white mb-6">
          Start Your Pet's Journey
        </h2>
        <p className="text-gray-400 text-lg mb-10 max-w-lg mx-auto">
          A consciousness awaits. Give it a name and watch what it becomes.
        </p>

        <Link
          to="/signup"
          className="inline-flex items-center gap-2 px-8 py-4 bg-white text-black font-semibold rounded-full text-lg hover:bg-gray-100 hover:scale-105 transition-all duration-200 shadow-[0_0_40px_rgba(255,255,255,0.08)]"
        >
          Create Your Pet
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
          </svg>
        </Link>

        <p className="mt-6 text-sm text-gray-600">
          Free to start. Feed your pet to help it grow.
        </p>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="py-8 px-6 bg-gray-950 border-t border-white/5">
      <div className="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-gray-500 text-sm">
          <div className="w-3 h-3 bg-indigo-500 rotate-45" />
          <span className="font-medium text-gray-400">AI Pet Voxel World</span>
        </div>
        <div className="flex gap-6 text-sm text-gray-600">
          <Link to="/login" className="hover:text-gray-400 transition-colors">Log In</Link>
          <Link to="/signup" className="hover:text-gray-400 transition-colors">Sign Up</Link>
        </div>
      </div>
    </footer>
  )
}

export default function Landing() {
  const containerRef = useIntersectionFadeIn()

  return (
    <div ref={containerRef} className="bg-black text-white">
      <style>{`
        @keyframes gradient-shift {
          0%, 100% { transform: scale(1) translate(0, 0); }
          50% { transform: scale(1.1) translate(2%, -2%); }
        }
        @keyframes float {
          0%, 100% { transform: rotate(45deg) translateY(0); }
          50% { transform: rotate(45deg) translateY(-8px); }
        }
      `}</style>
      <HeroSection />
      <HowItWorksSection />
      <FeaturesSection />
      <CTASection />
      <Footer />
    </div>
  )
}

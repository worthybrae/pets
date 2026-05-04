import { useState, useEffect } from 'react'
import { rarityColors } from '../../data/rarity'
import type { Rarity } from '../../data/rarity'
import type { QualityTier } from './types'

function getStatColor(value: number): string {
  if (value >= 9) return '#f59e0b'
  if (value >= 7) return '#3b82f6'
  if (value >= 5) return '#8b5cf6'
  if (value >= 3) return '#10b981'
  return '#6b7280'
}

export function StatBar({ name, value, delay, revealed }: {
  name: string; value: number; delay: number; revealed: boolean
}) {
  const [active, setActive] = useState(false)
  const [filled, setFilled] = useState(false)
  const [locked, setLocked] = useState(false)
  const [scrambleVal, setScrambleVal] = useState(0)
  const [showShimmer, setShowShimmer] = useState(false)
  const barColor = getStatColor(value)

  useEffect(() => {
    if (!revealed) return
    const t1 = setTimeout(() => setActive(true), delay)
    const t2 = setTimeout(() => {
      let count = 0
      const scramble = setInterval(() => {
        setScrambleVal(Math.floor(Math.random() * 10) + 1)
        count++
        if (count > 12) {
          clearInterval(scramble)
          setScrambleVal(value)
          setLocked(true)
        }
      }, 50)
      setFilled(true)
    }, delay + 50)
    const t3 = setTimeout(() => setShowShimmer(true), delay + 400)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3) }
  }, [revealed, delay, value])

  return (
    <div className="flex items-center gap-3 text-sm" style={{
      opacity: active ? 1 : 0,
      transform: active ? 'translateX(0)' : 'translateX(-10px)',
      transition: 'opacity 0.4s ease-out, transform 0.4s ease-out',
    }}>
      <span className="text-neutral-500 w-24 capitalize text-xs tracking-wide">{name}</span>
      <div className="flex-1 h-2 bg-neutral-200 rounded-full overflow-hidden relative">
        <div className="h-full rounded-full relative overflow-hidden" style={{
          width: filled ? `${value * 10}%` : '0%',
          backgroundColor: barColor,
          boxShadow: locked ? `0 0 16px ${barColor}50, 0 0 4px ${barColor}30` : 'none',
          transition: 'width 1s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease-out',
        }}>
          {showShimmer && (
            <div className="absolute inset-0 stat-shimmer" style={{
              background: `linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.4) 50%, transparent 100%)`,
            }} />
          )}
        </div>
      </div>
      <span className="w-8 text-right font-bold tabular-nums" style={{
        color: active ? barColor : 'transparent',
        fontSize: locked ? '14px' : '11px',
        transition: 'color 0.15s ease-out, font-size 0.2s ease-out',
        textShadow: locked ? `0 0 8px ${barColor}60` : 'none',
      }}>{active ? scrambleVal : 0}</span>
    </div>
  )
}

export function TotalReveal({ total, visible }: { total: number; visible: boolean }) {
  const [displayTotal, setDisplayTotal] = useState(0)

  useEffect(() => {
    if (!visible) return
    const start = Date.now()
    const animate = () => {
      const p = Math.min((Date.now() - start) / 800, 1)
      setDisplayTotal(Math.round((1 - Math.pow(1 - p, 3)) * total))
      if (p < 1) requestAnimationFrame(animate)
    }
    requestAnimationFrame(animate)
  }, [visible, total])

  if (!visible) return null

  return (
    <div className="flex justify-between items-center pt-2 border-t border-neutral-200" style={{ animation: 'fadeUp 0.4s ease-out both' }}>
      <span className="text-neutral-400 text-xs">Total</span>
      <span className="text-neutral-800 font-semibold text-lg">{displayTotal}</span>
    </div>
  )
}

export function RarityBadge({ rarity, visible }: { rarity: Rarity; visible: boolean }) {
  const [show, setShow] = useState(false)
  const color = rarityColors[rarity]
  const isSpecial = rarity === 'legendary' || rarity === 'mythic'

  useEffect(() => {
    if (visible) { const t = setTimeout(() => setShow(true), 50); return () => clearTimeout(t) }
  }, [visible])

  if (!visible) return null

  return (
    <div className="relative inline-block">
      {isSpecial && show && (
        <div className="absolute inset-0 rounded-full blur-xl animate-pulse" style={{ backgroundColor: `${color}30` }} />
      )}
      <div
        className={`relative inline-block px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest ${rarity === 'mythic' ? 'mythic-badge' : ''}`}
        style={{
          ...(rarity === 'mythic' ? {} : { backgroundColor: `${color}15`, color, border: `1px solid ${color}40` }),
          opacity: show ? 1 : 0,
          transform: show ? 'scale(1)' : 'scale(0.3)',
          transition: 'all 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
        }}
      >{rarity}</div>
    </div>
  )
}

export function QualityBadge({ quality, visible }: { quality: QualityTier; visible: boolean }) {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (visible) { const t = setTimeout(() => setShow(true), 300); return () => clearTimeout(t) }
  }, [visible])

  if (!visible || quality === 'neutral') return null

  const isEnhanced = quality === 'enhanced'
  const color = isEnhanced ? '#fbbf24' : '#6b7280'
  const label = isEnhanced ? 'ENHANCED' : 'FRACTURED'

  return (
    <div
      className="text-center pt-1"
      style={{
        opacity: show ? 1 : 0,
        transform: show ? 'scale(1)' : 'scale(0.8)',
        transition: 'all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
      }}
    >
      <div
        className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-widest"
        style={{
          backgroundColor: `${color}15`,
          color,
          border: `1px solid ${color}40`,
          boxShadow: isEnhanced ? `0 0 16px ${color}20` : 'none',
        }}
      >
        {label}
      </div>
    </div>
  )
}

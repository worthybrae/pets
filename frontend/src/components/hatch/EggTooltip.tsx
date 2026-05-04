import { rarityColors } from '../../data/rarity'
import type { EggProfile, RolledAttribute } from './types'
import { TIER_POINTS } from './eggAttributes'

const STAT_BIAS_LABELS: Record<string, string[]> = {
  shape:  ['resilience', 'energy'],
  scales: ['focus', 'creativity'],
  color:  ['social', 'humor'],
  size:   ['energy', 'resilience'],
  mist:   ['curiosity', 'creativity'],
}

const TIER_COLORS: Record<string, string> = {
  common: '#9ca3af',
  uncommon: '#22c55e',
  rare: '#3b82f6',
  legendary: '#a855f7',
  mythic: '#ec4899',
}

function AttributeRow({ attr }: { attr: RolledAttribute }) {
  const tierColor = TIER_COLORS[attr.option.tier] || '#9ca3af'
  const biases = STAT_BIAS_LABELS[attr.category] || []

  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <div className="flex items-center gap-2">
        <span className="text-white/40 text-xs capitalize w-12">{attr.category}</span>
        <span className="text-white text-xs font-medium">{attr.option.name}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: tierColor }}>{attr.option.tier}</span>
        {biases.length > 0 && (
          <span className="text-white/25 text-[10px]">
            +{biases.join(', +')}
          </span>
        )}
      </div>
    </div>
  )
}

export default function EggTooltip({ egg, visible }: { egg: EggProfile; visible: boolean }) {
  if (!visible) return null

  return (
    <div
      className="absolute top-4 right-4 z-20 w-64 rounded-2xl p-4 space-y-2"
      style={{
        background: 'rgba(15, 15, 20, 0.9)',
        backdropFilter: 'blur(30px)',
        WebkitBackdropFilter: 'blur(30px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 12px 40px rgba(0, 0, 0, 0.3)',
        animation: 'fadeUp 0.3s ease-out',
      }}
    >
      <div className="text-center pb-2 border-b border-white/10">
        <div className="text-white text-sm font-medium tracking-wide">{egg.name}</div>
        <div className="text-xs mt-1" style={{ color: rarityColors[egg.rarity] }}>
          {egg.rarity.toUpperCase()} — {egg.totalPoints.toFixed(1)} / 10
        </div>
      </div>

      <div className="space-y-0.5">
        {egg.attributes.map(attr => (
          <AttributeRow key={attr.category} attr={attr} />
        ))}
      </div>
    </div>
  )
}

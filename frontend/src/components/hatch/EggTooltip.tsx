import { rarityColors } from '../../data/rarity'
import type { EggProfile, RolledAttribute } from './types'

const TIER_COLORS: Record<string, string> = {
  common: '#9ca3af',
  uncommon: '#22c55e',
  rare: '#3b82f6',
  legendary: '#a855f7',
  mythic: '#ec4899',
}

const TIER_BG: Record<string, string> = {
  common: 'rgba(156,163,175,0.08)',
  uncommon: 'rgba(34,197,94,0.08)',
  rare: 'rgba(59,130,246,0.08)',
  legendary: 'rgba(168,85,247,0.1)',
  mythic: 'rgba(236,72,153,0.1)',
}

function AttributeRow({ attr }: { attr: RolledAttribute }) {
  const tierColor = TIER_COLORS[attr.option.tier] || '#9ca3af'
  const tierBg = TIER_BG[attr.option.tier] || 'transparent'

  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-neutral-400 text-[11px] uppercase tracking-wider w-14 shrink-0">{attr.category}</span>
      <span className="text-neutral-800 text-sm font-medium flex-1">{attr.option.name}</span>
      <span
        className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
        style={{ color: tierColor, backgroundColor: tierBg }}
      >
        {attr.option.tier}
      </span>
    </div>
  )
}

export default function EggTooltip({ egg, visible, mousePos }: { egg: EggProfile; visible: boolean; mousePos: { x: number; y: number } }) {
  if (!visible) return null

  const rarityColor = rarityColors[egg.rarity]

  return (
    <div
      className="fixed z-50 w-72 rounded-2xl pointer-events-none overflow-hidden"
      style={{
        left: mousePos.x + 16,
        top: mousePos.y + 16,
        background: 'rgba(255, 255, 255, 0.88)',
        backdropFilter: 'blur(40px)',
        WebkitBackdropFilter: 'blur(40px)',
        border: '1px solid rgba(0, 0, 0, 0.06)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.04)',
      }}
    >
      {/* Header with rarity accent */}
      <div
        className="px-5 pt-4 pb-3"
        style={{
          borderBottom: '1px solid rgba(0, 0, 0, 0.05)',
          background: `linear-gradient(135deg, ${rarityColor}08, transparent)`,
        }}
      >
        <div className="text-neutral-900 text-sm font-semibold tracking-wide">{egg.name}</div>
        <div className="flex items-center gap-2 mt-1.5">
          <span
            className="text-[10px] font-bold uppercase tracking-widest px-2.5 py-0.5 rounded-full"
            style={{
              color: rarityColor,
              backgroundColor: `${rarityColor}12`,
              border: `1px solid ${rarityColor}25`,
            }}
          >
            {egg.rarity}
          </span>
          <span className="text-neutral-300 text-[10px]">{egg.totalPoints.toFixed(1)} / 10</span>
        </div>
      </div>

      {/* Attributes */}
      <div className="px-5 py-3 space-y-0">
        {egg.attributes.map(attr => (
          <AttributeRow key={attr.category} attr={attr} />
        ))}
      </div>
    </div>
  )
}

import { AIR, BLOCKS } from '../engine/blocks'
import { chestText } from './hud'
import type { Chests, Recipe } from './types'

const BLOCK_TYPES = BLOCKS.filter((block) => block.id !== AIR)

/** The owner's crafting help: the same rules and persistent inventory the pet uses. */
export default function CraftingPanel({ name, inventory, chests, recipes, stations, worldSeed, message, onAction, onClose }: {
  name: string
  inventory: Record<string, number>
  /** What Mimo keeps in its chests at home. */
  chests: Chests
  recipes: Record<string, Recipe>
  stations: Set<string>
  worldSeed: string
  message: string
  onAction: (action: string, item: string) => void
  onClose: () => void
}) {
  const owned = Object.entries(inventory).filter(([, amount]) => amount > 0)
  const stored = chestText(chests)
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-[#203b38]/45 p-4" role="presentation" onClick={onClose}>
      <section role="dialog" aria-modal="true" aria-label={`${name}'s blocks and crafting`} onClick={(event) => event.stopPropagation()}
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-[#f5faf7] p-6 shadow-2xl sm:p-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-[#65817b]">World systems</p>
            <h2 className="mt-1 text-3xl font-semibold tracking-tight">Blocks & crafting</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close blocks and crafting" className="rounded-xl bg-[#e1eee7] px-3 py-1.5 text-xl">×</button>
        </div>
        <p className="mt-3 max-w-xl text-sm leading-6 text-[#54726e]">You can help {name} craft with what it carries. Inventory and machines persist when you leave.</p>
        <p className="mt-2 text-xs text-[#54726e]">World seed: <code>{worldSeed}</code></p>
        <h3 className="mt-6 text-sm font-semibold">{name}'s inventory</h3>
        <div className="mt-2 flex flex-wrap gap-2 text-sm">
          {owned.length === 0 && <span className="text-[#65817b]">Nothing yet.</span>}
          {owned.map(([item, amount]) =>
            <span key={item} className="rounded-lg bg-[#e1eee7] px-3 py-1.5">{item.replaceAll('_', ' ')} ×{amount}</span>)}
        </div>
        {stored && <p className="mt-2 text-xs text-[#54726e]">In {name}'s chest at home: {stored}</p>}
        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" disabled={!inventory.crafting_table} onClick={() => onAction('place_machine', 'crafting_table')}
            className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place crafting table</button>
          <button type="button" disabled={!inventory.furnace} onClick={() => onAction('place_machine', 'furnace')}
            className="rounded-lg bg-[#315e58] px-3 py-2 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-35">Place furnace</button>
          <button type="button" disabled={!inventory.iron_ore || !stations.has('furnace') || !(inventory.coal || inventory.planks)}
            onClick={() => onAction('smelt', 'iron_ore')}
            className="rounded-lg border border-[#bfd5cd] px-3 py-2 text-xs font-medium text-[#315e58] disabled:cursor-not-allowed disabled:opacity-35">Smelt iron ore</button>
        </div>
        <p className="mt-2 text-xs text-[#65817b]">Smelting needs a placed furnace and coal or planks for fuel.</p>
        {message && <p className="mt-3 rounded-lg bg-[#e1eee7] px-3 py-2 text-xs text-[#315e58]" role="status">{message}</p>}
        <h3 className="mt-6 text-sm font-semibold">Recipes</h3>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {Object.entries(recipes).map(([recipeName, recipe]) => (
            <div key={recipeName} className="rounded-xl bg-[#e9f2eb] px-3 py-2 text-xs leading-5">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{recipeName.replaceAll('_', ' ')}</p>
                <button type="button" disabled={Boolean(recipe.station && !stations.has(recipe.station)) ||
                  Object.entries(recipe.ingredients).some(([item, amount]) => (inventory[item] || 0) < amount)}
                  onClick={() => onAction('craft', recipeName)}
                  className="rounded-md bg-[#315e58] px-2 py-1 font-medium text-white hover:bg-[#244b47] disabled:cursor-not-allowed disabled:opacity-35">Craft</button>
              </div>
              <p className="text-[#54726e]">{Object.entries(recipe.ingredients).map(([item, amount]) => `${amount} ${item.replaceAll('_', ' ')}`).join(' + ')}
                {recipe.station ? ` · needs placed ${recipe.station.replaceAll('_', ' ')}` : ''}</p>
            </div>
          ))}
        </div>
        <h3 className="mt-6 text-sm font-semibold">{BLOCK_TYPES.length} block types</h3>
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {BLOCK_TYPES.map((block) => (
            <div key={block.name} className="flex items-center gap-2 rounded-lg border border-[#d6e5dc] px-2 py-1.5 text-xs">
              <span className="h-5 w-5 shrink-0 rounded-sm border border-black/10" style={{ backgroundColor: `rgb(${block.color.join(',')})` }} />
              {block.name.replaceAll('_', ' ')}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

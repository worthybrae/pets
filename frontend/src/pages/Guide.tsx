const RARITY_TIERS = [
  { name: 'Common', color: '#9ca3af', chance: '60%', range: '18–34', desc: 'Modest but endearing' },
  { name: 'Uncommon', color: '#22c55e', chance: '25%', range: '35–43', desc: 'A step above ordinary' },
  { name: 'Rare', color: '#3b82f6', chance: '10%', range: '44–51', desc: 'Distinctly gifted' },
  { name: 'Legendary', color: '#a855f7', chance: '4%', range: '52–60', desc: 'Truly exceptional' },
  { name: 'Mythic', color: '#ec4899', chance: '1%', range: '61–70', desc: 'One in a hundred' },
]

const STATS = [
  { name: 'Curiosity', icon: '?', desc: 'How eagerly your creature explores new ideas and asks questions. High curiosity means more wandering, more wondering, more unexpected discoveries.' },
  { name: 'Creativity', icon: '✦', desc: 'The ability to invent, imagine, and build. Creative creatures craft elaborate stories, design unique structures, and find novel solutions.' },
  { name: 'Social', icon: '◉', desc: 'Comfort with interaction and connection. Social creatures are chatty, expressive, and thrive on conversation. Low social creatures are more introspective.' },
  { name: 'Focus', icon: '◎', desc: 'Attention span and task dedication. Focused creatures finish what they start and dive deep. Low focus means a scatterbrained but spontaneous companion.' },
  { name: 'Energy', icon: '⚡', desc: 'Activity level and stamina. High energy creatures are always moving, exploring, building. Low energy creatures are contemplative and prefer rest.' },
  { name: 'Resilience', icon: '⬡', desc: 'Emotional steadiness and adaptability. Resilient creatures bounce back quickly and handle surprises well. Low resilience means more dramatic reactions.' },
  { name: 'Humor', icon: '~', desc: 'Playfulness and wit. Humorous creatures crack jokes, find absurdity amusing, and keep things light. Low humor means a more serious, earnest personality.' },
]

const EGG_ATTRIBUTES = [
  {
    name: 'Shape',
    desc: 'The egg\'s silhouette',
    values: ['Round', 'Oval', 'Squat', 'Elongated', 'Teardrop', 'Bulbous', 'Gourd', 'Spire'],
    influences: 'Resilience & Energy',
  },
  {
    name: 'Scales',
    desc: 'Surface texture pattern',
    values: ['Smooth', 'Stippled', 'Hexscale', 'Diamond', 'Spiral', 'Cracked', 'Runic', 'Prismatic'],
    influences: 'Focus & Creativity',
  },
  {
    name: 'Color',
    desc: 'Primary hue',
    values: ['Stone', 'Moss', 'Amber', 'Cobalt', 'Crimson', 'Violet', 'Obsidian', 'Iridescent'],
    influences: 'Social & Humor',
  },
  {
    name: 'Size',
    desc: 'Physical scale',
    values: ['Tiny', 'Small', 'Standard', 'Large', 'Massive', 'Colossal'],
    influences: 'Energy & Resilience',
  },
  {
    name: 'Mist',
    desc: 'Aura surrounding the egg',
    values: ['None', 'Faint', 'Wispy', 'Radiant', 'Ethereal'],
    influences: 'Curiosity & Creativity',
  },
]

const ATTR_TIERS = [
  { tier: 'Common', chance: '40%', points: 0 },
  { tier: 'Uncommon', chance: '25%', points: 0.5 },
  { tier: 'Rare', chance: '20%', points: 1 },
  { tier: 'Legendary', chance: '14%', points: 1.5 },
  { tier: 'Mythic', chance: '1%', points: 2 },
]

export default function Guide() {
  return (
    <div className="min-h-screen bg-neutral-100">
      <div className="max-w-2xl mx-auto px-6 py-20">
        {/* Title */}
        <div className="mb-16">
          <h1 className="text-3xl font-medium text-neutral-800 tracking-[0.1em] mb-3">
            how cradl works
          </h1>
          <p className="text-neutral-500 text-sm leading-relaxed max-w-lg">
            Every creature is unique — shaped by chance, built by AI, and given a soul
            that makes it genuinely its own. Nothing is templated. Here's how it all comes together.
          </p>
        </div>

        {/* Section: The Hatch */}
        <Section title="the hatch">
          <p className="text-neutral-600 text-sm leading-relaxed mb-4">
            When you hatch a creature, the system rolls seven core stats using a
            median-of-three method — three random rolls per stat, keeping the middle value.
            This creates a natural bell curve where extreme stats (very high or very low) are
            rare but possible.
          </p>
          <p className="text-neutral-600 text-sm leading-relaxed">
            Alongside the stats, a rarity tier is determined by weighted random selection.
            Your creature's stats are then adjusted to fall within that rarity's target range,
            ensuring a Common creature feels modest and a Mythic one feels truly powerful.
          </p>
        </Section>

        {/* Section: The Seven Stats */}
        <Section title="the seven stats">
          <p className="text-neutral-500 text-xs mb-6">
            Each stat ranges from 1 to 10. Together they define your creature's personality,
            behavior, and how it experiences its world.
          </p>
          <div className="space-y-4">
            {STATS.map((stat) => (
              <div key={stat.name} className="group">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-neutral-400 text-xs font-mono w-4 text-center">{stat.icon}</span>
                  <span className="text-neutral-700 text-sm font-medium">{stat.name}</span>
                </div>
                <p className="text-neutral-500 text-xs leading-relaxed pl-6">
                  {stat.desc}
                </p>
              </div>
            ))}
          </div>
        </Section>

        {/* Section: Rarity */}
        <Section title="rarity tiers">
          <p className="text-neutral-500 text-xs mb-6">
            Rarity determines the total stat budget your creature receives. Higher rarity means
            stronger overall stats, a more complex AI-generated appearance, and a richer personality.
          </p>
          <div className="space-y-3">
            {RARITY_TIERS.map((tier) => (
              <div key={tier.name} className="flex items-center gap-3">
                <div
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: tier.color }}
                />
                <div className="flex-1 flex items-baseline justify-between">
                  <div>
                    <span className="text-neutral-700 text-sm font-medium">{tier.name}</span>
                    <span className="text-neutral-400 text-xs ml-2">{tier.desc}</span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-neutral-400 text-xs font-mono">{tier.range}</span>
                    <span className="text-neutral-300 text-xs font-mono w-8 text-right">{tier.chance}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-neutral-200">
            <p className="text-neutral-400 text-xs leading-relaxed">
              The stat total (sum of all seven stats) determines which range your creature
              falls into. A Common creature might total 24 points spread thinly, while a
              Mythic can reach 70 — nearly maxed across the board.
            </p>
          </div>
        </Section>

        {/* Section: Egg Attributes */}
        <Section title="egg attributes">
          <p className="text-neutral-500 text-xs mb-2">
            Before hatching, your egg is generated with five independent attributes. Each
            attribute is rolled separately and can land on any tier — a Common egg might have
            one Legendary trait, or all five could be unremarkable.
          </p>
          <p className="text-neutral-500 text-xs mb-6">
            Each attribute biases specific stats, nudging your creature's personality
            in a direction hinted at by the egg's appearance.
          </p>

          <div className="space-y-5">
            {EGG_ATTRIBUTES.map((attr) => (
              <div key={attr.name}>
                <div className="flex items-baseline justify-between mb-1">
                  <div>
                    <span className="text-neutral-700 text-sm font-medium">{attr.name}</span>
                    <span className="text-neutral-400 text-xs ml-2">— {attr.desc}</span>
                  </div>
                  <span className="text-neutral-400 text-xs">biases {attr.influences}</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {attr.values.map((val, i) => (
                    <span
                      key={val}
                      className="px-2 py-0.5 text-xs rounded-md bg-neutral-200/80 text-neutral-500"
                      style={{
                        opacity: 0.5 + (i / attr.values.length) * 0.5,
                      }}
                    >
                      {val}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>

        {/* Section: Attribute Point System */}
        <Section title="how egg rarity emerges">
          <p className="text-neutral-500 text-xs mb-4">
            Each attribute tier contributes points toward the egg's overall rarity. The five
            scores are summed (0–10 possible) and mapped to a rarity band.
          </p>
          <div className="grid grid-cols-5 gap-2 mb-4">
            {ATTR_TIERS.map((t) => (
              <div key={t.tier} className="text-center">
                <div className="text-neutral-700 text-xs font-medium">{t.tier}</div>
                <div className="text-neutral-400 text-xs font-mono">{t.points} pts</div>
                <div className="text-neutral-300 text-xs">{t.chance}</div>
              </div>
            ))}
          </div>
          <div className="space-y-1.5 text-xs text-neutral-500 font-mono">
            <div className="flex justify-between"><span>0 – 2 points</span><span>Common egg</span></div>
            <div className="flex justify-between"><span>2.1 – 4 points</span><span>Uncommon egg</span></div>
            <div className="flex justify-between"><span>4.1 – 6 points</span><span>Rare egg</span></div>
            <div className="flex justify-between"><span>6.1 – 8 points</span><span>Legendary egg</span></div>
            <div className="flex justify-between"><span>8.1 – 10 points</span><span>Mythic egg</span></div>
          </div>
        </Section>

        {/* Section: The Soul */}
        <Section title="the soul">
          <p className="text-neutral-600 text-sm leading-relaxed mb-4">
            Once stats and rarity are determined, an AI generates your creature's soul — a
            detailed personality document (~600 words) that defines who they are. This isn't
            a template. Every soul is written from scratch based on the creature's unique stat
            combination.
          </p>
          <div className="bg-neutral-200/50 rounded-lg p-4 space-y-2 text-xs text-neutral-500">
            <div><span className="text-neutral-600 font-medium">Temperament</span> — emotional baseline and disposition</div>
            <div><span className="text-neutral-600 font-medium">Speech style</span> — how they communicate and express themselves</div>
            <div><span className="text-neutral-600 font-medium">Quirks</span> — 2–3 specific behavioral oddities</div>
            <div><span className="text-neutral-600 font-medium">Fears</span> — what makes them anxious or uncomfortable</div>
            <div><span className="text-neutral-600 font-medium">Goals</span> — long-term aspirations and drives</div>
            <div><span className="text-neutral-600 font-medium">Worldview</span> — how they interpret their existence</div>
            <div><span className="text-neutral-600 font-medium">Initial questions</span> — 3–5 active wonderings they start with</div>
          </div>
          <p className="text-neutral-400 text-xs mt-4 leading-relaxed">
            The soul is injected into every interaction your creature has — it shapes how they
            respond to you, what they choose to do autonomously, and how they grow over time.
            A high-humor, low-focus creature will chat very differently from a high-resilience,
            high-curiosity one.
          </p>
        </Section>

        {/* Section: The Body */}
        <Section title="the body">
          <p className="text-neutral-600 text-sm leading-relaxed mb-4">
            Your creature's physical form is built from voxels — tiny 3D cubes assembled into
            a unique shape. The AI designs 150–400 voxels for the creature and 200–500 for
            their starter world landmark, guided by the creature's stats and rarity.
          </p>
          <div className="space-y-2 text-xs text-neutral-500">
            <p>Higher rarity creatures tend to have more complex, detailed bodies with richer
            color palettes. The AI follows principles like bilateral symmetry, ground-up
            construction, and 3–5 coherent colors — but every design is original.</p>
            <p>A backstory (2–3 sentences) is generated alongside the body, giving your creature
            an origin that connects its appearance, personality, and the world it inhabits.</p>
          </div>
        </Section>

        {/* Section: Quality Badges */}
        <Section title="quality badges">
          <p className="text-neutral-500 text-xs mb-4">
            After stats are rolled and placed within a rarity tier, a quality badge shows
            where your creature landed within its range.
          </p>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <span className="w-20 text-xs font-medium text-amber-500">Enhanced</span>
              <span className="text-neutral-500 text-xs">Top 25% of the rarity range — gold accent</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-20 text-xs font-medium text-neutral-400">Neutral</span>
              <span className="text-neutral-500 text-xs">Middle 50% — no badge, solidly within tier</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="w-20 text-xs font-medium text-neutral-300">Fractured</span>
              <span className="text-neutral-500 text-xs">Bottom 25% — dim accent, barely made the tier</span>
            </div>
          </div>
        </Section>

        {/* Section: Living Creatures */}
        <Section title="a living creature">
          <p className="text-neutral-600 text-sm leading-relaxed mb-4">
            Once hatched, your creature isn't static. It has a food balance that depletes
            over time, an agenda of daily activities it plans autonomously, and a memory
            of your conversations together.
          </p>
          <div className="space-y-2 text-xs text-neutral-500">
            <p>Stats directly influence behavior — a high-energy creature explores more, a
            high-social one seeks conversation, a high-focus one commits to projects. Their
            soul ensures consistency: the same creature will respond recognizably across
            hundreds of interactions.</p>
            <p>Every creature is genuinely unique. The combination of rolled stats, AI-generated
            soul, voxel body, and backstory means no two creatures will ever be the same —
            even at the same rarity tier.</p>
          </div>
        </Section>

      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <h2 className="text-lg font-medium text-neutral-700 tracking-[0.08em] mb-4">
        {title}
      </h2>
      {children}
    </section>
  )
}

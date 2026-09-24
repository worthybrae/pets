# Living World: Design Spec

Sub-project 3 of the "Mimo's world feels like Minecraft" roadmap. It builds on the Survival Core (sub-project 2, done on `worthy/23_09_2026/survival_core`): lives and vitals, the three-layer brain, food and renewal, purposeful building, and camera modes.

## Why (the owner's words, 2026-09-23 night)

After watching Pebble build its cottage, the owner said:

> "we are for sure missing the full world like the animals and the health component. also going underground we see these small passageways ideally they are a bit bigger so we can see more inside. ideally though I want the actions of the pet to be purposeful. I also think the world is lacking a bit. like in minecraft theres almost an endless combination of things and way more different types of blocks and you can craft weapons and bow and arrows it should be more like that."

Earlier they asked for creatures that could fight Mimo, and for "seeds that could grow other creatures". They also want Mimo to remember where it has been, so it explores somewhere new.

## Decisions

The owner pre-approved designing overnight ("try to craft the vision I'm going for … just keep on working"). The controller made these calls; each can be changed later.

- **Original creatures.** Designs and names are our own, not Minecraft's. Passive animals get plain names (rabbit, sheep, cow, chicken, fish). Hostile creatures get invented names: *gloomling*, a slow night walker, and *skitter*, a fast cave crawler.
- **Server owns creatures.** Creatures live in the world database and move in the tick, like Mimo. The viewer only draws them. Only creatures within 48 blocks of Mimo are simulated; the rest stay put.
- **Creatures stay cheap.** No A* search for creatures. They move greedily, one block at a time, using the same step-up-1 / drop-3 rules and the Grid. There is a hard cap on creatures near Mimo.
- **Health matters.** Damage sources are creatures, falls, starvation and cold. Health comes back slowly while Mimo is fed. Armor reduces damage. "Killed by a creature" is a death cause.
- **Weapons like Minecraft.** Swords in wood, stone and iron (later gold and diamond). A bow shoots arrows made from flint, sticks and feathers. The string for the bow comes from skitters. Mimo crafts these through the same recipe and portable-station system.
- **Light keeps monsters away.** A simple light level: sky light by day, plus block light from torches, lanterns, campfires and furnaces, fading one level per block. Hostiles spawn only where the light is low. Torches around home keep the yard safe.
- **Doors.** A door block that Mimo can walk through and creatures cannot. Shelters get one in the door gap.
- **Bigger passages.** Mimo's dug staircases and tunnels become 2 wide and 3 tall. Natural caves get bigger. This gives the camera room to see inside.
- **More world.** Many more blocks: stone variants, new ores (gold, diamond), new trees (birch, spruce), and desert, taiga and swamp plants. Also boulders and outcrops on the surface, cave entrances that open to the sky, and underground lakes and lava.
- **Creature seeds.** A rare seed, found in grass and leaves. When planted, it grows into a passive animal over a game day. This is how the world regains animals, and it is the owner's "seeds that grow creatures".
- **Purposeful life.** A goal layer above purposes: long projects with progress, such as "a real home", "iron tools", "armor up", "a full larder" or "map the north". Goals come from traits, memory, threats and vitals, and Jev picks them when a key is set. Purposes that advance the active goal score higher. The HUD shows the goal and its progress.
- **Cost.** No model calls inside the tick. Goal picks follow the same cost rules as purpose picks, capped at 8 model calls per game hour plus the daily cap. Tests never call a model.

## Milestones

Each milestone gets its own plan, is built task by task with a review of every task, then gets a final review with one round of fixes and a live check on the demo.

| # | Name | Delivers |
|---|------|----------|
| L1 | Animals | Creature system (table, kinds registry, spawning, the tick, API stream, viewer models and animations). Passive rabbit, sheep, cow and chicken, plus fish in water. Hunting with a hand or sword, meat and hides, cooked meats, and wool, feathers and leather. |
| L2 | Danger and combat | Gloomling and skitter; light levels and dark spawning; attack, flee and burn at dawn; Mimo's health regen and damage; the melee attack and bow shoot steps with arrows in the viewer; swords, bow, arrows and leather armor; fight and flee reflexes; doors; death by creature; threats in the model payload; HUD danger cues. |
| L3 | Bigger world | New blocks, trees, ores and biomes (taiga, swamp, birch forest). Surface boulders, outcrops and cave entrances. Bigger caves, underground lakes and deep lava. Mimo digs 2-wide, 3-tall passages. Gold and diamond tiers, iron armor, lanterns, ladders and fences. Creature seeds. Python/TS worldgen parity for all of it. |
| L4 | Purposeful life | The goal layer, goal choice by Jev or rules, goal progress, and purposes weighted by the active goal. A daily plan at dawn. The HUD goal line and memorial goals. Purposeful exploring (every trip has a reason). Fewer aimless loops. |
| L5 | Frontier | Danger and riches grow with distance from home: danger rings, tougher hostiles and one new hostile farther out, better drops, frontier ruins with loot chests, gloom dust put to use, and Mimo weighing risk against reward. |

## L1 Animals (detail)

### Creatures table and registry
- **World database table** `creatures(id INTEGER PRIMARY KEY, kind TEXT, x REAL, y REAL, z REAL, heading REAL, health REAL, state TEXT JSON, spawned_at REAL, next_at REAL)`, with an index on `(x, z)`. Created by an idempotent migration in `create_memory_tables` or a new world-schema hook.
- **Kinds registry** `backend/survival/creatures/kinds.py`, pure data: `name`, `health`, `speed` (seconds per block), `size`, `hostile` (bool), `damage`, `reach`, `drops` (item → (min, max) or chance), `biomes`, `herd` (min, max), `water` (for fish), and `flee_when_hurt`.
  - rabbit: 3 health, fast. Drops raw_rabbit and sometimes rabbit_hide.
  - chicken: 4 health. Drops raw_chicken and 0–2 feathers.
  - sheep: 8 health. Drops raw_mutton and 1–2 wool.
  - cow: 10 health. Drops raw_beef and 0–2 leather.
  - fish: 2 health, swims in water. Not hunted; it is where fishing's catch shows. Fishing stock stays as in M4, and more fish nearby slightly raises the catch chance.

### Spawning
- When Mimo first comes within 48 blocks of a chunk, herds spawn at deterministic spots in that chunk: seeded by the world seed and the chunk, 0–2 herds per chunk, chosen by biome.
- Numbers are capped: at most 24 passive creatures within 48 blocks, and 6 fish per water region.
- Animals come back slowly. A chunk that lost its animals regains one herd after 3 game days, and creature seeds (L3) add more.

### Creature tick
- Creatures run inside `advance_world` at step resolution, only within 48 blocks of Mimo.
- Each creature has a `next_at`, and acts when it comes due:
  - **Wander:** a random step to a standable neighbour cell, with pauses. Animals stay within 12 blocks of their spawn point.
  - **Flee:** when hurt, or when Mimo is hunting within 6 blocks, the creature runs away at double speed for about 8 blocks.
  - **Graze and idle** poses.
- Movement uses Grid standability: step up 1, drop up to 3, no water for land animals. Water only for fish.
- The cost is bounded: at most N creature actions per slice, and no path search. Moves are written to the creature row; there are no block edits.

### Hunting
- **New step** `attack(creature_id)`:
  - Reach 2.5 blocks. Duration is 0.6 s for a hand or 0.5 s for a sword.
  - Damage is 1 for a hand, 4 for a wooden sword, 5 for stone and 6 for iron.
  - The target takes damage, flees, and dies at 0 health. Its drops go straight into Mimo's arms, subject to the carry limits.
- **New purpose `hunt`:**
  - Scored by food need, in the needs band, with the late-day penalty. It rises for hungry pets and falls when food is carried.
  - It picks the nearest huntable animal within 32 blocks, not near a failed step, walks within reach, and attacks until the animal is dead or has fled out of range.
  - Traits matter: kind pets hunt a little less (a kindness or gentleness trait if one exists), bold pets a little more.
- **Cooking:** raw_beef, raw_mutton, raw_chicken and raw_rabbit cook into cooked_*. FOOD values go from roughly 8 raw to 25–35 cooked, and raw chicken has a small chance of sickness.
- **Crafting:**
  - wooden_sword: 2 planks and 1 stick.
  - stone_sword: 2 cobblestone and 1 stick.
  - iron_sword: 2 iron_ingot and 1 stick.
  - The toolmaking ladder also makes the next sword, but only after the pickaxe it needs.

### API and viewer
- **API:** `/api/mimo` adds `creatures`, a list of creatures within 48 blocks: id, kind, x, y, z, heading, health fraction, and state (walking, fleeing, idle, dead). Plus `creature_moves`: each creature's last move with from, to, started and ends, so the viewer can replay it 1.5 s behind the server.
- **Viewer models:** each kind gets a small blocky voxel model in the soft-pixel style: a white rabbit with long ears, a woolly sheep, a spotted cow, a small chicken, and a fish in water.
- **Animation:** a walk hop and bob, a head-down graze, a hurt flash and knockback, and a death puff that shows the drops popping.
- **Hunting visuals:** Mimo's attack swing plays at the target. A health bar appears over a creature for a few seconds after it is hit.
- **Minimap:** creatures show as small dots.

### Tests
- Registry values and spawn determinism.
- The creature cap.
- Wander stays standable and within range. Flee runs away.
- The attack step reduces health and drops loot into the inventory, with carry limits respected.
- Hunt validity and scoring.
- Cooking the meats.
- API shape and size, and GETs stay read-only.
- Viewer: pure model, animation and replay helpers.
- The headless sims still pass, and a new sim shows a pet hunting and cooking.

## L2 Danger and combat (outline; detailed in its plan)

- **Hostile kinds:**
  - gloomling: 20 health, slow. Melee for 3 damage every 1.2 s. Spawns on dark surface cells at night and in caves. Burns and fades at dawn if under the open sky. Drops gloom_dust, used later for lanterns or potions (L3).
  - skitter: 12 health, fast. Melee for 2. Lives in caves and dark places. Drops 0–2 string.
- **Light levels:** sky light is 15 by day, falling to 4 at night and 0 underground. Block light is 14 for a torch, 15 for a lantern and 13 for a campfire, dropping by 1 per block (Manhattan distance), computed on demand in a bounded radius. Hostiles spawn only where light is 7 or less, 16–40 blocks from Mimo, and never inside a claimed shelter room.
- **Hostile AI:** chase Mimo within 16 blocks, attack when in reach (cooldown), give up past 24 blocks, and despawn beyond 64 or at dawn.
- **Mimo's health:** regen of 1 per game minute while hunger is above 60. Damage flashes in the viewer, and the HUD shows a danger line ("A gloomling is close!").
- **Fight and flee reflexes:**
  - flee (priority 30): health below 35, or a hostile within 6 and no weapon. Mimo runs to home or away from the threat and ends up safe.
  - fight (priority 40): a hostile within 4, health 50 or more, and a weapon. Mimo attacks with the sword, or with the bow when the target is 5 or more blocks away and arrows are carried.
  - Both are data in the reflex registry.
- **Bow:**
  - Crafted from 3 sticks and 3 string. Arrows: 1 flint, 1 stick and 1 feather make 4. Flint comes from gravel (1 in 8 when mined).
  - The `shoot(creature_id)` step lasts 1.0 s, with a range of 16 blocks and a hit chance that falls with distance. It does 5 damage. The arrow flies in the viewer (a projectile arc) and is used up.
- **Armor:** a leather cap and tunic from leather cut damage by 20%; iron armor (L3) cuts it by 45%. The pet model shows the armor.
- **Door:** crafted from 6 planks. The M5 generator places a door in the door gap. Mimo's pathing treats it as passable; creatures treat it as solid. The viewer draws it open while Mimo passes through.
- **Death and memory:** death by creature goes on the memorial ("was caught by a gloomling on day 3"). Mimo remembers danger places. The model payload gets `threats`.

## L3 Bigger world (outline)

- **Blocks:**
  - Stone variants: granite, andesite, diorite and tuff-like "ashstone".
  - New ores: gold and diamond.
  - Trees: birch and spruce, with their logs, leaves and planks.
  - Biome blocks: snow_block, ice, mud, cactus, sugar_cane, pumpkin, melon, fern, dead_bush, mossy_cobblestone.
  - Building blocks: stone_bricks and brick (already present).
  - New blocks go at the end of the registry.
- **Biomes:** taiga (spruce, snow patches), swamp (mud, shallow pools, sugar cane), birch forest, and the existing desert, meadow, forest and alpine.
- **Terrain features:**
  - boulders and outcrops on hills;
  - cave entrances that open to the sky: sinkholes and hillside mouths;
  - caves that are larger and taller;
  - underground lakes, and lava pools below y = −3.
- **Bigger passages:** Mimo's staircases and tunnels are 2 wide and 3 tall, and escape stairs likewise where they fit. Home and passage claims follow.
- **Crafting tiers:**
  - gold and diamond pickaxes and swords;
  - iron armor;
  - lantern (iron plus torch);
  - ladder, fence, stone_bricks and door.
- **Creature seeds:** a rare drop from tall grass or leaves (1 in 60). Planted on grass, it grows into a random local passive animal in 1 game day. Farm purposes may plant them near home once a pen exists (a fence ring).
- **Parity:** Python/TS worldgen parity, and the fixture regenerates.

## L4 Purposeful life (outline)

- **Goals** are a registry: name, why, validity, progress (0–1 from state and memory), the purposes that advance them, and completion.
- **Example goals:**
  - First shelter (M5), then a better home (a bigger tier, stone walls).
  - Iron tools, then armor.
  - A full larder: a chest with food.
  - A safe yard: torches, a door, a fence.
  - A herd: creature seeds and a pen.
  - Map the land: explore memory from the exploring task.
- **Picking goals:**
  - Jev picks a goal at dawn, or when one completes or fails, from a small offered set with facts. The rules picker is the fallback. A goal lasts days, not minutes.
  - Purposes that advance the active goal get +15 score. Purposes that don't are capped in the leisure band unless they meet a need.
  - A "day plan" at dawn lists the goal's next steps and is shown in the HUD. Completing a goal is a notable event with a mood boost.
- **HUD and memorial:** the HUD shows the goal and its progress bar. The memorial lists the goals reached. The Jev payload carries the goal context.

## Owner input, 2026-09-24 morning

After watching the L3 preview (creatures and more terrain), the owner said:

> "even exploring should be purposeful though. also i feel like the farther from the center you wander the harder the enemies get but better loot or something idk"

The owner also asked for work to continue all day. As before, the controller makes the design calls below. Each can be changed later.

## L4 addition: purposeful exploring

- **Every trip has a reason.** Explore never picks just the least-explored ground. The reason comes from the active goal or a current need. Examples:
  - "Look for iron for my armor." Head toward unexplored stone, hills, cave mouths and sinkholes, or remembered cave entrances.
  - "Find birch wood," "find sheep for wool" or "find a creature seed." Head toward unexplored biomes of the right kind.
  - "Scout for a better home site."
  - "Map the land," the mapping goal.
- **Targets are scored by how likely they hold what the reason needs.** The inputs are explore memory patches, remembered places and landmarks, and the biome and height of the terrain.
- **A trip ends early on a find.** Mimo remembers the find as a place or landmark to come back to, and the next purpose follows up on it.
- **The reason is visible.** It shows in the thought, the event, the HUD and the Jev payload. Example thought: "Heading north to look for iron. My pickaxe needs it."
- **Rules pick the reason when Jev isn't used.** A headless check counts explores without a reason, and that count must be 0.

## L5 Frontier (outline; detailed in its plan)

- **The centre is home.** It is Mimo's built home, or its birthplace until a home stands. Distance from it sets a danger ring:

  | Ring | Distance from home | Danger |
  |---|---|---|
  | Home ground | under 48 | 0 |
  | Near wilds | 48–128 | 1 |
  | Far wilds | 128–256 | 2 |
  | Frontier | 256–512 | 3 |
  | Deep frontier | 512 and beyond | 4 |

  Rings move with home, for example when L4 builds a better home. Home ground plays exactly as today.
- **Harder enemies farther out.**
  - Hostiles that spawn in a ring get more health (+35 % per danger level) and hit harder (+1 damage per two levels).
  - The spawn cap grows by one per level.
  - From danger 3, gloomlings and skitters can be *elder* variants. They are tougher and faintly glowing in the viewer.
  - One new hostile, the ***thornback***, walks the far wilds and beyond (danger 2+). It is a slow, heavily armoured crawler that hits hard, and arrows are its weakness.
  - The names and designs are our own.
- **Better loot farther out.**
  - Hostile drops improve by ring. From danger 1, gloom dust gets likelier. From danger 2, gold nuggets and a new gem, *amber*. From danger 3, rare diamonds.
  - Mining in a ring has a small chance of an extra ore drop, rising per level.
  - Terrain never depends on home. Worldgen stays a pure function of seed and cell, so the Python and TypeScript ports stay identical.
- **Frontier ruins.**
  - A small ruin (stone-brick walls, mossy cobblestone, a chest) sometimes stands in a region. It is placed by worldgen, as a pure function of seed and region, in both ports.
  - The server rolls its chest's loot the first time Mimo opens it, by the ruin's danger ring. Nearer ruins hold food, arrows and iron. Farther ones hold gold, amber and diamonds.
  - Ruins are landmarks that exploring can aim for.
- **Loot is useful.**
  - Gloom dust with a lantern makes a *warding lantern*. It gives light 15, and hostiles won't step within 6 blocks of it.
  - Amber with iron makes *amber-studded armor*, a step past iron.
  - Diamonds and gold feed L3's tool ladder sooner.
- **Mimo weighs risk against reward.**
  - The Situation knows Mimo's ring and the ring of each target.
  - Rules offer frontier trips ("seek riches farther out") only when Mimo is armed, armored and healthy enough for that ring.
  - Flee and fight thresholds account for the ring.
  - Mimo heads home before dark when far out.
  - Jev sees each option's ring and its gear readiness.
- **Viewer.**
  - The HUD names the current ring ("Far wilds · danger 2").
  - The minimap shades the rings faintly around home.
  - Elder hostiles glow. The thornback gets its own voxel model.
  - Ruins and their chests are drawn.
- **Tests.**
  - A pet that stays near home lives as before.
  - A geared pet survives a trip to danger 2 and back with better loot.
  - An ungeared pet is never offered a frontier trip.
  - Ruin loot is deterministic from seed and ring.
  - Worldgen parity holds for ruins.

## Error handling and testing
- The same as the survival core: crashes are logged once, the tick is model-free, GETs are read-only, and migrations are idempotent. Every milestone keeps the headless sims green and adds its own sim check.
- Performance budget: creature simulation plus light checks cost no more than 20 ms per 60-game-second slice on average, with at most 24 passive and 8 hostile creatures active.

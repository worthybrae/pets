# Mind and Making: Design Spec

Two new sub-projects answer the owner's note from the night of 2026-09-25. They build on the Living World (L1–L4b) and on Bond (talking to Mimo).

## Why (the owner, 2026-09-25 night)

> "with conversation you should also be able to teach the pet things. for example you could tell them about all the idfferent animals or you could tell them about the armor and all that stuff. use a good enough memory system that mirrors humans and can handle a lot of historic experiences and thoughts. also continue making the world more complex through more block types or objects to create (use minecraft as an inspiration - it would be so cool for the pet to develop a computer or something like other people have done in minecraft after looking at a video from online or something. Thats where im trying to get at."

The owner approved designing on their behalf ("work all night and all of tomorrow"). Each decision below can change later.

## Part A: Mind (memory and teaching)

### How human memory works, and what we copy

People keep:
- **episodes**: what happened, when and where;
- **meaning**: facts and skills pulled out of many episodes;
- **thoughts**: reflections about themselves and their world.

Recall is cued. A thing is remembered when it is recent, when it mattered, or when it relates to what is happening now. Using a memory strengthens it. Sleep consolidates the day: it keeps what mattered, merges what repeated into a gist, and lets the rest fade. The Generative Agents design (a memory stream, scored by recency, importance and relevance, with reflections) is a proven shape for this. Mimo's differs in one way: **every memory's words are written by rules**, and a model only picks among them. That keeps it cheap, deterministic in tests, and safe.

### Decisions

- **One memory stream.** A table `mind_memories` holds every notable experience. Each item has:
  - `at` and `game_day`;
  - `kind`: `episode`, `gist`, `thought`, `told` or `lesson`;
  - `text`: rule-written, in Mimo's voice, at most 160 characters;
  - `about`: tags such as creature kinds, blocks, items, place kinds, `owner`, goal names and biomes;
  - `importance`: 1–10, set by the rules per event kind. For example: near death 9, a first sighting 6, a goal reached 7, a meal 1.
  - `feeling`: -2 to +2;
  - `strength`: starts at 1 and grows each time the memory is recalled;
  - `last_recalled`.

  Existing notable events feed it through a mirror keyed by event kind. The "memory mirror" and the "inbox mirror" share one hook: `events.MIRRORS`, which Bond's plan already names. Routine events never become memories one by one; the daily gist summarises them.
- **Recall.** `recall(cue, limit)` scores every candidate as `recency + importance + relevance`:
  - `recency` decays exponentially with a half-life of 2 game days, scaled up by `strength`, so rehearsed memories fade slower.
  - `relevance` is tag overlap plus keyword overlap with the cue, through a small synonym table (cow→cattle, beef, leather; armor→cap, tunic, iron).

  Recall is pure rules, bounded to the best 400 candidates by an indexed pre-filter, and never calls a model. Recalling a memory marks it recalled, which grows its strength. That write happens only in write contexts, never in a GET.
- **Sleep consolidates.** When Mimo falls asleep at night, the tick consolidates the game day just ended, in rules only and in one short transaction:
  - It writes a **gist** memory for the day ("Day 52: studied five animals, set out east, slept under the stars far from home"), built from the day's episodes and counts.
  - It merges repeated routine episodes into counts ("fished 9 times").
  - It keeps every episode of importance 6 or more whole.
  - It **forgets** episodes that are old, weak and unimportant. The score is importance × strength against age, and a forgotten episode survives only in its day's gist.
  - The stream is capped at 5,000 items per life. Gists and thoughts are never forgotten. A life of 100+ game days keeps every gist, every important moment, and a fading tail of the rest.
- **Thoughts (reflection).** Once a game day, at dusk, the worker's Chooser asks Jev one extra question in the purpose call it already makes (no extra call). The rules write 3–5 candidate insights from patterns in memory, for example:
  - "I keep coming home hungry from long trips. I should pack more food."
  - "Skitters come out near the caves at night."
  - "You visit me in the evenings."
  - "I love fishing by the lake."
  - "I have learned 20 things; there is so much more out there."

  Jev picks 0–2. A picked insight becomes a `thought` memory (importance 7). A few insight kinds carry a small, bounded behaviour nudge that is written in rules: pack +15 food, avoid a place at night, prefer a liked activity by +5 score. Without Jev, the rules keep the top-scoring insight every other day.
- **Teaching (through chat).** When the owner writes something that teaches, such as "cows give leather", "iron armor needs iron ingots", "skitters hate light" or "you can make a bow from sticks and string":
  1. The rules shortlist up to 5 **teachable lessons** whose words or synonyms appear in the owner's text.
  2. Jev picks one or none in the chat call it already makes, as a new chat question `teach`.

  The candidate lessons are:
  - L4b's journal lessons (32);
  - new **recipe lessons**: every armor, tool and weapon recipe, plus Part B's new ones, written from the recipe table ("An iron sword takes two iron ingots and a stick.");
  - **creature lessons**: every kind's drops and habits.

  A lesson taught this way:
  - is learned at once, and journalled with the source "from you" ("You told me that cows give leather.");
  - unlocks what that lesson unlocks, such as the flint and gold gates, or Part B's wiring;
  - becomes a `told` memory (importance 7, about `owner`);
  - earns the bond "kept promise" credit when Mimo later sees it true ("You were right, cows really do give leather!"), once B2's bond exists.

  The owner **cannot teach falsehoods**. Only real lessons can be picked, and when nothing fits, Mimo says it doesn't understand yet or isn't sure. The owner's words stay data.
- **Using memory.** Four places read it:
  - Chat replies (Bond B1) recall with the owner's message as the cue. The rule-written reply options can quote a memory ("I remember the night the skitter chased me...").
  - The daily story (B3) is built from the day's gist and its top memories.
  - The goal-choice payload gains the 3 most relevant thoughts.
  - The memorial lists the life's gists and thoughts.
- **Viewer.** A "Memories" panel sits beside the Journal. It shows:
  - recent memories;
  - "Moments that mattered", the most important;
  - "Thoughts";
  - a day-by-day gist timeline.

  The journal marks lessons learned "from you".
- **Cost.** There are no new model calls. Reflection rides the purpose call, and teaching rides the chat call. Luna is untouched.

### Milestones

| # | Name | Delivers |
|---|------|----------|
| M1 | Memory stream | `mind_memories`, the mirror from notable events, recall (recency/importance/relevance), rehearsal, sleep consolidation with gists and forgetting, the 5,000 cap, and the `/api/mimo` `memories` view |
| M2 | Thoughts and teaching | Daily reflection (rule insights, Jev picks, bounded nudges); teaching through chat (lesson shortlist, Jev's `teach` question, recipe and creature lessons, "from you"); chat replies that recall |
| M3 | Memories in the viewer | The Memories panel, gist timeline, "from you" in the journal, and the memorial's gists and thoughts |

## Part B: Making (a richer world and Mimo's computer)

### Decisions

- **More blocks and things to make (Minecraft-inspired), about 30 new ones.** Each new block gets a soft-pixel texture, a recipe, and a use Mimo actually has:
  - **Paper**: 3 sugar cane.
  - **Books**: 3 paper + leather.
  - **Bookshelf**: 6 planks + 3 books. It goes in homes, and a home with bookshelves makes Mimo content.
  - **Coloured wool**: dyes from flowers. Mimo decorates its home in its favourite colour, a trait.
  - **Clay bricks and a kiln**: clay is smelted into bricks, a better building block.
  - **Stairs and slabs**: better roofs, and stairs to upper floors.
  - **Glass panes and windows**: glass from sand; homes get windows.
  - **Trapdoors**.
  - **Copper**: copper ore is smelted into copper ingots, then copper wire. See the wiring bullet.
  - **Iron bars**.
  - **Flower pots**: a home touch.
  - **Signs**: Mimo names places. B2's naming shows here.
  - **Barrels**: storage.
  - **Composter**: turns spare plants into bone-meal-like fertiliser that speeds crops.
  - **Candles**: wax from bees is out of scope, so candles are made from tallow, from sheep.

  Blueprints use the new blocks: windows, bookshelves, a brick hearth, stairs to a loft. A "workshop" structure (a crafting table, furnace, kiln and barrel under one roof) becomes a goal.
- **Wiring.** Copper wire carries a signal. The parts are:
  - **Sources**: lever, button (a 1-second pulse), pressure plate, daylight sensor.
  - **Wire**: carries the signal up to 15 blocks, weakening like redstone.
  - **Logic**: repeater (delay and boost), inverter (NOT), and a comparator-like "joiner" (OR/AND by arrangement).
  - **Outputs**: lamp (glowing copper), door (powered opens), bell (a sound event).

  **A signal engine** runs server-side. It updates only circuits that changed, in a breadth-first pass per tick, bounded to 256 powered cells per world per tick. Cost is capped and circuits are tested headlessly. The viewer draws wire and lit lamps.
- **Knowledge gates the making.** Wiring needs the lesson "copper carries a spark" (a new L4b lesson). Mimo gets it one of three ways:
  - **the owner teaches it** (Part A);
  - **Mimo finds an old manual** in a ruin (L5; until L5, a rare find when digging deep copper);
  - **Mimo tinkers**: a curious pet with copper wire, a lever and a lamp sometimes discovers it by trying (a curiosity experiment purpose, "Tinker").

  Each larger machine has its own lesson (clock, latch, adder). The owner can teach those, or Mimo can work them out from the previous machine through a "Tinker" session.
- **The computer (a life goal: "Build a thinking machine").** The milestones are machines Mimo builds from rule blueprints on a flat "workshop yard":
  1. a lamp on a lever: its first circuit;
  2. an automatic door: a pressure plate opens the home door;
  3. a night-light: a daylight sensor feeds an inverter, which drives a lamp;
  4. a clock: a loop of repeaters that ticks;
  5. a memory cell: an RS latch built from two inverters, which remembers one bit;
  6. a counter: 4 latches and a clock that count;
  7. **Mimo's computer**: a 4-bit counter with a lamp display that **counts the game days Mimo has lived, in binary**. It has a lever to show and hide it, and a bell that rings at dawn. Mimo says "I built a machine that remembers how long I've been alive!"

  Each machine is a structure (the existing structures table) with a blueprint and a working test: the signal engine, fed its inputs, gives the right outputs. After the computer, a repeating "improve the machine" goal can widen it to 8 bits, or add a "calculator" that adds two lever-set numbers on the lamps. This is the "develop a computer like people have done in Minecraft" aspiration, made achievable and legible.
- **"After looking at a video online."** Mimo has no web access, for safety and cost. Its equivalents are **the owner teaching it** (the owner has seen the video) and **books and manuals** it finds or makes. The owner can say "people build computers out of redstone" and Mimo takes up the thinking-machine goal as an owner-suggested goal (Bond B2) once it knows wiring.
- **Viewer.**
  - Every new block gets a texture.
  - Wire is drawn flat, dim when off and bright when on.
  - Lamps glow when lit.
  - The computer's lamp display is readable in the scene, with a HUD caption ("Mimo's computer: day 13 = 1101").
  - A "Workshop" panel lists the machines built.

### Milestones

| # | Name | Delivers |
|---|------|----------|
| T1 | New blocks and crafts | About 30 blocks and items with textures and recipes. Homes with windows, bookshelves, bricks and stairs, and the workshop structure. Python/TS parity kept, and worldgen untouched apart from the new ores (copper already exists). |
| T2 | Wiring | Copper wire, sources, logic parts and outputs; the signal engine (bounded); the "copper carries a spark" lesson, and its three ways in; the first circuits (a lamp on a lever, an automatic door, a night-light); the viewer's wire and lamps. |
| T3 | The thinking machine | The clock, memory cell, counter and computer blueprints with engine tests; the "Build a thinking machine" life goal and its milestones; the Tinker purpose; the HUD caption and Workshop panel. |

## Order (the controller's ruling; the owner can reorder)

Bond B1 (Talk) is being built and finishes first, since teaching needs the chat. Then:

**M1 → M2 → T1 → T2 → T3 → M3 → Bond B2 → Bond B3 → L5 Frontier**

M3 moves after T3 so the viewer work is batched. B2 and B3 (the bond meter, requests, inbox, daily story) come after, and they gain from memory (the story reads gists). L5's ruins then carry the old manuals.

## Error handling and testing

- No model call runs inside the tick. Consolidation, recall, the signal engine and tinkering are rules.
- Reflection and teaching ride the worker's existing Jev calls, and fall back to the rules on any failure.
- Every new hook is crash-guarded (`once.log_once`). GETs never write; recall's rehearsal write happens only in write paths. New tables are created idempotently, and an archive without them reads as empty.
- Headless tests cover:
  - memory: the cap and forgetting over a 30-game-day life, recall ranking, consolidation writing one gist per day, and teaching mapping only to real lessons (a falsehood is refused);
  - the signal engine: every gate's truth table, the clock's period, the latch holding, the counter counting;
  - the computer showing the day count after N days;
  - tick cost within budget with a large circuit.
- L4a's and L4b's headless checks stay green.

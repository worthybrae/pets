# Wild World: Design Spec

The next sub-project after L5 Frontier. It builds on everything on `worthy/23_09_2026/survival_core`: the survival core (lives, vitals, the brain, food, building), the living world (L1 animals, L2 danger, L3 the bigger world, L4a/L4b a purposeful and curious life, L5 the frontier), Bond (talk, the inbox, the daily story) and Mind and Making (memory, teaching, the computer).

## Why (the owner, 2026-09-27, before bed)

> "can we make the world even more interesting and compelling? i kinda want to make it hard for the pet to survive unless you talk to it and help teach it. also just maek the world even crazier and better and more compelling… keep on iterating and making this better"

Today a pet left alone does fine. It knows how to cook, light a fire, build a house with a door and sleep in a bed from the moment it hatches. The owner's part is optional. This sub-project makes the owner's teaching the thing that keeps a young pet alive, and makes the world itself stranger: seasons, storms, red moons, falling stars and wolves.

## Words used here

- A **game day** is 3,600 game seconds, a real hour at production scale. A **game minute** is 60 game seconds, a real minute. This spec never says "game hour": the code's `triggers.HOUR` is 3,600 game seconds (a game day) and `curiosity.CLOCK_HOUR` is 150.
- **Wild** and **gentle** are the two difficulties (W1). **Untaught**, **taught** and **liar** are the owner conditions the gates run.
- A **lesson** is a row in `journal.LESSONS`. A **survival lesson** is a new kind of lesson ("survival"), named `wild:<name>`, that unlocks behaviour a wild pet does not have at birth.
- A **knock** is a painful experience that may teach a survival lesson by trial and error.
- A **wonder** is something Mimo meets and does not understand. It becomes a question to the owner.

## Goals

- A new wild pet hatches knowing only instinct. Survival knowledge (safe and poison food, fire, cooking, keeping food, light, shelter, the bed, wounds and herbs) is lessons.
- The owner can teach every lesson in one sentence, in the chat or by answering Mimo's questions. Mimo also learns alone, slowly and painfully.
- Mimo asks the owner when it meets something it doesn't understand, waits a while for the answer, then risks it.
- An untaught pet clearly struggles and may die. A taught pet thrives and still reaches the late game (the computer route).
- Nobody's current pet dies from the upgrade. Old worlds are grandfathered as gentle.
- The world gets seasons (a hard winter), weather (rain, storms with lightning and fire, snow, fog), red moons, meteor showers with star metal, wolves you can tame and aurora nights.
- Every new thing is a lesson, a question, a Mind moment and inbox news in Mimo's own voice, and the viewer draws it.
- The server owns the truth, the tick stays bounded, no model call runs in the tick, and worldgen stays a pure function of seed and cell in both ports.

## Milestones

Each milestone gets its own plan, is built task by task with a review of every task, then gets a final review with one round of fixes, its headless gate, and a live check on the demo stack.

| # | Name | Delivers |
|---|------|----------|
| W1 | A newborn in a wild world | Difficulty (wild, gentle), 11 survival lessons and their gates, instinct, sickness, poison lookalikes, spoilage, wounds, cold nights, learning by knocks, Mimo's questions (inbox, chat, answer chips), yes/no answers, grandfathering, the viewer's ailments and questions |
| W2 | Weather and seasons | A 40-day year of four 10-day seasons, weather by season, rain, snow, fog, thunderstorms with lightning and tree fires, frozen lakes and snow cover as overlays, the hard winter, 7 more lessons, the "Ready for winter" goal, the cloak, the hearth, smoked meat, the viewer's sky, particles, flash, fire, snow and ice |
| W3 | Wild nights and strange skies | Red moons every 7th night, meteor showers with craters, hot rock and star metal (a new top tier), wolf packs and a tamed wolf companion, aurora nights, 4 more lessons, the viewer's moons, meteors, craters, wolves and auroras |
| W4 | The Glimmer | Sketch only (below). Not planned now. |

---

## W1: A newborn in a wild world

### Difficulty

- A life has a difficulty, `state["difficulty"]`: `"wild"` or `"gentle"`. It is set at hatch and never changes.
- `POST /api/lives/hatch` takes an optional body `{"difficulty": "wild" | "gentle"}`. The API's default is **wild**. There is no UI for choosing yet.
- `hatch(registry, rng, timestamp, difficulty="gentle")`: the Python function's default stays gentle, so the 53 test files that hatch pets keep measuring what they measure today (resolution 2).
- A world with no `difficulty` key (every world made before W1: the demo, and the owner's real world if merged) is **gentle**. The first tick after the upgrade writes `"gentle"` and grants every survival lesson (below).
- `/api/mimo` gains `difficulty`.

| | Gentle | Wild |
|---|---|---|
| Survival lessons at birth | All of them, from every milestone, marked "knew from the start" | None: instinct only |
| Sickness as a state (tummy ache, chill) | Off. Food keeps today's rules: a red mushroom (or a nightberry) takes 10 health, raw chicken is a 25 % gamble for 4 | On |
| Festering wounds | Off | On |
| Spoilage | Off | On |
| Questions to the owner | None (nothing is unknown) | On |
| W2 weather and seasons, W3 nights | On | On |

Gentle is today's game plus W2 and W3. The difference between the two is what the pet knows and which W1 hazards exist (resolution 1).

### What a wild newborn knows (instinct)

- Eat when hungry: apples, carrots, bread, brown mushrooms, fish and meat are familiar foods. Raw fish and meat carry a sickness risk until Mimo knows cooking.
- The eat-now reflex when starving (hunger under 15).
- Flee danger (L2's flee reflex), surface when drowning, avoid drops, get warm at a remembered sheltered spot (a cave or overhang it found).
- Sleep at night, where it stands or at a remembered sheltered spot.
- Everything else L1 to L5 and Making do today, except what the survival lessons below gate. It gathers, digs, crafts tools and weapons, hunts, fishes, farms, explores and studies (L4b's journal lessons still come from investigating).

Untried foods: red berries (which look like nightberries), red mushrooms and sunleaf. A wild pet carries them but eats one only after it asks and waits (below), or when starving.

### The survival lessons

Each is a `journal.LESSONS` entry of kind `"survival"` with thing `wild:<name>`. The colon keeps them out of L4b's curios (nothing is investigated to learn them), as Mind's `recipe:` lessons are. The fact is the one sentence the owner can teach. Facts never hold a negation word (`lessons.NEGATIONS`) and say one side of a pair only, so the doubt rules can read them (resolution 7).

| Lesson | Fact | Unlocks for a wild pet | Without it |
|---|---|---|---|
| `wild:berries` | Bright red berries are safe to eat. | Eats and forages the red-berry group without asking | Untried: asks, waits, tastes one |
| `wild:nightberries` | Nightberries, the dark purple berries with pale specks, are poison. | Tells nightberries from berries: never picks or eats them, drops any it carries | Sees both bushes as "red berries" |
| `wild:red_mushroom` | Red mushrooms are poison. | Never picks or eats them | Untried |
| `wild:sunleaf` | Sunleaf, the little yellow herb, cures sickness when eaten and cleans a wound. | Picks up to 2 to carry; the `take_herb` reflex eats one when sick; dresses a wound with one | Untried; a sick pet may nibble one by chance |
| `wild:bandage` | A bandage of wool on a wound stops it festering. | The bandage recipe (1 wool makes 2, no station) and the dress step | Wounds fester |
| `wild:fire` | Two logs and three sticks make a campfire, and a fire keeps you warm at night. | The campfire recipe; warm_up lights one; camps get one | No campfire; warm_up only walks to a sheltered spot or a furnace |
| `wild:cooking` | Meat and fish cooked on a fire are safe to eat and fill you up far more. | The cook purpose | Eats meat and fish raw |
| `wild:keeping` | Raw food goes bad in a day or two, and food in a chest keeps twice as long. | Cooks raw food before it turns, stores spare food in a chest, drops spoiled food | Eats spoiled food when hungry |
| `wild:light` | Torches keep the dark creatures away, because they only come out where it is dark. | light_up (torches round home), torches at camps, the safe_yard goal | Home stays dark at night |
| `wild:shelter` | A shelter with walls, a roof and a door keeps out the cold and the dark creatures at night. | build_shelter, the door recipe, improve_home, camp (L4b's dug-in camp), first_shelter and every goal that needs a built home | Sleeps out or in a natural sheltered spot |
| `wild:bed` | Six planks make a bed, and sleep in a bed rests you best. | The bed recipe and furnishing the shelter with one | Sleeps on the floor (+0.2 energy a second, not +0.35) |

Nothing else is gated. A wild pet still learns L4b's 32 journal lessons by meeting things, Mind's recipe and creature lessons from the owner, and Making's lessons by tinkering or teaching. The coal lesson still teaches the torch recipe; `wild:light` is what makes Mimo put torches round its home.

### Hazards

Five hazards, each one sentence the owner can teach. All numbers are for a wild pet.

**1. Poison lookalikes.**

- Two new plants, placed by worldgen in both ports: `nightberry_bush` / `nightberry_bush_ripe` and `sunleaf` (placement under "Worldgen").
- A ripe nightberry bush looks like a berry bush with darker berries. Picking it gives 3 `nightberries` and leaves an unripe bush that turns ripe again in 2 game days, like berries.
- Until Mimo knows `wild:nightberries`, the two bushes and their items are one group, "red berries", to it. Forage picks from both. A meal of "red berries" eats from the items it carries in proportion to their counts (a seeded roll per eat step), so an untaught pet eats nightberries at their share of what it picked.
- Eating a nightberry or a red mushroom: 5 health at once and a tummy ache.
- After a sickness from the red-berry group, Mimo shuns the whole group for `SHUN` = 2 game days ("Berries made me sick. I'll leave them alone for a while."), unless the knock taught it the difference.
- The owner sees the difference: the viewer draws the two bushes apart, and the inventory lists nightberries by name.

**2. Sickness with symptoms and remedies.** One sickness at a time (`state["ailments"]["sick"]`); a new one keeps the longer of the two.

| Kind | Caused by | Symptom (HUD and Mimo's words) | Lasts | Drain | Also |
|---|---|---|---|---|---|
| Tummy ache | A poison plant (sure), a raw meal (chance below), spoiled food (0.6) | "My tummy hurts." | 12 game minutes | 1 health per 45 game s (16 over a full bout) | Hunger drains ×1.5 |
| Chill | A cold night (below) | "I'm shivery and hot." | 25 game minutes; each second resting or asleep with warmth 60 or more counts double | 1 health per 60 game s (25) | Energy drains ×1.5 |

- No health regenerates while Mimo is sick. Mood's target falls 15.
- **Remedy:** eating one sunleaf ends any sickness at once. A pet that knows `wild:sunleaf` and carries one eats it through the `take_herb` reflex (priority 45, between eat_now and warm_up). A sick pet that knows sunleaf but carries none gets `find_herb` in the needs band (75) while a sunleaf it has seen lies within 64 blocks. A sick pet that does not know sunleaf may nibble one by instinct: with chance 0.4 a sickness, `nibble` walks to a sunleaf within 16 blocks and eats it. It feels better that once and learns nothing: `wild:sunleaf` comes only from the owner (resolution 29).
- **Raw meals:** a meal (the eat steps of one batch) that holds raw food rolls once, at the highest chance among its raw items: raw chicken 0.35, raw beef, mutton or rabbit 0.2, raw fish 0.1.
- Sickness can kill. When the sickness drain is the largest damage in the killing step, the cause is `"sickness"` ("fell sick and never got better"). `vitals.CAUSE_ORDER` gains it after starvation.

**3. Food that spoils (wild only).**

- Perishable food ages. Shelf life in arms, in game days: raw meat and raw fish 1.5; berries, nightberries and brown mushrooms 2; cooked meat and fish 4; apples and carrots 5; bread 6. Sunleaf, seeds and wheat never spoil. W2 adds smoked meat, which never spoils.
- In a chest food ages half as fast. In winter (W2) it ages a third as fast, in arms or chest.
- Each perishable item keeps at most `LOTS` = 3 lots, `[count, wear]`, with `wear` from 0 to 1 (the share of its shelf life used). Food added within a game minute of the newest lot joins it; a fourth lot merges into the oldest. Eating, storing and taking move the most worn food first. A lot that reaches wear 1 becomes that many `spoiled_food`.
- Spoiled food fills 4 hunger and gives a tummy ache with chance 0.6. An untaught pet eats it only when hungry (under 50) with nothing else to eat. A pet that knows `wild:keeping` drops it, or puts it in the composter (Making) when one stands at home.
- `wild:keeping` also lifts cook's score by 20 while raw food carried is past wear 0.5, and makes build_storage put food beyond a day's worth in the chest.

**4. Wounds that fester (wild only).**

- A creature's blow (a hostile's, or a wolf's in W3) that does 2 or more damage after armor opens a wound with chance 0.35. Leather armor keeps a skitter's blow under 2. Mimo has at most one wound; a new blow while wounded does not open another.
- While a wound is open no health regenerates.
- Undressed for 10 game minutes, it **festers**: 1 health per 90 game s, and mood's target falls 10.
- A wound heals by itself 1 game day after it opened, festering or not. The most a festering wound can take is about 33 health.
- **Dressing** (the `dress` step, 2 s): a bandage (`wild:bandage`) or a sunleaf (`wild:sunleaf`). The owner's care bandage dresses it too, besides its +25 health. A dressed wound stops festering at once and closes 5 game minutes later. Both lessons come only from the owner (resolution 29), so an untaught pet's wound festers until it heals by itself, unless the owner's care bandage dresses it.

**5. Cold at night (wild only).**

- Warmth targets are today's. At night in the meadow an unsheltered pet drifts to 30.
- Each night the tick counts the game seconds with warmth under `CHILL_BELOW` = 35. At dawn: 5 game minutes or more gives a chill with chance 0.6; 15 game minutes or more, or any freezing that night, gives one for sure.
- A shelter (+45, so 75) or a fire within 4 blocks (100) keeps the count at 0. A natural sheltered spot counts as a shelter for warmth, as today.

### Learning alone: knocks

A knock is a painful experience. Nine survival lessons list the knocks that can teach them; `wild:sunleaf` and `wild:bandage` are never learned alone (resolution 29). On each knock the tick rolls (a seeded roll, `nature.roll`) against a chance that grows with every knock of that lesson: `first + step × (knocks so far)`, times `0.8 + curiosity trait / 250` (0.8 to 1.2). Some experiences teach for sure. A lesson learned this way is logged as a notable `figured` event ("Pip worked out that cooking makes meat safe."), is a discovery for curiosity, and is journalled "worked out myself".

| Lesson | Knock | First | Step | Sure when |
|---|---|---|---|---|
| `wild:berries` | | | | Eats from the red-berry group and is not sick. From then on it trusts every red berry, nightberries too, until it learns them apart |
| `wild:nightberries` | Sick from a nightberry | 0.25 | 0.15 | |
| `wild:red_mushroom` | | | | Sick from a red mushroom (today's rule) |
| `wild:fire` | A chilled night | 0.15 | 0.15 | It stands within 8 blocks of a fire it did not make (a lightning fire in W2, hot rock in W3), or smelts at a furnace for the first time |
| `wild:cooking` | Sick from a raw meal, knowing fire | 0.25 | 0.15 | |
| `wild:keeping` | Sick from spoiled food, or food spoils in its arms or chest | 0.20 | 0.15 | |
| `wild:light` | A hostile's blow at night | 0.10 | 0.10 | |
| `wild:shelter` | A bad night: a chill at dawn, or a hostile's blow that night | 0.25 | 0.20 | |
| `wild:bed` | A night asleep on the floor of a sheltered spot | 0.10 | 0.10 | |

Knock counts live in `state["wild"]["knocks"]`. The first chances are one step (0.05) lower than first written, as low as the "not hopeless" criteria allow (resolution 29): a second step left untaught pets that knew only 6 or 7 lessons alone by day 60. The expected cost of learning alone is 2 to 4 knocks a lesson, so an untaught pet pays with a handful of sick days, wounds and cold nights in its first weeks.

**Only the owner teaches sunleaf and bandages** (resolution 29). A pet cannot guess that an herb cures a sickness, or that wool on a wound stops it festering. No knock teaches either: an instinct nibble cures one sickness and teaches nothing, and a wound festering while Mimo carries wool teaches nothing. Mimo still asks about the herb, its tummy and its wound (the wonders below), and the owner's answer or teaching (Mind's teaching, the chat, a chip) is the only way in. Without them every sickness an untaught pet catches runs its course, and every wound festers until it heals by itself.

### Mimo asks the owner

**Wonders.** A wonder is a registry entry (`wild.WONDERS`): an id, a trigger read by the tick, Mimo's words, the lessons that answer it, and two or three answer chips, each mapped to the lessons it teaches, to "false" or to nothing. A wonder asked as a yes-or-no question (red berries, red mushroom, raw meat; W2's fog; W3's red moon) also has a yes-claim and a no-claim, fixed sentences for the chat. The tick marks a wonder as met in `state["wild"]["wonders"]`. It never posts anything itself.

| Wonder | Met when | Mimo asks | Chips (each teaches, or is false, or teaches nothing) |
|---|---|---|---|
| `red_berries` | A ripe berry or nightberry bush within 8 blocks after a walk, first time | "I found red berries by the lake. Are they safe to eat?" (where, from `inbox.place_words`' compass) | "Yes, bright red berries are safe." (berries) · "The dark purple ones are nightberries, and they're poison." (nightberries and berries) · "They're all poison." (false) |
| `red_mushroom` | A red mushroom within 8 blocks, first time | "There are red mushrooms here. Can I eat them?" | "Red mushrooms are poison." (red_mushroom) · "Sure, they're tasty." (false) |
| `sunleaf` | A sunleaf within 8 blocks, first time | "There's a little yellow herb here. What is it for?" | "That's sunleaf. It cures sickness and cleans wounds." (sunleaf) · "It's just a weed." (nothing) |
| `tummy` | First sickness | "My tummy hurts after eating those berries. What helps?" | "Eat sunleaf, the little yellow herb." (sunleaf) · "Rest. It will pass." (nothing) |
| `raw_meat` | First raw meat or fish carried | "Can I eat this raw beef?" | "Cook it on a campfire first." (fire and cooking) · "Raw is fine." (false) |
| `cold_night` | First night with 2 game minutes under warmth 35 | "It's so cold tonight. How do I stay warm?" | "Two logs and three sticks make a campfire." (fire) · "Build a shelter with a roof and a door." (shelter) · "Just keep moving." (nothing) |
| `dark_creature` | First hostile that comes after Mimo | "Something with glowing eyes came at me in the dark! How do I keep them away?" | "Torches keep them away." (light) · "Sleep in a shelter with a door." (shelter) · "They just want to play." (nothing) |
| `wound` | First wound | "A skitter cut me and it won't stop hurting. What should I do?" | "Wrap it in a wool bandage." (bandage) · "Press sunleaf on it." (sunleaf) · "Leave it alone." (nothing) |
| `spoiled` | First spoiled food | "My raw beef went bad! How do I keep food fresh?" | "Food in a chest keeps twice as long." (keeping) · "Cook it before it turns." (cooking and keeping) |
| `hard_floor` | Third night asleep on the floor | "The floor is so hard to sleep on." | "Six planks make a bed." (bed) · "You'll get used to it." (nothing) |

The place, food or creature in Mimo's line is filled from what it met; the table shows one filling ("by the lake", "those berries", "raw beef", "A skitter"). A wonder whose lessons Mimo already knows is never asked, and an open question whose lessons it learns another way closes as "figured out".

**Posting a question.** A Talker chore, `ask_wonders`, runs outside the tick after the mirrors:

- It posts the oldest met wonder that is not asked yet: an inbox item of kind `"ask"`, `data = {"ask": "wonder", "wonder": id, "chips": [...], "answer": null, "closed": null}`, and the same words as a Mimo line in the chat (`teaching.say`). The inbox's opt-in browser notification picks it up like any unread item.
- At most `OPEN_MOST` = 3 questions are open at once. A new one is posted at least `ASK_GAP` = 5 game minutes after the last. The chips' order is a seeded shuffle, so the true one is not always first.
- A wild pet asks each wonder once a life. Gentle pets never ask.
- The words come from rules only, in Mimo's voice (`replies.in_my_voice`), through `inbox.asking` so they use the owner's name when Mimo knows it.

**Hesitating.** A question makes Mimo wait `HESITATE` = 8 game minutes (8 real minutes at production scale) before it risks what it asked about. It risks only when it needs to:

- An untried food is tasted (one serving, never a handful, as `purposes.meal` already does for poison) when hunger is under 50, no known-safe food is carried, and the question has waited HESITATE or could not be posted (3 already open). Starving (under 15), eat_now tastes at once.
- A wonder that is not about food (a symptom, a wound, the cold, a creature) holds nothing back. Mimo goes on by instinct, and the knocks apply.
- While Mimo waits, its thought says so ("I asked about the red berries. I'll wait a bit before I try one.").

**Answering.** Three ways, all rules, all through Mind's teaching (`teaching.teach_lesson`), so a lesson taught by an answer is "from you", a told memory, and later "You were right" when Mimo sees it true:

1. **A chip** in the inbox, through Bond's existing `POST /api/mimo/inbox/{id}/answer` (today it takes `{"text"}` to name a place). A question's answer is `{"choice": n}`. The chip's lessons are taught at once in one short transaction, the item is closed (`"taught"`, `"doubted"` or `"noted"` for a chip that teaches nothing) and Mimo answers in the chat. The naming answer's error codes hold: 404 for no such question, 400 for one already closed or a choice out of range, 409 when Mimo died. Chips are rule-written text, not owner words; only the index is stored.
2. **Yes or no in the chat.** While a yes-or-no question is open, an owner line that names no lesson's subject and opens with a yes-word (yes, yeah, yep, yup, sure, of course, ok, okay, fine, safe) or a no-word (no, nope, nah, don't, never, careful, poison) answers the newest open yes-or-no question: the Talker's HEARING hook `answer` swaps the line for that question's yes-claim or no-claim before `lessons.claims` reads it. For red berries they are "Red berries are safe to eat." (taught) and "Red berries are poison." (doubted); for red mushrooms, "Red mushrooms are safe to eat." (doubted) and "Red mushrooms are poison." (taught); for raw meat, "Raw meat is safe to eat." (doubted) and "Cooked meat and fish are safe to eat." (taught). A bare yes or no with no yes-or-no question open teaches nothing. The owner's own words are still stored and shown as they are.
3. **Anything else in the chat.** `lessons.claims` reads it as today. A line that teaches a lesson closes every open question that lesson answers. Teaching without being asked works the same way at any time.

**Wrong answers.** A false chip, or a claim that contradicts the lesson, is doubted as Mind doubts today: nothing is learned, the question closes as `"doubted"`, and Mimo says "Hmm, I'm not sure that's right. I'll be careful." It then acts as if nobody answered: it hesitates, and risks one taste only when it must. A liar owner can never make Mimo eat poison by the handful, skip cooking on purpose or leave a wound undressed on purpose. The worst a wrong answer costs is what no answer costs.

### Teaching the survival lessons

`lessons.claims` must teach every line in the first column and doubt every line in the second. These lines are the gate's scripted owner (below) and a test table:

| Lesson | Teaches | Doubted |
|---|---|---|
| berries | "Red berries are safe to eat." | "Red berries are poison." |
| nightberries | "Nightberries are the dark purple ones, and they are poison." · "The purple berries are poison." · "Don't eat the purple berries." | "Nightberries are safe to eat." |
| red_mushroom | "Red mushrooms are poison." · "Never eat red mushrooms." | "Red mushrooms are safe to eat." |
| sunleaf | "Sunleaf cures sickness and cleans wounds." | "Sunleaf is poison." |
| bandage | "A wool bandage stops a wound festering." | |
| fire | "Two logs and three sticks make a campfire." · "A campfire keeps you warm at night." | "Five logs make a campfire." |
| cooking | "Cooked meat and fish are safe to eat." · "Cook your meat on a fire." | "Raw meat is safe to eat." |
| keeping | "Food keeps twice as long in a chest." | |
| light | "Torches keep the dark creatures away." | "Torches bring the dark creatures." |
| shelter | "A shelter with a roof and a door keeps you safe at night." | |
| bed | "Six planks make a bed." | "Two planks make a bed." |

What this asks of `lessons.py` (the plan decides how):

- `named` reads the part after `wild:`. TEACH_SYNONYMS gains purple/dark/night (for nightberries), herb/sunleaf, bandage/wrap, campfire/fire, torch/light, shelter/house/home, poison/poisonous/toxic.
- OPPOSITES gains safe/fine/edible against poison/poisonous/toxic/bad, raw against cooked, keep-away against bring/attract, and warm against cold.
- **Warnings teach.** A sentence that opens with "don't eat", "do not eat", "never eat" or "avoid" followed by the subject of a poison lesson reads as "<subject> are poison". Followed by "raw meat" or "raw fish", it teaches cooking. Without this, `NEGATIONS` would doubt a true warning.
- "Cook your meat on a fire." opens with a command. A command stays a request (Bond B2) and also teaches when its words fit a survival lesson's fact with no contradiction. This is narrower than B2's pre-flight rule ("commands teach nothing"), which stays for every other lesson (resolution 8).

### Worldgen

- Two new plants in both ports, placed only in columns where `plant_stack` found nothing before (after tall grass fails), so no plant anywhere moves or changes. Never within the legacy clearing (`LEGACY_RADIUS`). Both are `replaceable: true`, like tall grass, so a build that meets one simply replaces it.
- `nightberry_bush_ripe`: meadow and forest-edge grass (berries' ground), hash channel 160, one per 150 such bare columns (about two for every three berry bushes).
- `sunleaf`: grass, moss or mud in meadow, forest, birch forest, taiga and swamp, hash channel 161, one per 180 bare columns. A sick pet has about four within 16 blocks in a meadow.
- New blocks go at the end of `shared/blocks.json`: `nightberry_bush`, `nightberry_bush_ripe`, `sunleaf`. The fixture regenerates and both parity suites run.
- Renewal: a picked nightberry bush ripens again after 2 game days. A picked sunleaf comes back in its chunk like a mushroom (one a chunk a game day, at most 2 a chunk).
- Old worlds gain these plants only on bare natural ground they never edited. A grandfathered pet knows both lessons, so nothing it does near home changes (resolution 12).

### Grandfathering

- A world with no `difficulty` key reads gentle, and its first tick writes `"gentle"`.
- A gentle pet's first tick (an old world's, or a new gentle hatch's) grants every survival lesson of every landed milestone: rows in `memory_knowledge` with fact `"lesson"` and a second fact `"born_knowing"`. It logs nothing, fires no discovery, writes no memory and asks for no choice, like curiosity's `learn_quietly` on an old save. Lessons known from birth don't count in the tallies that read how many lessons Mimo learned (the journal payload's count, investigate's and tinker's facts, Mind's "I have learned 20 things" insight), so a gentle pet's choices and words stay as they are today.
- `state["wild"]["granted"]` holds the milestone version granted. When W2 or W3 lands, a gentle pet is granted the new lessons on its next tick the same way.
- The grant runs only in the tick of a living pet. An archive (a dead pet) is never written.
- A gentle world never has a sickness state, a wound or a lot. The gate checks this.

### State and API

No new table (as in L5). New state, each read with a default so older saves and archives read as empty:

- `state["difficulty"]`.
- `state["wild"]`: `knocks`, `wonders` (`{id: {"met_at", "asked_at", "item", "closed"}}`), `shun` (`{group: until}`), `night_cold` (seconds under 35 tonight), `floor_nights`, `granted`, and `lost` (the health a wild pet lost to its hazards: the drain of a sickness or a festering wound, and poison; the gate reads it).
- `state["ailments"]`: `sick` (`{"kind", "since", "left"}` or null) and `wound` (`{"since", "festering", "dressed_at"}` or null).
- `state["lots"]` (`{item: [[count, wear], ...]}`) and each chest's `"lots"` beside its contents in `state["chests"]`. The lots of an item always sum to its count (an invariant the tests check after every step kind).

`/api/mimo` gains `difficulty`, `ailments`, and in `inbox` the open questions with their chips. `POST /api/mimo/inbox/{id}/answer` takes `{"choice": n}` for a question besides `{"text"}` for a name. The journal view gains `source`: `"from_you"`, `"figured"` or `"from_start"` (Mind's `from_you` stays).

### Moments, news and voice

- Events (third person in the log, first person everywhere Mimo speaks, through `in_my_voice`): `sick` ("Pip ate nightberries and felt sick.", exists), `cured` ("Pip ate sunleaf and felt better."), `wound` ("A skitter cut Pip."), `festering` ("Pip's wound is festering."), `dressed` ("Pip wrapped its wound in a bandage."), `spoiled` ("Pip's raw beef went bad."), `chill` ("Pip caught a chill in the night."), `figured` ("Pip worked out that cooking makes meat safe.") and `asked` ("Pip asked you whether red berries are safe to eat.").
- Mind moments: `figured` 7 (+2, kind lesson), `cured` 4 (+1), `wound` 4 (-2), `festering` 5 (-2), `chill` 5 (-2), `spoiled` 2 (-1, "{n} of my food went bad."), `asked` 3 (0, about owner).
- Inbox: `figured` as news ("I worked it out myself: ..."), and `festering`, `chill` and a sickness through the danger writer (at most once a game day each).
- The voice table test (`test_survival_voice.py`) gains every one of these texts.
- `teaching.confirms` learns the events that show each survival lesson true: berries by `ate` (red berries), cooking by `cook`, fire by a campfire placed, sunleaf by `cured` or `dressed`, bandage by `dressed`, shelter by a night in its built shelter, bed by a night in a bed, light by a night with no hostile within 8 blocks of home.

### Viewer

- New textures: nightberry bush (the berry bush's shape, dark purple berries with pale specks), sunleaf (a low yellow-green rosette), the items nightberries, sunleaf, bandage and spoiled food.
- The pet: a sick tint (green, 0.25), droopy ears and a slower hop when sick, a shiver every few seconds with a chill, a white wrap on its side when a wound is dressed, a red mark while it festers, and a "?" bubble for 10 s when it asks.
- HUD: an ailment line ("Tummy ache · 7 min", "Chill · 18 min", "Wound festering"), a small "Wild" badge beside the name, and a "?" count that opens the inbox's questions.
- Inbox: a question shows its chips as buttons; closed questions say "You told me", "Not sure about that one" or "I figured it out".
- Journal: a Survival section listing each survival lesson with its source ("from you", "worked it out", "knew from the start"), and the ones still unknown shown as "?".
- Memorial: the cause "sickness" in words, and how many lessons came from the owner and how many Mimo worked out.
- Pure logic in `.ts` modules with Vitest: `wild.ts` (ailment words, chip state, lesson sources).

### W1 tests (besides the gate)

- Difficulty: the API hatches wild by default and gentle when asked; `hatch()` defaults to gentle; a world without the key reads gentle and is granted every lesson on its first tick, silently; an archive is never written.
- Each hazard: poison plant gives a tummy ache and 5 health; the tummy ache and chill run their time and drain; resting warm halves a chill; sunleaf ends any sickness; raw meal rolls once at the highest chance; spoilage wear per shelf life, in a chest and (W2) in winter; lots sum to counts through eat, pick, store, take, drop, craft and cook; a wound's chance, festering after 10 game minutes, healing after a game day, dressing by bandage, sunleaf or the owner's care.
- Gates: every row of the lessons table, known and unknown (a purpose or recipe offered or not).
- Lookalikes: an untaught meal of red berries eats nightberries at their share; a taught pet never picks one; a sickness from the group shuns it 2 game days.
- Knocks: each row, the growing chance, the curiosity factor, sure knocks, and the `figured` event; sunleaf and bandage are never learned alone, not even when a nibble cures a sickness.
- Questions: posting, caps, gap, the shuffle, once a life, gentle never asks; hesitation holds a taste 8 game minutes; starving overrides; chips teach, doubt or note; yes and no bind to the newest open question; a lesson taught another way closes it as figured out.
- Teaching table: every line teaches or is doubted as listed.
- Privacy: a free-text answer never reaches a Luna payload (the existing Mind privacy test, extended with an answer).
- No model call in any of it (`no_model`).

---

## W2: Weather and seasons

### Seasons

- A year is 40 game days: spring, summer, autumn and winter, `SEASON_DAYS` = 10 each.
- The season day is `(day_number - 1 + state["sky"]["offset"]) mod 40`. A newborn's offset is 0: it hatches on spring day 1 and meets its first winter on day 31.
- An old world's offset is set on its first W2 tick so that tick's day is spring day 1. Its first winter is 30 game days after the upgrade.
- At production scale a season is 10 real hours and a year is about 1.7 real days.

**Warmth targets** (outdoors, before shelter, cloak and fire):

| Season | Day | Night |
|---|---|---|
| Spring | 100 | 30 (as today) |
| Summer | 100 | 45 |
| Autumn | 85 | 20 |
| Winter | 45 | -10 |

- Alpine stays 60 colder by day and 50 at night, as today. Snowfall takes 10 more off outdoors.
- A shelter adds 45, a wool cloak adds 20 (W2), and a fire, furnace or hearth within 4 blocks sets 100, as today.
- A winter night outdoors with no shelter freezes (under 20): 1 health per 15 game s, today's rate. Sheltered it is 35, with a cloak 55, by a hearth 100.

**Winter** (winter days 1 to 10):

- Crops, saplings, berry and nightberry bushes, sunleaf and forest-floor mushrooms stop growing. Renewal entries that fall due in winter are moved to the first spring dawn. Farmland does not revert. Cave mushrooms keep regrowing, so caves are winter food.
- Animals thin out. New chunks roll at most one herd, the land cap near Mimo falls from 24 to 12, and a hunted-out chunk does not regain its herd until spring. Animals already alive stay.
- Surface lakes and rivers freeze into walkable ice (below). Fish can't be caught through ice. Cave lakes stay open, and the fish stock does not recover in winter.
- Spoilage (wild) runs a third as fast.

**Mimo notices.** On autumn day 3 at dusk the tick logs "The nights are getting colder." as a thought and a notable `season` event. A wild pet that does not know `wild:winter` meets the `colder` wonder. Every season's first dawn is a routine `season` event ("Winter has come."), and spring's first is notable ("Spring! Things are growing again.").

### Weather

- Weather is a pure function of the world seed, the season and the 10-game-minute segment of the life (`sky.weather_at`). A game day has 6 segments. Each segment keeps the last segment's weather with chance 0.5, else rolls the season's table, so a spell runs 20 game minutes or more on average. The look back stops after 6 segments (the sixth rolls fresh), and a kept weather the new season's table lacks (rain carried into winter) rolls fresh too.
- The tick stores the current weather in `state["sky"]` for `/api/mimo`. A long catch-up plays the weather in time order, because each step reads the weather at its own time.

| Season | Clear | Rain | Storm | Fog | Snow |
|---|---|---|---|---|---|
| Spring | 0.55 | 0.30 | 0.08 | 0.07 | |
| Summer | 0.65 | 0.15 | 0.15 | 0.05 | |
| Autumn | 0.45 | 0.25 | 0.05 | 0.25 | |
| Winter | 0.45 | | | 0.15 | 0.40 |

- **Rain:** walking under the open sky takes 1.15 times as long. A campfire under the open sky goes out when rain starts (it becomes `campfire_out`: no light, no warmth; a `relight` step with 1 stick lights it again). Crops grow at the watered rate (a stage every 12 game minutes) wherever it rains. Fire spreads a third as often.
- **Snow** (winter only): walking under the open sky takes 1.3 times as long, it is 10 colder outdoors, and snow cover builds (below).
- **Fog:** hostiles treat open ground by day as dark (sky light counts as 6 for spawning), the sun does not burn or fade them, and the hostile cap rises by 2. Torches and lanterns keep their light. The viewer's fog closes to 0.35 of the view distance.
- **Thunderstorm:** rain, plus lightning (below).

### Lightning and fire

- In a storm, a strike falls every 60 game seconds within 64 blocks of a living Mimo. The tick samples 6 columns within 48 blocks (seeded) and strikes the highest; a tree's top counts as its height.
- A strike never lands within 16 blocks of the home Mimo built, nor in the legacy clearing. The yard is safe, and that is what "stay inside" means.
- **Mimo struck:** when Mimo is under the open sky and its column is the highest within 8 blocks (a hilltop, a pillar, a treetop), each strike has a 0.05 chance to hit it instead: 25 damage, armor no help, cause `"lightning"`. On flat ground or indoors it is never struck. A pet that knows `wild:storm` goes home or to low ground when a storm starts.
- **Tree fire:** a strike on a tree turns its top leaf or log into a `fire` block (glow, light 13, not solid). Every 10 game seconds each burning cell may spread to one neighbouring natural log or leaf (0.35, a third of that in rain). A fire holds at most 24 cells, and at most 2 fires burn at once. Each burning cell burns out 20 to 40 game seconds after it caught, leaving air. Fire never enters a cell Mimo built or edited, a claimed cell, or anything within 8 blocks of home.
- Mimo in or beside a burning cell takes 2 health a game second (cause `"fire"`). Pathing treats burning cells and their neighbours like lava.
- Burned trees are ordinary block edits through `_write_block`, synced like chopping. Worldgen is untouched.

### Snow and ice: overlays, not blocks

Snow cover and ice are overlays driven by `state["sky"]`, not blocks (resolution 13).

- **Ice.** From the first winter dawn to the first spring dawn, `Grid.material` reports `"ice"` for a natural, never-edited water cell at `SEA_LEVEL` with open sky above it (the surface of a lake, a river or a swamp pool; cave lakes lie lower and stay water). It is solid, standable and walkable, so lakes become paths. It can't be mined ("the ice is too thick"), so no block is ever written. A cell Mimo stands or swims in when the freeze comes stays water until it leaves (`state["sky"]["open_cells"]`, cleared at the next dawn). Fish in a frozen cell move down a cell or fade.
- **Snow cover.** `state["sky"]["snow"]` (0 to 1) rises 0.1 a game minute while it snows and melts over 20 game minutes after the first spring dawn. It changes nothing on the server.
- The viewer draws both through shader uniforms, so the season turning needs no remesh (below).
- Why not blocks: freezing every lake surface and laying snow on every column near Mimo would be tens of thousands of block edits a season, each synced and kept for good in the world and its archive, and undone again in spring. Overlays cost one comparison in `Grid.material` and a uniform in the viewer. Worldgen and the parity suites are untouched. Real blocks stay for things that change one place for good: burned trees (W2) and craters (W3).

### Lessons, wonders and knocks

| Lesson | Fact | Unlocks | Knock (first, step) | Sure when |
|---|---|---|---|---|
| `wild:winter` | Winter comes after autumn, when crops stop and animals hide, so fill a chest with food in autumn. | The "Ready for winter" goal and its food target | A winter day with hunger under 30 (0.30, 0.15) | It lives through a winter: it knows for the next |
| `wild:cloak` | Five wool make a wool cloak that keeps you warm in the snow. | The cloak recipe and wearing it | 2 game minutes freezing while 5 wool are carried or stored (0.30, 0.15) | |
| `wild:hearth` | A hearth of stone with a fire in it keeps the home warm all winter. | The hearth recipe and placing it in home | A chilled or freezing night at home in winter, knowing fire (0.25, 0.15) | |
| `wild:smoking` | Meat smoked over a fire keeps all winter. | The smoke step | Food spoils, or a winter day hungry, knowing fire (0.25, 0.15) | |
| `wild:rain` | Rain puts out a fire under the open sky, so keep your fire under a roof. | Fires placed under a roof (a solid block within 4 above) when one is in reach | Its fire goes out in the rain (0.50, 0.25) | |
| `wild:storm` | Lightning strikes high ground and tall trees, so in a storm stay low and inside. | Goes home, or down off high ground, when a storm starts | A strike within 16 blocks (0.50, 0.25) | It is struck |
| `wild:fog` | Fog hides the sun and lets the dark creatures walk by day, so stay close to home in the fog. | Keeps to home ground and torchlight in fog; no trips start in fog | A blow from a hostile in fog by day (0.35, 0.15) | |

Wonders (asked like W1's, with chips): `colder` (autumn day 3: "The nights are getting colder. Is something coming?"), `fire_out` ("The rain put my fire out!"), `storm` ("The sky is booming and flashing! What should I do?"), `fog` ("Everything is grey and foggy. Is it safe out here?"; yes-claim "Fog is safe." is doubted, no-claim "Stay close to home in the fog." teaches), `freezing` ("I'm freezing! How do I keep warm in the snow?", chips for cloak and hearth), `winter_food` ("The lake is frozen and nothing grows. What do I eat?", chips for winter and smoking).

Owner lines the teaching test table gains: "Fill a chest with food before winter." (winter), "Five wool make a wool cloak." (cloak), "A stone hearth keeps the home warm." (hearth), "Smoked meat keeps all winter." (smoking), "Rain puts out a fire under the open sky." (rain), "In a storm stay low and inside." (storm), "Stay close to home in the fog." (fog). Doubted: "Six wool make a wool cloak." and "Lightning is harmless."

### Recipes, blocks and the winter goal

- `wool_cloak`: 5 wool at a crafting table. It sits in its own slot, not armor, and adds 20 warmth. The pet model draws it.
- `hearth`: 8 cobblestone and 1 campfire at a crafting table, a block (glow, light 13, warms like a furnace, cooks and smokes like a campfire, never goes out in rain). The `build_hearth` purpose (work band, 60, by day at home, while the winter goal wants one) places it in the home's room against a wall, claimed by the home.
- `smoked_meat`: the `smoke` step at a campfire or hearth, 20 s, turns 1 raw meat and 1 stick into 1 smoked meat. It fills 20 hunger and never spoils.
- New blocks at the end of the registry: `campfire_out`, `fire`, `hearth`. New items: `wool_cloak`, `smoked_meat`.
- **"Ready for winter"** (goal `winter_ready`, repeating): offered from autumn day 1 until winter day 1 to a pet with a built home that knows `wild:winter` (a gentle pet always does). Rules score 70 plus a tenth of caution (70 to 80), above iron tools (60 to 70) and never past the survival floor. Milestones, each only for a lesson Mimo knows: the chests hold `WINTER_FOOD` = 360 hunger points (six winter days) that will still be good on winter day 5 at chest rates, a wool cloak, a hearth in home, 8 smoked meat. stock_larder serves it with that target. Reached: a notable `goal` event, as goals are.

### State and API

`state["sky"]`: `offset`, `season`, `season_day`, `weather`, `weather_until`, `snow`, `frozen`, `open_cells`, `strikes` (the last 5, `{x, y, z, at}`), `fires` (burning cells with their end time, at most 48). `/api/mimo` gains `sky`: season, season day, days to the next season, weather and until, snow, frozen, and strikes since the viewer's last poll.

### Moments, news and voice

Events: `season` (above), `storm` ("A thunderstorm rolled in."), `struck` ("Lightning struck Pip!"), `fire` ("Lightning set a tree on fire near Pip."), `fire_out` ("The rain put out Pip's campfire."). Mind moments: `struck` 8 (-2), `fire` 5 (0), `season` 4 (+1, spring's first 6). Inbox: `struck` and `fire` as danger, winter's and spring's first days as news. The voice table gains them all. Deaths by lightning and fire read "was struck by lightning" and "was caught in a fire".

### Viewer

- **Sky:** per weather, a tint mixed into `skyColor` (rain and storm: grey-blue, desaturated 40 %; fog: pale grey; snow: white-grey), and in winter a colder day sky.
- **Rain and snow:** instanced particles in a box that follows the camera (1,500 rain streaks, 800 flakes; half on a phone-sized screen), faded out when the camera is under a roof in first-person or close follow.
- **Lightning:** a bolt (a jagged line from the sky to the strike point) and a flash that lifts ambient and sky light to 3 times for 0.15 s, from `strikes`.
- **Fire:** the `fire` block's animated flame texture, glow, and ember particles; smoke over a burned-out tree for a game minute.
- **Snow cover:** a `uSnow` uniform on the terrain materials (the `applyDaylight` pattern) that whitens up-facing faces open to the sky. The mesher adds one static per-vertex attribute, `open`, true for a top face with no opaque block above it in its column, so cave floors never whiten. The uniform eases to `snow` over 10 s.
- **Ice:** a `uFrozen` uniform on the water material that turns surface water (world y at or above `SEA_LEVEL`) opaque pale blue with a crackle texture, eased over one game minute at the freeze and the thaw. Cave lakes stay water.
- **HUD:** a season badge ("Winter · day 34 · 6 days to spring") and a weather icon with a word ("Storm").
- Pure logic in `seasons.ts` and `weather.ts` (tints, the flash curve, particle counts, snow easing) with Vitest.

### W2 tests (besides the gate)

- The season from day and offset; an old world's offset; warmth targets by season, biome, shelter, cloak and fire.
- `weather_at` is deterministic, keeps spells, and follows each season's table over 10,000 segments (within 0.02 of each share).
- Rain: walk time, fires out and relit, crop rate. Snow: walk time, cover. Fog: dark spawning by day, no sun burn, the cap.
- Lightning: never within 16 blocks of home or in the clearing; struck only when highest; damage and cause. Fire: spread chance, 24-cell and 2-fire caps, burn-out, never into built, edited or claimed cells or near home; burns Mimo beside it.
- Ice: `Grid.material` in and out of winter, only surface water, never mined, the open cell a swimming pet keeps; pathing crosses a frozen lake.
- Winter: growth moved to spring, cave mushrooms still grow, herds thinned, no fishing through ice.
- The winter goal, its milestones by lesson, the cloak, hearth and smoke.
- Old worlds: a world saved before W2 reads a default sky, gets its offset on its first tick, and an archive reads without writing.

---

## W3: Wild nights and strange skies

### Which night gets what

At most one sky event a night, decided at dusk, in this order. Nights count from birth, or from the W3 upgrade for an old world (`state["sky"]["moon_offset"]`).

1. **Red moon** on the night of every 7th game day from day 14 on (days 14, 21, 28 ...). The first 13 days have none.
2. **Meteor shower** on a clear night with chance 1/20. Every life gets its first between nights 12 and 24: the first clear night in that window whose roll is under 0.25, or night 24 whatever its weather if none is (24 is never a red-moon night).
3. **Aurora** on a clear night with chance 1/8 in autumn and winter, 1/25 otherwise. Every life gets one in its first autumn: the last autumn night if none came by then.

All rolls are seeded (`nature.roll` on channels 200 to 259, reserved for Wild World). `state["sky"]["night"]` holds tonight's event for `/api/mimo`.

### Red moons

At dusk the moon rises red. From 2,400 to 3,420 game seconds:

- The hostile cap rises from 8 to 12 (plus the ring's bonus), a spawn chance comes every 15 game seconds (not 30), and hostiles spawn where light is 9 or less (not 7), so a torch keeps a smaller circle clear.
- Hostiles are bolder: they chase from 24 blocks (not 16), give up at 40 (not 24), never lose interest, and have 25 % more health.
- **Delvers:** one gloomling in 4 digs through natural soft blocks in its way (dirt, grass, sand, gravel, snow, mud, leaves), 3 s a block. It never breaks a placed block, a door or a claimed cell. Dug cells are block edits.
- **Climbers:** skitters climb any wall up to 4 blocks high. They never pass a roof or a door.
- A built shelter with a door stays safe (`harm.sheltered`). A dug-in camp of natural dirt is not.
- At dawn every red-moon hostile left near Mimo fades.
- Lesson `wild:red_moon`: "Every seventh night the moon turns red and the dark creatures swarm, so be home behind a lit door by dusk." It moves the homeward window 3 game minutes earlier on red-moon days, lets no trip, expedition or camp overlap a red-moon night, and has light_up light the door. Knock: a blow on a red-moon night (0.40, 0.20). Wonder `red_moon` at the first red dusk: "The moon is turning red! Is that bad?" Its yes-claim is "Be home behind a lit door on a red moon." (taught); its no-claim, "The red moon is harmless.", is doubted.

### Meteor showers and star metal

- Falling stars streak the sky all night (the viewer only). At a seeded time between 2,600 and 3,200 game seconds one meteor lands 40 to 120 blocks from Mimo: on dry natural land, never within 24 blocks of home, never in the legacy clearing, never in water.
- **The crater** is at most 40 block edits: a bowl of radius 3 carved to at most 2 deep in natural ground, 3 to 6 `star_metal_ore` at its bottom and 8 to 12 `hot_rock` round its rim.
- **Hot rock** glows (light 12) and burns: Mimo on or beside it takes 2 health a game second (cause `"fire"`), and natural leaves or logs beside it catch fire (W2's fire rules). Each hot rock cools into `basalt` 2 game days later (a renewal entry). Standing within 8 blocks of hot rock is a sure knock for `wild:fire`.
- **Star metal:** star_metal_ore (hardness 12) needs an iron pickaxe or better (2 s with iron) and drops star_metal_ore, plus a `star_shard` one time in 4 (W4's key). Smelted with 1 coal in a furnace: `star_metal_ingot`.
- **Star tools,** the new top tier: `star_pickaxe` (3 ingots, 2 sticks; speed 10, diamond is 8) and `star_sword` (2 ingots, 1 stick; damage 9, diamond is 8), at a crafting table. `toolmaking` adds them to the ladder above diamond.
- The crash is a notable `found` event ("A falling star crashed north of Pip!"), a discovery for curiosity, a place (kind `"crater"`), and an urge to go and look once the hot rock has cooled (the rim is a curio from then on).
- Lesson `wild:star_metal`: "Star metal from a fallen star makes the best tools, once it is smelted with coal." It unlocks mining, smelting and the star recipes. Knock: none; a pet learns it by seeing a crater up close (sure) or from the owner. Wonder `falling_star`: "A star fell out of the sky and crashed nearby! Can I go look?"

### Wolves

- **Kind** `wolf`: 16 health, 0.35 s a block (just slower than Mimo), a bite of 3 every 1.0 s from 1.5 blocks, packs of 3 to 5 (`herd`), in taiga, forest, birch forest, alpine and meadow. Drops 1 to 2 `bone`.
- **Where:** only in the far wilds and beyond (danger 2+, the L5 rings). A chunk there that Mimo comes near for the first time holds a pack with chance 0.25. At most 2 packs near Mimo. Wolves take L1's passive turns (wander, graze) and live by day and night.
- **Wary, not hostile:** a pack attacks when Mimo comes within 6 blocks by day or 12 at night, or hurts one of them. Then it fights like a hostile until Mimo is 24 blocks away. A calm pet (below) may come within 3.
- **Taming.** Lesson `wild:wolves`: "A wolf offered a bone or raw meat, calmly, may become your friend." With it, `tame_wolf` (a work purpose, 55 plus a tenth of sociability, by day, in the far wilds, carrying a bone or raw meat and no tame wolf yet) walks up slowly (half speed, so the pack stays calm) and uses the `offer` step (1 s, within 3 blocks). Each offer tames with chance 0.5 for a bone and 0.3 for raw meat, at most 3 offers a wolf a game day, never a wolf Mimo hurt.
- **The companion:** one tame wolf at a time. It leaves its pack, gets 20 health and regenerates 1 a game minute, bites for 4, follows within 6 blocks, passes doors like Mimo, sleeps beside it, attacks hostiles within 8 blocks of Mimo and joins Mimo's hunts. It is exempt from caps and despawning. Left more than 48 blocks behind for 60 game seconds, it walks home and waits there.
- **Feeding:** at dusk Mimo gives it 1 raw meat, cooked meat or bone (the `feed` step). Two game days unfed and it goes back to the wild ("left").
- **Naming:** the taming posts a naming ask, as Bond's places do: "I made a friend, a wolf! What should we call it?". The name goes in the creature's state and on its label.
- **Loss:** a tame wolf that dies is a notable `wolf_lost` event, a Mind moment (8, -2) and inbox news. Mimo may tame another after 3 game days.
- Wolves are threats to fight and flee from only while attacking. `defense.threats` and the Jev payload count them then. A wolf pack in the frontier run is L5's world getting wilder, a deliberate change (see the gates).
- Wolves need a new `Kind` field, `wary` (the attack radius by day and by night), so they are neither passive animals (the land cap, hunting) nor hostiles (the dark's cap and despawning).
- Knock for `wild:wolves`: none. It comes from the owner, or from an old note: opening a ruin chest in the far wilds or deeper teaches it with chance 0.2 ("Pip found an old note about wolves in the ruin's chest."), as Making's manuals do. Wonder `wolves` on the first pack seen: "I saw a pack of grey wolves. Are they dangerous?"

### Aurora nights

- Curtains of green and violet light over a clear night. Mood's target rises 10 for the night, and the first is a Mind moment (6, +2) and inbox news ("The sky danced with green light tonight!").
- Lesson `wild:aurora` (a sky lesson, unlocks nothing): "Green lights dance in the sky on some cold clear nights: the aurora." Learned by seeing one (sure). Wonder `aurora`: "The sky is dancing with green light! What is it?" (chips: the aurora, or "Nothing to worry about.").

### Teaching lines

The teaching table gains, for the scripted owner and the tests: "Be home behind a lit door on a red moon." (red_moon), "Star metal makes the best tools." (star_metal), "A bone can make a wolf your friend." (wolves), "The green lights in the sky are the aurora." (aurora). Doubted: "The red moon is harmless."

### New blocks, items and events

- Blocks at the end of the registry: `star_metal_ore`, `hot_rock`. Items: `star_metal_ingot`, `star_pickaxe`, `star_sword`, `star_shard`, `bone`.
- Events: `red_moon` ("The moon rose red."), `meteor` (the crash, as `found`), `tamed` ("Pip tamed a wolf!"), `wolf_lost`, `aurora`. Mind moments: `red_moon` 5 (-1), `tamed` 8 (+2), `aurora` 6 (+2). All in the voice table.
- `/api/mimo`: `sky.night` (`"red_moon"`, `"meteors"`, `"aurora"` or null), the crater and its hot cells, and each creature's `tame` and `name`.

### Viewer

- **Red moon:** a large red moon disc, a red tint on the night sky and fog, red moonlight on the terrain (the night floor of `daylightFactor` tinted), and a HUD line at dusk: "Red moon tonight: get inside!".
- **Meteors:** streaks with glowing trails across the sky all night; at the crash a bright streak down, a flash and a dust puff; the crater's hot rock glows and smokes until it cools.
- **Star metal:** ore texture (dark rock with silver-blue sparks), ingot and tool models; the pet draws a star sword or pickaxe with a faint shimmer.
- **Wolves:** a grey voxel wolf (pointed ears, a bushy tail, amber eyes). A tame wolf wears a collar in Mimo's favourite colour and a name label, and trots at the pet's heel.
- **Aurora:** animated ribbons, additive blend, high in the night sky.
- Pure logic in `moon.ts` (tonight's event words and tints) and the wolf in `creatures.ts`, with Vitest.

### W3 tests (besides the gate)

- The night schedule: red moons on 7k from 14, the meteor window, the aurora guarantee, one event a night, all deterministic.
- Red moon: cap, spawn rate, light threshold, bolder chase, delvers dig only natural soft blocks, climbers never pass roofs or doors, a shelter with a door stays safe, fading at dawn.
- Meteors: site rules, at most 40 edits, hot rock burns and cools, star ore needs iron, shards one in 4, smelting, the star tier in toolmaking.
- Wolves: ring-only spawning, wary radius by day and night, taming chances and limits, the companion's follow, guard, doors, feeding, leaving, naming, loss and the 3-day wait.
- Aurora mood and the first-time moment.

---

## W4 sketch: the Glimmer

Not planned now. This is how it could work and what it would cost.

**The portal.** Obsidian comes from water on lava. The game has no carried water, so W4 adds a bucket (3 iron ingots) that lifts one water cell and a `pour` step. Water poured on a lava cell turns it to `obsidian`, which only a diamond or star pickaxe mines (15 s). A frame of 10 obsidian (4 wide, 5 tall, corners optional) is lit with a star shard (W3), used up, and its inside fills with `glimmer_portal` blocks. Stepping in is a new `travel` step.

**The Glimmer itself.** A far band of the one grid: every column with x from 22,000 to 30,000. Survival worlds spawn 3,000 to 6,000 blocks from the origin and trips reach at most about 500, so no pet walks there. Worldgen reads `realm_at(x, z)`: inside the band its own rules apply, still a pure function of seed and cell in both ports. Floating islands come from `noise3` density between y 20 and 90, with nothing below (a void: a fall off an edge is death, which the avoid-drop reflex already guards). There are glowing flora (glowcaps, crystal shrubs), rare materials (prism ore, glimmer dust), passive wisps and a hostile shardback. The sky is violet.

**Travel.** A portal at (x, z) links to (25,000 + (x mod 4,000), z), a fixed mapping. On the first crossing the server finds the nearest island top to that point and builds the return portal there as block edits. The rings measure from that portal while Mimo is in the band, at danger 3 everywhere.

**What it costs.** About three milestones: G1 (bucket, obsidian, the portal, the travel step, the viewer's cut between places), G2 (the band's worldgen in both ports with parity, the fixture's new rows, the violet sky, the minimap), G3 (creatures, materials, lessons, wonders and a "See the Glimmer" goal). The server's ±30,000 limit already covers the band, and Float32 still holds fractions of a block there. Risks: worldgen parity grows by a whole second rule set; the column cache sees a second hot area; a pet that dies in the Glimmer leaves its archive's camera there; and every "far from home" rule (rings, trips, go_home) needs to know which side of the portal home is. The other design, a second world database per place, is cleaner for the server but would split the viewer, the block sync and the archive, so the band is the better fit for this engine.

---

## Resolutions

Decisions the brief did not give, each with its reason and its cost if wrong.

1. **Gentle is today's game plus W2 and W3, with every lesson known and no W1 hazards.** Why: the grandfather rule becomes simple to guarantee (a gentle world never gets sick, wounded or spoiled), and the L4a, L4b, Making and L5 sims, which hatch gentle, measure exactly what they measured. Cost if wrong: gentle has less texture than wild. Hazard flags per difficulty can be added later without touching wild.
2. **`hatch()` defaults to gentle; the API defaults to wild.** Why: 53 test files hatch pets, and their thresholds measure L-behaviour. The API is the only production caller. Cost: a new production caller that forgets the keyword hatches gentle. A test pins the API's default.
3. **Survival lessons are journal lessons named `wild:<name>`.** Why: Mind's teaching, the journal, "from you" and "You were right" work unchanged, and the colon keeps them out of investigate. Cost: `lessons.named` and the key builder need the prefix handled.
4. **Knocks, not timers, teach alone.** Why: learning follows pain, is legible in the log ("worked out that ..."), and is seeded and deterministic. Cost: the chances need tuning in the gate. They are the first knobs to move.
5. **Nightberries look like berries to an untaught pet, in its arms too.** Why: "only a lesson tells them apart" needs the pet to mix them up. The owner can see the difference in the viewer and the inventory, which is a nudge to teach. Cost: the meal's share roll is new logic in `purposes.meal`.
6. **Wrong answers are doubted and never learned; Mimo then acts as if nobody answered.** Why: the brief keeps Mind's doubt, and a liar must cost no more than silence. Cost: an owner can probe the truth by watching what Mimo doubts. That is harmless.
7. **Survival facts hold no negation word and state one side of a pair.** Why: `lessons.contradicts` doubts any negation and never doubts a fact that says both sides. Cost: some facts read a little stiff.
8. **Warnings and survival commands teach.** "Don't eat the purple berries." and "Cook your meat on a fire." are how people talk. B2's rule that commands teach nothing stays for every other lesson. Cost: the parser grows two narrow rules, pinned by the teaching table.
9. **Questions: 3 open at most, one every 5 game minutes, each wonder once a life, hesitation 8 game minutes.** Why: at production pace these are real minutes. The owner away for 8 hours is 8 game days, so Mimo can't wait for answers to live; it waits only when it has a choice. Cost: an owner who is never around sees at most 3 stale questions, which close as "figured out" as Mimo learns.
10. **Chips answer as well as chat.** Why: a phone owner answers in one tap, and a chip is rule-written, so it carries no owner words. They go through Bond's existing answer endpoint, which learns a second body shape. Cost: the endpoint now has two meanings, told apart by the item's `ask` kind.
11. **Sickness can kill (cause "sickness").** Why: "untreated sickness drains health", and a memorial should say what happened. Cost: a death the owner could have prevented. That is the point of the milestone, and the inbox warns them first.
12. **New plants fill only bare natural columns, outside the legacy clearing, and are replaceable.** Why: no plant moves or vanishes in any old world, and a build meeting a new plant replaces it. Cost: a few bare columns near old homes gain plants a gentle pet ignores.
13. **Snow and ice are overlays; fire and craters are blocks.** Why: see "Snow and ice: overlays, not blocks". Seasonal, world-wide and undone every spring suits state. One place changed for good suits blocks. Cost: the viewer needs two uniforms and a mesher attribute, and `Grid.material` gets a branch on its hot path (one integer compare for most cells).
14. **Weather is a pure function of seed and time segment.** Why: catch-up, tests and the viewer all agree with no stored history. Cost: weather can't react to anything (for example, no weather the owner summons).
15. **Lightning never strikes within 16 blocks of the built home, and fire never enters built, edited or claimed cells or comes within 8 blocks of home.** Why: "stay inside" must work, and upgrading must never burn an old home. Cost: a storm is never a threat at home. The yard is the safe place by design.
16. **A year is 40 game days; a new life starts in spring; an old world starts spring at its upgrade.** Why: the first winter comes after 30 game days of learning, and the demo gets the same runway. Cost: a pet born into autumn never happens, so no life starts hard.
17. **Red moons from day 14, every 7th day.** Why: a newborn's first two weeks are for learning, and no L-sim (10 days at most) sees one. Cost: "about every 7th night" is a fixed schedule. It is teachable ("every seventh night"), so the owner can warn Mimo ahead.
18. **Red-moon cap 12, not 16.** Why: the 20 ms creature budget was measured at 8 to 10 hostiles; 12 plus a ring bonus and wolves is the most it can hold with margin. Cost: a smaller surge than the word "swarm" suggests. Boldness, delvers and climbers make up the difference.
19. **Delvers dig only natural soft blocks; nothing breaks placed blocks or doors.** Why: "stay behind a lit door" must save a pet that listens. Cost: a pet's own cobblestone walls are always safe.
20. **One tame wolf at a time, exempt from caps, fed daily.** Why: a companion story, not a pack to manage, and a bounded cost. Cost: no wolf pack of its own.
21. **Meteors 1 in 20 clear nights, the first guaranteed between nights 12 and 24.** Why: every life sees one early, and star metal stays rare (about 5 a life). Cost: a guaranteed event is less of a surprise, but the owner gets the news either way.
22. **The cloak is its own slot, not armor.** Why: it must not compete with the leather, iron and amber tunics. Cost: one more slot in `harm.SLOTS` and the pet model.
23. **No new tables.** Everything lives in the state, `memory_knowledge`, `mimo_inbox`, block edits and creature state, as L5 did. Cost: `state` grows by a few kilobytes. Fires are capped at 48 cells and strikes at 5.
24. **Gate lives run in a committed script,** `backend/scripts/wild_gate.py`, not a scratchpad copy as Making's longrun was. Why: three milestones reuse it, and the controller re-runs it after fixes. Cost: a script to keep working. Its unit test runs it for one short life.
25. **The scripted owner teaches through the real chat and answer paths,** with the teaching table's lines. Why: the gate then tests teaching end to end, and a parser gap fails the gate instead of hiding. Cost: a line the parser can't read fails the gate until the parser is fixed.
26. **The owner's care bandage dresses a wound; the snack cures nothing.** Why: the owner's daily bandage becomes more valuable in wild, and a snack is food, not medicine. Cost: none found.
27. **Roll channels 200 to 259 and worldgen hash channels 160 to 169 are Wild World's.** Why: no collision with the 30s to 150s the game uses. Cost: none.
28. **Out of scope:** a difficulty UI, buckets and flowing water (W4), hunger or mood for the wolf beyond daily feeding, seasons or weather in the legacy life or the archive browser, weather the owner controls, Luna choosing anything new.
29. **The untaught pet stays dependent on the owner** (the controller's ruling on the W1 dry run, 2026-09-27, `.superpowers/sdd/2026-09-27-wild-world-w1/replan-ruling.md`). Why: the dry run found that an untaught pet worked out 6 to 9 lessons alone in about three game weeks and was rarely sick after, so the gap to a taught pet closed over 150 days and the first criteria 6 and 7 (sick minutes 3 times and 600 or more, near-death days, a health mean 10 below) could not be met by any knob; a health mean also recovers, so it measures the gap poorly. The owner asked for a pet that is "hard to survive unless you talk to it and help teach it", which takes a change of structure, not more tuning. So: (a) `wild:sunleaf` and `wild:bandage` come only from the owner: no knock teaches them, an instinct nibble cures one sickness without teaching, Mind's teaching and Mimo's questions still teach them, and the knock table holds the other nine; (b) the nine knocks are as unlikely as the "not hopeless" criteria allow (at most 3 of 6 untaught pets die, none before day 5, and every one alive on day 60 knows 8 lessons alone); (c) criteria 6, 7 and 10 become 6′ (a newborn's first month), 7′ (a life without the owner) and 10′ (4 wonders); the others are unchanged. Cost: an untaught pet can never cure itself or dress a wound, so its sicknesses and festering wounds run their course; the "not hopeless" criteria still bound how often that kills. The W1 plan's tuning (raw-meal chances, sickness drains) is in the plan's resolutions.

---

## Error handling and testing

- **No model in the tick.** Knocks, sickness, spoilage, wounds, weather, lightning, fire, the night events, wolves and taming are rules. Questions are posted by a Talker chore. Answers come by the chat job (Jev only picks among real lessons, as today) or by the answer endpoint (rules only). No new Jev or Luna call exists. Tests never call a model (`backend/tests/no_model.py`).
- **Crash guards.** New registries, each called guarded and logged once (`once.log_once`), a crash counting as nothing: `wild.KNOCKS`, `wild.WONDERS`, `wild.AILMENTS`, `wild.PERISHABLE`, `sky.EFFECTS` (season, weather, strikes, fire, ice), `sky.NIGHTS` (red moon, meteors, aurora), `creatures.tame.ACTS`. A crashing Talker chore posts nothing and tries again next chore. A crashing answer returns 500 and changes nothing (its own transaction rolls back).
- **Bounded.** Per vitals step, W1 adds O(items carried) for lots and O(1) for ailments. Chests' lots age once a game minute. W2 adds one weather lookup, at most one strike (6 height samples) and at most 48 fire cells every 10 game seconds. W3's red moon stays inside the creature budget. Targets: tick p99 in the low milliseconds as today, the sky hook at most 2 ms mean and 8 ms p99 a transaction in a storm, the creature hook at most 20 ms mean a slice on a red moon.
- **GETs never write.** The sky, ailments and questions are written by the tick and chores and read by `/api/mimo`.
- **Old worlds and archives.** Every new state key has a default. A world from before W1 reads gentle and empty. A dead pet's world is never written: the grant, the offset and the moon counter are set only in a living pet's tick. `advance_world` still never writes a dead world.
- **Catch-up.** A laptop that slept plays seasons, weather, sicknesses and spoilage in time order, because each 60-second step reads its own time. Strikes in catch-up are capped at one a step. Fires spread in renewal's chunks.
- **Determinism.** Every chance rolls from the world seed (`nature.roll`, `creatures.moves.roll`), never `random` or the clock.
- **Privacy.** Owner words go only where they go today: stored, shown, matched by rules, and handed to Jev as data. Questions and chips are rule-written. Told memories stay out of Luna's payloads (`mind.story_memories`). The Mind privacy test adds a free-text answer and a chip answer and checks that neither reaches a Luna payload.
- **Worldgen parity.** W1 regenerates the fixture (two new plants). W2 and W3 do not touch worldgen. Both parity suites run after W1.
- Each milestone's unit tests are listed under it. Each adds its checks to `test_survival_voice.py`, `test_survival_mind_privacy.py`, `test_survival_api.py` (GETs stay read-only, the new fields' shapes) and the viewer's Vitest suites.

---

## Balance gates

### The harness

`backend/scripts/wild_gate.py` runs one life per process: `--seed`, `--days`, `--condition gentle|untaught|taught|liar`, `--out DIR`, and `--parallel N` to fan out.

- Each life hatches with `random.Random(seed)` at `BORN = 1_000_000`, gentle for `gentle` and wild for the rest, and ticks at scale 60 and action scale 60, one tick per 60 game seconds, like `test_survival_days.py`. The worker's Chooser (rules, `env={}`) and Talker (rules) run after every tick. HTTP is a counting `NoModel`; any call fails the gate.
- **The scripted owner** (`taught`): on game day 1 at game minutes 5, 10, 15 ... it says the first teaching-table line of each W1 lesson, one line every 5 game minutes, through `talk.owner_says` (11 lines by minute 55, under the chat's 20 lines a game day). W2's 7 lines and W3's 4 follow the same way on day 2 once those milestones land. It answers every question within 5 game minutes with its true chip, through the function the answer endpoint calls, which is not a chat line. It gives no care, so the gate isolates knowledge.
- **The liar** answers every question within 5 game minutes with a false chip, or with the wonder's false claim in the chat when it has no false chip. It teaches nothing else.
- Each life samples every tick and writes a summary: death day and cause; sick game minutes (and by day); the health lost to hazards (`state["wild"]["lost"]`, and by day); wounds and festering minutes; near-death days (game days with health under 20 at least once); the time-weighted health mean, over the whole life and over each winter; freezing and starving minutes; lessons known and their sources by day; questions asked and open at most; blows by night kind; lightning strikes and their distance from home; fire cells in built or claimed cells; edits in the legacy clearing; the day of each machine built and of the "computer" event; star tools; tame wolves and their days; logged errors.
- `wild_gate.py --check W1|W2|W3 DIR` applies the criteria below and prints pass or fail for each.
- Seeds for every gate: **3, 5, 8, 11, 21, 42** (Making's route gate). A 150-day life takes about 13 minutes alone (Making's 150-day run of seed 11 took 768 s), so a gate of 18 lives takes about 45 minutes at 6 in parallel.
- The unit suite gets `test_survival_wild_run.py`: by default seed 8 for 3 game days, untaught and taught (the untaught pet posts at least 3 questions, the taught one knows all 11 W1 lessons by the end of day 1, both live); with `MIMO_SLOW_TESTS=1` seeds 3 and 11 for 20 game days (the untaught pet's sick minutes are at least twice the taught pet's, both are alive on day 5, the taught one on day 20).

### W1 gate

Conditions: `gentle`, `untaught` and `taught` for 150 game days, and `liar` for 30.

Taught:
1. All 6 alive on day 150.
2. Each life's health mean is 75 or more.
3. Each life has at most 3 near-death days.
4. Each life has at most 150 sick game minutes.
5. At least 3 of 6 build a lamp on a lever by day 150, and the taught pet with the most machines has built at least as many as the gentle pet with the most, less one (Making's seven machines, the computer last).

Untaught (clearly harder; 6′ and 7′ replace the first 6 and 7, resolution 29):
6′. **A newborn's first month.** Over the first 30 game days of each life, summed over the 6 seeds: untaught sick minutes at least 3 times the taught sum, and health lost to hazards (the drain of a sickness or a festering wound, and poison) at least 3 times the taught sum and at least 100 a life on average.
7′. **A life without the owner.** Over the 150 days, summed over the 6 seeds: untaught sick minutes at least 5 times the taught sum, and untaught deaths plus near-death days at least 6 in all.

Untaught (not hopeless):
8. At most 3 of 6 die before day 150, and none before day 5.
9. Every untaught pet alive on day 60 knows at least 8 of the 11 W1 lessons, learned alone.
10′. Every untaught pet meets at least 4 wonders (was 5, resolution 29) and posts at least 3 questions in its first 3 game days. (Nobody answers it, so the cap of 3 open questions holds the rest back until it figures one out.) No pet in any condition ever has more than 3 open.

Liar:
11. No lesson is ever learned from a false chip or false claim.
12. By day 30, liar deaths are no more than untaught deaths by day 30, and on each seed the liar's sick minutes are at most the untaught pet's plus 30.

Gentle:
13. All 6 alive on day 150. No sickness state, wound, lot or question ever. Every survival lesson known from the first tick.

All: no model call and no logged error in any life.

**Tuning.** The criteria are fixed. The knobs move, in this order: knock chances (in steps of 0.05), the raw-meal chances, `CHILL_BELOW`, then the sickness drains. If untaught pets die too often (criterion 8), knocks get likelier first. If they don't struggle enough (6′, 7′), raw meals and chills get likelier first. The nine knocks are set as low as criteria 8 and 9 allow (resolution 29). The review records every knob it moved and the measure before and after. If 6′ or 7′ still cannot be met, the review reports the measures and the knob at its limit; the criteria are not loosened.

### W2 gate

Conditions: `gentle`, `untaught` and `taught` for 150 game days (winters on days 31 to 40, 71 to 80 and 111 to 120). The W1 gate re-runs on W2's code and must still pass; if a W1 criterion breaks, W2's numbers are tuned first.

Gentle and taught:
1. All 6 alive on day 150.
2. In each winter, the health mean is 60 or more, freezing is at most 10 game minutes, and starving at most 10 game minutes.
3. The chests hold `WINTER_FOOD` on winter day 1: at least 5 of 6 in the first winter, all 6 in the second and third.
4. At most 1 lightning strike on Mimo a life.
5. Criterion 5 of the W1 gate still holds (lamps on levers, the furthest machine).

Untaught:
6. The mean of the winter health means is at least 15 below the taught one.
7. At least 2 of 6 alive on day 150, none dead before day 5.

Safety, over every life:
8. No strike within 16 blocks of a built home, no fire cell in a built, edited or claimed cell, no block edit in the legacy clearing.

Upgrade:
9. A world made by the pre-W2 code, ticked to its day 20 and then upgraded, gets spring on its upgrade day and lives gentle through its first winter (45 more game days).

Cost:
10. The sky hook is at most 2 ms mean and 8 ms p99 a transaction over a storm near a forest (fires burning), measured like L5's budget test. A route search across a frozen lake takes at most 10 % longer than the same search with the overlay switched off.

### W3 gate

Conditions: `gentle`, `untaught` and `taught` for 150 game days (red moons on days 14, 21 ... 147: 20 of them). The W1 and W2 gates re-run on W3's code and must still pass.

Gentle and taught:
1. All 6 alive on day 150.
2. On at least 90 % of red moons the pet is inside its shelter (`harm.sheltered`) at every sample from 2,400 to 3,420 game seconds, and its health at the next dawn is 50 or more.
3. Every life has at least one meteor, the first by night 24, and at least 3 of 6 taught pets make a star tool by day 150.
4. At least 3 of 6 taught pets tame a wolf by day 150. A tame wolf never harms its own pet. Tame wolves live 10 game days or more on average.
5. Every life sees an aurora by the end of its first autumn.

Untaught:
6. Blows taken on red-moon nights, summed, are at least 3 times the taught sum.
7. At least 2 of 6 alive on day 150.

Safety:
8. No crater edit within 24 blocks of home or in the legacy clearing, no hot rock or fire in a built, edited or claimed cell, no delver or climber edit on a placed block or door.

Cost:
9. A geared pet in the far wilds on a red moon, with the cap full (12 plus the ring's 2), a wolf pack and its tame wolf near: the creature hook's mean over five 60-game-second transactions is at most 20 ms.

### The existing sims

- **W1** changes nothing for gentle, and every existing sim hatches gentle. `test_survival_sim.py`, `test_survival_days.py`, `test_survival_expedition_run.py`, `test_survival_frontier_run.py`, `test_survival_making_route.py`, `test_survival_away.py` and `test_survival_mind_life.py` pass in default and slow mode with every threshold unchanged.
- **W2 deliberately changes them:** weather reaches every world, and these sims run in spring (rain 30 %, storms 8 %, fog 7 %). Rain slows walks, fog brings hostiles by day, and storms send taught pets home. Each threshold must still hold. If one moves, the W2 review re-measures it on the seeds and both pickers, records the new number and the reason in the test's comment (as L4a and L5 did), and the controller rules on it. No sim reaches winter (the longest is 10 days).
- **W3 deliberately changes one:** wolf packs stand in the far wilds, where `test_survival_frontier_run.py` takes its geared pets. Its criteria (alive, loot, home at every nightfall, no riches trip ungeared) must hold. No sim reaches a red moon (day 14), and the meteor window opens on night 12, past the 10-day making route.

---

## Risks

1. **W1 balance.** The untaught pet could die in its first week or barely notice the hazards. The gate catches both, and the tuning order says what moves first. The cost is gate runs: about 45 minutes each. The first dry run found the second case over a whole life (an untaught pet learned too much alone), and resolution 29 answers it.
2. **The parser.** Survival lessons stretch `lessons.claims`, a module already shaped by many fix rounds. A true answer doubted is bad for trust; a false one taught breaks the promise of resolution 6. The teaching table is the contract, and the gate's scripted owner exercises it end to end.
3. **Question fatigue.** At production pace a curious newborn could post its 10 W1 questions in its first hour. The caps hold it to 3 open, and each wonder is asked once a life. Notifications stay opt-in.
4. **Spoilage bookkeeping.** Lots must follow every item move (pick, eat, store, take, drop, craft, cook, smoke, loot, care). A missed path leaves lots out of step with counts. The invariant test runs after every step kind, and a mismatch is repaired toward the count and logged once.
5. **The computer route.** Taught pets spend time on cooking, bandages and winter prep. Gentle seed 11 built the computer on day 126.5, so a taught pet may miss it by day 150. W1 criterion 5 asks for route progress, not the computer itself. If even that fails, the review looks at L4a's keep list first (full arms were Making's last stall).
6. **The upgraded demo's first winter.** A gentle pet with a home and a farm must stock a larder it never needed. The upgrade check (W2 criterion 9) runs that exact case. If it fails, the first winter after an upgrade can be made mild (autumn temperatures) as a fallback.
7. **Weather in the L-sims.** Fog by day and storms may push rest share or churn past their thresholds. The rule is to re-measure and record, not to loosen silently.
8. **Performance.** The red moon's extra hostiles, a tame wolf and wolf packs share the 20 ms budget. The cap of 12 leaves margin; if the budget test fails, far red-moon hostiles (beyond 24 blocks) take turns at half cadence before the cap falls.
9. **The ice overlay on the hot path.** `Grid.material` runs up to 20,000 times a path search. The frozen branch must cost one integer compare for cells off `SEA_LEVEL`. The W2 budget check includes a path across a frozen lake.
10. **Viewer cost on phones.** Particles, the aurora and fire embers are capped and halved on small screens. The snow and ice uniforms cost nothing extra per frame.
11. **Tame wolves and doors.** A wolf that passes doors must never let a hostile follow it in. Doors stay solid to every creature but Mimo and its tame wolf, and the shelter tests cover a hostile at the door while the wolf goes through.
12. **No difficulty UI.** The owner's next egg hatches wild without being asked. The first questions explain it in Mimo's voice, and the HUD's "Wild" badge shows it. A choice screen is the obvious follow-up.

---

## Spec self-review

Four checks, run on the written document. Each lists what it found and how it was fixed.

**Placeholders.** A search for TBD, TODO, "to be decided" and unnumbered "tune" found none. Every hazard, knock, cap, window and gate criterion has a value, and the brief's "tune the numbers" is answered by fixed criteria plus an ordered list of knobs. One soft spot was fixed: the wonder table said "the words in brackets are filled from the event", but its lines had no brackets. It now says which parts are filled and shows one filling.

**Contradictions.** Found and fixed:
- The spec called `POST /api/mimo/inbox/{id}/answer` a new endpoint with a 410 for a dead pet. Bond already has that endpoint for naming places, with 404, 400 and 409. A question's chip is now a second body shape on it (`{"choice": n}`), with Bond's codes (resolution 10).
- Two "doubted" teaching lines would not be doubted by the rules they rely on. "Three logs make a campfire." matches a number the fire fact says (three sticks), so it became "Five logs". "Lightning strikes low ground." faces a storm fact that says both high and low, so it became "Lightning is harmless."
- The scripted owner said 11 lines 10 game minutes apart on day 1, which runs past a 60-minute game day. Lines are now 5 minutes apart, 11 by minute 55, under the chat's 20 a game day.
- Untaught criterion 10 asked for 5 questions in 3 days, but with nobody answering, the 3-open cap allows only 3. It now asks for 5 wonders met and 3 questions posted.
- The winter goal scored "70 plus a fifth of caution", up to 90, past the survival floor of 80. It is now a tenth (70 to 80).
- Star ore took "5 s with iron", which does not follow from hardness over tool speed. It is now hardness 12, 2 s with iron.
- The ice rule named swamp pools but required ground below `SEA_LEVEL`, which swamp pools do not have. It now reads "open sky above it".
- The grant was written for old worlds only, but every existing sim hatches a new gentle pet, which needs it too; and the granted lessons would have raised the "lessons learned" counts that payloads, facts and insights read. Both are now stated: every gentle pet is granted on its first tick, and born-knowing lessons stay out of those counts.
- Wounds came from "a hostile's blow", but W3's wolves are wary, not hostile, and bite. Wounds now come from a creature's blow.
- Delvers could dig natural cells a home claims (under a floor). They now never dig a claimed cell.

**Scope.** W4 stays a sketch; the only W1 to W3 item that points at it is the star shard, which W3 drops and nothing uses yet. The spec adds no difficulty UI, no buckets or flowing water, no new tables and no new model calls. Left out while drafting, to keep the hazards few: a lookalike mushroom pair (red mushrooms stay a plain poison), a wolf-pelt cloak, and a taiga colder in every season (it would have changed gentle worlds outside winter). W3's teaching lines were missing, although the scripted owner says them; a short "Teaching lines" section now lists them.

**Ambiguity.** Found and fixed:
- A bare "yes" or "no" had no meaning for open questions such as "How do I stay warm?". Only yes-or-no wonders (red berries, red mushroom, raw meat, fog, red moon) now have claims, each listed, and a bare yes or no with none open teaches nothing.
- Weather spells were said to last "20 game minutes on average", which a re-roll that repeats makes wrong, and the look-back had no end and could carry rain into winter. The look-back now stops at 6 segments, and a kept weather the new season lacks rolls fresh.
- "Game hour" means two different things in the code, so the spec uses only game minutes and game days ("Words used here").
- Terms the gates count are defined: a near-death day, sick minutes, the time-weighted health mean.
- "Nothing near home changes" is concrete: new plants fill bare columns only; no strike within 16 blocks of home, no fire within 8, no crater within 24, nothing in the legacy clearing; an old world gets 30 days before its first winter and 13 before its first red moon.

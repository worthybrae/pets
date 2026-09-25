# Bond: Mimo and You — Design Spec

This is sub-project 4 of the roadmap ("chat with Mimo"). It widens that item into the relationship loop the owner's question pointed at. It builds on the Living World (L1–L4).

## Why (the owner, 2026-09-24 evening)

> "In order for this game to get mass adoption, what features do you think are still missing? how do we make this more engaging?"

The controller's answer named the biggest gap: **the player's part**. Today the owner mostly watches. Their only actions are a daily snack, a daily bandage and a "Say hello" hop. People don't stay with a pet they can only watch. The owner agreed with this order: finish L4a, then L4b, then plan this milestone ("talk to Mimo, a daily story and notifications"), and build it after L4b.

## Decisions

The owner approved designing on their behalf. Each call below can change later.

- **Talking.** A chat panel lets the owner write to Mimo, and Mimo answers in character, in one or two short sentences, through Jev. The answer draws on its state: vitals, mood, traits, goal, day plan, trip, curiosity, recent notable events, what it knows about the owner, and (after L4b) its journal. Chat never runs inside the tick. It is rate-limited: at most 20 owner messages a game hour and 200 a real day. With no model key, Mimo answers from a small table of rule-based replies keyed on mood and what it is doing.
- **Mimo remembers you.** Facts the owner shares, such as a name, a favourite, or a request it refused, are stored as `owner` facts in memory, capped at 40 and pruned oldest-first. Jev decides what is worth keeping, choosing from a fixed set of fact kinds. Mimo uses the owner's name.
- **Bond.** A bond value from 0 to 100 grows with care (snack, bandage, hello), with chats, and with kept promises. It fades slowly when the owner stays away. Bond changes nothing about survival. It shapes tone and willingness: a high-bond Mimo takes up the owner's requests more readily and shares more. The value is shown on the HUD as a small heart meter.
- **Requests, both ways.**
  - The owner can ask for something ("could you build a tower by the lake?", "go look at the cave"). Jev maps the request to a known goal or trip reason, or to "can't do that yet", from a list it is given. An accepted request becomes an owner-suggested goal offer. It is scored higher, weighted by bond and traits, at the next goal choice. Mimo says whether it will and why ("After my armor's done, I promise."). Nothing the owner writes changes the world directly.
  - Mimo asks too: for a snack or bandage when it truly needs one, or for help naming a place it found, or it reports a milestone. These are written by rules from state, never from free model text, and queued as messages to the owner.
- **The daily story ("While you were away").** At the first game dawn after the owner's last visit, Mimo writes a short diary entry about the previous game day. It is 3 to 6 sentences with the day's highlights (goal progress, discoveries, danger, meals, things built), taken from events and the day plan. Luna writes it, capped at 1 story per real day. The rules template writes it when there's no key. It is shown first when the owner opens the viewer. Past entries are kept as the life's diary, with the latest 30 in the API and all of them in the memorial.
- **An inbox, then notifications.** Notable moments go into an inbox: a goal reached, a first sighting, danger, near death, a creature seed hatching, a request from Mimo. The viewer shows an unread count. Browser notifications, through the Notification API while the tab is open or in the background, are opt-in. Web push to a closed app waits for the app-shell sub-project.
- **Safety.** Owner text is untrusted model input. It is length-capped (280 characters), passed as data (never as instructions), and never executed. Replies are length-capped and plain text. Model output can only pick from offered options for requests and facts. The free-text reply is display-only.
- **Cost.** Chat uses Jev, which the owner says is cheap, but it is still capped per hour and per day (above). The daily story uses one Luna call per real day. Tests never call a model; a fake stands in.

## Milestones

| # | Name | Delivers |
|---|------|----------|
| B1 | Talk | Chat panel, `POST /api/mimo/chat`, in-character replies from state (Jev, or rules without a key), rate limits, remembered owner facts, and the owner's name in replies. |
| B2 | Bond and requests | The bond value and the HUD heart. Owner requests become goal offers, with Mimo's yes/no and why. Mimo's own requests and reports go to the inbox. |
| B3 | While you were away | The daily story (Luna or rules), the diary, the unread inbox with its count, and opt-in browser notifications. |

## Error handling and testing

- Every model call runs outside the tick and falls back to rules on failure, timeout or an unoffered choice.
- `POST /api/mimo/chat` writes in its own short transaction: `BEGIN IMMEDIATE`, then the owner message plus the queued reply job. The reply is stored by the worker's Chooser loop, or by an API-side background task. The plan picks one, and it must never block the tick.
- Headless tests check the following:
  - Chat replies stay within limits.
  - Owner facts cap and prune.
  - Bond moves as specified.
  - An accepted request shows up as a goal offer, and an impossible one is declined with a reason.
  - The daily story is written once per dawn after a visit, and the rules template covers a day with no events.
  - The inbox counts unread items and marks them read.
- Frontend tests cover the chat panel state, the inbox count and the story panel as pure `.ts` logic, with Vitest in the node environment.

# Demo script: final, Sat 17 Oct 2026, 08:00 IST

Numbers: see REPORT.md. This script quotes none on purpose: say "a second or two" for a fight alert once the model has looked, and point at the screen for the rest.
Roles: **Aryan** drives the M5 (mouse, keyboard, every click) · **Abhinav** cameras and the staged shove · **Riddhi** the chat · **Shivansh** narrates and calls every fallback.
Words in quotes are the dashboard's own labels. "VLM" = the vision-language model (Qwen, running in Ollama; its name sits in the header).

**Rules on stage**
- No number from memory: "numbers: see REPORT.md". The one phrase we use is "a second or two" for a fight alert after the model looks.
- A fallback is said plainly ("the live take missed; this is the recording"), never hidden. Judges trust what they can see fail.
- Two tries at most for anything live, then the fallback. Shivansh calls it; Aryan clicks it.
- One clip at a time: start the next clip when the tile says "Finished", and ■ any finished tile if alerts feel slow. Several clips at once share one GPU and slow every alert.

## The rehearsal settles (write the answers on the paper copy)

- Which camera the shove pair plays to (webcam or iPhone), and where the X is taped.
- Which network the M5 joins for the Telegram alerts (pre-show step 3), and where the phone sits so the judges can see it.
- Whether "iPhone (live)" and "<webcam>" are swapped (D70), and the webcam's exact button name.
- Chrome zoom: default (the layout fits 1512×982 and 1920×1080).
- Rehearsal events do NOT survive: every server start wipes the live rows (`replay.reset_live_tables_on_start`) and run_demo.sh re-seeds the demo history, so the pre-show start begins with the seeded history only, and Act 3's "last 10 minutes" question shows just this demo's events.
- Heat: no benchmark or long clip runs in the hour before the demo. A long GPU run slows every model call (REPORT.md §6c); start the demo on a cool machine.

## Pre-show (T-30)

**Aryan: the machine**
1. M5 on mains. System Settings → Battery → Low Power Mode: Never. Lock Screen → turn display off on power adapter: Never. Focus: Do Not Disturb.
2. Mirror the display to the projector (mirror, not extend) so Aryan sees what the judges see.
3. Internet on, for one thing only: the Telegram alert to the guard's phone (D91). Join a network that works (a phone hotspot as backup); every model still runs on the laptop. Continuity Camera is unaffected (it needs the Wi-Fi and Bluetooth radios on anyway). No network → everything else works and only Telegram stays quiet: say so.
4. Terminal, in the repo folder, on `main` (it now equals `ui-next`): `git pull`, then `cd web && npm ci && npm run build && cd ..` once if the dashboard changed since the last build. Telegram keys: copy the team's `.env` file into the repo folder (two lines, `TELEGRAM_BOT_TOKEN=…` and `TELEGRAM_CHAT_ID=…`; gitignored, never committed, shared privately), or `export` both in this Terminal (`uv run python -m app.telegram --chat-id` prints the chat id once the phone has tapped Start on the bot). Then `./run_demo.sh`; with a `.env` it prints "loaded .env".
   It checks uv, Chrome, the YOLO weights and the Python env, starts Ollama, warms the model, re-seeds the chat history (times relative to now), rebuilds the dashboard if stale, starts the server and opens Chrome at http://localhost:8000. It ends with "dashboard ready"; with the two Telegram variables set the server also prints "Telegram alerts on: 1 chat(s)". Any red line names its own fix (port 8000 busy → it prints the `kill` to run); fix it and re-run.
5. Chrome, not Safari. One window, one tab, full screen (View → Enter Full Screen). Default zoom. Terminal stays behind Chrome.
6. Navbar: six tabs "Clips", "Live", "Alerts", "Ask", "Pipeline", "Report"; the "Local · offline" text has a green dot (red "Reconnecting" = the server is gone); "Clips" is the selected tab (a small dot on it = the server's mode). Click the blue "Arm sound" (top right) until it turns into a bell icon (again after any reload). The sun/moon button switches light/dark; dark is the default.
7. The Clips tab has three columns, "Slot 1 clip", "Slot 2 clip", "Slot 3 clip". Open any slot's dropdown: it lists the demo and dev clips grouped by folder, each with its label and onset, including the five used today: v011.avi, sample_bus.mp4, floor_sit.mp4, fire_bucket.mp4 and the fallback p3c_shove_sit_hug.mp4. Missing → the gitignored `data/` folder was not copied: copy it from the dev Mac, or choose "Upload video" at the bottom of the dropdown (or drop a file on a column).
8. One smoke test: "Slot 1 clip" → v011.avi → a red "Critical · Fighting" notification pops up bottom right and the "Alerts" tab gets a red count; click "Acknowledge" on the notification. The phone gets the Telegram alert, then the key frame with the model's summary. Then ■ on the tile and nothing else on the GPU until the demo (heat).

**Abhinav: the cameras**
9. iPhone mounted ~2 m high, floor in view, landscape, rear camera to the room, locked and still, charger on, same Apple ID as the M5, Bluetooth on (Continuity's own rules).
10. Webcam on the same stage. Tape an X on the floor that both cameras see. No window behind the actors.
11. Click the "Live" tab (with a clip still listed it asks "Switch to Live mode?": click "Switch to Live"). "Slot 1 source" → "iPhone (live)" (it starts at once), "Slot 2 source" → "<webcam>". Both tiles show a green dot and "Live" (bottom left), boxes, and a sane "ppl" count in the line under the frame. If the iPhone entry shows the webcam picture, the device order is swapped (D70): remember which entry is which.
12. Click the "Clips" tab again → "Switch to Clips" (this stops both sources; history is kept).

**Riddhi: the chat**
13. "Ask" tab: ask "How many fights were there?" → a conversational answer with #id chips; the small line says who read the question and "model answer". Ask "Summarise the incidents in the lobby today" → a paragraph and "model, N rows, …" in the small line. Both fine → reload (⌘R) so the chat log is empty at the start; Aryan re-arms the sound.
14. The three Act 3 questions on paper, exactly as written below.

**Shivansh**
15. REPORT.md to hand for Q&A (§1 is the one-minute version). Decides every fallback; nobody argues with the machine on stage.
16. The alert phone: Telegram open on the bot's chat (it has tapped Start), sound on, Do Not Disturb off, the chat not muted. The bot token does not expire.

## Opening (1 min, Shivansh)

"Everything you will see runs on this laptop: detection, the vision-language model, the database, the chat. No cloud AI: the one thing that leaves the laptop is the alert we send to the guard's phone on Telegram. Three acts: recorded clips, live cameras, then questions."

## Act 1: Clips (4 min) — on the "Clips" tab, three empty columns

**1. Fight clip**
- Aryan: "Slot 1 clip" → v011.avi. The tile appears in column 1: "Connecting…" → the frame with boxes on people, "v011.avi · Playing" bottom left, "ppl · YOLO · keep-up" in the line under it. "Verdict" below it reads "Running".
- Say: "A fight clip from a public dataset. YOLO tracks every person; a cheap rule, two people in contact and moving fast, decides when to wake the vision-language model. Watch the bottom right."
- Alert: beep, a red "Critical · Fighting" notification bottom right (it stays until "Acknowledge" or "False alarm"), a red ring and a "Fighting · N%" chip on the tile, a red count on the "Alerts" tab. The tile turns "Finished"; "Verdict" reads "Detected", with the expected label, what was detected and the alert time in the clip.
- Say: "Alert, a second or two after the model looked. The bar is the model's top three categories; the summary is written from the frames, not from a template." Click the notification's text: the "Alerts" tab opens on that alert's report (key frame, summary, top-three bar, "Trigger → alert"). Click "Acknowledge" there; an unacknowledged critical stacks the next one as "1 more unacknowledged". Every alert has exactly two actions: "Acknowledge" and "False alarm".
- Shivansh holds up the phone: the Telegram alert (what, where, how sure, how many seconds after the fight began, what to do), then the key frame with the model's one-line summary. Say: "The guard doesn't have to be at this screen: the same alert reaches their phone, with the frame the model saw. Only that still and the text leave the laptop, never video." Nothing on the phone within ~10 s: don't wait; "the phone alert needs the internet; the dashboard alert is the one that counts", and move on.
- Aryan: click the "Pipeline" tab. Say: "Each stage of that model call, timed: frame, YOLO, gate, VLM, event. Below it, what the model actually saw: the mosaic of recent frames, the hint we sent with it, and the raw JSON it streamed back." Point at the hint: "The rule tells the model what it saw and what it might be instead, a fight, or people hugging or helping someone up, and leaves the call to the frames." Click "Clips".
- If no alert by "Finished" ("Verdict" reads "Finishing", then "Missed"): open "Pipeline", point at the raw JSON ("the model's verdict is on screen either way") and move on. Do not replay.
- If the tile sticks on "connecting": the ↻ button beside the slot's dropdown plays it again (a new play replaces the old one).
- If the dropdown lists no clips: "Upload video" (bottom of the dropdown) → pick the clip from the data folder in Finder.

**2. Normal clip**
- Aryan: "Slot 2 clip" → sample_bus.mp4 (column 1 keeps its finished verdict beside it).
- Say: "A normal scene: people and motion, no incident. The rules stay quiet, so the model only takes a regular look every few seconds; that is how one laptop watches several cameras. 'GPU' in the top bar is the model's share of the last minute."
- It ends: "Finished"; "Verdict" reads "Finishing" for up to 20 s ("The model is still reviewing the last frames"), then a green "Correct" with "No incidents" under Detected. Start the next clip without waiting for it.
- If an alert fires: "A false alarm, which is exactly what the false-alarm count in the report measures." Move on.

**3. Look-alike clip**
- Aryan: "Slot 3 clip" → floor_sit.mp4.
- Say: "We filmed this one ourselves: three people, and one of us sits down cross-legged on the floor. Look-alikes are the hard part: to a motion rule, two people close together look like a scuffle and a person on the floor looks like a fall."
- The fight rule fires on the group, the model looks, answers normal, and nothing happens. Let it run to "Finished" ("Correct" after "Finishing").
- Say: "No alert. The rule woke the model, and the model said normal: that is the second filter." Aryan: click "Pipeline" (pick that camera's chip, top right): the call is there and the raw JSON says normal. Click "Clips".
- If it alerts: "That is a false alarm, and it goes in the report." Move on.

**4. Fire clip (what no rule can see)**
- Aryan: ■ the finished tile in slot 1, then "Slot 1 clip" → fire_bucket.mp4 (45 s; the dropdown shows its labelled onset, 17 s).
- Say: "A plant room. No people-rule can see fire, so the model's regular look every few seconds has to catch it, and it waits for a few looks in a row before it alerts, so expect several seconds after the flame appears." A small fire starts in a bucket by the machinery about 17 s in.
- Alert: a red "Critical · Fire smoke" notification and a ring on the tile, several seconds after the flame. Click "Acknowledge". "Verdict" puts the labelled onset next to the alert time: "onset to alert is the number we quote, never the model time alone."
- If it is missed: "Missed"; say "fire with no rule behind it is the slow path; the report has the per-category numbers" and move on.

**The judges' own video (if offered; it replaces clip 4 when time is short)**
- Aryan: any slot's dropdown → "Upload video" (or drop the file on a column). Every common format plays: mp4, mov, avi, mkv, m4v, webm, mpg, wmv, flv, 3gp, ts, mts. A clip plays once at real speed.
- "Verdict" reads "Unlabelled" (we were not told what is in it, so there is no right or wrong to show); "Detected" lists every alert with its time in the clip. After the end it shows "Finishing" for up to 20 s while the last looks finish.
- Say: "Nothing was tuned on this video. The rules decide when to look closely; the regular look covers what no rule sees, like fire, crowds, vandalism and theft."
- Say plainly what to expect if it misses: "Fights, fire, a crowd panic and a theft were caught in our tests. Falls are our weak spot: the detector loses a person lying down. Vandalism usually comes out as 'suspicious activity': the operator still gets an alert, under the wrong label." (REPORT.md §5e.) If the alert is the wrong category, click "False alarm" on it and say "that's the operator's feedback; it is logged for the next tuning round."
- A long video: let it play while Shivansh opens "Pipeline" and talks through the latest call; it plays once and stops by itself.

## Act 2: Live (3 min)

- Aryan: click the "Live" tab → "Switch to Live" (clips stop; history stays). "Slot 1 source" → "iPhone (live)", "Slot 2 source" → "<webcam>"; each starts as soon as it is chosen. Two tiles: "Connecting…" → green dot and "Live", boxes on people; each camera's details and its alerts sit under its tile.
- Say: "Two live cameras: the phone up high with the floor in view, and the webcam. Same pipeline, nothing recorded in between. The 'Now' line under each tile is the detector describing the scene between model calls."
- Abhinav and Riddhi walk at each other on the taped X, grab and shove each other chest to chest for two or three seconds, then push apart. A sustained grapple, not a tap: the model looks the moment the rule fires, and a fight it can see in those frames alerts on that first look; a brief bump can wait for the next look a few seconds later. The rehearsal decides which camera they play to: the webcam is the one proven on the shove (D72); the iPhone's high angle is not yet.
- Alert: red notification bottom right, a red ring on that camera's tile. Click "Acknowledge" on the notification after the line below. Say: "Caught live, a second or two after the model looked; the stopwatch from first contact is the onset-to-alert number in the report." The phone buzzes again (live, it counts from the moment the rule fired: nobody labelled the onset).
- Abhinav sits down on the floor and stays down for a few seconds.
- Say: "The look-alike: a person on the floor. Sitting down is not a fall; the model is told what it might be instead and judges the frames. No alert." (Time left: a hug; the rule wakes the model, the model says normal. If the hug alerts, say so: it is the look-alike our report counts.)
- If "iPhone (live)" is missing: iPhone locked, landscape, still, Bluetooth on, same Apple Account as this Mac, not paired to another Mac (Continuity serves one Mac at a time); click "Rescan" (top right of the Live tab; the list also refreshes when the window regains focus). Still missing → USB-C cable and Rescan; still missing → webcam alone, and say so.
- If the entries are swapped (D70): use the other one. Tile "Down" or "Reconnecting": click its ■ (top right of the tile) and choose it again in that slot's dropdown.
- If the shove is not caught after two tries: click the "Clips" tab → "Switch to Clips", play p3c_shove_sit_hug.mp4 in slot 1 and say plainly: "The live take missed. This is the same shove recorded on our webcam, through the same pipeline." Once the fighting alert is in (about 10 s into the clip), ■ the tile: the take goes on to a floor-sit and a hug, and the hug can raise a second, false fight alert (REPORT.md §5b). No third live try.
- If "3+ live cameras: alerts may slow" appears (amber, top right of the tab): ■ the third tile; keep two.
- "VLM errors" in "Pipeline" → "System" above 0 (red): carry on; the Terminal prints each "[vlm_error]" for afterwards.

## Act 3: Chat (2 min)

- Aryan: click the "Clips" tab → "Switch to Clips" first (stops the live cameras so the model is free; history stays). Riddhi presses / (shown on the "Ask" tab) or clicks "Ask" and types; Q1 to Q3 are also one-click suggestions under "Try". Shivansh narrates.
- Q1 "Show all tailgating events from camera 2 today" → "No matching events" for camera 2; if camera 2 has no history it also names the cameras it does have and shows the tailgating it found on another camera (the seeded Lobby event).
  Say: "The brief's own example. Camera 2 has no tailgating today, so it says so, and it shows the one it did find elsewhere instead of inventing one. A grounded no is the point."
- Q2 "What incidents happened in the last 10 minutes?" → the Act 1 and Act 2 events, one #id chip each, with a key frame, IST time and camera under the answer. Riddhi clicks one #id chip → the "Alerts" tab opens on that event's report (key frame, summary, top-three bar, "Trigger → alert") → × or Esc back to the list, then the "Ask" tab (the conversation is kept).
  Say: "Every #id is a stored event: key frame, IST timestamp, summary. Click one and you get the report you saw earlier."
- Q3 "Summarise the incidents in the lobby today" → a paragraph; the small line reads "… · model answer, N rows, M sentences dropped".
  Say: "This one is written by the model, but every sentence must cite an event; a sentence without a citation is dropped before you see it. The line underneath always says whether a template or the model answered." If it ends "→ template": "the model was busy, so it fell back to the template; alerts outrank chat." Answers take a few seconds (two model calls on a follow-up); if chat misbehaves on stage, set `chat: llm: false` in config.yaml and restart (chat v1).
- If Q2 lists nothing (Acts 1 and 2 produced no events): ask "Show all events today" (the seeded demo history, tagged "History" on the cards: "the earlier ones are seeded demo history so the chat has a day to talk about").
- If an answer says "error": ⌘R and ask again.
- The grey "History" chips in "Alerts": seeded demo history so the chat has a day to talk about; say so if asked.

## Close (1 min, Shivansh)

"Three acts, one laptop: alerts a second or two after the model looks, on screen and on the guard's phone, look-alikes declined, a fire caught with no rule behind it, and questions answered only from stored events. How we set every threshold, what we measured, and what we still get wrong are in REPORT.md. Questions?"

## Q&A crib (read numbers from REPORT.md, never from memory)

1. Cloud? No cloud AI. YOLO, the Qwen VLM in Ollama, SQLite and the chat run on this laptop; open weights, no API keys for any model, no CDN. The one thing that leaves it is the Telegram alert to the guard's phone (the alert text and one key frame with its summary, never video), through Telegram's Bot API. It is opt-in: without its two environment variables the system runs fully offline (D91).
2. Design: gate → VLM → chat. A cheap always-on gate (person tracks plus rules: fast drop, a body wider than tall, contact plus speed) decides when to look now; a regular look every few seconds covers what no rule sees (fire, crowds, vandalism, theft). The VLM sees a letterboxed mosaic of recent frames and returns structured JSON (category, probabilities from its log-probabilities, summary); events go to SQLite; the chat answers only from stored events.
3. Why a gate? A VLM on every frame does not fit on a laptop. The gate plus the regular looks (skipped while nothing and nobody moves) let one model serve several cameras.
4. How did you set the thresholds? One real pass records every model call; we replay those recordings offline with any setting, sweep each threshold on the dev clips only, re-ask the model on the recorded frames after a prompt change, then confirm with one real pass (REPORT.md §4). The thresholds sat on a plateau; the wording of the hint was what mattered (§5d).
5. Accuracy? 31 clips over 7 of the 8 categories: tuned on 16, scored on 15. Read §1 and §5a. Say it straight: we read the first test run's errors before choosing the fixes, so the test number is a check, not a clean held-out score (§3).
6. Onset-to-alert: the stopwatch from the moment the incident starts in the video to the alert on screen, what a judge would time; we never quote the model-only number alone. Fights §6a, fire/crowd/theft §6b. Our target for fights was 3 s at p95 and we miss it; the trade we made for fewer false alarms is in §6a.
7. Look-alikes and false alarms: the rules fire on hugs, bending and sitting; the model is the second filter, and the hint names the look-alikes so it does not just agree with the rule; a detector cross-check vetoes an answer that contradicts the people count. False alarms on normal footage: §5a, §5b (too little normal footage for a per-hour rate yet).
8. Honest limits (§5e): falls, because the recorded falls start with a deliberate look-alike and the detector loses a person lying down; vandalism, which the model files as suspicious activity; no tailgating clip yet; everything measured on the dev laptop, not this one.
9. Will it work on our video? Upload any common format and it runs with nothing tuned on it; see "The judges' own video" above for what to expect per category.
10. Chat limits: rules plus full-text search plus the model reading the question; it lists, counts and summarises stored events; it does not reason about video it never flagged.
11. Hardware and models: one Apple-silicon laptop, no GPU box. The VLM and the chat model are separate config lines; another open-weight model is a config change (a Gemma A/B is planned, not done).
12. Scale: the dashboard warns above two live cameras on this laptop; more cameras means more laptops or a GPU box; RTSP IP cameras plug in through "Stream URL…" in a slot's dropdown, then "Add URL".
13. The "Report" tab: the newest dev pass with the same scoring as REPORT.md (§5b), plus the operator's false-alarm count from this session.

## Timing

| Act | Minutes | Owner |
|---|---|---|
| Pre-show | 30 before | Aryan machine · Abhinav cameras · Riddhi chat · Shivansh checklist |
| Opening | 1 | Shivansh |
| Act 1 Clips (+ the judges' video if offered) | 4 | Aryan clicks · Shivansh narrates |
| Act 2 Live | 3 | Abhinav (+ Riddhi) stage · Aryan clicks · Shivansh narrates |
| Act 3 Chat | 2 | Riddhi types · Shivansh narrates |
| Close + Q&A | 1 + the rest | Shivansh; each answers their own area |

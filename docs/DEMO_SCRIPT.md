# Demo script: Round 1, Fri 16 Oct 2026, 09:00 IST (rehearse at 07:00)

Numbers: see REPORT.md. This script quotes none on purpose: say "about a second" for the alert and point at the screen for the rest.
Roles: **Aryan** drives the M5 (mouse, keyboard, every click) · **Abhinav** cameras and the staged shove · **Riddhi** the chat · **Shivansh** narrates and calls every fallback.
Words in quotes are the dashboard's own labels. "VLM" = the vision-language model (Qwen, running in Ollama; its name sits in the header).

**Rules on stage**
- No number from memory: "numbers: see REPORT.md". The one phrase we use is "about a second" for the alert after the gate fires.
- A fallback is said plainly ("the live take missed; this is the recording"), never hidden. Judges trust what they can see fail.
- Two tries at most for anything live, then the fallback. Shivansh calls it; Aryan clicks it.

## 07:00 rehearsal settles (write the answers on the paper copy)

- Which camera the shove pair plays to (webcam or iPhone), and where the X is taped.
- Wi-Fi off with a cable, or Wi-Fi radio on with no network (pre-show step 3).
- Whether "iPhone (live)" and "<webcam>" are swapped (D70), and the webcam's exact button name.
- Chrome zoom: default (the P5b layout fits 1512×982 and 1920×1080).
- Rehearsal events do NOT survive: every server start wipes the live rows (`replay.reset_live_tables_on_start`) and run_demo.sh re-seeds the demo history, so the 08:30 start begins with the seeded history only, and Act 3's "last 10 minutes" question shows just this demo's events.

## Pre-show (T-30, 08:30)

**Aryan: the machine**
1. M5 on mains. System Settings → Battery → Low Power Mode: Never. Lock Screen → turn display off on power adapter: Never. Focus: Do Not Disturb.
2. Mirror the display to the projector (mirror, not extend) so Aryan sees what the judges see.
3. Internet off. Wireless Continuity Camera needs the Wi-Fi and Bluetooth radios on (no network needed), so decide with Abhinav: USB-C cable to the iPhone and Wi-Fi off, or Wi-Fi on but joined to no network. Either way nothing leaves the laptop, which is the claim we make.
4. Terminal, in the repo folder: `./run_demo.sh`
   It checks uv, Chrome, the YOLO weights and the Python env, starts Ollama, warms the model, re-seeds the chat history (times relative to now), rebuilds the dashboard if stale, starts the server and opens Chrome at http://localhost:8000. It ends with "dashboard ready". Any red line names its own fix (port 8000 busy → it prints the `kill` to run); fix it and re-run.
5. Chrome, not Safari. One window, one tab, full screen (View → Enter Full Screen). Default zoom (the layout fits the laptop and the projector without ⌘−). Terminal stays behind Chrome.
6. Top bar: the "Local · offline" badge has a green dot (red "Reconnecting" = the server is gone); "Clips" is selected in the centre toggle; the right rail shows "Alerts". Click the blue "Arm sound" (top right) until it turns into a grey bell (again after any reload).
7. "Clip library" lists v011.avi, sample_bus.mp4, p3c_shove_sit_hug.mp4 and idle_60s.mp4 (and the rest). Missing → the gitignored `data/` folder was not copied: copy it from the dev Mac, or use "Upload video" in the library header (or drop a file on the library).
8. One smoke test: click the v011.avi row → red "Critical · Fighting" banner and a card in "Alerts"; click "Ack" on the banner. Then nothing else on the GPU until 09:00 (heat).

**Abhinav: the cameras**
9. iPhone mounted ~2 m high, floor in view, landscape, rear camera to the room, locked and still, charger on, same Apple ID as the M5, Bluetooth on (Continuity's own rules).
10. Webcam on the same stage. Tape an X on the floor that both cameras see. No window behind the actors.
11. Click "Live" → "Add source" → "iPhone (live)", then "<webcam>". Both tiles show a green dot and "Live" (bottom left), boxes, and a sane "ppl" count in the line under the frame. If the iPhone button shows the webcam picture, the device order is swapped (D70): remember which button is which.
12. Click "Clips" again (this stops both sources; history is kept).

**Riddhi: the chat**
13. Ask "How many fights were there?" → a conversational answer with #id chips; the small line says who read the question and "model answer". Ask "Summarise the incidents in the lobby today" → a paragraph and "model, N rows, …" in the small line. Both fine → reload (⌘R) so the chat log is empty at 09:00; Aryan re-arms the sound.
14. The three Act 3 questions on paper, exactly as written below.

**Shivansh**
15. REPORT.md numbers to hand for Q&A. Decides every fallback; nobody argues with the machine on stage.

## Opening (1 min, Shivansh)

"Everything you will see runs on this laptop: detection, the vision-language model, the database, the chat. The internet is off. Three acts: recorded clips, live cameras, then questions."

## Act 1: Clips (3 min) — already in "Clips" mode, "Alerts" tab in the right rail

**1. Fight clip**
- Aryan: click the v011.avi row in "Clip library". A tile appears: "Connecting…" → the frame with boxes on people, "v011.avi · Playing" bottom left, "ppl · YOLO · keep-up" in the line under it. "Verdict" next to it reads "Running".
- Say: "A fight clip from a public dataset. YOLO tracks every person; a cheap rule, two people in contact and moving fast, decides when to wake the vision-language model. Watch the top right."
- Alert: beep, red "Critical · Fighting" banner at the top of the right rail (it stays until "Ack"), a red ring and a "Fighting · N%" chip on the tile, a new card at the top of "Alerts" with the top-three bar and "trigger → alert"; the summary fills in a moment later. The tile turns "Finished"; "Verdict" reads "Detected": expected against detected and the alert time in the clip.
- Say: "Alert, about a second after the gate fired. The bar is the model's top three categories; the summary is written from the frames, not from a template." Click "Ack" on the banner (operator acknowledgement; an un-acked banner stacks the next one as "1 more unacknowledged").
- Aryan: click the "Pipeline" tab. Say: "Each stage of that model call, timed: frame, YOLO, gate, VLM, event. Below it, what the model actually saw: the mosaic of recent frames, the hints we sent with it, and the raw JSON it streamed back." Click "Alerts".
- If no alert by "Finished" ("Verdict" reads "Missed"): open "Pipeline", point at the raw JSON ("the model's verdict is on screen either way") and move on. Do not replay.
- If the tile sticks on "connecting": click the row again (a new play replaces the old one).
- If "Clip library" is empty: "Upload video" → pick the clip from the data folder in Finder.

**2. Normal clip**
- Aryan: click the sample_bus.mp4 row.
- Say: "A normal scene: people and motion, no incident. The gate stays quiet, so the model is hardly called; that is how one laptop watches several cameras. 'GPU' in the top bar is the model's share of the last minute."
- It ends: "Finished"; "Verdict" reads a green "Correct" with "No incidents" under Detected.
- If an alert fires: "A false alarm, which is exactly what the false-alarm rate in the report measures." Move on.
- If it runs long: point at "Alerts" (nothing new) and start the next clip; it replaces this one. Spare normal clip: idle_60s.mp4 (a full minute long).

**3. Look-alike clip**
- Aryan: click the p3c_shove_sit_hug.mp4 row (its "Onset" column shows the labelled 5.6 s).
- Say: "We filmed this one ourselves: a shove, then someone sits on the floor, then a hug. Look-alikes are the hard part; a hug and a grapple look the same to a motion rule."
- Shove → fighting alert (banner, card, ring on the tile). Sit → nothing. Hug → the gate wakes the model, the model answers normal → nothing. Let it run to "Finished".
- Say: "One alert, for the shove. The hug woke the model and the model said normal: that is the second filter. The verdict puts the labelled onset next to the alert time, and onset to alert is its one big number: the number we quote, never the model time alone." Click "Ack" on the banner.
- Aryan: click "Pipeline": the last call on that camera is the hug, raw JSON says normal. Click "Alerts".
- If the sit or the hug alerts: "That is a false alarm, and it goes in the report." If the shove is missed: Pipeline raw JSON, move on; Act 2 stages it live.

## Act 2: Live (3 min)

- Aryan: click "Live". Tiles clear. In "Add source" click "iPhone (live)", then "<webcam>". Two tiles: "Connecting…" → green dot and "Live", boxes on people.
- Say: "Two live cameras: the phone up high with the floor in view, our fall camera, and the webcam. Same pipeline, nothing recorded in between. The 'Now' line under each tile is the detector describing the scene between model calls."
- Abhinav and Riddhi walk at each other on the taped X, bump chest to chest, hold it a beat, push apart. A real push, not a tap. The 07:00 rehearsal decides which camera they play to: the webcam is the one proven on the shove (D72); the iPhone's high angle is not yet.
- Alert: banner, card, and a red ring on that camera's tile. Click "Ack" on the banner after the line below. Say: "Caught live. The alert came about a second after the gate fired; the stopwatch from first contact is the onset-to-alert number in the report."
- Abhinav sits down on the floor and stays down for a few seconds.
- Say: "The look-alike: a person on the floor. The fall rule wants a fast drop and a horizontal body; sitting down is neither. No alert." (Time left: a hug; the gate wakes the model, the model says normal.)
- If "iPhone (live)" is missing: iPhone locked, landscape, still, Bluetooth on; click "Clips" then "Live" to rescan. Still missing → webcam alone, and say so.
- If the buttons are swapped (D70): use the other one. Tile "Down" or "Reconnecting": click its ■ (top right of the tile) and add it again.
- If the shove is not caught after two tries: click "Clips", play p3c_shove_sit_hug.mp4 and say plainly: "The live take missed. This is the same sequence recorded on our webcam, through the same pipeline." No third try.
- If "3+ live cameras: alerts may slow" appears (amber, above the tiles): ■ the third tile; keep two.
- "VLM errors" in "Pipeline" → "System" above 0 (red): carry on; the Terminal prints each "[vlm_error]" for afterwards.

## Act 3: Chat (2 min)

- Aryan: click "Clips" first (stops the live cameras so the model is free; history stays). Riddhi presses / (or clicks the "Ask" tab) and types; Q1 to Q3 are also one-click suggestions on the empty tab. Shivansh narrates.
- Q1 "Show all tailgating events from camera 2 today" → "No matching events" plus the cameras it does have.
  Say: "The brief's own example. No camera 2 has tailgating today, so it says so and names the cameras it knows. A grounded no is the point: it never invents an event."
- Q2 "What incidents happened in the last 10 minutes?" → the Act 1 and Act 2 events, one #id chip each, with a key frame, IST time and camera under the answer. Riddhi clicks one #id chip → the event opens (key frame, summary, top-three bar, "Trigger → alert") → × or Esc.
  Say: "Every #id is a stored event: key frame, IST timestamp, summary. Click one and you get the card you saw earlier."
- Q3 "Summarise the incidents in the lobby today" → a paragraph; the small line reads "… · model answer, N rows, M sentences dropped".
  Say: "This one is written by the model, but every sentence must cite an event; a sentence without a citation is dropped before you see it. The line underneath always says whether a template or the model answered." If it ends "→ template": "the model was busy, so it fell back to the template; alerts outrank chat." Answers take a few seconds (two model calls on a follow-up); if chat misbehaves on stage, set `chat: llm: false` in config.yaml and restart (chat v1).
- If Q2 lists nothing (Acts 1 and 2 produced no events): ask "Show all events today" (the seeded demo history, tagged "History" on the cards: "the earlier ones are seeded demo history so the chat has a day to talk about").
- If an answer says "error": ⌘R and ask again.
- The grey "History" tags in "Alerts": seeded demo history so the chat has a day to talk about; say so if asked.

## Close (1 min, Shivansh)

"Three acts, one laptop: alerts about a second after the gate fires, look-alikes declined, questions answered only from stored events. The measurements, and what our clip set cannot yet measure, are in REPORT.md. Questions?"

## Q&A crib

1. Cloud? None. YOLO, the Qwen VLM in Ollama, SQLite and the chat run on this laptop; the internet is off right now. Open weights, no API keys, no CDN.
2. Design: gate → VLM → chat. A cheap always-on gate (person tracks plus rules: fast drop, horizontal body, contact plus speed) decides when to look; the VLM sees a letterboxed mosaic of recent frames and returns structured JSON (category, probabilities, summary); events go to SQLite; the chat answers only from stored events.
3. Why a gate? A VLM on every frame does not fit on a laptop. The gate plus periodic baselines (only when the scene changed) let one model serve several cameras.
4. Onset-to-alert: the stopwatch from the moment the incident starts in the video to the card on screen, what a judge would time. We never quote the model-only number alone. Numbers: see REPORT.md.
5. Look-alikes and false alarms: the gate fires on hugs and bending; the model is the second filter; a detector cross-check vetoes an answer that contradicts the people count.
6. Honest limit: a small clip set. No fall or tailgating clips yet, so no numbers for those; the fall gate exists, tailgating needs a door zone on a door camera.
7. Honest limit: thresholds were tuned on the dev clips only and are judged on a held-out test split later; today's clip results are dev results.
8. Chat limits: rules plus full-text search plus a model fallback for summaries. It lists, counts and summarises stored events; it does not reason about video it never flagged.
9. Hardware: one Apple-silicon laptop, no GPU box. Model-independent: the VLM is a config line (a Gemma A/B is planned).
10. Scale: the dashboard warns above two live cameras on this laptop; more cameras means more laptops or a GPU box; RTSP IP cameras plug in through "Add URL".

## Timing

| Act | Minutes | Owner |
|---|---|---|
| Pre-show | 30 before | Aryan machine · Abhinav cameras · Riddhi chat · Shivansh checklist |
| Opening | 1 | Shivansh |
| Act 1 Clips | 3 | Aryan clicks · Shivansh narrates |
| Act 2 Live | 3 | Abhinav (+ Riddhi) stage · Aryan clicks · Shivansh narrates |
| Act 3 Chat | 2 | Riddhi types · Shivansh narrates |
| Close + Q&A | 1 + the rest | Shivansh; each answers their own area |

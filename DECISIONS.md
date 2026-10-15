# HackHive: Decisions & Contracts

> **Project:** Honeywell Problem Statement 3: Open-Source AI System for Live Video Event Summarization, Classification & Conversational Querying
> **Format:** 48-hour hackathon · **Builder:** Claude Code (automated) · **Team:** tests, ideates, decides, pitches
> **Status:** 🟡 Questions open: answer them as a team, then Claude locks them into §5 and starts building.

---

## How to use this doc

1. Read **§1** (what we're building) and **§2** (roles) so everyone shares the same picture.
2. Discuss **§3**. For each question, write the answer on its `Decision:` line. "Go with recommended" is a valid answer.
3. Answer the **🔴 Blocking** questions first. Building can't start without them. 🟡 can be answered during the hackathon; 🟢 has a sensible default.
4. Review the **§4 draft contracts** and mark anything you'd change.
5. When it's done, Claude moves every answer into **§5 Decision Log**. That log is the single source of truth. Change a decision only by adding a new log entry; never by editing an old one silently.

---

## 1. What we're building (the 1-page version)

**The problem:** Security operators can't watch every camera feed. Incidents are found after the fact, and searching footage is slow.

**Our system, in one sentence:** A fully local app that watches live camera feeds, flags incidents (fall, fight, fire, crowd, tailgating, suspicious activity) within ~2–3 s, writes a short summary of each, stores it, and lets anyone ask questions in plain English: *"Show tailgating events from camera 2 today."*

**How it works (pipeline):**
```
Camera (file / webcam / RTSP / phone)
  → YOLO + ByteTrack: finds & tracks people/objects, ~10 FPS, fast
  → Gate rules: "a person went horizontal", "2 people overlapping + fast motion", "8+ people", "2 people through the door"
  → VLM (vision-language model): every 3 s, or immediately when a gate fires, looks at a 2×2 grid of the last 2 s
      and returns {category, confidence, summary}
  → Cross-check + event merging: one fight = one event with start/end, not 40 rows
  → SQLite: every summary + every incident + key frames
  → Dashboard: live cameras, incident feed with alerts, latency metrics, chat
  → Chat: small local LLM turns the question into filters → SQL → answer that cites real event IDs only
```

**Official evaluation criteria (confirmed by the organisers, see D6):**

| Criterion | What it means for us |
|---|---|
| **Summarisation** | Every window and every incident gets an accurate, objective summary. We also keep a live "what's happening now" summary per camera. |
| **Classification of incidents** | Correct category + meaningful confidence, measured per class. |
| **Chatbot interface** | Natural questions → correct, grounded answers with evidence (event cards + frames). |
| **Approach + workflow demonstration** | Judges must *see* the pipeline working: a live **Workflow view** showing frame → YOLO → gate → VLM → event → DB → chat with per-stage timings. |
| **🔥 MAJOR: Latency** | How quickly frames are processed and summarised. This must be the best in the room: shown live, measured, reported. |
| **🔥 MAJOR: Accuracy** | Classification + summary correctness. This must be the best in the room: measured on a held-out test set, reported. |
| **Implementation quality** | Clean architecture, reproducible setup, honest numbers that match the live demo. |

**Design principle that follows:** latency and accuracy pull in opposite directions (bigger model = more accurate, slower). We use **one well-chosen model plus engineering tricks** (see Q35): stream the category first so the alert fires almost instantly, feed the model multiple frames plus detector evidence, and look again only when it's unsure.

**Hard rules:** open-source models only · weights downloaded and run locally · **no API keys, not even for open-source hosted models** · runs on a laptop/consumer GPU · deliverable includes an **accuracy & latency report**.

**Our edge:** speed shown live on screen, multi-frame understanding, detector-grounded prompts, zero-hallucination chat, measured numbers, a polished demo.

---

## 2. Roles (proposed: confirm in Q1)

Claude writes the code. Each teammate **owns an area**: you decide, test, break things, collect data, and file issues. Claude fixes and improves.

| Role | Owns (decides + tests) | Main activities |
|---|---|---|
| **R1: Vision Lead** | Detection, tracking, gate rules, cameras | Record staged footage, tune gate thresholds, test webcam/phone/RTSP inputs, find false triggers |
| **R2: AI/Model Lead** | VLM choice, prompt, categories, accuracy | Run model bake-offs, review misclassified frames, propose prompt and definition changes |
| **R3: Data & Chat Lead** | Datasets, labels, DB, chatbot | Build and label the test/dev sets, write 20+ chat test questions, try to make the chatbot hallucinate |
| **R4: Product & Pitch Lead** | Dashboard UX, report, demo, slides | Use the app like an operator, give UI feedback, own the demo script, slides and backup video, run rehearsals |

The team captain (Q1) breaks ties and has the final say on scope cuts.

---

## 3. Questions to answer

Format: **options** → **⭐ recommendation (why)** → `Decision:` line for your answer.

### A. Team, event & logistics

**Q1 🔴 Team members and roles.** Who takes R1–R4? Who is captain? (If you have 3 or 5 people, say so and Claude will reshape the roles.)
- ⭐ Captain = the person who runs the builder machine and talks to Claude most.
- Team: **Shivansh, Riddhi, Abhinav, Aryan** ✅
- `Decision:` *(proposed: swap freely, then confirm)*
  - Captain + R2 AI/Model Lead: **Shivansh** (runs the builder Mac, so model/prompt work stays next to Claude)
  - R1 Vision & Cameras Lead: **Abhinav**
  - R3 Data & Chat Lead: **Riddhi**
  - R4 Product & Pitch Lead: **Aryan**

**Q2 🔴 Event timing & judging format.**
- Start date/time, end date/time, timezone (assumed IST):
- Is there a mid-point review or checkpoint? When?
- Final judging: live demo? slides? code walkthrough? Q&A? **How many minutes?**
- What must be submitted: repo link, video, report PDF, deck?
- `Decision:` Ends **the morning of Sat 17 Oct 2026** ✅. Still needed: exact end time, whether the 48 h clock has already started, judging format/length, submission items.

**Q3 🔴 Is building before the hackathon allowed?** (Writing code, or only research/downloads?)
- A: Code allowed before → Claude builds the whole MVP before day 1 and the 48 h go to testing.
- B: Only ideas/downloads allowed → Claude builds the MVP in the first ~16 h.
- ⭐ Ask the organisers explicitly and get the answer in writing (chat/email). Downloading weights and datasets beforehand is almost certainly fine either way.
- `Decision:` ✅ **B**: all building happens inside the 48 h. Before the event we only research, download models/datasets and film clips (confirm that filming beforehand is OK). Logged as D7.

**Q4 🟡 Venue conditions.** Reliable Wi-Fi? Power at desks? Can we bring an external monitor/webcam? Is there a door nearby for filming tailgating?
- ⭐ Assume **no internet**: everything runs offline, all weights pre-downloaded.
- `Decision:`

**Q5 🟢 Code hosting & workflow.**
- A: Private GitHub repo; Claude commits to short feature branches → merges to `main` after self-tests; `main` always runnable.
- B: Claude commits straight to `main`.
- ⭐ A. Plus **GitHub Issues as the feedback channel**: testers file issues with labels (`bug`, `accuracy`, `ui`, `idea`) and Claude picks them up. This keeps feedback from getting lost in chat.
- `Decision:`

**Q6 🟢 How many Claude Code "builder" sessions?**
- A: One builder (captain's Mac); teammates pull `main` and test on their own machines.
- B: Several teammates each run Claude Code on separate modules.
- ⭐ A. One builder avoids merge chaos. Claude can run parallel work internally. Teammates' time goes to testing.
- `Decision:`

### B. Hardware (critical: decides model size)

**Q7 🔴 Every teammate's machine.** Chip and RAM (Apple menu → About This Mac). Does anyone have an **NVIDIA GPU laptop**?
- Known: Captain's Mac = **Apple M4, 16 GB**.
- `Decision:`
  - ✅ Max RAM across the team = 16 GB. One teammate has an **M5**.
  - **Switch rule:** in H0–3 Claude runs the same benchmark on the M4 and the M5. Switch the demo to the M5 only if it is **≥ 25 % faster at p95 VLM latency** (likely: M5 GPUs have neural accelerators that speed up prompt/image processing a lot). Otherwise stay on the M4.

**Q8 🔴 Which machine runs the demo?**
- ⭐ The Mac with the **most unified memory** (an M-series Pro/Max with 32 GB+ beats a base M4 16 GB). If 16 GB is the best we have, it works, but we'll likely use a ~2B VLM and share one model for vision and chat.
- An NVIDIA laptop with ≥8 GB VRAM would also be strong (vLLM). Only choose it if it's equally available.
- `Decision:` ✅ Captain's **Apple M4, 16 GB** (unless a teammate's Mac turns out to have more RAM; check Q7). Logged as D8.

**Q33 🔴 Hardware budget: "at any cost" applies here first.** Latency is mostly decided by the demo machine. Are we willing to **borrow, rent or buy** a stronger machine for the 48 h?
- A: Use the best Mac in the team as-is
- B: Borrow a Mac with an M-series **Pro/Max chip and 32 GB+** (from a friend, senior, lab or college); roughly 2–3× faster for a VLM than a base M4 16 GB
- C: Borrow or rent an **NVIDIA RTX laptop** (4070+ with 8 GB+ VRAM) → vLLM with batching, typically the fastest option for this workload
- ⭐ B or C if at all possible. Everything still runs locally/on-prem, so it's fully within the rules. Claude benchmarks every candidate machine on day 0 and we demo on the fastest.
- `Decision:` ✅ **A**: no stronger machines are available. We win on model choice + engineering (two tiers, gating, small images, short outputs, MLX). Logged as D8.

**Q9 ✅ Camera sources for the demo** (team decision: pre-recorded videos for the data + webcam/phone for live).

We run **three kinds of "camera" at once**; the system treats them all the same way:

| Source | How it connects to the Mac | What it proves | Reliability |
|---|---|---|---|
| **Pre-recorded videos** (datasets + our clips) | Played at real-time speed and looped. Optionally re-streamed through a local **RTSP server (MediaMTX)** so they look exactly like IP cameras | "Works with standard CCTV/IP-camera streams"; repeatable incidents every loop | ★★★ |
| **MacBook webcam** | Built-in camera (OpenCV device 0) | Live, unscripted: the fall demo in front of the judges | ★★★ |
| **Phone as a camera** | iPhone or Android, see below | A second live viewpoint, e.g. pointed at a door for tailgating | ★★ (depends on the network) |

**Phone options (decide by which phones you have):**
- **iPhone → Continuity Camera** (built into macOS): the iPhone appears as a normal webcam. It works over Wi-Fi + Bluetooth, or **via USB cable (most reliable)**. Needs the same Apple ID on the Mac and iPhone. Zero setup in our code.
- **Android → "IP Webcam" app** (free): the phone serves a stream at `http://<phone-ip>:8080/video`, which we put in `config.yaml` as the camera source. Also works with "DroidCam" (USB or Wi-Fi).
- **Any phone → RTSP/SRT broadcaster app** (e.g. Larix Broadcaster) pushing to MediaMTX on the Mac: the most "real IP camera"-like option.

**Network trap at venues:** many venue/college Wi-Fi networks block device-to-device traffic, so the phone and Mac can't see each other. Fixes, in order: (1) use a **USB cable** (Continuity Camera / DroidCam USB); (2) connect the Mac to a **second phone's hotspot** and put the camera phone on the same hotspot (a local network doesn't need internet). Test this on day 1, not at judging time.

**Camera placement tips:** mount high (shelf/tripod, ~2 m), angled down like real CCTV; steady; the door fully in frame for tailgating; avoid pointing at a bright window (backlight ruins detection).

- **Demo layout:** cam1 = webcam (live), cam2 = phone at a door (live), cam3–4 = looping recorded incidents (fight, fire, crowd). On 16 GB we run 3–4 cameras; Claude measures the limit.
- `Decision:` ✅ Videos + webcam + phone. **Still needed: which phones (iPhone/Android) the team has.**

**Q10 🔴 VLM serving runtime on Mac.** (All are local and expose an OpenAI-compatible localhost URL, so swapping is a config change.)
- A: **Ollama**: easiest, JSON-schema structured output, very stable
- B: **LM Studio** (MLX engine): usually faster on Apple Silicon, GUI for model management
- C: **mlx-vlm** (Python server): fastest and most control, slightly more fragile
- D: llama.cpp `llama-server`: fast, portable, more manual
- ⭐ **Decide by benchmark on day 0:** Claude times A vs C (and B if installed) on the demo Mac with our real prompt and keeps the fastest one that returns valid JSON every time. Default if no time: **Ollama**.
- `Decision:`

**Q11 ✅ VLM candidates.** *(Researched on 2026-10-15 against current releases. Constraint: M4, 16 GB, no stronger hardware.)*

| Model | Size (4-bit) | License | Why it's on the list | Mac runtime |
|---|---|---|---|---|
| **Qwen3.5-4B** | ~3.4–4 GB | Qwen open license (Apache-style; check the HF card) | Strongest all-rounder at this size; best multi-image score (MuirBench 62), which matters for our 4-frame grids | Ollama (`qwen3.5:4b`, `:4b-mlx`), LM Studio, mlx-vlm |
| **Qwen3.5-2B** | ~2.7–3.1 GB | same | ~2× faster than the 4B, same family and prompt | Ollama (`qwen3.5:2b`, `:2b-mlx`) |
| **LFM2.5-VL-3B / 1.6B** (Liquid AI, Aug 2026) | ~2 / ~1.2 GB | LFM Open License v1.0 (free; commercial use only under $10M revenue, so not OSI) | **Best real-world-scene score (RealWorldQA 73.1)** and built for low latency with multiple frames | mlx-vlm, LM Studio (MLX) |
| **Gemma 4 E4B / E2B** | ~3–5 GB | **Apache 2.0** | Judges named Gemma; native video input; cleanest license | Ollama, mlx-vlm |

*Caveat: the published benchmark table comes from Liquid AI's own blog, so it may favour their model. We trust only our own bake-off on our own clips.*

- **Plan:** in the first 3 h of the hackathon, Claude benchmarks all four on the demo Mac with our real prompt and the dev clips. It measures latency p50/p95, JSON validity and dev-set macro F1.
- **Expected outcome** (to confirm by benchmark): **one model** (Q35) for vision + chat: Qwen3.5-4B or LFM2.5-VL-3B if it meets ≤ 1.5 s p95, otherwise its 2B/1.6B sibling.
- **Tie-breaker:** on equal accuracy, prefer the Apache-licensed model (Qwen3.5 / Gemma 4). It's the cleaner "open-source" story for the judges.
- `Decision:` ✅ Shortlist approved; final pick by the hour-0–3 benchmark (logged as D9)

**Q35 ✅ Inference architecture: critique of "two-tier" and the recommended design**

*Original proposal:* a small VLM raises alerts; a bigger VLM verifies every event and rewrites the summary.

**Critique (why it's weaker on a 16 GB M4 than it looks):**
1. **One GPU, two models → contention exactly when it matters.** On a Mac, both models share one GPU. The verifier runs *when an incident happens*, which is exactly when tier 1 must be fastest. Tier-1 latency would spike during incidents, the worst moment for judges to watch.
2. **Memory pressure.** Two VLMs + YOLO + browser + app on 16 GB risks swapping, and swapping kills latency.
3. **The final summary arrives late.** Judges score "how quickly we summarise". If the good summary only appears after the verifier (~4–6 s), that's the number they'll see.
4. **Flip-flopping alerts look bad.** "Fight!" followed by "dismissed by verifier" confuses a live audience more than it impresses.
5. **Uncertain gain.** On this task, a 4B model often isn't much better than a 2B one. Multi-frame input, detector hints and event merging usually matter more than model size, and two models double the prompt tuning.

**✅ Recommended instead: "One model, done right" (single VLM + 4 tricks)**
1. **One VLM, the best one the benchmark allows** (4B if it meets ≤ 1.5 s p95 on the demo Mac, otherwise 2B). It also powers the chatbot, so there's one model in memory and no contention.
2. **Streaming early alert.** The model's JSON starts with `category`. We stream the output and **fire the alert the moment the category word arrives** (≈ image-processing time + ~0.1 s), while the summary keeps streaming into the card in real time. Fast alert *and* full summary, from one call. This is the main latency trick.
3. **Prompt caching + small inputs.** A fixed system prompt cached by the runtime, a 2×2 grid of small tiles (~336 px), and a short summary cap (~30 words). This cuts every call's cost.
4. **Re-look only when unsure.** If confidence is in a grey zone (≈ 0.4–0.7), the *same* model looks again with more frames / higher resolution, **only when the GPU queue is empty**, so it never delays a live alert. Clear cases (most of them) never pay this cost.
5. **Optional accuracy booster: a fast learned classifier, decided by data.** If the dev-set accuracy of the VLM alone is below target, Claude trains a tiny classifier (a linear layer on top of a frozen SigLIP2 image model; minutes to train on the thousands of labelled dataset clips; ~20 ms per frame). Its prediction is passed to the VLM as an extra hint and combined into the confidence. Allowed: this is fine-tuning a small head, not training from scratch.

**What we report:** time-to-alert (category streamed), time-to-full-summary, % of windows needing a re-look, and accuracy with vs without each trick (ablation), which makes a strong "approach" story for the judges.

- `Decision:` ✅ *Recommended design adopted unless the team objects* (logged as D13). Tricks 1–4 are built by default; trick 5 only if the dev-set numbers call for it.

**Q12 🟡 Chat LLM.**
- A: **Reuse the same VLM** for chat (one model in memory, best for 16 GB)
- B: Separate text model (Qwen3-4B-Instruct-2507 or Qwen3-1.7B, 4-bit)
- ⭐ A if the demo machine has 16 GB; B if ≥ 24 GB (then chat never slows down the live pipeline).
- `Decision:` ✅ **A** (follows from D8): chat reuses the single VLM (Q35).

**Q13 🟡 Detector.**
- A: Ultralytics YOLO11n/s (or YOLO26), run on Apple GPU (`mps`) or exported to CoreML (Neural Engine). AGPL-3.0 license.
- B: An Apache-licensed alternative (RT-DETR via HF transformers / YOLOX): cleaner license, more work, slower
- ⭐ A, with a CoreML export if it's faster on the benchmark. AGPL is fine for an open hackathon prototype; we state it in the README. Stretch: add **YOLO-pose** for better fall/fight detection.
- `Decision:`

**Q14 🟢 Licensing stance in the pitch.**
- ⭐ "Every model is open-weight and runs locally; licenses are listed in the README." We do **not** claim "100% OSI open source" unless every component qualifies.
- `Decision:`

**Q15 🟢 Voice query (stretch)?** Ask the chatbot by voice using local Whisper (whisper.cpp / mlx-whisper).
- ⭐ Yes as a **stretch only** (after Q23 must-haves). It's a strong demo moment and cheap to add.
- `Decision:`

### D. Product scope

**Q16 🔴 Final category list.** Proposed (with severity):

| Category | Definition | Severity | Audible alert |
|---|---|---|---|
| `fire_smoke` | Visible flames or smoke | critical | yes |
| `fighting` | 2+ people punching, kicking, shoving, wrestling | critical | yes |
| `person_down` | Person lying/collapsed on the floor (not sitting) | critical | yes |
| `crowd_incident` | Abnormally dense gathering, or a crowd suddenly running | high | yes |
| `suspicious_activity` | Loitering, trespass/climbing, vandalism, theft, abandoned bag, visible weapon | medium | no |
| `tailgating` | 2+ people through a door zone on one opening | medium | no |
| `normal` | none of the above | none | no |

- Add, remove or split anything? (e.g., a separate `weapon` category = critical? `vandalism` separate?)
- ⭐ Keep these 7. More categories = lower accuracy and more labeling. Subtypes (e.g. "weapon") go inside the summary text.
- `Decision:`

**Q17 🟡 How many cameras simultaneously in the demo?**
- ⭐ 4 on a ≥24 GB Mac, 2–3 on 16 GB. Claude measures the real limit on day 0.
- `Decision:`

**Q18 🟢 What counts as an "event"?**
- A: Merged incident with start/end time; alert fires once when it opens ⭐
- B: Every VLM window is its own row
- ⭐ A. Raw windows are still kept in an `observations` table so the chat can answer "what happened at 3 pm?" even when nothing was flagged.
- `Decision:`

**Q19 🟡 Frontend technology.**
- A: **React + Vite + Tailwind**, bundled locally (works offline), most polished, easy for Claude to build
- B: Plain HTML/JS: simplest, fewer moving parts
- C: Streamlit: fastest to start, but janky for live video + chat (full-page reruns)
- ⭐ A. Polish wins demos, and Claude is building it anyway. The backend is FastAPI (Python).
- `Decision:`

**Q20 🟢 Python tooling.**
- ⭐ Python 3.12 + **uv** (fast, reproducible installs: one `uv sync` and a teammate's machine is ready).
- `Decision:`

**Q21 🟢 Storage.**
- ⭐ SQLite (WAL mode) + SQLite FTS5 for text search; key frames as JPEG files on disk. Embeddings only as a stretch.
- `Decision:`

**Q22 🟢 Timezone & time display.**
- ⭐ Stored as epoch seconds; displayed and parsed in **IST (Asia/Kolkata)**. Video-file "cameras" use wall-clock time when played, so "today" works.
- `Decision:`

**Q23 🔴 Must-have vs stretch list.** Tick or reorder:
- Must: file + webcam + simulated RTSP input · YOLO tracking · gate + 3 s baseline · VLM JSON classification · event merging · SQLite · dashboard (live grid, incident feed, alerts, metrics strip) · grounded chat with time/camera/category filters · accuracy & latency report tab · one-command demo script
- Must (added for the evaluation criteria, D6):
  - **Workflow view**: a live pipeline diagram where each stage lights up as a frame passes through it (capture → YOLO → gate → VLM → verifier → DB → UI), showing per-stage ms, the current mosaic sent to the VLM, the hints, and the raw JSON returned. This is how judges *see* the workflow and the latency.
  - **Live scene summary per camera**: a rolling "what's happening now" line under each camera feed, updated every window.
  - **Periodic digest**: every N minutes, or on request ("summarise the last 10 minutes on cam2"), a short narrative built from the observations.
- Stretch (in order): ① chat "look again" (VLM re-reads a stored key frame to answer "what was the person wearing?") ② per-camera timeline ③ phone as a real IP camera ④ voice query ⑤ face blur on stored key frames (privacy story) ⑥ incident PDF export ⑦ YOLO-pose ⑧ semantic search with embeddings
- `Decision:`

**Q24 🟡 Product name & identity.** (For the UI, slides and repo name. Don't use Honeywell's branding in the product.)
- Ideas: *Sentinel*, *Vigil*, *WatchLoop*, *Argus*, *OnPrem Eye*
- `Decision:`

### E. Data, evaluation & targets

**Q25 🔴 Filming our own clips: who acts, and where?**

*Why this is needed, in plain words:* the public datasets above cover fights, falls, fire and crowds, but **nobody has published videos of tailgating**, so the only way to test that category is to film it ourselves. Our own clips also matter because (1) the live demo happens in *our* room, with *our* lighting and *our* faces, and the system must work there, not only on YouTube footage; (2) judges trust a demo more when they see it work on fresh footage. It's just phone videos of teammates acting out the scenarios.

**Shot list (phone camera on a shelf or tripod, held still, at head height or higher like a CCTV camera, 10–20 s per clip):**

| Category | What to act out | How many |
|---|---|---|
| `tailgating` | Person A opens a door and walks through; person B follows close behind before it shuts. Also film **normal** single entries for contrast. | 15 tailgating + 10 normal entries |
| `person_down` | Walk in, then slowly "faint" onto a mat or bed. Also film *sitting on the floor* and *bending to pick something up* (these must **not** trigger). | 10 falls + 5 look-alikes |
| `fighting` | Slow, choreographed pushing/shoving with no real contact. Also film *hugging* and *high-fives* (must **not** trigger). | 8 + 5 look-alikes |
| `crowd_incident` | Everyone (plus friends) gathers tightly, then suddenly runs out of frame. | 5 |
| `suspicious_activity` | Leave a bag and walk away; someone loitering and peering into a room for 30+ s. | 5 + 5 |
| `normal` | People walking, talking, sitting, working. | 10 |

- Film in 2–3 different places (corridor, room, doorway) and under different lighting (bright, dim, evening).
- Everyone filmed must agree to it. Don't film strangers.
- Film **before the hackathon** if possible (filming isn't building code); otherwise in the first evening.
- `Decision:` ✅ Team supplies **already-filmed videos** for the data; live scenes come from the webcam/phone.
- ⚠️ **Remaining gap: tailgating.** No public dataset exists, so unless the team's videos include door entries, we have no way to measure tailgating accuracy. **Fix (20 minutes):** film ~15 tailgating + ~10 single-entry clips with the phone at any door during day 1. Same for the "look-alike" clips (sitting on the floor, hugging), which are the best way to catch false alarms.

**Q26 ✅ Public datasets: free, no request forms** (a free Kaggle account is enough):

| Our category | Dataset | What's in it | Where |
|---|---|---|---|
| `fighting` + `normal` | **Real Life Violence Situations** | 1,000 street-fight + 1,000 non-violent real videos (YouTube-sourced) | kaggle.com/datasets/mohamedmustafa/real-life-violence-situations-dataset |
| `person_down` | **Le2i Fall Dataset** (mirror) | RGB falls in home/office scenes, static camera | kaggle.com/datasets/tuyenldvn/falldataset-imvia |
| `person_down` | **UR Fall Detection** | 30 falls + 40 daily activities (use the RGB video) | fenix.ur.edu.pl/mkepski/ds/uf.html |
| `person_down` | **Fall Video Dataset** | compiled from 3 public fall datasets | kaggle.com/datasets/payutch/fall-video-dataset |
| `fire_smoke` | **Smoke and Fire Detection Videos** | 85 fire/smoke videos | kaggle.com/datasets/unidpro/fire-and-smoke-dataset |
| `fire_smoke` | **FireSense** | 49 fire/smoke videos | zenodo.org/records/836749 |
| `crowd_incident` | **UMN Unusual Crowd Activity** | 11 videos: normal crowd walking → sudden panic/escape | crcv.ucf.edu/projects/Abnormal_Crowd/ |
| `suspicious_activity` | **UCF-Crime** (official) | long CCTV videos: vandalism, shoplifting, stealing, burglary, assault, … (we cut short clips) | crcv.ucf.edu/projects/real-world/ (the Kaggle "odins0n" mirror is *extracted frames*, not videos, so avoid it) |
| `crowd`, `fire`, `normal` (extra) | **Pexels stock video** | free-license videos: crowds, offices, lobbies, fire | pexels.com/videos |
| `tailgating` | ❌ **No public dataset exists** (confirmed by search) | → we film it ourselves (Q25) | — |

- Most of these are research/academic-use datasets. That's fine for a hackathon evaluation; we list the sources and terms in `data/README.md` and never redistribute the videos.
- R3 downloads them **before** the hackathon (downloading isn't building).
- `Decision:` ✅ Approved (logged as D10)

**Q27 🟡 Test-set size.**
- ⭐ **Test: 15 clips × 7 classes = 105 · Dev: 5 × 7 = 35.** Prompts are tuned on dev only; test is touched once for the final numbers.
- `Decision:`

**Q28 🟡 Success targets (what we claim in the report).**

| Metric | Proposed target |
|---|---|
| Macro F1 (test set) | ≥ 0.75 |
| VLM call latency p50 / p95 | ≤ 1.5 s / ≤ 2.5 s |
| **Time-to-alert** (incident starts → card on screen) p95 | ≤ 3.5 s |
| YOLO per frame | ≤ 40 ms |
| Keep-up rate (frames processed / sampled) | 100 % |
| VLM calls saved vs every-frame | ≥ 90 % |
| Chat: filter accuracy / grounded answers | ≥ 90 % / 100 % (no invented events) |
| Memory peak on the demo Mac | ≤ 75 % of RAM, no swap thrash |
| Soak test | 30 min, no crash, no latency drift |
| **Summary quality** (human-rated, see Q34) | ≥ 4.0 / 5 average, 0 hallucinated people/objects |
| **Time-to-full-summary** (streamed) p95 | ≤ 4 s |

- Since latency and accuracy must be *best*, these are minimums. Claude keeps optimising past them and the report shows the actual values.
- `Decision:`

**Q34 🟡 How do we measure summarisation quality?** (It's a scored criterion, so we need a number.)
- A: **Human rubric**: 2 teammates rate 40 event summaries 1–5 on correct actors, correct action, correct location in the frame, no hallucination, and conciseness. Report the average + the hallucination rate.
- B: A + an automatic check: a stronger local VLM judges each summary against the key frames (LLM-as-judge, local only)
- C: Reference summaries written by us + text-similarity scores (BLEU/ROUGE); weak signal, not recommended alone
- ⭐ A (cheap, credible), plus B if time allows. R2 owns it.
- `Decision:`

### F. Demo & pitch

**Q29 🟡 Who presents, and which demo moments?** Proposed live script:
1. A teammate walks in front of the webcam, then "falls" onto a mat → critical alert in ~2 s with a summary
2. A phone/RTSP camera catches tailgating at a door; a video camera shows a crowd forming
3. Chat: "Did anyone fall in the last 5 minutes?" → "How many incidents on camera 2 today?" → "What was the person on the floor wearing?"
4. Report tab: live accuracy and latency numbers
- `Decision:` presenter(s) and any changes

**Q30 🟢 Backup plan.**
- ⭐ A pre-recorded full demo video + seeded history, ready to switch to within 10 s if anything fails live.
- `Decision:`

### G. Working with Claude

**Q31 🟢 How you send feedback during testing.**
- ⭐ GitHub Issue per finding: what you did, what you expected, what happened, screenshot/clip, label. Urgent items: tell the captain, who tells Claude directly.
- `Decision:`

**Q32 🟢 Change control.** After the contracts are locked, may Claude change a contract (schema, API) on its own if it improves things?
- ⭐ No. Claude **proposes** the change, the captain approves it, and it gets a new §5 log entry. Internal code can change freely.
- `Decision:`

---

## 4. Draft contracts (review & mark changes)

These lock when the 🔴 questions are answered. Names may change slightly with Q-answers.

### 4.1 Observation (one per VLM window, including `normal`)
```json
{
  "id": 1,
  "camera_id": "cam1",
  "ts": 1760524800.12,
  "category": "normal",
  "confidence": 0.91,
  "summary": "Two people walking toward the exit, no unusual activity.",
  "people_count": 2,
  "trigger": "baseline | gate:person_down | gate:fighting | gate:crowd | gate:tailgating | gate:loitering",
  "track_ids": [4, 7],
  "thumb_path": "data/thumbs/cam1/1760524800.jpg",
  "t_capture": 1760524799.20, "t_vlm_start": 1760524799.35, "t_vlm_done": 1760524800.10
}
```

### 4.2 Event (a merged incident)
```json
{
  "id": 12,
  "camera_id": "cam2",
  "category": "tailgating",
  "severity": "medium",
  "start_ts": 1760524810.0,
  "end_ts": 1760524816.5,
  "peak_confidence": 0.88,
  "summary": "Second person follows closely through the door behind the first.",
  "keyframe_paths": ["data/keyframes/12_0.jpg", "data/keyframes/12_1.jpg", "data/keyframes/12_mosaic.jpg"],
  "track_ids": [3, 5],
  "status": "open | closed | acknowledged",
  "n_obs": 3,
  "time_to_alert_ms": 2310,
  "latency_ms": 1480,
  "seeded": false
}
```

### 4.3 VLM output (strict JSON, `category` first)
```json
{ "category": "fighting", "confidence": 0.82, "summary": "≤30 words, objective: who, what, where in frame", "people_count": 3 }
```

### 4.4 Chat
- Request: `POST /api/chat {"session_id": "abc", "question": "Show tailgating events from camera 2 today"}`
- Extracted filters (internal; shown in the UI for transparency):
```json
{ "intent": "list | count | summary | latest | detail | visual_question",
  "cameras": ["cam2"], "categories": ["tailgating"],
  "t_from": 1760466600, "t_to": 1760553000, "keywords": null, "event_id": null, "limit": 20 }
```
- Response: `{"answer": "3 tailgating events on Lobby Door (cam2) today: [#12] 10:14, …", "events": [Event…], "filters": {…}, "latency_ms": 1200}`
- Rule: the answer may only cite event IDs present in the returned rows. Zero rows → "No matching events" + the filters used.

### 4.5 HTTP API (FastAPI, port 8000; UI dev server 5173)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/cameras` | camera list + status + FPS |
| GET | `/stream/{camera_id}` | MJPEG live view with boxes |
| GET | `/api/events?camera=&category=&from=&to=&status=&q=&limit=` | query events |
| GET | `/api/events/{id}` | event detail |
| POST | `/api/events/{id}/ack` | acknowledge |
| GET | `/api/observations?camera=&from=&to=&q=` | raw summaries |
| GET | `/api/metrics` | latency, FPS, keep-up, queue, memory, calls saved |
| GET | `/sse` | live push: `event_open`, `event_update`, `event_close`, `metrics` |
| POST | `/api/chat` | chatbot |
| GET | `/api/report` | benchmark results for the Report tab |
| GET | `/keyframes/*`, `/thumbs/*` | images |

### 4.6 Camera config (`config.yaml`)
```yaml
cameras:
  - id: cam1
    name: "Front Desk (webcam)"
    source: 0                                  # webcam index | file path | rtsp://...
  - id: cam2
    name: "Lobby Door"
    source: rtsp://localhost:8554/cam2
    door_zone: [[0.42,0.20],[0.58,0.20],[0.58,0.95],[0.42,0.95]]   # normalized polygon, optional
vlm:  { base_url: "http://localhost:11434/v1", model: "TBD (Q11)", baseline_interval_s: 3, empty_interval_s: 10,
        mosaic_frames: 4, mosaic_span_s: 2.0, tile_px: 336, max_tokens: 100, concurrency: 1, timeout_s: 6 }
chat: { base_url: "same as vlm unless Q12=B", model: "TBD (Q12)" }
detector: { model: "yolo11s", fps: 10, imgsz: 640, conf: 0.35, device: "mps" }
```

### 4.7 Engineering conventions
- Every timestamp is epoch seconds (`time.time()`) internally; IST only at display/parse time.
- Camera IDs: `cam1…camN`; display names live in config.
- Category strings: exactly the §3 Q16 list, lowercase snake_case.
- Every model is called through **one OpenAI-compatible localhost URL** per role, so swapping a runtime or model is a config change only.
- No CDNs or internet calls at runtime; `HF_HUB_OFFLINE=1` at the venue.
- Every module has a runnable self-check (`python -m app.<module>`); `main` must always run.
- Raw videos are never committed (`data/` is gitignored; `data/README.md` has download steps).

---

## 5. Decision log (source of truth)

| # | Date | Decision | Decided by | Notes |
|---|---|---|---|---|
| D1 | 2026-10-15 | Problem statement 3 (live video event summarization + chat) | Team | — |
| D2 | 2026-10-15 | Builder = Claude Code; team = testing, ideation, decisions, pitch | Captain | — |
| D3 | 2026-10-15 | Hackathon is 48 h; MVP must be finished well before the end, leaving most of the time for testing | Captain | Exact freeze hour set in the build plan |
| D4 | 2026-10-15 | Hardware: Apple Silicon Macs (captain = M4, 16 GB) | Captain | Demo machine pending Q8 |
| D5 | 2026-10-15 | Open-source models, local only, no API keys (confirmed by organisers in briefing) | Organisers | — |
| D7 | 2026-10-15 | All code is built inside the 48 h. Before the event: research, model/dataset downloads, filming only | Captain | Q3. MVP target ~H16 so most of the time goes to testing; exact schedule in the build plan |
| D8 | 2026-10-15 | Demo machine = Apple M4, 16 GB. No stronger hardware available | Captain | Q8/Q33. Implies chat reuses the VLM (Q12 = A), 2–3 cameras (Q17) |
| D9 | 2026-10-15 | VLM shortlist: Qwen3.5-2B/4B, LFM2.5-VL-1.6B/3B, Gemma 4 E2B/E4B; winner picked by benchmark in H0–3 | Captain | Q11 |
| D10 | 2026-10-15 | Free datasets: RLVS (fights/normal), Le2i + UR Fall + Fall Video (falls), Smoke&Fire + FireSense (fire), UMN (crowd), UCF-Crime official (suspicious), Pexels; tailgating = self-filmed | Captain | Q26 |
| D11 | 2026-10-15 | Team: Shivansh, Riddhi, Abhinav, Aryan; roles proposed in Q1 | Team | confirm the role split |
| D12 | 2026-10-15 | Demo machine stays the M4 unless the M5 is ≥ 25 % faster at p95 VLM latency in the H0–3 benchmark | Team | Q7 |
| D13 | 2026-10-15 | Inference design: single VLM + streaming early alert + prompt caching + uncertainty re-look; learned-classifier booster only if the dev data calls for it. Two-tier rejected | Claude (proposed) | Q35, pending team objection |
| D14 | 2026-10-15 | Sources: pre-recorded videos (looped, optionally via RTSP) + webcam + phone camera | Team | Q9/Q25; tailgating clips still to be filmed |
| D6 | 2026-10-15 | Evaluation criteria: summarisation, incident classification, chatbot interface, approach + workflow demonstration, implementation. **Major: latency and accuracy, which must be best-in-class.** | Organisers | Added the Workflow view, live scene summary and digest to the must-haves; added Q33–Q35 |

---

## 6. Open risks & notes

- **16 GB RAM** is the tightest constraint: it decides between a 4B and a 2B VLM and shared vs separate chat. → Q7/Q8/Q11/Q12/Q33.
- **Latency + accuracy are the major criteria.** No stronger hardware (D8), so the levers are model choice (D9), the single-model + streaming design (Q35) and possibly the M5 (Q7).
- **Time:** the event ends the morning of 17 Oct. If the 48 h clock has already started, building must start **now**; open 🟡/🟢 questions take their recommended defaults.
- **Pre-hackathon rules (Q3)** decide whether we arrive with a finished MVP or build it on day 1.
- **Dataset access forms** (RWF-2000 etc.) can take days → request now (Q26).
- **Staged footage** is the hardest data to get (tailgating, crowd) → plan the filming early (Q25).
- Don't run the demo on battery or in Low Power Mode: Apple Silicon throttles.

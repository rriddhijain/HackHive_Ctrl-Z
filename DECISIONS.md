# HackHive: Decisions (the *why*)

> **Role of this file:** the questions we answered and the **decision log (§5)**, i.e. *why* each choice was made. The *what* (requirements, pipeline, contracts) is in **[SPEC.md](SPEC.md)**; the *when/who* is in **[PLAN.md](PLAN.md)**. If this file and SPEC.md ever disagree, **SPEC.md wins** and this file gets a correcting log entry.

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
  → Gate rules: "a person dropped fast or went horizontal", "2 people overlapping + fast motion (in body heights/s)", "8+ people", "2 people through the door"
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
  - R4 End-to-end Reliability & Experience: **Aryan** (changed by D27; the pitch is done by the whole team)

**Q2 🔴 Event timing & judging format.**
- Start date/time, end date/time, timezone (assumed IST):
- Is there a mid-point review or checkpoint? When?
- Final judging: live demo? slides? code walkthrough? Q&A? **How many minutes?**
- What must be submitted: repo link, video, report PDF, deck?
- `Decision:` ✅ Ends **Sat 17 Oct 2026, 08:00 IST** (so it started ~Thu 15 Oct 08:00). Judging = **in-person presentation to the judges** (live demo + slides). Still useful to know: presentation length, whether there's Q&A, and whether judges may bring their own videos.

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
- `Decision:` ✅ Videos + webcam + phone. Phones available: **Pixel 8, Pixel 10, iPhone 13, iPhone 15**.
  - **Primary live door camera: iPhone 15 via Continuity Camera over USB.** It needs no network, and macOS treats it as a webcam (the Mac must use the same Apple ID as that iPhone). Only one iPhone can act as a Continuity Camera at a time.
  - **Network IP camera: Pixel 10 with the "IP Webcam" app** (Pixel 8 as spare). This proves the system ingests real network streams. It needs the phone + Mac on the same hotspot.
  - **Spare:** iPhone 13 as a hotspot / backup camera.
  - Is a phone needed at all? Yes, for one reason: the webcam is stuck to the laptop and can't point at a door. Tailgating needs a camera at a door. The network phone is a nice-to-have; if it's flaky at the venue, drop it without regret.

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

- `Decision:` ✅ **Adopted by the team** (D13). Tricks 1–4 are built by default; trick 5 only if the dev-set numbers call for it. **Revisit trigger:** if the benchmark shows the 4B is too slow *and* the 2B misses the accuracy target, Claude brings this back to the team with numbers rather than silently changing the design.

**Q36 🟡 Adaptive frame rate / frame selection (team proposal, 2026-10-15)**

*Proposal:* keep the detector at a constant rate (gate thresholds are per unit of time; changing the FPS breaks them and ByteTrack IDs). Optional, in priority order: ① pick the frames that matter at trigger time (the trigger frame, the peak-motion frame, the latest frame) instead of fixed spacing; ② idle mode: drop the detector to 2–3 FPS after a few seconds with no people, back to 10 FPS as soon as someone appears; ③ one follow-up VLM call 1–2 s after a trigger to confirm or upgrade the category (e.g. `suspicious_activity` → `fighting`).

*Claude's verdict (taking D28 into account: one VLM call at a time, ~1.8 s each, so a second camera waits 4–8 s):*
- **Constant rate: agreed, already in the spec (10 FPS).** One addition: compute speed and hold times from `t_capture` differences, not frame counts, because under load the detector can run slower than 10 FPS.
- **① Adopt, but anchor on the trigger time.** The mosaic is built at dispatch from the last 2 s, and with 4–8 s queue waits the trigger moment has often already left that window: the VLM sees the aftermath, not the incident. Fix: tiles = [trigger −0.7 s, trigger, peak motion between trigger and now, latest], each labelled with its time offset. Keep the frame references at trigger time; they're numpy arrays, so this costs nothing. Baseline calls keep uniform spacing.
- **② Skip for now.** The VLM already slows to every 10 s on empty scenes (`empty_interval_s`), and the demo cameras are rarely empty. Revisit only if profiling shows YOLO slowing the VLM down on the shared GPU.
- **③ Don't adopt.** Every extra call takes the single model slot for ~1.8 s and pushes other cameras' alerts back. Upgrades already happen: cooldown is per (camera, category), so a `fighting` gate still fires while a `suspicious_activity` event is open. The real problem is underneath: D28 found self-reported confidence is always 0.85–0.98, so `open_conf_single: 0.85` opens nearly every non-`normal` observation on the first try, and the 0.4–0.7 re-look band never triggers. Better "second vote" for free: count a matching gate trigger (detector evidence) as the second observation instead of the VLM's confidence.
- `Decision:` ✅ Closed (D56): ① adopted, ② skipped, ③ not adopted.

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
- `Decision:` ✅ Approved, **plus an 8th category `property_damage` (confirmed by the team, D18)**:

| Category | What counts | Severity | Audible |
|---|---|---|---|
| `property_damage` | Damage to property or a hazardous object event, **accidental or deliberate**: an object or debris falling, a shelf/ceiling/structure collapsing, items knocked over and broken, shattered glass, vandalism | high | yes |

  - **Why this shape and not "collateral damage / anything breaking":** a vague definition makes the model inconsistent, which costs accuracy (a major criterion). "Collateral" also implies damage *caused by another incident*, which we can't reliably tell. So: one tightly defined category, and the summary says the cause ("knocked over during a fight", "fell from a shelf", "deliberately smashed").
  - **Overlap fix:** *vandalism moves from `suspicious_activity` into `property_damage`.* Otherwise the two categories overlap and confuse each other.
  - **Tie-break order:** fire_smoke > fighting > person_down > crowd_incident > property_damage > suspicious_activity > tailgating > normal. A fight that breaks a table is logged as `fighting`, with the damage mentioned in the summary.
  - **Detection gap + fix:** falling objects often involve no person, so none of the YOLO gate rules fire, and we'd wait up to 3 s for the baseline check. We add a cheap **"sudden scene change" gate**: a burst of pixel motion in a region with no person in it (plain OpenCV, ~1 ms) triggers the VLM immediately.
  - **Data:** UCF-Crime *Vandalism* clips + self-filmed staged clips (topple a stack of boxes, knock a chair over, drop a box of items, push a bin over; cheap and safe, ~15 clips) + Pexels.
  - **Cost:** +1 class to label (~20 clips) and a small risk to macro F1. Worth it: it matches a facility-management/building-safety use case, and most teams won't have it.
- **Severity of `suspicious_activity`:** the team chose **critical** (D19). Claude's concern: this category includes loitering and abandoned bags, which happen often and are frequently false alarms. Making all of it critical (with a sound alert) causes alert fatigue, and in the live demo it could keep beeping at harmless scenes. **Claude recommends a split by subtype**: the VLM adds a `subtype` field (only ~3 extra output tokens) and severity follows it:

  | Subtype | Severity |
  |---|---|
  | `weapon`, `theft`, `trespass` | **critical** |
  | `loitering`, `abandoned_object`, `other` | medium |

  Severity affects only alerting and the UI, not classification accuracy. *Team: keep "all critical" or adopt the split?*

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
- `Decision:` ✅ Must-have and stretch lists approved as written.

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
- `Decision:` ✅ Superseded by SPEC §4 (v1.6): targets set from measured P0 values, onset-to-alert added, plus incident recall/precision, false alarms per camera-hour and watts per camera (D50, D51).

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

## 4. Draft contracts (SUPERSEDED: see [SPEC.md](SPEC.md), the universal contract)

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
- Rule: the answer may only cite event IDs present in the returned rows; a model-written sentence with no valid ID is dropped (D57). Zero rows → "No matching events" + the filters used.

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
| D13 | 2026-10-15 | Inference design: single VLM + streaming early alert + prompt caching + uncertainty re-look; learned-classifier booster only if the dev data calls for it. Two-tier rejected | Team | Q35, approved |
| D14 | 2026-10-15 | Sources: pre-recorded videos (looped, optionally via RTSP) + webcam + phone camera | Team | Q9/Q25; tailgating clips still to be filmed |
| D15 | 2026-10-15 | The 48 h clock has started; ends the morning of 17 Oct (exact time TBD) | Team | Q2 |
| D16 | 2026-10-15 | Categories (Q16) + must-have/stretch lists (Q23) approved; `property_damage` proposed as an 8th category with vandalism moved into it, plus a scene-change gate | Team / Claude | team to confirm property_damage |
| D17 | 2026-10-15 | Cameras: iPhone 15 (Continuity, USB) at the door, Pixel 10 (IP Webcam) as a network camera, webcam for live, recorded videos for incidents | Team | Q9 |
| D18 | 2026-10-15 | `property_damage` confirmed as the 8th category; vandalism moves into it; scene-change gate added | Team | Q16 |
| D19 | 2026-10-15 | `suspicious_activity` severity = critical (Claude recommends a subtype split; awaiting team) | Team | Q16 |
| D20 | 2026-10-15 | Deadline Sat 17 Oct 08:00 IST; judging = in-person presentation (live demo + slides) | Team | Q2/Q29. Schedule in PLAN.md |
| D21 | 2026-10-15 | No downloads/installs without the captain's explicit confirmation | Captain | — |
| D22 | 2026-10-15 | Model decided without a full bake-off: **Qwen3.5-4B** primary, Qwen3.5-2B fallback, on Ollama. Gemma 4 and LFM2.5-VL dropped for Round 1 | Claude (pending captain) | Saves ~1.5 h and ~10 GB; reasons in chat |
| D23 | 2026-10-15 | Round-1 evaluation Fri 16 Oct 09:00; demo-ready by 07:00. SPEC.md is the universal contract | Team | PLAN.md updated |
| D24 | 2026-10-15 | Docs restructured: README = index, SPEC = what (single source of truth), PLAN = when/who, DECISIONS = why. SPEC v1.1 adds the full dataflow (§5a) and 23 resolved edge cases (§12a) | Captain | — |
| D25 | 2026-10-15 | Contention rule: one arbiter, P1 incident > P2 chat > P3 baseline > P4 re-look; chat uses rules first, the model only when needed | Captain | SPEC FR-8a/8b, NFR-1a |
| D26 | 2026-10-15 | FR-5 upload-a-video approved and pulled into Round 1 (small: one endpoint + one UI drop zone; ingest already supports files) | Team | Judges may ask to test their own clip |
| D27 | 2026-10-15 | Team does no development: Claude builds everything, the team tests/inspects/critiques/validates. Aryan's role → end-to-end reliability & experience QA. The pitch is done by all four together; Claude drafts the deck | Captain | PLAN.md rewritten |
| D28 | 2026-10-15 | **P0 results (M4, unique image per call, streamed JSON, thinking off).** Time until category+confidence (p50/p95): 4B 336px 3.51/3.88 s · 4B-MLX 336px 3.10/3.34 · 2B 336px 2.07/2.27 · **4B-MLX 224px 1.74/2.00** · 2B 224px 1.35/1.46 · 160px tiles hurt answers. Calls run one at a time: with 2 incidents + 1 chat, the 2nd camera waits 4–8 s. The 2B mislabelled a calm street scene as fighting/tailgating at 0.95 confidence; the 4B said normal. → **Provisional: qwen3.5:4b-mlx, 224 px tiles, `confidence` before `subtype`.** Self-reported confidence is meaningless (always 0.85–0.98). Parallel-slot test pending an Ollama restart | Claude | bench/results/latency_p0_*.json |
| D29 | 2026-10-15 | **Confidence = log-probabilities**, not model-written: per-category probabilities from the first category token, calibrated on the dev set, shown as % + High/Medium/Low. Event rules become probability-based (SPEC §6.5). The model's `confidence` output field is removed. Replaces the evidence-only rule proposal | Captain | Verified: Ollama returns top-k logprobs for qwen3.5:4b-mlx |
| D30 | 2026-10-15 | Ollama parallel slots: 2 tested after restart, no gain (calls still run one at a time on the M4 GPU) → 1 slot; incidents are protected by the arbiter's priority order. Contention target revised to 2nd camera ≤ 4.0 s | Claude | SPEC E-2, NFR-1a |
| D31 | 2026-10-15 | **Approved package (9 items):** ① preempt P3/P4 (and retry P2) for incidents; cut confident-normal baselines short ② freeze P1 frames at trigger time, never downgrade, ≤ 3 waiting P1 per camera ③ log/show prefix-cache hits ④ person-crop + 2-frame grids in the accuracy A/B ⑤ native `/api/chat` + model-field confidence fallback ⑥ gate yield + gate ablation replace "calls saved" ⑦ upload + phone stream built last, dropped first ⑧ 2nd-camera target ≤ 4.5 s with summary cut-short ⑨ field-order ablation in the report | Captain | From two external reviews, verified against P0 measurements |
| D32 | 2026-10-15 | **Demo machine = the team's M5** (16 GB). Build continues on the M4 Air; the M5 gets `git pull` + `uv sync` + the model copied by AirDrop/USB; every deck number is re-measured on the M5; sustained-load (thermal) check required | Captain | Replaces D8/D12's M4 choice |
| D33 | 2026-10-15 | Loitering severity: **on hold** (options A medium / B critical + 60 s / C medium + zone-based; Claude recommends C). E-10 unchanged until decided | Captain | — |
| D34 | 2026-10-15 | Gate motion rules: speed normalised by box height (body heights/s), tracks < 0.5 s old ignored, `fight_speed: 1.0`; new **fast-drop** `person_down` rule (top of box drops ≥ 0.4 × height within 0.5 s) and `down_hold_s` 1.0 → 0.5 s. Durations from `t_capture`, not frame counts | Captain | SPEC §6.6, `app/gate.py`; thresholds tuned on staged + look-alike clips |
| D34 | 2026-10-15 | **YOLO26-nano on CPU.** Measured with 3 cameras + VLM on the M4: GPU (lock-serialised) YOLO 119 ms/frame, keep-up 79 %, VLM worst 1.87 s; CPU YOLO 70 ms/frame, keep-up 99 %, VLM worst 1.20 s (≈ no YOLO). Also: concurrent mps YOLO calls abort the process (Metal assertion), so mps needs a lock. VLM time-to-category varied 0.9–1.7 s between runs, possibly heat on the fanless Air; the soak test must check this | Claude | P1 measurement |
| D35 | 2026-10-15 | **Loitering = medium (no sound) everywhere; abandoned objects medium; weapon/theft/trespass stay critical.** Optional `watch_zone` per camera: if set, loitering counts only inside it (live cameras); otherwise the whole frame. Replaces D19 and resolves D33 | Captain | Zones can't be drawn for 100+ dataset clips or unseen uploads, hence optional |
| D36 | 2026-10-16 | YOLO input size 640 → **480** (CPU, 3 cameras: 58 → 36 ms/frame, same detections on the test clip; re-check far-away people on real CCTV clips). Neural Engine (CoreML) export attempted: **blocked**, because coremltools 9.0 supports PyTorch ≤ 2.7 and we run 2.14 | Captain | Workaround pending: export once in a throwaway torch-2.7 environment |
| D37 | 2026-10-16 | **Neural Engine result:** converted YOLO26n@480 → `models/yolo26n.mlpackage` (one-time, throwaway torch-2.7 env, deleted). Raw CoreML: 8 ms/frame on Neural Engine (vs 26 ms PyTorch CPU), 3.6 ms with ALL (GPU). **But through Ultralytics' loader** (3 cameras): 33 ms, keep-up 69 %, VLM time-to-category 2.8 s, because the loader doesn't pin it to the Neural Engine. **Decision: stay on PyTorch CPU for Round 1.** A custom CoreML runner pinned to CPU_AND_NE + Ultralytics' BYTETracker is ~1 h of work → post-Round-1 candidate, measured on the M5 | Claude | The file is kept in models/ (gitignored) |
| D38 | 2026-10-16 | From a 4th external review (measured): **adopt** fixed `num_ctx: 4096` on every vision + chat call (insurance against a multi-second model reload) and move all static text (incl. "Classify.") into the system prompt. **Reject** reordering hints before the image (hints are per-frame dynamic; measured 103/320 tokens already cached = the system prompt), llama.cpp image-slot patch and flash-attention/KV-quant flags (our model runs on Ollama's MLX engine, confirmed in the server log; prompts are ~320 tokens) | Captain | Implemented in P2's model client |
| D39 | 2026-10-16 | **Pose A/B approved** for P2: `yolo26n-pose` (~6 MB download approved) vs plain `yolo26n` for the fall/fight gates; adopt only if gate accuracy improves at similar CPU cost | Captain | SPEC FR-6a |
| D40 | 2026-10-16 | **Trained classifier approved** as the P6 accuracy upgrade: frozen SigLIP2-base embeddings + small classifier trained on our labelled train/dev clips, fused with the VLM's probabilities; SigLIP2 download (~400 MB) approved for P6. Kept only if dev macro F1 improves | Captain | SPEC FR-9b, §6.5. Biggest unused accuracy lever in the pipeline review |
| D41 | 2026-10-16 | **Pipeline review, rejected or deferred:** open-vocabulary detection (3–5× slower), BoT-SORT re-ID (slower, little gain for 2 s windows), speculative decoding (small gain, MLX risk), in-process mlx-vlm instead of Ollama (~10–30 ms, rewiring risk), HMM event smoothing (marginal; tune thresholds instead), letting the model write SQL (worse than rules + templates). Deferred: LoRA fine-tune of Qwen3.5 (after Round 1, if time), Neural Engine YOLO runner (D37). Proposed, not approved: fire/smoke trigger | Captain | Review requested by the captain |
| D42 | 2026-10-16 | **Baseline load control.** P0 numbers (full call 3.68 s p50; ~2.3 s with a 12-word cut) mean 3 cameras × a baseline every 3 s ask for ~2.3× the GPU: the queue is never empty, every alert must preempt, observations arrive every ~7 s, and the fanless Mac runs at 100 % GPU. → **Change-gated baselines** (skip when the scene is unchanged since the camera's last call; max 15 s between calls; never while an event is open), **confident-normal baselines stop at the category** (summary on every 3rd), "now" line from a detector template between summaries, **GPU duty ≤ 60 %** target shown in the metrics strip | Captain | Judge review W1. SPEC FR-8, FR-8a, FR-16, §5a step 4, NFR-4, E-24 |
| D43 | 2026-10-16 | **Close rule by observations:** an event closes only after 2 consecutive non-supporting observations of its camera **and** 8 s since the last support (or 8 s with the camera down). Wall time alone closed events whose camera was merely starved of model time, then reopened them as duplicates with a second alarm | Captain | W1. SPEC §5a step 10, §6.5, E-13 |
| D44 | 2026-10-16 | **16:9 tiles, letterboxed:** 288×160 per tile → 576×320 mosaic (~180 image tokens vs ~196 for 448×448). Square 224 px tiles would stretch 16:9 frames (lying people look less flat → hurts `person_down`) or crop 44 % of the width. Any source shape is fitted with grey padding, never stretched. YOLO itself was never distorted (it pads internally). One-off check that Ollama's MLX engine keeps the shape (E-25) | Captain | W2/W3 follow-up. Replaces the 224 px square tiles of D28. SPEC FR-9, §5a step 5, §10 |
| D45 | 2026-10-16 | **Track-crop tile (FR-9c)** for gate-triggered calls when the trigger box is < 40 % of the frame height: tiles 1–3 full frames, tile 4 a 16:9 crop of the trigger tracks × 1.75. Final, adopted only if the dev A/B wins | Captain | W2 + missed opportunity. Helps distant people on CCTV clips; little gain in the demo room |
| D46 | 2026-10-16 | **Detector cross-check (E-7) moved to Round 1** (the R1 §6.5 rules already depended on it). Person counts = max over the 4 s buffer (merged grapplers, undetected lying people); no veto for `crowd_incident` (nano undercounts dense crowds); tailgating needs a door zone + 2 entries. 0.5 is effectively a veto, so every veto is logged and the rule is loosened if it loses > 1 real fight/fall per 10 dev clips | Captain | W2. P0 already showed tailgating false positives on a bus scene. SPEC FR-10, §6.5, E-7 |
| D47 | 2026-10-16 | **Demo-day single points of failure scheduled:** M5 setup in PLAN Part 1 now (same Ollama, copied models, `uv sync`, camera permission, **Continuity needs the iPhone on the M5's Apple ID**, Wi-Fi-off run, latency test that also shows whether MLX uses the M5's GPU neural accelerators); **live fall camera = iPhone 15 mounted ~2 m high** (the lid webcam can't see the floor; a falling person leaves its frame); 10-min heat run on the M5 before Round 1 | Captain | W4. SPEC §13, NFR-5, §10 cameras |
| D48 | 2026-10-16 | **Classifier (FR-9b) made conditional and its split fixed:** built only if dev macro F1 < 0.70 after the prompt and cross-check fixes (time-box 2 h); trains on a separate train split, fusion weight and temperature fitted on dev (training and fitting on the same dev clips would leak and over-trust the classifier) | Captain | Amends D40 |
| D49 | 2026-10-16 | **Prompt carries every §6.1 definition plus "not this" exclusions** (P0's prompt had bare category names, and the model read "tailgating" as vehicles). Extra static text is prefix-cached (D38). **`subtype` is a flat enum**; invalid category/subtype pairs are nulled in Python (a conditional schema is unverified on Ollama's MLX engine and could shift the first-token probabilities) | Captain | W2. SPEC §6.1, §7.3 |
| D50 | 2026-10-16 | **Honest latency definitions and targets:** three numbers, **onset-to-alert** (what a judge times; 240 fps phone video live, labelled onset on clips), **model time-to-alert** (never quoted alone), time-to-full-summary; targets set to measured P0 values (full call 3.7/4.1 s, model time-to-alert ≤ 2.0 s p95, onset-to-alert ≤ 3.0 s p95 for gated categories), measured under demo load, not an empty queue | Captain | W3. SPEC NFR-1, §12 |
| D51 | 2026-10-16 | **Operator-centred metrics added to the report:** incident-vs-normal recall/precision next to macro F1 (comparable to binary fight/no-fight claims), **false alarms per camera-hour** on ≥ 30 min of normal footage (target ≤ 1), onset-to-alert per category from `bench/labels.csv` onset times, veto log, GPU duty and **watts per camera** (`powermetrics`). Macro F1 is over **8 labels** (7 incident categories + normal); "9" in v1.5 was a mistake | Captain | W3/W5/W8 + missed opportunities. SPEC FR-20, FR-21, NFR-2, §12 |
| D52 | 2026-10-16 | **Make the differentiators visible and fit operations:** alert cards show the top-3 probability bar and "trigger → alert ms"; the demo includes a look-alike moment (hug / sit → no alert); **"mark false alarm"** (status `dismissed`, `dismiss_reason: operator`, FR-25) and digests framed as a **shift-handover report** (FR-17) | Captain | W8 + missed opportunities. SPEC FR-14, FR-17, FR-25, §7.2, §8, §9 |
| D53 | 2026-10-16 | **Chat v1 keyword search:** leftover content words become `keywords` → FTS5 over event and observation summaries (free-text questions answered without a model call) | Captain | Missed opportunity. SPEC FR-18, §5a.2 |
| D54 | 2026-10-16 | **P1 fixes (applied):** one coordinate system, **pixels of the 640 px frame**, for boxes, track histories and zones (per-axis normalisation scaled every width/height ratio by 0.56 on 16:9 and undercounted sideways speed by 44 %, so the "lying flat" rule could not fire); zones stay fractions in `config.yaml` and are converted once per frame size; **only person tracks reach the gates** (`Detector.person_hists()`; a backpack's box turned walking into a "fighting" speed, a suitcase looked horizontal); duplicate `Track.aspect/speed` removed; `config.yaml` gate keys synced (`down_hold_s` 0.5 per D34, + `drop_frac`, `drop_window_s`, `fight_speed`, `min_track_age_s`); `coremltools` removed from dependencies (only needed for the one-off D37 export) | Captain | W5/W6. `app/detect.py`, `app/gate.py`, `config.yaml`, `pyproject.toml`; self-checks pass |
| D55 | 2026-10-16 | **4B vs 2B decision rule** (P2, real dev clips, real prompt): keep the 4B unless the 2B is within 2 clips **and** raises no more false alarms on normal + look-alike clips (the 2B saves ~0.4 s to the category). **Tailgating gate** refined (two distinct tracks, both present together, same direction, 2.5 s) and **built only if a door camera is used**; otherwise the E-7 door-zone veto alone stops tailgating firing | Captain | W2. SPEC §5 VLM row, FR-7, §6.6 |
| D56 | 2026-10-16 | **Judge-review "W7" (cut Round-1 scope: React, upload, pose A/B, extra preemption, extra A/Bs) rejected**: Round-1 scope stays as in v1.5. Q36 closed: ① trigger-time frames adopted (already in §5a), ② detector idle mode skipped, ③ follow-up call not adopted (D42's change-gating and the gate corroboration cover it) | Captain | — |
| D57 | 2026-10-16 | **Chat sentence-level grounding:** in `summary` answers, every sentence must cite a valid `[#id]` from the returned rows; invalid IDs are removed and sentences left without one are dropped (all dropped → template list). Rest of the low-light/RAG review rejected: entropy circuit breaker (facts never come from the model; templates do), dense+sparse RRF (no embedding search; filters are already exact SQL), temporal frame averaging (blurs the motion falls/fights depend on), dark-frame threshold drop (conf already 0.35; more false alarms). CLAHE kept only as a P6 A/B if dim-light test clips show missed people | Captain | SPEC §5a.2 step 6, §7 Chat. Pitch line: "every sentence is traceable to a stored event" |
| D58 | 2026-10-16 | **npm installs for `web/` approved (D21):** React + Vite + Tailwind and their build deps may be installed in `web/` during P3; `node_modules/` stays gitignored, the built bundle is served offline by FastAPI. No other installs are covered | Captain | SPEC §5 stack, §11 |
| D59 | 2026-10-16 | **`yolo26n-pose.pt` download approved and done (D21):** 7.5 MB, in `models/` (gitignored), for the P2b pose-vs-plain gate A/B (FR-6a). FastAPI's built-in `fastapi.sse.EventSourceResponse` is used for SSE in P3 (no new dependency). Rejected as duplicating P1 or adding latency: `ultralytics.solutions`, `supervision`, LangChain/LlamaIndex/vector DB, shadcn/chart libraries, scikit-learn. mediamtx (RTSP sim) deferred to P7, needs its own approval | Captain | FR-6a, SPEC §9.2 |
| D60 | 2026-10-16 | **Category probabilities by prefix-tree walk (§6.5).** Measured in P2a: with the JSON schema, qwen3.5:4b-mlx starts the category value with ONE character (`c`, `s`, `f`, `p`), so `f` = fire_smoke/fighting and `p` = person_down/property_damage collide, and rewording is impossible (enum strings fixed by §6.1). We walk the value tokens until the chosen name is unique (1–2 tokens, ~35 ms each); chosen branch exact, un-taken colliding branch split evenly. Rejected: renaming the enum (contract change everywhere), first-token even split (fire vs fighting 50/50 at alert time) | Captain | SPEC v1.8 §6.5. `app/vlm.py` `walk()` |
| D61 | 2026-10-16 | **GPU duty fixes from the first 3-camera run (99.5 % duty, 27 false P1s in 75 s on a normal clip):** (1) a gate-triggered ① whose verdict is confident `normal` (c ≥ 0.80) stops at the category token like baselines (~1.2 s instead of ~3 s; no recall risk). (2) The fast-drop gate ignores a box that got > `fast_drop_max_narrow` (0.20) narrower while its top dropped (sample_bus.mp4: top −45 %, bottom fixed, width 94→60 px = occlusion). Config key, not hard-coded: P2b's gate test must show every real fall clip still fires the fast drop; if any misses, set it to 1.0 (guard off). (3) A `person_down` **horizontal** trigger whose call came back confident `normal` is silenced for that track until its box stops being wide or the track leaves, with a safety re-arm after `horizontal_recheck_s` (30 s): a static close-up (`zidane.jpg`, box 388×258) re-fired 46 P1s in 60 s. Fast drop always fires | Captain | SPEC v1.8 FR-8a, §6.6, §10. `app/gate.py`, `app/pipeline.py`, `config.yaml` |
| D62 | 2026-10-16 | **P3 dashboard API additions (SPEC v1.9), additive only:** (1) SSE `alert` + `t_stored` (server time the event row was written) and `onset_to_alert_ms` (labelled clip played once, category = label, else null); (2) §9.1 per-camera `people` + `now {text, ts, source}` (FR-16 detector template between summaries, computed server-side) and a `latency` block (onset-to-alert, store→card); (3) `POST /api/ui/latency`: the browser reports its measured store→card ms so the number on screen comes from the backend; **valid only for a browser on the server machine** (clock comparison), other clients are ignored; (4) upload takes the raw body + `?name=` because python-multipart is not installed (no new dependency): bare file name, mp4/mov/avi/mkv, ≤ 500 MB, streamed to `data/uploads/`, 400/413. Measured in headless Chrome on real clips: store→card p50 22–28 ms, p95 41 ms (n = 9; budget ≤ 100 ms); emit→SSE 0.6 ms | Captain | SPEC v1.9 §9, §9.1, §9.2. `app/server.py`, `web/` |
| D63 | 2026-10-16 | **Veto count and fighting veto (P2b Step 1a).** The 51-of-52 veto rate was the rule working as written, not a bug: all 412 logged vetoes in the P3 log were `tailgating` on cameras with no door zone at p ≤ 0.10 (every call vetoes a ~0.03 tailgating probability); 0 fight/fall vetoes, 0 real incidents suppressed; buffer-max person counts were filled (3–9). Changes: (1) the dashboard and run summaries count only vetoes with p_before ≥ 0.3 (the log keeps all); (2) `fighting` is vetoed only when the detector saw **0** people in the 4 s buffer (was < 2): YOLO-nano misses fighters in motion blur and saw ≤ 1 person on v026 (dark corridor fight). Fight recall on the dev clips, 4B, one clip at a time: 3/6 before → 3/6 after (no fighting veto ≥ 0.3 fired on this set either way); false alarms on normal: 0 → 0 | Captain | SPEC v1.10 E-7, §9.1, FR-10. `app/vlm.py`, `app/server.py`, `app/pipeline.py` |
| D64 | 2026-10-16 | **Fight gate: `fight_speed` 1.0 → 0.6 + fight-pair silence (P2b Step 1b).** Diagnosis (offline detector replay at 10 FPS, `bench/ab.py --gate`): the gate needs an overlapping pair moving ≥ 1.0 body heights/s, but nano boxes the bystanders and loses the blurred fighters, so overlapping-pair speed peaked at 0.62 (v001) and 0.66 (v011 until 8.4 s of 8.7 s); v026 never has 2 people detected. Lowering detector conf (0.25/0.15) did not help. At 0.6 the gate fires on 5/6 fight clips offline (v001 0.7 s, v003 1.2, v006 1.5, v011 5.6, w001 1.6; v026 never). Guard against people walking past each other: a fight pair whose call is confident normal (c ≥ 0.80) stays silent until a track leaves, their centroid distance changes by > 0.5 body heights, or 30 s (`horizontal_recheck_s`), as D61 does for horizontal. Fight-gate false triggers on sample_bus looped 60 s: 0/min → 1/min (verdict normal, no alert). Live, 4B, one clip at a time: clip start→alert p50 6.6 → 3.7 s, v011 7.8 → 2.6 s (gate at 1.4 s instead of none). Only 1 normal clip: re-check on look-alikes when they exist. Ended clips/uploads now count as down for the close rule (Step 1c, approved): v006 upload closed 9 s after it ended | Captain | SPEC v1.10 §6.6, §10, E-13. `app/gate.py`, `app/scheduler.py`, `app/pipeline.py`, `config.yaml` |
| D65 | 2026-10-16 | **A/B `--model` (P2b): 4B kept, D55 deferred: needs negatives.** Real pipeline + real prompt, each dev clip alone, played once (6 fights, 1 normal), v1.10 gates. 4B (`qwen3.5:4b-mlx`): 4/7 right, macro F1 0.39 (labels present), incident recall/precision 0.67/1.0, 0 false alarms on normal, trigger→alert p50/p95 1.21/1.26 s, clip start→alert p50/p95 3.7/4.3 s, GPU duty 79 %. 2B (`qwen3.5:2b`, GGUF, not MLX): 5/7, F1 0.65, 0.67/1.0, 0 false alarms, trigger→alert 1.49/1.91 s, start→alert 3.7/8.3 s, duty 85 %. 2B is within 2 clips, but the false-alarm half of the D55 rule can't be applied with 1 normal clip and no look-alikes (smoke mode), so the model is not switched. Confusions: 4B fighting→normal v001 (suspicious 0.30), v003 (person_down 0.70, not corroborated by the fight gate), fighting→person_down v026; 2B fighting→normal v026, w001 (fighting 0.95 on one uncorroborated observation, clip ended). Onset-to-alert not measurable: `onset_s` blank. `bench/results/ab_model.csv` | Captain (pending) | D55, PLAN P2b |
| D66 | 2026-10-16 | **Duty fix (P2b Step 3, approved): baselines back off while GPU duty > `duty_target` (0.60).** Above the target each camera gets one baseline per 15 s (`baseline_skip.max_skip_s`) instead of every 3 s; ① calls are never throttled and the arbiter already serves them first and preempts a running ③. Measured, 60 s, 3 cameras looping, before → after: mix (v001 busy, sample_bus, v026 static): duty 99.6 → 94 %, baselines run/skipped per camera 6/0 → 4/4–5, v001 ① queue p50 2.9 → 1.9 s, trigger→alert p95 v001 4.3 → 1.3 s, v026 17.2 → 16.3 s (no gate: baseline window path). 3 looping fights (P3 worst case): duty 99.5 → 99.5 %, unchanged — the load is all ①s (13–15 triggers/min, full 3–4 s calls, ① queue p50 11–15 s), which the rule must not throttle; this led to D67. Target ≤ 60 % not reached on either set | Captain | SPEC v1.11 FR-8a, §10. `app/scheduler.py`, `config.yaml` |
| D67 | 2026-10-16 | **A ① that agrees with an already-open event stops at the category (approved).** If the top category of a gate-triggered call matches an event already open on that camera, the call stops at the category token: no summary, the event just updates; a different category still runs the full call. 3 looping fights, 60 s, D66 alone → D66 + D67: duty 99.5 → 91 %; ① queue p50 v003 12.8 → 3.3 s, v006 15.6 → 3.6 s, v011 13.0 → 2.4 s; trigger→alert p95 v003 no alert → 7.8 s (fighting now alerts; it also raised 2 person_down alerts), v006 6.4 → 4.8 s, v011 7.3 → 0.6 s. Single 60 s run: v003's recovery is one sample, and v003 alone (played once) is still read as person_down 0.70 in 2 of 4 runs — a model confusion D67 doesn't touch. trigger→alert ≤ 2.0 s (D50) met on v011 only | Captain | SPEC v1.11 FR-8a. `app/pipeline.py` |
| D68 | 2026-10-16 | **A/B `--gate` (FR-6a): plain `yolo26n` kept for gates (report; switch needs captain).** Offline detector replay at 10 FPS, `fight_speed` 0.6. Trigger recall on fight clips: plain 5/6 (first trigger v001 0.7 s, v003 1.2, v006 1.5, v011 5.6, w001 1.6), pose 4/6 (2.7, 1.9, 1.5, 3.7; misses w001, v026). False triggers on sample_bus: 0 / 0. YOLO ms/frame (idle CPU): 16 vs 18 ms (1.15×, inside FR-6a's 1.3×), but pose would need plain alongside for bags/knives (≈ 2.15×). Pose only helps v011 (3.7 vs 5.6 s); box-only pose gates (no keypoint rules built). **Fast-drop check (D61) not measurable: no fall clips in the dev set**, so `fast_drop_max_narrow` stays 0.20 untested; the only fast drop seen (v011 8.4 s, a fighter knocked down) fired with the guard on. v026 (dark corridor) never has 2 people detected by either model | Captain (pending) | FR-6a, D59, D61. `bench/results/ab_gate.csv` |
| D69 | 2026-10-16 | **A/B `--tiles`: mosaic kept (report; switch needs captain).** Real pipeline, each clip alone, played once, 4B. Mosaic: 4/7, F1 0.44, incident recall/precision 0.83/1.0, 0 false alarms, trigger→alert p50/p95 3.2/5.0 s, duty 87 %. Person-crop tile 4 (FR-9c): 4/7, F1 0.39, 0.67/1.0, 0, 2.6/3.2 s, 89 %. Native video (4 frames as separate 576×320 images, 1262 vs 736 prompt tokens): 5/7, F1 0.49, 0.83/1.0, 0, 5.9/7.5 s, 97 %, 8 call timeouts (> 6 s). Confusions — mosaic: fighting→person_down v003, v026; fighting→normal w001 (suspicious 0.83). Crop: fighting→normal v003, w001; →person_down v026. Native: →person_down v026; →normal w001. Native's +1 clip doesn't pay for ~2× latency; crop gives nothing. Latency here ran hotter than D65 (machine warm), compare within this table only | Captain (pending) | FR-9c, D45. `bench/results/ab_tiles.csv` |
| D70 | 2026-10-16 | **Demo modes Clips \| Live (P3b, approved) + P2b locks.** (1) The server boots in Clips mode with nothing running (`config.yaml` cameras are Live presets only); `POST /api/mode` switches and stops/releases every source; history is never cleared (chat spans both acts). (2) Clips (Act 1): playlist `GET /api/clips` (data/demo, data/dev/*, label/onset from labels.csv), one click plays a clip or upload **once, one at a time** (a new clip stops the old one): P2b measured 3 busy sources at > 90 % GPU duty (D66/D67) with alerts several seconds late; alone, trigger→alert ≈ 1.2 s. A finished clip's tile shows a result card (incidents: category, confidence, time in clip, summary; or "No incidents"; with an onset: "incident at X s → alert at Y s"). (3) Live (Act 2): `GET /api/devices` (list_cameras logic, "iPhone (live)"), `POST /api/cameras` accepts a device index or an http/https/rtsp URL only (file paths and other schemes → 400), ■ stop per tile, tile status connecting/live/reconnecting/down, "3+ live cameras: alerts may slow" on the metrics strip above 2 live sources. (4) Thumbnails only for non-normal observations. **Found while testing:** ffmpeg's AVFoundation indices ≠ OpenCV's when a Desk View camera exists (ffmpeg [1] Desk View → OpenCV "out of bound (0-0)"); `list_cameras.names()` now skips Desk View/screens and numbers the rest in order (assumes both lists keep the same order: check with the iPhone). `Camera._stop` shadowed `Thread._stop` (join crashed): renamed; reconnect backoff now wakes on stop. **Measured** (headless Chrome, real clips, M4): mode switch click → tiles gone 18 ms (Clips → Live), 48 ms (Live → Clips with the webcam running); ■ stop ≤ 0.2 s; store→card p95 30.2 ms (n = 3); v011 alone: alert 6.7 s into the 8.7 s clip, trigger→alert 1158 ms; sample_bus: No incidents. **P2b locks (captain):** plain `yolo26n` stays for the gates (pose 4/6 vs plain 5/6 fight clips, D68); the mosaic stays (native video ≈ 2× latency and 8 timeouts, D69) | Captain | SPEC v1.12 §9, §9.1, §9.2, §10, E-12, E-17. `app/server.py`, `app/ingest.py`, `app/pipeline.py`, `scripts/list_cameras.py`, `web/` |
| D71 | 2026-10-16 | **Chat v1 (P4).** `app/chat.py`: rules parse camera ("camera 2", names, "<word> camera" naming no camera → said plainly), category + synonyms + subtypes, IST time phrases (today, yesterday, last N min/hours, last night, morning/afternoon/evening, at/since/before/between clock times; a clock time still to come = yesterday's), intent (list/count/latest/detail/summary); leftover words → FTS5 keywords (all must match, singular or plural). list/count/latest/detail are templates citing every event as [#id]; `summary` = model at arbiter P2 (≤ 30 rows oldest-first, `max_tokens` 150, `num_ctx` 4096), sentence check per D57, all dropped or no model within 10 s → template list. A P1 now also cancels a running P2 chat call, which retries (FR-8a; the arbiter only cancelled P3/P4 before). **Additive contract change (v1.13):** response field `how` (the P4 brief asked the UI to show "template" or "model, N rows, M sentences dropped"), `camera_name` on events, filters `subtypes`/`unknown_cameras`. FTS5 sync by triggers + a rebuild on open. **Not built:** model extraction (§5a.2 step 3; rules always parse), FR-8c new-incidents chip (F). Seeded history: `scripts/seed_history.py` (24 events on 4 cameras with readable ids lobby/parking_lot/loading_dock/server_room, never colliding with live cam ids; `--remove` deletes them). **Measured** (M4, `bench/chat_runner.py`, 30 questions incl. 6 traps, now = 06:00 IST): 30/30 right, 0 invented events, 0 uncited sentences; template p95 2 ms; summary first token 117–714 ms (no camera running), full summary 2.4–5.2 s. Found while testing: with severity/confidence in the rows the model wrote "a critical condition with a 90 % severity rating", and with rows newest-first it got the chronology wrong → model rows are now time, camera, category, summary, oldest first; relative-day slips ("the following day") can still happen and the citation check can't catch them. Browser (headless Chrome): 3 questions, every [#id] link opened its card; v011 played with chat summaries in flight: fighting trigger→alert 548 ms (v011 alone right after: 1149 ms; single samples), a chat answer during the clip took 10 s (queued behind ①s, template fallback by design) | Captain (`how` field pending sign-off) | SPEC v1.13 §5a.2, §7.5. `app/chat.py`, `app/db.py`, `app/models.py`, `app/pipeline.py`, `app/server.py`, `web/`, `scripts/seed_history.py`, `bench/chat_runner.py` |
| D72 | 2026-10-16 | **Live-mode fix (P3c).** (1) **Tiles:** the MJPEG `<img>` is replaced by `GET /snapshot/{id}` polled at ~10 fps; each JPEG is fetched whole, checked for its start/end markers, decoded off-screen and only then swapped in; a failed or truncated frame keeps the last good one (Safari painted half-received MJPEG frames grey on the M5). Chrome (the installed Google Chrome via Playwright, 2 cameras looping with the full pipeline): 1,184 tile samples over 10 min, 0 not loaded, 0 grey bottom thirds, 9.8 fps per tile, 0 VLM errors. WebKit could not be automated (the cached WebKit build doesn't match the cached Playwright; a download was declined): Safari is checked by eye in the captain's final live check and by Abhinav on the M5. (2) **Overload diagnosis** (no iPhone today: the webcam opened twice = 2 live 1080p feeds, and recorded clips replayed on 2 cameras). The captain's numbers (100 % duty, 11 VLM errors, "6 ppl", YOLO 122 ms) were **not reproduced** on this Mac: idle clip ×2 before the fix: duty 61 %, 0 errors, 3 people on 82 % of frames for 3 real (2 on 17 %, 4 on 1 %), conf ≥ 0.7 on 98 % of person boxes (no phantoms), YOLO 27 ms, keep-up 100 %. VLM errors: 0 in every run here; the server log prints each `[vlm_error]` with its cause, so read it on the next live run with the iPhone. Found and fixed: (a) **bug:** a silenced wide track re-armed on any single frame below 1.2 wide-per-tall; a seated close-up at the laptop hovers at 1.17–1.34, so 2 live feeds made 14 horizontal ①s/min, all normal. It now re-arms only once the box is clearly upright (< 0.8 × `down_ratio`): desk close-up ×2 looped 60 s, horizontal ①s 8 → 6 (≤ 1 per track per `horizontal_recheck_s`), duty 75 → 67 %. (b) people standing at different depths overlap only in the picture: 3 false fight ①s/min on the idle clip, pair height ratios 0.32–0.56 vs ≥ 0.53 on dev fights at first fire → `fight_min_height_ratio` 0.5 (captain chose 0.5 over 0.6: v003 dips to 0.53; 1 of 4 idle false fires, at 0.56, stays). (c) the staged shove was **missed by the fight gate**, which needed overlap and speed on the same frame: the approach peaks at 0.56 body heights/s, the grapple is one merged box, and the 1.4 b.h./s push comes after the boxes part; the gate fired only on the hug. → `fight_contact_s` 0.5: the pair overlapped on some frame in the last 0.5 s, both boxes from that frame (this also stops pairing a box with one up to 5 s stale). Offline: every dev fight keeps its first-fire time, the shove fires at 7.6 s (shove at 7.2 s), no new false fires; given the shove mosaic the model says fighting 0.92. (d) **bounded cost (captain):** at most one ① per camera in flight: a trigger refreshes a waiting ① (newest frames; same rule: also hint and tracks) or merges into a running one, never queued (was up to 3 queued per camera). Trade-off: a different-rule trigger that arrives while that camera's ① runs gets no call of its own; it still corroborates the next call (4 s window), and a fight's gate keeps firing for ~0.5 s. **Measured before → after** (2 cameras, recorded clips, M4): idle 60 s ×2: duty 61.0 → 60.3 % (target ≤ 60 % missed by 0.3 points: the D66 back-off holds duty at `duty_target`, and 16 of 18 calls are baselines), fight ①s 3 → 2, errors 0 → 0, false alerts 0 → 0, people 3/3 correct. Staged (cam1 shove/sit/hug clip once, cam2 floor-sit once): shove no alert → **fighting (critical) c 1.00, trigger→alert 1,297 ms, onset→alert 3,275 ms** (onset 5.6 s = chest to chest); floor-sit no alert → no alert; hug no alert → no alert (the fight gate fires on the hug approach, answered normal 0.45). **New dev clips** (webcam, this room, gitignored): `fighting/p3c_shove_sit_hug.mp4` (onset 5.6 s; look-alikes in the same take: floor-sit 13–21 s, hug 24–26 s), `normal/idle_60s.mp4` (1 seated + 2 standing), `normal/floor_sit.mp4`, `normal/desk_closeup.mp4`. **Gate regression check** `uv run python -m bench.ab --gate --check` (the real Detector + Scheduler on every dev clip, CPU, ~45 s, every call answered at once so the D61/D64 silences act as live): each incident clip's gate must fire from onset −1 s to +5 s (new ① or merged), normal/look-alike clips ≤ 2 ①s per camera-minute: ok (v026 the one known miss, D64; normal 0.98/min). Every future gate or threshold change must pass it (CLAUDE.md). **Hold-out:** `fight_speed` 0.6, `fight_min_height_ratio` 0.5 and `fight_contact_s` 0.5 were tuned on the dev clips only; re-check them on the test split in P8 (Abhinav's and any public clips), never re-tune them on the clips they are judged on | Captain | SPEC v1.14 §5a step 4, §6.6, §9, §10. `app/gate.py`, `app/scheduler.py`, `app/server.py`, `web/`, `config.yaml`, `bench/ab.py`, `bench/labels.csv`, `CLAUDE.md` |
| D73 | 2026-10-16 | **P5 Round-1 hardening (approved package).** (1) **D71 `how` field signed off.** (2) **`vlm.duty_target` 0.60 → 0.55** (idle 2-camera duty sat at the 0.60 target, D72); the gate regression check passes unchanged (`bench/results/gate_check_p5.txt`: every incident clip fires in its window, normal/look-alike 0.98 ①/min). (3) **Optional door zone per clip approved** (so a real tailgating clip isn't vetoed); **not built**: `data/dev/tailgating/` has no clip. Planned path when one arrives: a `door_zone` column in `bench/labels.csv` (frame fractions, like `config.yaml`) that `play_clip` passes to `Camera(door_zone=…)`. **Built:** `run_demo.sh` (checks uv / Chrome / weights / Python env / port 8000, starts Ollama if needed, warm-up call with the pipeline's `keep_alive`/`num_ctx`, re-seeds the chat history, rebuilds a stale bundle, starts the server, opens Chrome; a red error and stop on anything missing): **cold start with Ollama killed first 10.2 s** to a working dashboard on the M4 (`p5_cold_start.json`; Ollama already up: 5.7 s; store→card p50/p95 13/20 ms, n = 2). `REPORT.md` (preliminary, for the judges; every number from `bench/results/`), `docs/DECK.md`, `docs/DEMO_SCRIPT.md`. **Chat key frames:** every answer lists its events as key-frame thumbnail + IST time + category · camera (`web/`); API check 2/2 live events with key frames, URLs 200. The brief's example ("Show all tailgating events from camera 2 today" → No matching events + the camera list) and the four §13 chat questions added to `bench/chat_questions.csv`: runner **35/35, 0 invented, 0 uncited**, template p95 1 ms, summary p50 3.3 s. **RTSP:** ffmpeg 8.0.1 has **no RTSP listen mode** (the muxer lists no `rtsp_flags`; `-f rtsp -rtsp_flags listen` connects and dies) and VLC/mediamtx aren't installed → `scripts/rtsp_sim.py` (stdlib RTSP server, UDP + TCP-interleaved, fed by `ffmpeg -f rtp`) + `scripts/rtsp_sim.sh`; as a Live source in the app: `live` 2.6 s after add, fighting alert 5.5 s after add (looping v011), trigger→alert 1,281 ms, keep-up 0.97 at 30 fps / 1280×720 (`p5_rtsp.json`). **Fresh dev-set pass** (v1.14 gates, each of the 11 clips alone, `ab_p5_dev.csv`): 10/11 right (v026 dark-corridor fight → person_down, the known D64/D65 miss), incident recall/precision 1.0/1.0, 0 false alarms on the 4 normal/look-alike clips, trigger→alert p50/p95 1,268/1,332 ms, p3c onset→alert 3,216 ms (3,141 ms in the browser run), GPU duty 0.75 one clip at a time; macro F1 0.64 over the 3 labels present only. **desk_closeup.mp4 removed** from the dev set and the demo playlist after the P5 run (captain, 05:56; the results files keep its row as measured: 10/11 counts it, without it 9/10 and 0 false alarms on 3 normal/look-alike clips). **Pending/cut:** M5 numbers (cold start, latency test, 10-min heat run, Safari tiles, Wi-Fi-off) await Aryan; no fall or tailgating clips; `web/dist` stays gitignored, so the M5 needs `cd web && npm ci && npm run build` once (internet) or a copied `web/dist` (captain's call whether to commit it) | Captain | SPEC v1.15 §10. `run_demo.sh`, `REPORT.md`, `docs/`, `scripts/rtsp_sim.*`, `web/src/App.jsx`, `bench/chat_questions.csv`, `bench/results/{ab_p5_dev*, gate_check_p5.txt, p5_cold_start.json, p5_rtsp.json, chat_runner*}`, `config.yaml` |
| D74 | 2026-10-16 | **Chat search: stemming + filler words (approved, Layer 1 of hybrid retrieval).** Found live: event #82 ("…one is being pushed or thrown back") was missed by "someone being pushed", "events with pushing", "anyone thrown back today?": every non-stop word was a required FTS5 keyword ("someone", "anyone", "person" included) and only a plural -s was folded. Fix: both FTS5 tables use `tokenize='porter unicode61'` (SQLite built-in, no dependency; a pre-D74 DB is migrated on open: FTS tables dropped, recreated, rebuilt); filler words (someone, anyone, person, people, guy, one–four, being, got…) join the stop list; the query keeps AND (no any-word fallback: "red jacket" must not return the blue-jacket events). Chat runner 35 → 44 questions (9 paraphrases): **44/44, 0 invented, 0 uncited**, template p95 1 ms. Still missed (lexical limit, need meaning-level search): "running away" vs "runs out", "lying still" vs "lies still" (Porter doesn't map lying → lie). **Layer 2 (pending the captain's download OK, D21):** a local embedding model in Ollama (`embeddinggemma`, ~300 MB) embeds each summary at write time, brute-force cosine in numpy, rank fusion with bm25, a similarity cutoff tuned on the chat runner so a grounded "no match" survives; later key-frame image embeddings (SigLIP, already planned as FR-9b) | Captain | SPEC v1.16 §8. `app/db.py`, `app/chat.py`, `bench/chat_questions.csv`, `bench/results/chat_runner*` |
| D75 | 2026-10-16 | **Chat v2: an LLM chat, not a search (approved).** The captain asked for no new word lists and "an actual LLM chat". (1) **The model writes every answer that has events**: conversational, ≤ 3 sentences, ≤ 30 rows oldest first with (today)/(yesterday) marks and the database's exact totals per category; the D57 sentence check stays (unknown [#id]s removed, uncited sentences dropped; `[19]` normalised to `[#19]`); the template is the fallback. (2) **The model reads the question** (§5a.2 step 3) as strict JSON with the §6.1 definitions from `app/vlm.py` (no new lists) and a `meaning` paraphrase generated first, which fixed injured → person_down and bags → abandoned_object; follow-ups use the session's last 3 turns. (3) **Cascade, measured:** model-only reading scored 31/48 (it chose subtype fire for "last fire", read "barrier" as a camera, dropped "forklift"), so the rules' exact reading wins when it finds events on a fresh question; the model reads when the rules find no filter, find nothing, or there is a conversation; clock times, #ids and exact camera matches always come from the rules ("camera 2" had become "Camera 2 recorded…" for a lobby event). (4) Unmatched details fall back to a category only when the model chose a specific subtype, with a `note`; a bare category never does ("man in red" listed every suspicious event before). **Measured** (`bench/results/chat_runner*`, 48 questions, M4, idle GPU): **45/48, 0 invented, 0 uncited**; model answers 38/48, latency p50 2718 ms, p95 5870 ms, max 6942 ms, 3 over 5 s (NFR-1a ≤ 5 s missed on those); model reading 14 questions, p50 2235 ms. Misses: 'What did the man in red do?', 'Did anyone get hurt?', 'Any suspicious package?'. Across 4 runs the model's reading of "Was anyone injured?" / "Did anyone get hurt?" varied (category found in some runs, not others: the answer text was right, the key-frame strip listed all events). "Any suspicious package?" needs meaning-level search (embeddings, pending D21). **Also found:** the MLX runner kept a buffer cache: `qwen3.5:4b-mlx` (4.0 GB on disk) showed 12 GB loaded after a night of calls, 4.1 GB after a reload (free memory 33 % → 77 %); `run_demo.sh` now unloads the model before its warm-up | Captain | SPEC v1.17 §5a.2, §7.5, §10. `app/chat.py`, `app/server.py`, `web/src/App.jsx`, `config.yaml`, `run_demo.sh`, `bench/chat_questions.csv`, `bench/results/chat_runner*` |
| D76 | 2026-10-16 | **P5b UI redesign (front end only, approved brief).** Goal: a calm, dense security-operations console that judges read as professional. **Behaviour unchanged**: same SSE handlers, beep, D72 double-buffered snapshot `Live` (untouched apart from its class), every control and endpoint. (1) **Files:** `App.jsx` split into `App.jsx` + `ui.jsx` (primitives, formatters) + `icons.jsx` (13 inline Lucide-style SVGs); no new dependency, no network. (2) **Tokens** in Tailwind v4 `@theme` (`index.css`): Tailwind's palette and type scale are cleared, so only the tokens exist; a light theme is that block redefined. Zinc-950 page, zinc-900 surfaces, 1 px zinc-800 hairlines; one accent (blue) for interactive elements only; red/amber/green for severity or state only; muted text `#8f8f99`, **not zinc-500** (zinc-500 is 3.6:1 on zinc-900 and fails the 4.5:1 rule); 5 sizes 11/12/13/15/20; system font + SF Mono for numbers; tabular-nums everywhere; 150 ms opacity/transform motion, off under reduced motion; the modal's is the only shadow. (3) **Layout:** 48 px top bar (wordmark · Clips \| Live · model, GPU %, onset→alert p50, "Local · offline" badge doubling as the SSE state, IST clock, "Arm sound" → bell); 16:9 tiles (name + state dot, LIVE/CLIP, ■, 2 px inset ring + category chip on an open critical/high event); 400 px rail with tabs Alerts \| Ask \| Pipeline. (4) **The 10 s critical toast is replaced by a banner above the rail that stays until Ack** ("N more unacknowledged"). (5) **Clips:** library list (clip, label, onset, folder; upload in its header and drop target) and a verdict panel (Running/Detected/Missed/False alarm/Correct; onset → alert as its one 20 px number, server value only, D50). (6) **Pipeline** = the Workflow view as a stage stepper (frame → YOLO → gate → VLM → event) + a waterfall of the trace stages + mosaic, hints, raw JSON + the old metrics strip as a System grid. (7) **States:** skeletons for loading, an empty and an error state with a one-line hint per panel; a non-OK GET no longer crashes the app (`getJSON`). (8) **A11y:** focus rings, `/` focuses Ask, Esc closes the event dialog, the banner is `role=alert`, the alert list is `aria-live`. (9) A tile no longer polls `/snapshot` while "connecting" (it 404s before the first frame). Checked: 3+ screenshot rounds at 1512×982 and 1920×1080 (mock states + real server), one real clip end to end (banner 6.0 s after Play, onset→alert 3,631 ms, Ack clears it), 0 console errors. **SPEC §6.3 / FR-14 still say "toast" and "pulsing border"**: wording change for the captain (v1.18) | Captain | `web/` only; `docs/DEMO_SCRIPT.md`, `docs/DECK.md` labels |
| D77 | 2026-10-16 | **Lower window threshold for ungated categories (captain).** `crowd_incident`, `property_damage` and `suspicious_activity` have no gate, so the one-observation path (needs corroboration) can never open them; the 3-observation mean is their only path, and one earlier normal observation drags it down. Evidence: a highway truck crash scored 0.83 then 0.73 after a normal observation, mean 0.52 → no alert at 0.55. New key `events.open_window_ungated: 0.50`; gated categories and `fire_smoke` keep 0.55 (they have the gate path). Replay of every unseeded observation in data/hackhive.db today: 0.55 → 9 openings, 0.50 for all categories → 13 (2 more fights, the truck, one theft reading on a fight clip); 0.50 for ungated only → the truck and that theft reading. Not fixed by this: the F1 crash clip (gettyimages-1406913199; property_damage p mostly 0.0–0.4, cut between crash and crowd shots) needs a better model reading, not a lower bar; 0.45 would add 4 more fight openings and is too loose. Still to measure: false alarms per camera-hour on ≥ 30 min of normal footage (P8) | Captain | `app/events.py`, `config.yaml`, SPEC §6.5, §10 |
| D78 | 2026-10-16 | **Hint contract: the model must not narrate our detector metadata (captain).** The user turn was `Detector: up to 6 people in the last 4 s. Gate: Track 12 top of box dropped 68% of its height in 0.5 s.` and the system prompt never said what it was, so the model wrote it into summaries as scene content (race-track clip, stored: "A track gate drops suddenly, causing dust to rise", "A gate or barrier collapses and breaks down over 2 seconds"; nothing of the kind is in the video). Summaries are a judged criterion and the chat quotes them. Fix at the cause: (1) one static system-prompt sentence (prefix cache kept, D38): the text with the image is detector metadata (people counts, box motion, scene change), not a description of the scene; use it as a hint, never mention it or the detector in the summary; (2) `vlm.user_turn()` is the one builder: `Detector metadata, not visible in the frames: …; trigger: <hint or none>.`; (3) every hint producer reworded without track ids or the words gate/track, numbers kept, hypothesis named: drop → "(possible fall)", horizontal → "for at least N s (possible person down)", fight → "(possible fight)", scene change → "the background changed abruptly … (mean pixel change N%, people excluded)" (the number is a mean intensity change, not a pixel share; people are excluded, not absent). Reviewed by three independent reviewers (rule / prompt / regression); their fixes applied. The two-consecutive run rule reviewed with it was dropped in favour of D77. `bench/latency_test.py` keeps its own standalone prompt (only its user line was aligned). Self-checks: gate (asserts the contract on the hints), scheduler, events; gate regression check ok. Validation (`bench.ab --dev --tag p6`, the 10 dev clips each alone, with D77 + D78): 9/10 right, the same clips as P5 (v026 dark-corridor fight → person_down, the known miss); incident recall/precision 1.0/1.0 (unchanged); 0 false alarms on the 3 normal clips; 0 of 8 summaries mention gate, track, detector, metadata or bounding boxes; trigger → alert p50/p95 1,287/2,021 ms (P5 1,268/1,332; the p95 is v006 waiting 747 ms behind a running baseline, queue contention, not the prompt); onset → alert, now measurable on 6 right clips with the onsets labelled from the frame sheets (v001 0.0, v003 0.0, v006 2.0, v011 1.0, v026 0.0, w001 0.5; Riddhi to verify): p50 3,239 ms, p95 6,381 ms (v011: no gate fired, caught by a baseline), against the 3,000 ms target: missed; GPU duty 0.74 | Captain | `app/vlm.py`, `app/pipeline.py`, `app/gate.py`, `app/scheduler.py`, SPEC §5a step 6, §7.1, §7.4 |
| D79 | 2026-10-16 | **Operator workflow + report tab, first cut (captain: PLAN items 2, 3).** (1) **Mark false alarm** (FR-25) on the alert card, the event dialog and the critical banner → `POST /api/events/{id}/dismiss`: status `dismissed`, reason `operator`, hidden from the feed and the chat (they already exclude dismissed), kept for audit; `EventManager.dismiss()` removes it from the open set and **holds that camera + category for `dismiss_hold_s` (60 s)**, otherwise the same scene re-alerts on the next observation, which is the opposite of what the guard asked for. (2) **Labelled data:** each dismiss appends that event's observations with their probabilities to `data/feedback/operator_false_alarms.csv`, **a file, not the DB**, because every pipeline start clears the live tables (E-14) and the labels must outlive that; `GET /api/report/feedback.csv` serves it, so P8 can calibrate thresholds on real false alarms. The report's operator block is labelled "since server start" for the same reason. (3) **Report tab** (FR-20, rail tab 4): the newest `bench.ab --dev` pass (clips right, incident recall/precision, false alarms on normal clips, onset→alert and trigger→alert p50/p95, per-clip table, errors by confusion pair), with the honest caption that dev numbers are training-set numbers; live operator block: real events, marked false alarms, monitored camera-hours, false alarms per camera-hour (shown only from 3 camera-minutes), live onset→alert, store→card. **Not in this cut:** confusion matrix, veto log, ablations, calibration chart, watts (FR-20's full list, P8). `bench.ab --dev --tag T` added: the one-command headline pass. Server self-check covers dismiss (incl. 404), report and CSV with a throwaway event it deletes | Captain | `app/events.py`, `app/server.py`, `web/src/App.jsx`, `config.yaml`, `bench/ab.py`, SPEC §9, §10 |
| D80 | 2026-10-16 | **Faster fight trigger: `gate.fight_speed` 0.6 → 0.5, and honest onset → alert (captain: fix the latency weak point).** Onset → alert missed the 3 s target (p50 3,239 ms, D78). Split per clip, the trigger was the slow part, not the model: on the staged shove the gate fired 2.0 s after the labelled onset, trigger → alert 1.3 s. A frame-by-frame trace of the fight rule's inputs (tracks touching, height ratio, speed) showed why: at the chest-to-chest onset (5.5–5.6 s) the pair was touching at 0.55–0.56 body heights/s, just under 0.6, and the gate waited for the push at 7.6 s. **Sweep, CPU gate check on every dev clip** (onset → first fight gate; false gate calls on normal clips): 0.60: p3c +2.0 s, v011 +4.6 s, 1 false (0.65/min) · 0.55: +0.0, +4.6, 2 (1.31/min) · **0.50: −0.1, +1.0, 2 (1.31/min)** · 0.45: same as 0.50. 0.50 takes the whole gain at the 0.55 cost; the extra trigger (floor_sit, a look-alike) costs one model call, which says normal. **Measured honestly:** clips whose incident starts before the first full 2 s mosaic (v001, v003, v026 at 0.0; w001 0.5; v011 1.0) also time the buffer filling, which a running camera never does, so the bench and the report tab now give onset → alert for the steady-state group (onset ≥ `mosaic_span_s`) as the headline and the mid-start group apart, and add `onset_s` and `onset_to_gate_ms` per clip. **Validation (`bench.ab --dev --tag p6b`):** 9/10 (same clips), recall/precision 1.0/1.0, 0 false alarms; steady-state onset → alert **p50/p95 810/1,294 ms** (p3c 3,239 → 1,294; v006 3,318 → 810), n = 2, small, more clips needed; mid-start group p50/p95 3,788/6,026 ms (n = 4; v011's early trigger at 2.0 s in the CPU replay came back normal on a short buffer in the live run, and the gate fired again at 5.7 s); trigger → alert p50/p95 1,317/1,764 ms; GPU duty 0.74 → 0.78. Gate regression check ok (`gate_check_p6b.txt`). Thresholds tuned on the dev clips: the held-out test split (P8) is what judges it | Captain | `config.yaml` gate, `bench/ab.py`, `app/server.py`, `web/src/App.jsx`, SPEC §6.6, §10 |
| D81 | 2026-10-16 | **Shift-handover digest (FR-17).** `chat.digest()` + `GET /api/digest`: for the last 1/8/24 h, all cameras or one: a headline (counts by category, how many need follow-up, how many marked false alarm), a short model-written narrative, the incidents most severe first, then notable normal activity per camera (newest 2 summaries, peak people). Facts come straight from the DB; the model only writes the narrative, and with the chat's D57 check: every sentence must cite a listed #id or it is dropped; the template ("Follow up [#id] …") stands in when the model can't. Follow-up = still open, or critical and never acknowledged (an alert that closed unseen still needs someone to look). UI: "Shift handover" + 1 h / 8 h / 24 h in the Ask tab; the report lands in the conversation with clickable #ids and key frames. Seeded history: alerts older than 1 h are now `acknowledged` (an earlier shift handled them), so the digest's follow-up list is the realistic last-hour one; no chat test depends on the seeded status | Captain | `app/chat.py`, `app/server.py`, `web/src/App.jsx`, `web/src/icons.jsx`, `scripts/seed_history.py`, SPEC §9 |
| D82 | 2026-10-16 | **Three dashboard slots: up to 3 clips side by side (captain: the multi-camera objective; approved as the one backend change of the Next.js UI overhaul).** Clips mode played ONE clip at a time by design (D70; 3 busy sources pushed GPU duty > 90 % and alerts to 4-15 s, P2b), so a 3-column Clips tab needs the server's help. Change, `app/server.py` only: a `SLOTS` map camera id → column 1-3; `POST /api/clips/play` and the upload take an optional `slot` and replace only that slot's clip; **no slot keeps the original behaviour** (every clip stops, the new one plays in slot 1), so older callers and the bench are unaffected; Live `POST /api/cameras` takes `slot` too (replaces that slot's source; none = first free column); `GET /api/cameras` rows add `slot`; bad slot → 400; the same source in another slot → 409. The measured cost stands and the UI says so: three busy clips at once share one model, so alerts slow down; the headline accuracy/latency numbers stay one-clip-at-a-time (`bench.ab --dev`). Self-check: two clips in slots 1 and 2, slot 1 replaced while slot 2 runs on, slot 0/4/'1'/True → 400, no-slot play leaves one clip in slot 1, live slot replace and the 409 | Captain | `app/server.py`, SPEC §9 |
| D83 | 2026-10-16 | **PROPOSED, pending captain (branch `fix/benchmark-metrics-v026`). Benchmark correctness + person_down second look.** (1) Metrics: `bench/metrics.py`; `macro_f1` keeps the historical observed-label value (0.641 re-verified on p5/p6/p6b), named `observed_label_macro_f1`; a `fixed` 8-label block (per-class support/TP/FP/FN/P/R/F1 incl. zero-support, macro over supported and over 8, weighted, confusion) with `final_metric_valid` (test split + all classes + no tuned clip + metadata); run metadata on every dev pass. (2) `bench/validate.py`: labels/files/splits/onsets/results checks, exit 1; historical unlabelled rows must be marked in `bench/unlabelled_rows.csv`. (3) v026 diagnosis on the real clip (bench.diagnose): YOLO sees 1 person in 3/97 frames, no gate can fire, 2 baseline calls in 9.7 s. (4) `events.down_guard`, alert-first (team call, 16 Oct): a person_down alerts at once as before; if the detector can't vouch for it (people in < 50 % of the buffer, or a fighting gate in it) a P4 re-look over 4 s corrects it in the open: fighting -> a fighting event opens and the person_down row is marked dismissed/relook, both rows kept and linked by `related_event_id`, both cards stay in the feed with the re-check note; confident normal -> marked dismissed/relook; otherwise confirmed; no verdict -> the alert stands. Box overlap alone was rejected as "interaction" (19/19 calls on idle_60s). Not measured with the model: A/B `--no-down-guard` decides. (5) Instrumentation: gate-fire log, arbiter stats (`GET /api/arbiter`), stale P4 drop, clock-drift flag, negative onset warnings. Contract changes for sign-off: SPEC §9 `GET /api/arbiter`; §10 `events.down_guard`, `vlm.relook_span_s`, `vlm.relook_max_age_s`; events gain `opened_by` (not stored in the DB); §8 `events.related_event_id INTEGER` (nullable, added to older DB files on open, no row changed); E-9: a relook-dismissed card stays in the feed marked "Re-checked" instead of hiding after 5 s (operator false alarms still hide) | Proposed (Aryan) | REPORT §11. `bench/metrics.py`, `bench/validate.py`, `bench/diagnose.py`, `bench/ab.py`, `app/events.py`, `app/scheduler.py`, `app/models.py`, `app/pipeline.py`, `app/server.py`, `app/db.py`, `web/src/App.jsx`, `config.yaml`, `tests/` |
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
- **GPU saturation + heat (D42, D47):** the fanless M5 throttles under a continuously busy GPU; change-gated baselines keep duty ≤ 60 %, and the 10-min heat run before Round 1 checks it.
- **Demo machine never run yet (D47):** M5 setup, Continuity Apple ID and the Wi-Fi-off run are scheduled first in PLAN Part 1.
- **Accuracy evidence is still zero real clips:** the 4B choice rests on one synthetic mosaic until the P2 dev-clip A/B (D55).
- **Detector-dependent veto (D46):** the cross-check is only as good as YOLO-nano's person counts; the veto log shows its cost.

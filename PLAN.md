# HackHive Ctrl-Z: Build & Validate Plan

> **Now:** Fri 16 Oct ~01:15 IST (re-timed for SPEC v1.6) · **Round 1: Fri 16 Oct 09:00 → demo-ready by 07:00** · **Final: Sat 17 Oct 08:00**
> **Division of labour:** **Claude builds everything** (code, scripts, prompts, benchmarks, report drafts, deck draft). **The team does no development**: they test, inspect, critique, ideate and validate, each owning one area. Contract: [SPEC.md](SPEC.md) · Why: [DECISIONS.md](DECISIONS.md)
> **v1.6 package (D42–D56):** every fix and missed opportunity from the judge review is placed in a phase below. Round-1 scope is unchanged (the proposed cuts, "W7", were rejected, D56).

## Validation owners

| Person | Owns (signs off that it works) | Checks in particular |
|---|---|---|
| **Shivansh** (Captain) | **Model & accuracy**: VLM choice, prompt, classification, summaries | Wrong categories, bad or hallucinated summaries, confidence that doesn't match reality; the 4B-vs-2B decision (D55); the veto log (real incidents lost vs false alarms removed); reviews the latency-test and benchmark numbers; triages all issues; final say on scope |
| **Abhinav** | **Vision & cameras**: capture, YOLO tracking, gate rules, live sources | Webcam / iPhone / Pixel streams, false triggers and missed triggers (incl. none from bags), door zone, lighting and camera angles; **mounts the iPhone ~2 m high as the fall camera** (D47); films the missing clips (tailgating, property damage, look-alikes) |
| **Riddhi** | **Data & chat**: datasets, labels, storage, chatbot | Picks and labels the dev/test clips **with incident onset times** (`bench/labels.csv`); collects ≥ 30 min of normal footage for false alarms per camera-hour; writes the chat test questions (incl. keyword questions); tries to make the chatbot invent events or misread time/camera; checks stored events match what happened |
| **Aryan** | **End-to-end reliability & experience**: the system as a whole | **M5 setup and checks** (D47); cold start with `./run_demo.sh`; dashboard + Workflow view usability; GPU duty and heat run on the M5; upload-a-video; stress test (2 incidents + chat, NFR-1a); 30-min soak test; checks every number on screen matches the logs; keeps the Round-1/final acceptance checklists (SPEC §13) |

**Pitch:** the whole team together at the end. Claude drafts the deck and demo script from real numbers; the team critiques and rehearses.

## Build phases (Claude does all development, phase by phase)

Each phase ends with a **gate**: Claude pushes the phase with its self-checks passing and posts a short "what to test" note; the named validator tests it and signs off (or files issues). Claude starts the next phase while the validation runs, and fixes that phase's issues as they come in.

| Phase | Builds | Target done | Validated by | Gate (passes when…) |
|---|---|---|---|---|
| **P0 Model lock** ✅ | Latency + contention test: qwen3.5 4B vs 4B-MLX vs 2B, 1 vs 2 slots, thinking off | Thu 22:15 | Shivansh | Model + slots chosen from measured numbers; logged in DECISIONS |
| **P1 Eyes** ✅ (+ v1.6 fixes) | Repo scaffold, config, capture (file/webcam/URL), YOLO + ByteTrack, ring buffer, annotated live stream, `list_cameras.py`. **v1.6 fixes applied (D54):** one coordinate system (frame pixels) for boxes, histories and zones; `Detector.person_hists()` is the only gate input (bags/knives never gated); duplicate shape/speed code removed (gate.py's is the one); `config.yaml` gate block synced with SPEC §10 + new v1.6 keys; `coremltools` dependency removed | Thu 23:30 · fixes Fri 01:15 | Abhinav | All 3 live sources + a video show boxes/track IDs at ~10 FPS, keep-up 100 %; `app.detect` self-check proves pixel boxes, pixel zones, person-only gate input |
| **P2a Brain: core loop** | Gate rules wired via `person_hists()`, scheduler + arbiter (priorities), **change-gated baselines + confident-normal stop at category + summary every 3rd baseline (D42)**, **observation-based close rule (D43)**, **16:9 letterboxed 288×160 tiles (D44) + the 5-min MLX image-shape check (E-25)**, **prompt with §6.1 definitions + "not this" exclusions, flat subtype enum (D49)**, streaming VLM client (`num_ctx` fixed, D38), early decision, **detector cross-check E-7 with buffer-max counts + veto log (D46)**, event manager, SQLite. Ends with `uv run python -m app.pipeline <clip>` printing alerts + onset-to-alert ms | Fri 03:00 | Shivansh (labels/summaries, veto log) · Abhinav (triggers) | Demo clips produce the right incidents with sensible summaries; look-alikes don't alert; GPU duty ≤ 60 % with 3 cameras; onset-to-alert logged |
| **P2b Brain: A/B** | `bench/ab.py` (one script, one flag per test): **4B vs 2B on real dev clips with the real prompt, decided by the D55 rule** (blocking: locks the model before P3); pose vs plain YOLO for gates (FR-6a) and mosaic vs person-crop vs native video run **in the background during P3** | 4B/2B Fri 03:30 · rest Fri 05:00 | Shivansh (4B vs 2B) · Abhinav (pose A/B) | A/B results logged in DECISIONS; model locked |
| **P3 Face** | FastAPI + SSE, React dashboard: grid, incident feed (**top-3 probability bar + "trigger → alert ms" on each card**, D52), alerts, metrics strip (**+ GPU duty %, baselines skipped, vetoes**), Workflow view, "now" line (**detector template between summaries**), upload-a-video | Fri 05:00 | Aryan | Every SPEC §13 dashboard item works in the browser; upload works |
| **P4 Voice** | Chat v1 (rules + **keyword → FTS5 search (D53)** + model fallback, templates, grounding with **sentence-level citation check (D57)**), seeded history | Fri 05:45 | Riddhi | Chat test questions (incl. keyword questions) answered correctly, no invented events, no uncited sentence in any summary answer |
| **P5 Round-1 hardening** | `run_demo.sh`, **M5 run: latency test + 10-min heat run (NFR-5)**, stress test, fixes, preliminary numbers, **240 fps fall → toast clip**, deck + demo-script draft (incl. the **look-alike moment**: hug / sit → no alert) | Fri 06:45 | Aryan (cold start, M5, heat, stress) · all (deck critique) | SPEC §13 Round-1 checklist all ✅ → git tag `round1` |
| **P6 Accuracy** | Re-look, benchmark harness (**`bench/labels.csv` with onset times**), dev-set tuning loop (prompt, thresholds, **loosen E-7 if it loses > 1 real fight/fall per 10 clips**). **Track-crop tile A/B (FR-9c, D45).** **Trained classifier (FR-9b) only if dev macro F1 < 0.70 after the above (D48):** SigLIP2-base + small classifier on a separate **train** split, fusion weight on **dev**, time-box 2 h | Fri 14:00 | Shivansh · Riddhi (labelled clips are the training data) | Dev macro F1, incident recall/precision and latency reported, with and without each change; tuning log committed |
| **P7 Completeness** | Digests as a **shift-handover report** (FR-17), **"mark false alarm" operator workflow (FR-25)**, full chat (follow-ups, look-again), RTSP sim, report tab, **tailgating gate only if a door camera is used (D55)**, **GPU duty + watts per camera measurement**, judge-feedback items | Fri 18:00 | Riddhi (chat, digest) · Abhinav (RTSP, tailgating) · Aryan (report tab, operator workflow, watts) | All **F** requirements in SPEC §3 done |
| **P8 Final validation** | Test-set run (macro F1, **incident recall/precision, onset-to-alert per category, veto log**), **false alarms per camera-hour on ≥ 30 min of normal footage**, gate + field-order ablations, soak test, final report | Fri 22:00 (**freeze**) | All | NFR targets measured; soak passed; report committed |
| **P9 Demo assets** | Final deck (incl. 240 fps latency clip, false alarms per camera-hour, watts per camera, on-prem story), demo script, backup video | Sat 02:00 | All | Team rehearsed it twice and is happy with it |

## Phase protocol (one phase per session, no context dilution)

1. **One fresh Claude session per phase.** The previous phase hands over only through git: code + PLAN tick (✅) + a commit message ending with the "what to test" note. No chat history is carried over.
2. **Read only what the phase needs:** `CLAUDE.md`, this file's phase row, and the SPEC/DECISIONS sections below. Read code only for the interfaces the phase calls into (signatures and docstrings, not whole files).
3. **Build only that phase's row.** Anything outside it goes in the "what to test" note as a follow-up, not into the code.
4. **Done =** every new module's self-check passes, the phase gate is measured (numbers, not adjectives), committed and pushed, PLAN ticked. Then stop and report; the next phase starts on the captain's "start Pn".

| Phase | SPEC sections | DECISIONS |
|---|---|---|
| P2a | §5, §5a.1, §6, §7.1–7.4, §8, §10, §12a | D38, D42–D46, D49, D50, D54 |
| P2b | §12 | D55; FR-6a in §3 |
| P3 | §3 (dashboard FRs), §9, §9.1, §9.2, §13 (Round-1) | D50, D52 |
| P4 | §5a.2, §7.5, §8 (FTS5) | D53, D57 |
| P5 | §4, §12, §13 (Round-1) | D47, D50 |
| P6 | §3 (FR-9b, FR-9c), §12 | D45, D48 |
| P7 | §3 (all F requirements) | — |
| P8 | §4, §12, §13 (final) | — |
| P9 | §2 | — |

## Part 1: Road to Round 1 (re-timed from Fri 01:15 → 09:00)

| Time | Claude builds | Shivansh | Abhinav | Riddhi | Aryan |
|---|---|---|---|---|---|
| **01:30–03:30** | **P2a** (to 03:00): gates wired, scheduler/arbiter with baseline load control, tiles + shape check, prompt, streaming VLM, cross-check, events, SQLite; **P2b** (03:00–03:30): 4B vs 2B on the dev clips; pose + tile A/Bs queued to run in the background during P3 | Inspect the prompt and the first raw VLM outputs; decide 4B vs 2B (D55) | Mount the iPhone ~2 m high (floor in view, door if available); film falls + look-alikes (sit, bend, hug) | **By 02:00:** ≥ 3 clips per category + look-alikes in `data/dev/<category>/`, `bench/labels.csv` with onset times | **M5 setup now** (D47): Ollama same version, copy `~/.ollama/models`, `uv sync`, camera permission, Continuity with the iPhone 15 (same Apple ID), `TILE` latency test, Wi-Fi-off run |
| **03:30–05:00** | **P3** dashboard, Workflow view, "now" line, alert cards, upload-a-video | On watch (keeps the Claude session alive); end-to-end check at 03:30 | Live false-trigger hunting on all cameras (incl. people carrying bags) | **Sleep 03:00–05:30** | **Sleep 02:30–05:00** |
| **05:00–05:45** | **P4** chat v1 (rules + keywords), seeded history | Review misclassifications and the veto log | Live staged fall + look-alike tests on the iPhone camera | (sleeping) | Dashboard check; GPU duty on screen |
| **05:45–06:45** | **P5**: `run_demo.sh`, M5 latency + 10-min heat run, fixes, deck + demo-script draft | **Sleep 05:30–07:30** | **Sleep 05:30–07:30** | Run the chat test questions; critique the deck | Cold-start + stress test on the M5; 240 fps fall → toast clip; Round-1 checklist |
| **06:45–07:00** | **Round-1 freeze** (git tag `round1`), backup screen recording | (sleeping) | (sleeping) | Critique the deck draft | Verify the on-screen numbers vs the logs |
| **07:00–09:00** | Standby, P0 fixes only | Venue setup | Mount the iPhone camera, check lighting and floor view | Full run-through | Full run-through |
| **09:00** | | **Whole team presents together** | | | |

**Go/no-go at 03:30:** if the core loop (camera → alert → card → chat) isn't solid, Claude drops polish (Workflow-view extras, the phone network camera) to secure it.

## Part 2: Round 1 → Final (Fri 09:00 → Sat 08:00)

| Time | Claude builds | Team validates |
|---|---|---|
| Fri 09:00–10:00 | Turns judge feedback into SPEC changes | Debrief; the captain approves the changes |
| Fri 10:00–18:00 | F requirements: re-look, digests (shift handover), mark-false-alarm, full chat, RTSP sim, benchmark harness with onset labels, report tab (incl. false alarms per camera-hour, incident recall/precision, watts per camera); track-crop A/B; classifier only if dev F1 < 0.70; tailgating gate only with a door camera; accuracy-tuning loop on the dev set | Riddhi labels the **test set (with onset times) by 14:00** and assembles ≥ 30 min of normal footage; everyone files issues from their area; test rounds at 12:00, 15:00, 18:00 |
| Fri 18:00–22:00 | Final test-set run → report; false-alarm run; watts measurement; soak test; stretch only if green | Aryan runs soak + stress tests; Shivansh signs off accuracy; Abhinav signs off cameras; Riddhi signs off chat |
| **Fri 22:00** | **FINAL FEATURE FREEZE**: bug fixes only | |
| Fri 22:00–02:00 | Final deck + demo script + backup video | Whole team critiques and rehearses (23:30, 01:00) |
| Sat 02:00–06:30 | Standby | Sleep |
| Sat 06:30–08:00 | Standby | Cold-start test, final rehearsal, **present together** |

## How validation works
- Every finding → **GitHub Issue** (or pasted to Claude): what you did → expected → what happened → screenshot/clip. Labels: `bug`, `accuracy`, `latency`, `ui`, `idea`.
- `P0` breaks the demo (fixed now) · `P1` within 2 h · `P2` backlog.
- Ideas and critiques are welcome anytime; the captain triages them at each test round.
- Pull `main` before every test round; `main` is always runnable.

## Standing rules
1. SPEC §6–§11 change only with the captain's approval + a version bump.
2. No downloads or installs without the captain's confirmation (D21).
3. Real numbers only: the demo matches the report. Latency is quoted as onset-to-alert (what a judge times), never the model-only number alone.
4. Cut scope before cutting rehearsals or sleep.
5. One coordinate system: frame pixels everywhere (D54).

# HackHive Ctrl-Z: Build & Validate Plan

> **Now:** Thu 15 Oct ~21:30 IST · **Round 1: Fri 16 Oct 09:00 → demo-ready by 07:00** · **Final: Sat 17 Oct 08:00**
> **Division of labour:** **Claude builds everything** (code, scripts, prompts, benchmarks, report drafts, deck draft). **The team does no development**: they test, inspect, critique, ideate and validate, each owning one area. Contract: [SPEC.md](SPEC.md) · Why: [DECISIONS.md](DECISIONS.md)

## Validation owners

| Person | Owns (signs off that it works) | Checks in particular |
|---|---|---|
| **Shivansh** (Captain) | **Model & accuracy**: VLM choice, prompt, classification, summaries | Wrong categories, bad or hallucinated summaries, confidence that doesn't match reality; reviews the latency-test and benchmark numbers; triages all issues; final say on scope |
| **Abhinav** | **Vision & cameras**: capture, YOLO tracking, gate rules, live sources | Webcam / iPhone / Pixel streams, false triggers and missed triggers, door zone, lighting and camera angles; films the missing clips (tailgating, property damage, look-alikes) |
| **Riddhi** | **Data & chat**: datasets, labels, storage, chatbot | Picks and labels the dev/test clips; writes the chat test questions; tries to make the chatbot invent events or misread time/camera; checks stored events match what happened |
| **Aryan** | **End-to-end reliability & experience**: the system as a whole | Cold start with `./run_demo.sh`; dashboard + Workflow view usability; upload-a-video; stress test (2 incidents + chat, NFR-1a); 30-min soak test; checks every number on screen matches the logs; keeps the Round-1/final acceptance checklists (SPEC §13) |

**Pitch:** the whole team together at the end. Claude drafts the deck and demo script from real numbers; the team critiques and rehearses.

## Part 1: Road to Round 1 (Thu 21:30 → Fri 09:00)

| Time | Claude builds | Shivansh | Abhinav | Riddhi | Aryan |
|---|---|---|---|---|---|
| **21:30–22:15** | Latency + contention test (4B vs 4B-MLX vs 2B; 1 vs 2 slots) → model locked; repo scaffold | Review the numbers, confirm the model; sign SPEC | Connect iPhone 15 (USB) + Pixel 10 (IP Webcam); confirm video on the Mac | Download the datasets (SPEC/DECISIONS Q26) | Sign SPEC; write the Round-1 test script from SPEC §13 |
| **22:15–00:30** | Capture → YOLO → gate → scheduler/arbiter → streaming VLM → events → SQLite → API | Inspect the prompt and the first raw VLM outputs | Film tailgating / property-damage / look-alike clips | Pick **one strong demo clip per category** (by 23:00), then the **dev set** (5 per class) | Test each module's self-check as it lands; file issues |
| **00:30–03:00** | Dashboard, Workflow view, "now" line, chat v1, upload-a-video, seeded history, `run_demo.sh` | On watch (keeps the Claude session alive); end-to-end check at 02:00 | Live false-trigger hunting on all cameras | **Sleep 01:00–05:00** | **Sleep 01:00–05:00** |
| **03:00–05:00** | Fix issues; preliminary dev-set accuracy + latency numbers | Review misclassifications, critique the prompt | Live staged fall + tailgating tests | (sleeping) | (sleeping) |
| **05:00–06:00** | Fix P0s; draft the Round-1 deck + demo script | **Sleep 05:00–07:30** | **Sleep 05:00–07:30** | Run the chat test questions | Cold-start test + stress test + Round-1 checklist |
| **06:00–07:00** | **Round-1 freeze** (git tag `round1`), backup screen recording | (sleeping) | (sleeping) | Critique the deck draft | Verify the on-screen numbers vs the logs |
| **07:00–09:00** | Standby, P0 fixes only | Venue setup | Mount cameras, check lighting | Full run-through | Full run-through |
| **09:00** | | **Whole team presents together** | | | |

**Go/no-go at 02:00:** if the core loop (camera → alert → card → chat) isn't solid, Claude drops polish (Workflow-view extras, the phone network camera) to secure it.

## Part 2: Round 1 → Final (Fri 09:00 → Sat 08:00)

| Time | Claude builds | Team validates |
|---|---|---|
| Fri 09:00–10:00 | Turns judge feedback into SPEC changes | Debrief; the captain approves the changes |
| Fri 10:00–18:00 | F requirements: cross-check, re-look, digests, full chat, RTSP sim, benchmark harness, report tab; accuracy-tuning loop on the dev set | Riddhi labels the **test set by 14:00**; everyone files issues from their area; test rounds at 12:00, 15:00, 18:00 |
| Fri 18:00–22:00 | Final test-set run → report; soak test; stretch only if green | Aryan runs soak + stress tests; Shivansh signs off accuracy; Abhinav signs off cameras; Riddhi signs off chat |
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
3. Real numbers only: the demo matches the report.
4. Cut scope before cutting rehearsals or sleep.

# HackHive Ctrl-Z: Build & Test Plan

> **Now:** Thu 15 Oct ~19:50 IST · **Round 1 evaluation: Fri 16 Oct 09:00 → demo-ready by 07:00** · **Final deadline: Sat 17 Oct 08:00**
> Claude builds continuously; the team tests from the moment anything runs. Contract: [SPEC.md](SPEC.md) · Decisions: [DECISIONS.md](DECISIONS.md)

## Part 1: Road to Round 1 (Thu 19:50 → Fri 09:00)

Target: every **R1** requirement in SPEC §3 and the Round-1 checklist in SPEC §13.

| Time | Claude | Shivansh (Captain, AI/Model) | Abhinav (Vision & Cameras) | Riddhi (Data & Chat) | Aryan (Product & Pitch) |
|---|---|---|---|---|---|
| **19:50–20:30** | Downloads (after approval); repo scaffold; CLAUDE.md; 10-min latency test of Qwen3.5 4B (GGUF vs MLX) and 2B | Approve downloads; sign SPEC; set Claude Code permissions so builds don't stall | Connect iPhone 15 (Continuity, USB) + Pixel 10 (IP Webcam) to the Mac; confirm video | Download fight/fall/fire/crowd datasets | Read SPEC; draft the Round-1 deck outline |
| **20:30–00:30** | Ingest → YOLO → gate → scheduler → streaming VLM → events → SQLite → API (pushed module by module) | Test each module as it lands; review the prompt | Film tailgating, property-damage and look-alike clips | Cut **one strong demo clip per category** (by 22:00), then the **dev set** (5 per class) | Deck: problem, approach, architecture, workflow; 15 chat test questions |
| **00:30–03:00** | Dashboard (grid, feed, alerts, metrics), Workflow view, live "now" line, chat v1, seeded history, `run_demo.sh` | Watch the session; end-to-end test at 02:00 | Live-camera false-trigger testing; file issues | **Sleep 01:00–05:00** | **Sleep 01:00–05:00** |
| **03:00–05:00** | Fix issues; preliminary dev-set latency + accuracy numbers | Triage issues with Claude | Test the staged fall + tailgating live | (sleeping) | (sleeping) |
| **05:00–06:00** | Fix P0s only | **Sleep 05:00–07:30** | **Sleep 05:00–07:30** | Run the chat test questions; file issues | Put the preliminary numbers into the deck; full app walkthrough |
| **06:00–07:00** | **Round-1 freeze**: git tag `round1`; record a backup screen video | (sleeping) | (sleeping) | Rehearse the demo with Aryan ×2 | Rehearse the demo with Riddhi ×2 |
| **07:00–09:00** | Standby for P0 fixes only | Cold-start test at the venue | Mount cameras, check lighting | Final run-through | **Presents** (most rested) |

**Round-1 demo (~5 min):** problem (30 s) → architecture + workflow (1 min) → live: staged fall on webcam → alert + summary; recorded fight/fire/crowd clips → incident cards; Workflow view with timings (2 min) → chat: 3 questions (1 min) → early numbers + what comes in the final (30 s).

**Go/no-go at 02:00:** if the end-to-end pipeline isn't working with the dashboard, drop the phone network camera, the Workflow-view polish and chat follow-ups. The core loop (camera → alert → card → chat) must work.

## Part 2: Round 1 → Final (Fri 09:00 → Sat 08:00)

| Time | Focus |
|---|---|
| Fri 09:00–10:00 | Debrief: apply judge feedback to SPEC/DECISIONS |
| Fri 10:00–18:00 | **F** requirements: cross-check, re-look, digests, full chat, RTSP sim, upload-a-video, benchmark harness, report tab. Test set labelled by 14:00 (Riddhi). Accuracy-tuning loop on the dev set |
| Fri 18:00–22:00 | Final test-set run → report numbers; 30-min soak test; stretch only if green |
| **Fri 22:00** | **FINAL FEATURE FREEZE**: bug fixes only after this |
| Fri 22:00–02:00 | Deck with real numbers, demo script, backup video, rehearsals at 23:30 and 01:00 |
| Sat 02:00–06:30 | Sleep (everyone) |
| Sat 06:30–08:00 | Cold-start test, final rehearsal, present |

## How testing works
- Every finding → **GitHub Issue**: what you did → expected → what happened → screenshot/clip. Labels: `bug`, `accuracy`, `latency`, `ui`, `idea`.
- `P0` breaks the demo (fixed now) · `P1` within 2 h · `P2` backlog.
- The captain triages ideas; nothing new mid-block without triage.
- Pull `main` before every test round; `main` is always runnable.

## Standing rules
1. SPEC §6–§11 change only with the captain's approval + a version bump.
2. No downloads or installs without the captain's confirmation (D21).
3. Real numbers only: the demo matches the report.
4. Cut scope before cutting rehearsals or sleep.

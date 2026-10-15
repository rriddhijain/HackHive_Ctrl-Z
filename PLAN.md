# HackHive Ctrl-Z: 36-Hour Build & Test Plan

> **Now:** Thu 15 Oct, 19:30 IST · **Deadline:** Sat 17 Oct, 08:00 IST · **Time left:** ~36.5 h
> **Rule of the plan:** Claude builds continuously; the team tests from the moment anything runs. Every milestone ends with a test round. Decisions live in [DECISIONS.md](DECISIONS.md).

## Milestones (go / no-go gates)

| Milestone | When | Done means | If it slips |
|---|---|---|---|
| **M0: Model picked** | Thu 22:30 | Bake-off numbers on the M4 (and M5); model chosen; one clip runs end to end in the terminal | VLM p95 > 2.5 s → smaller tiles / LFM2.5-VL-1.6B / shorter output; decide by 23:00 |
| **M1: MVP** | Fri 06:00 | Dashboard with 3 cameras, live incidents + sound alerts, SQLite, basic chat | Drop the phone network camera; keep webcam + videos |
| **M2: Feature-complete** | Fri 14:00 | Workflow view, live summaries + digests, full chat, report tab, benchmark harness, first dev-set numbers | Dev macro-F1 < 0.65 → switch on the learned-classifier booster (Q35 trick 5) |
| **M3: FEATURE FREEZE** | **Fri 22:00** | Tuned; final test-set numbers; 30-min soak test passed | After this: bug fixes only, no exceptions |
| **M4: Demo locked** | Sat 04:00 | Deck with real numbers, demo script, backup video, 3 rehearsals done | Cut the stage, not the rehearsal |

## Timeline

### Block 1: Setup & model bake-off (Thu 19:30 → 22:30)
| Who | Does |
|---|---|
| **Claude** | (after download approval) installs runtimes, pulls the shortlisted models, writes the bake-off script; scaffolds the repo (CLAUDE.md, config, contracts); builds ingestion + YOLO tracking first |
| **Shivansh** (Captain, AI/Model) | Approves downloads; sets Claude Code permissions so builds don't stall on prompts; reviews bake-off numbers and picks the model with Claude; gets the M5 owner to run the same bake-off script |
| **Abhinav** (Vision & Cameras) | Films the missing clips (Q25: tailgating 15 + single entries 10, property damage 15, look-alikes 10); connects the iPhone 15 (Continuity/USB) and Pixel 10 (IP Webcam) to the Mac and confirms both show video |
| **Riddhi** (Data & Chat) | Downloads datasets (Q26); cuts clips; **builds the dev set first (5 per class × 8 = 40 clips)**, needed by Fri 02:00 for tuning |
| **Aryan** (Product & Pitch) | Product name, deck outline, first demo storyline; writes 25 chat test questions with Riddhi |

### Block 2: Core build, overnight (Thu 22:30 → Fri 06:00)
| Who | Does |
|---|---|
| **Claude** | Gate rules + scheduler, streaming VLM classification, event merging, SQLite, API, dashboard v1, chat v1. Pushes each module to `main` with its self-check passing |
| **Team** | **Sleep in shifts.** One person on watch keeps the Claude session alive and answers prompts. Proposed shifts: Shivansh 22:30–01:00 · Abhinav 01:00–03:30 · Aryan 03:30–06:00 · Riddhi sleeps through, then labels in the morning |

### Block 3: Test round 1 + feature completion (Fri 06:00 → 14:00)
| Who | Does |
|---|---|
| **Claude** | Workflow view, live scene summaries + digests, full chat (incl. "look again"), report tab, benchmark harness; fixes P0/P1 issues as they arrive |
| **Shivansh** | Runs the dev benchmark; reviews misclassified frames with Claude; prompt ideas |
| **Abhinav** | Live-camera testing: false triggers, door-zone setup, lighting, camera angles; files issues |
| **Riddhi** | **Labels the test set (15 per class, locked at 12:00)**; runs the chat test questions |
| **Aryan** | Uses the dashboard like a security operator and files UX issues; deck v1 |

### Block 4: Tune & harden (Fri 14:00 → 22:00)
| Who | Does |
|---|---|
| **Claude** | Accuracy tuning loop on the dev set; latency optimisation; stretch items in order if green; 30-min soak test; fixes |
| **Team** | Test rounds at 16:00 and 19:00. **After 18:00, a new feature needs the captain's approval.** 21:00: final test-set run → report numbers |

### Block 5: Demo lock (Fri 22:00 → Sat 04:00)
| Who | Does |
|---|---|
| **Claude** | Bug fixes only; one-command demo launcher; seeded history; README; final report |
| **Aryan + all** | Deck with real numbers; demo script; rehearsals at **23:30, 01:30, 03:00**; record the backup video at 02:30; Q&A prep |

### Block 6: Rest & go (Sat 04:00 → 08:00)
Sleep 04:00–06:30 · 06:30 set up at the venue and run a cold-start test · 07:30 ready.

## How testing works

- **Report every finding as a GitHub Issue:** what you did → what you expected → what happened → screenshot or clip. Labels: `bug`, `accuracy`, `latency`, `ui`, `idea`.
- **Priority:** `P0` = breaks the demo (fixed immediately) · `P1` = fixed within 2 h · `P2` = backlog.
- **Ideas** go in as `idea` issues. The captain triages them at each test round, and nothing gets built mid-block without that triage.
- **`main` is always runnable.** Pull it before every test round.

## Standing rules
1. Contracts (DECISIONS.md §4) change only with the captain's approval + a new log entry.
2. No downloads or installs without the captain's confirmation (D21).
3. Real numbers only: the demo must match the report.
4. Cut scope before cutting rehearsals.

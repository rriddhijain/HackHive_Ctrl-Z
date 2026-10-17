# How HackHive works: from camera to classification

A plain-English guide for the team and the pitch. Every number here is a setting in `config.yaml` or a measurement in `REPORT.md`; the code is the final word (`app/gate.py`, `app/scheduler.py`, `app/vlm.py`, `app/events.py`).

## The short version

- A small, fast detector (YOLO) watches **every frame** of every camera on the CPU and tracks where each person is.
- The big AI model (a vision-language model, Qwen3.5-4B, running locally on the laptop's GPU) is too slow to watch every frame, so it only **looks when it is asked to**: when a cheap rule sees something suspicious (a fall, a scuffle), or on a regular timer for what no rule can see (fire, vandalism, theft).
- Each look shows the model the **last 2 seconds as one picture** (4 frames in a 2×2 grid) plus a short note from the rule.
- The model streams its answer; we **alert the moment it names the category**, with a confidence read from its own token probabilities.
- Event rules turn single answers into **incidents**: one confident look backed by a rule is enough for critical things; otherwise a few looks have to agree.

```
camera ─► frames (10/s, 640 px wide) ─► 4-second buffer
                                          │
                     every frame (CPU)    ▼
                    YOLO26n + ByteTrack: people, boxes, track ids
                                          │
              ┌───────────────────────────┴──────────────────────────┐
              ▼                                                      ▼
   RULES ("look now!")                                REGULAR LOOK ("look every few s")
   fall · fight · scene change                        3 s (5 s if empty), skipped if
              │                                       nothing changed, never > 8 s apart
              └─────────────────► ARBITER ◄──────────────────────────┘
                     one model slot · incident > chat > regular > re-look
                                     │
                                     ▼
              last 2 s as a 2×2 picture + the rule's note   (GPU)
                                     │
                     Qwen3.5-4B streams JSON, category first
                                     │
                   category + confidence (token probabilities)
                                     │
                   EVENT RULES: open / update / close an incident
                                     │
              alert: dashboard + sound · ESP32 console · Telegram
```

## 1. Cameras in

- A source is a **webcam or iPhone** (Live tab), a **video file** (Clips tab, or a judge's upload), or a **network camera** (an `http`/`rtsp` URL). Each gets an id (`cam1`, `cam2`…) and a column on the dashboard.
- Frames are taken at **10 per second**, resized to **640 px wide**, and the last **4 seconds** are kept in a ring buffer. Everything below measures in pixels of that 640-px frame.

## 2. Every frame: who is where

- **YOLO26n** (the nano model, 480-px input, on the CPU) finds people, plus bags and knives, keeping detections with confidence **≥ 0.35**. It takes about **15–25 ms per frame**, so it keeps up at 10 frames a second while the AI model runs on the GPU.
- **ByteTrack** links detections over time, so each person has an id and a short history of boxes: where they were, how tall, how fast they moved.
- Nothing is sent to the AI yet. This part is cheap and never stops.

## 3. When the AI model looks

There is **one model slot**, shared by all cameras, given out by priority: **1** an incident (a rule fired) › **2** a chat question › **3** a regular look › **4** a re-look. An incident request **interrupts** a running regular look; an incident call is never interrupted.

### a. A rule fires: "look now"

| Rule | Fires when | Asks the model about |
|---|---|---|
| **Fall / person down** | a person's box is at least **1.2× wider than tall for 0.5 s**, or it **drops by ≥ 40 % of its height within 0.5 s** (unless it also got > 20 % narrower: that is someone walking away) | `person_down` |
| **Fight** | two tracked people of **similar size** (the smaller at least half the height of the larger) whose boxes **touched in the last 0.5 s**, one of them moving at **≥ 0.5 body heights per second** | `fighting` |
| **Scene change** | **more than 25 %** of the picture changes, with people masked out: lights off, camera covered or moved | anything |

People tracked for under 0.5 s are ignored. After the model answers a confident "normal", that rule **goes quiet** for that person or pair (someone still lying down is re-checked after 30 s), so a person on a sofa doesn't wake the model all day.

There is **no rule** for fire, smoke, crowd panic, vandalism or theft (tailgating and loitering have settings in `config.yaml` but no rule in the code yet). Those are caught by the regular look.

### b. The regular look: "check every few seconds"

- Every **3 s** per camera if someone is in view, every **5 s** if the room is empty.
- **Skipped** if nothing changed since that camera's last look (the picture moved by less than 6 grey levels on average with people blanked out, and nobody moved), but **never more than 8 s** without a look.
- If the GPU is busy (over **55 %** of the last minute), regular looks slow down; every camera still gets one at least every 8 s, and rule-triggered looks are never slowed.

## 4. A quiet camera: 1.5 hours of nothing

The system never really sleeps. The "eyes" (YOLO) stay open; the "brain" (the AI model) blinks every few seconds and wakes instantly when a rule fires.

- **YOLO**: 10 frames a second × 90 minutes = **54,000 frames analysed** per camera, about 20 ms each on the CPU.
- **Model looks**: an empty, unchanging room gets one look every **8 s** (the skip rule stretches the 5 s timer to the 8 s cap): about **450 an hour, ~675 in 1.5 hours**. If people move around, up to one every 3 s (**1,200 an hour**).
- **Each quiet look is short**: the model reads "normal" in about **1.2–1.4 s** and, when it is at least **80 %** sure, **stops right there** without writing a summary (every third regular look writes a short one anyway). One still camera therefore keeps the GPU busy roughly **15–20 %** of the time (our estimate: about 1.3–1.5 s of model time every 8 s).
- **What is stored**: every look is logged as an observation; a thumbnail is saved only when the answer isn't normal.
- **The model stays loaded** in memory the whole time, so the first real alert after hours of quiet is as fast as any other.

## 5. The AI's look

1. **The picture**: 4 frames from the last 2 seconds (−2.0, −1.33, −0.67 and 0 s) tiled into one **2×2 image of 576×320**, each frame letterboxed (fitted with grey bars, never stretched).
2. **The note**: labelled detector facts (how many people in the last 4 s) and, from a rule, a hint that also names the look-alikes, e.g. "two people in contact, moving fast; it might be a fight, or people hugging or helping someone up; judge the frames". Naming look-alikes stopped the model from simply agreeing with the rule.
3. **The answer**: Qwen3.5-4B (open weights, run locally by Ollama, temperature 0) streams JSON with the **category first**, then a subtype, the people count and a one-line summary.
4. **The confidence**: not a number the model makes up. We read the probability it gives every category from its **token log-probabilities**, then:
   - **× 1.15** if the rule that woke it agrees (a fight rule, and the model says fighting),
   - **× 0.5** if the detector contradicts it (it says fighting or a fall, but YOLO saw nobody in 4 s),
   - capped at 1.0.
5. **The early stop**: a confident "normal" (**≥ 0.80**) ends the call at the first word, which saves GPU time; otherwise the model writes its summary.

## 6. From a look to an incident

Checked the moment the category is read, before the summary arrives:

1. **One look is enough** if the rule backs it (or it is fire) and the confidence is **≥ 0.70** for a critical category (fire, fight, person down, theft / weapon / trespass) or **≥ 0.85** for any other.
2. **Otherwise the looks must agree**: over the last 3 looks (at least 2), an average of **≥ 0.55**, or **≥ 0.50** for crowd, vandalism and suspicious activity, which no rule can back.
3. **One incident per camera and category**: more looks update it (peak confidence, best key frame) instead of raising new alerts.
4. **The alert fires immediately**: it reaches the dashboard (with sound for critical and high), the ESP32 console and the guard's phone on Telegram. The summary and key frames follow about a second later.
5. **It closes** after 2 looks in a row and 8 s below **0.40**.
6. **The operator's "False alarm"** keeps that camera and category quiet for 60 s.

Severity: **critical** = fire, fight, person down, theft / weapon / trespass · **high** = crowd, vandalism · **medium** = tailgating, loitering, abandoned object. The card's rating: **High ≥ 0.80**, **Medium ≥ 0.60**, otherwise Low.

## 7. Four examples

- **A fight after 1.5 hours of quiet.** Two people grab and shove. As soon as their boxes touch and one moves fast enough, the fight rule fires; the incident request interrupts any regular look; the model sees the last 2 seconds and names "fighting" about 1.2–1.4 s later, say at 0.82, ×1.15 = 0.94, above 0.70: alert. *Measured on our fight clips (laptop cool): 1.4–5.2 s from the start of the fight, median 2.7 s.*
- **A fire in an empty room.** No rule can see fire, so it waits for the next regular look (at most 5–8 s). One look at ≥ 0.70 opens it; otherwise two or three looks averaging ≥ 0.55. *Measured for fire, crowd and theft: 7–10 s.*
- **A hug, or someone sitting on the floor.** The rule fires because it looks like a scuffle or a fall; the model answers "normal" at ≥ 0.80 and stops; no alert, and the rule goes quiet for that pair. *Honestly: the hug in our own staged clip still sometimes raises a fight alert.*
- **Someone collapses.** Their box turns wider than tall for half a second (or drops fast); the model is asked about a fall; ≥ 0.70: alert. *Our weakest category: the nano detector can lose a person lying flat.*

## 8. The numbers that matter

| What | Value | Where |
|---|---|---|
| Frames | 10 per second, 640 px wide, 4 s kept | `detector.fps`, `frame_width`, `buffer_s` |
| Detector | YOLO26n, 480-px input, confidence ≥ 0.35, CPU | `detector:` |
| Fall rule | box ≥ 1.2× wider than tall for 0.5 s, or a ≥ 40 % drop in 0.5 s | `gate.down_ratio`, `down_hold_s`, `drop_frac`, `drop_window_s` |
| Fight rule | contact in the last 0.5 s, ≥ 0.5 body heights/s, similar size | `gate.fight_contact_s`, `fight_speed`, `fight_min_height_ratio` |
| Scene change | > 25 % of the picture | `gate.scene_change_frac` |
| Regular look | 3 s (5 s empty), skipped if unchanged, never > 8 s apart | `vlm.baseline_interval_s`, `empty_interval_s`, `baseline_skip` |
| GPU back-off | above 55 % of the last minute | `vlm.duty_target` |
| Picture | 4 frames over 2 s, 2×2 grid, 576×320 | `vlm.mosaic_frames`, `mosaic_span_s`, `tile` |
| Early stop | "normal" ≥ 0.80 | `app/pipeline.py` |
| Rule agrees / detector disagrees | × 1.15 / × 0.5 | `events.corroborate_boost`, `contradict_factor` |
| Open on one look | ≥ 0.70 critical (rule-backed or fire), ≥ 0.85 other | `events.open_single_critical`, `open_single_other` |
| Open over looks | average of the last 3 ≥ 0.55 (0.50 unbacked) | `events.open_window`, `open_window_ungated` |
| Close | 2 looks and 8 s below 0.40 | `events.close_c`, `close_after_s`, `close_after_obs` |
| False-alarm hold | 60 s | `events.dismiss_hold_s` |

## 9. What we measured (`REPORT.md`)

- **Speed**: fights alert **1.4–5.2 s** after they start (median **2.7 s**) on a cool laptop; our target was 3 s for 95 % and we miss it at the tail. Categories no rule can see: **7–10 s**. The model names the category about 1.2–1.4 s after the newest frame.
- **Accuracy**: it caught 5 of 7 fights on our tuning clips and both fires, the crowd panic and the theft on the test clips; it is weakest on falls (the detector loses people lying down) and vandalism (the model calls it suspicious activity). On the test clips 4 of 15 were right overall, and we read those clips' errors while tuning, so it is a check, not a clean held-out score.
- **Everything runs on one laptop**: no cloud AI, open-weight models; only the phone alert leaves the machine.

## 10. Pitch lines

- **"Cheap eyes, smart brain."** A tiny detector watches every frame; the vision-language model looks only when a rule or the clock says so. That's how one laptop watches several cameras.
- **"We alert at the first word."** We stream the model's answer and raise the alert the moment it names the category, before it finishes the sentence.
- **"Confidence is measured, not made up."** It comes from the model's own token probabilities, then checked against the detector.
- **"Two filters against false alarms."** Rules wake the model; the model decides, and it is told what the look-alikes are.
- **"Honest numbers."** Every number we quote is the time a person with a stopwatch would measure, from the incident starting to the alert on screen.

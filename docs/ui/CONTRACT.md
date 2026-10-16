# UI behaviour contract (Next.js overhaul)

Status: written in the Research phase of the UI overhaul on branch `ui-next` (2026-10-16). Source of truth for "functionality must not change": the old React/Vite UI (`git show main:web/src/App.jsx`, `ui.jsx`, `icons.jsx`, `index.css`), `app/server.py` and SPEC.md §9 (v1.21). The backend is frozen: nothing here asks for a change under `app/`, `bench/`, `scripts/*.py`, `config.yaml` or `data/`.

How to read it:
- §1 and §2 are the wire contract (what the server sends and accepts). The new UI must not call anything else.
- §3 is every behaviour of the old UI, numbered `B-n`. Each one survives unless §4 says the brief replaces it.
- Text in `code quotes` is verbatim copy. Keep it character for character (the honesty captions and tooltips matter to the captain). Layout, colour, type and motion are free; words and numbers are not.
- §5 is the checklist: one line per B-id saying how to check it in the new UI.

Formatting helpers used throughout (old `ui.jsx`, keep their exact output):

| Helper | Output |
|---|---|
| `ist(ts)` | `new Date(ts*1000).toLocaleTimeString("en-GB", {timeZone: "Asia/Kolkata", hour12: false})` → `14:03:27`; falsy ts → `—` |
| `media(p)` | `"/" + p.replace(/^data\//, "media/")` (`data/keyframes/12_0.jpg` → `/media/keyframes/12_0.jpg`) |
| `v(x, unit="")` | `x == null` → `—`, else `${x}${unit}` (no rounding) |
| `ms(x)` | `x == null` → `—`, else `${Math.round(x).toLocaleString("en-US")} ms` (`2,526 ms`) |
| `pc(c)` | `c == null` → `—`, else `${Math.round(c*100)}%` |
| `name(c)` | underscores → spaces (`person_down` → `person down`) |
| `title(c)` | `name(c)` with the first letter capitalised; falsy → `""` |
| `getJSON(u)` | `fetch(u)`; non-2xx rejects |
| `post(u, body)` | `fetch(u, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)})`; never rejects on HTTP status |

---

## 1. HTTP endpoints the UI uses

All same-origin, relative URLs (the UI is served by the same FastAPI app at `/`). JSON unless noted. FastAPI errors are `{"detail": "<string>"}`; a 422 (request validation, e.g. `?name=` missing or `?slot=abc`) has `detail` as an array of objects, so the UI must stringify a non-string `detail` before showing it.

| # | Method, path | Request | Response (2xx) | Errors the UI can hit (status: `detail`) |
|---|---|---|---|---|
| E-1 | `GET /api/cameras` | — | `[Camera]` (below) | — |
| E-2 | `POST /api/mode` | `{mode: "clips" \| "live"}` | `{mode, switch_ms}` | 400 `mode must be clips or live` |
| E-3 | `GET /api/clips` | — | `[{path, name, folder, label, onset_s}]` | — |
| E-4 | `POST /api/clips/play` | `{path, slot?}`; `path` from E-3, `slot` int 1-3 | `{id, name, status, slot}` (slot = given or 1) | 400 `not a playlist clip` · 400 `slot must be 1-3` · 409 `switch to clips mode first` |
| E-5 | `POST /api/cameras/upload?name=<file name>&slot=<1-3>` | raw file bytes as the body (no multipart), `name` URL-encoded | `{id, name, status, slot}` | 409 `switch to clips mode first` · 400 `slot must be 1-3` · 400 `file must be .mp4, .mov, .avi or .mkv` · 413 `file is over 500 MB` · 400 `empty file` · 422 (array detail) |
| E-6 | `GET /api/devices` | — | `[{source: int \| string, name}]`; an iPhone is named exactly `iPhone (live)`; string sources are the stream URLs preset in `config.yaml` | — (rejects only if the server is gone) |
| E-7 | `POST /api/cameras` | `{source, name, slot?}`; `source` = device index int ≥ 0 or an http/https/rtsp URL string; `name` may be `null` | `{id, name, status, slot}` (`slot` may be `null` only when no slot was sent and all 3 are full) | 400 `source must be a device index or an http, https or rtsp URL` · 400 `slot must be 1-3` · 409 `switch to live mode first` · 409 `already running` (same source running in another slot, or anywhere when no slot is sent) |
| E-8 | `DELETE /api/cameras/{id}` | — | `{id, removed: true}`; also emits SSE `camera_status {camera_id, status: "down"}` | 404 `Not Found` |
| E-9 | `GET /snapshot/{id}` | `cache: "no-store"` | `image/jpeg` bytes, `Cache-Control: no-store` | 404 until the first frame / after removal |
| E-10 | `GET /api/events?limit=50` | also accepts `camera, category, status, from, to, q` (unused by the UI) | `[Event]`, `ORDER BY start_ts DESC`, limit capped at 500 | — |
| E-11 | `GET /api/events/{id}` | — | `Event + {observations: [Observation] ORDER BY ts}` | 404 |
| E-12 | `POST /api/events/{id}/ack` | — | `Event + observations`; sets `status: "acknowledged"`; also emits SSE `event_update` | 404 |
| E-13 | `POST /api/events/{id}/dismiss` | — | `Event + observations` with `status: "dismissed"`, `dismiss_reason: "operator"`; also emits SSE `event_update` | 404 |
| E-14 | `POST /api/chat` | `{session_id, question}` (question 1-500 chars after trim) | `{answer, events: [Event + camera_name], filters, as_of, latency_ms, how}` | 400 `question: 1-500 characters` |
| E-15 | `GET /api/digest?hours=<1\|8\|24>` | `camera=` exists, unused | `{from, to, camera, headline, narrative, incidents: [{id, line, status, severity, seeded}], follow_up: [id], activity: [{camera, notes: [string], peak_people}], events: [Event + camera_name], how, as_of, latency_ms}` | 400 `hours: more than 0, at most 24` |
| E-16 | `GET /api/report` | — | `{accuracy, latency, operator}` (below) | — |
| E-17 | `GET /api/report/feedback.csv` | plain link (download) | `text/csv`, `Content-Disposition: attachment; filename=operator_false_alarms.csv` | — |
| E-18 | `POST /api/ui/latency` | `{event_id, ms}` | `{accepted: true}`, or `{accepted: false, reason: "not the server machine"}` from a non-local browser | 400 if `ms` not a number in [0, 60000) |
| E-19 | `GET /sse` | `EventSource` | §2 | — |
| E-20 | `GET /media/keyframes/*`, `/media/thumbs/*`, `/media/mosaics/{id}.jpg?t=` | `<img src>` | JPEG | 404 |

Not used by the UI (do not start using them): `GET /api/metrics` (SSE `metrics` carries the same payload), `GET /api/observations`.

**Camera row (E-1)**: `{id: "camN", name, source_type: "file" | "webcam" | "stream", source: string | int, status: "connecting" | "live" | "reconnecting" | "down" | "ended" | "stopped", fps, has_door_zone, loop, t_first: epoch s | null, label: string | null, onset_s: number | null, slot: 1 | 2 | 3 | null}`. `label`/`onset_s` only for files listed in `bench/labels.csv`. An `ended` clip stays in the list (its Verdict stays readable) until replaced, stopped, or a mode switch. Camera ids are never reused.

**Event (E-10, SSE)**: `{id, camera_id, category, subtype, severity: "critical" | "high" | "medium", start_ts, end_ts, peak_confidence, summary: string | null, keyframe_paths: [string], track_ids: [int], status: "open" | "closed" | "acknowledged" | "dismissed", dismiss_reason: null | "relook" | "operator", n_obs, time_to_alert_ms, latency_ms, seeded: 0 | 1}`. DB rows (E-10..E-13 and the `event_update` they emit) have no `camera_name`; `event_open`/`event_close` from the pipeline and chat/digest events do. `seeded` is an int, test it for truthiness.

**Observation (E-11)**: SPEC §7.1; the UI reads only `probs` (`{category: c}`, may be null).

**Chat `how` (E-14)**: `{mode: "template" | "model", read_by: "rules" | "model", read_ms?, rows?, sentences?, dropped?, first_token_ms?, fallback?: "template", note?}`. **Digest `how` (E-15)**: `{mode, digest: true, rows?, sentences?, dropped?}`.

**Report (E-16)**: `accuracy` = `null` or `{tag, run_at (epoch s), n, right, macro_f1, incident_recall, incident_precision (may be null), false_alarms_normal, onset_to_alert_p50_p95: [p50, p95], onset_to_alert_n, onset_to_alert_mid_start_p50_p95, onset_to_alert_mid_start_n, trigger_to_alert_p50_p95, gpu_duty_mean?, errors: {"<label> -> <pred>": ["<clip> (<keyframe>)"]}, clips: [{clip, label, pred, confidence, onset_to_alert_ms, trigger_to_alert_ms, summary}]}` (clip fields are CSV strings; `onset_to_alert_ms` may be `""`); `latency` = §9.1 `latency` + `trigger_to_alert_p95_ms`; `operator` = `{events, false_alarms, camera_hours (float), false_alarms_per_camera_hour: number | null, by_category}`.

---

## 2. SSE (`GET /sse`)

One `EventSource("/sse")` per page load, opened once and kept for the life of the page (tab navigation must not close or reopen it). The server sends one `metrics` immediately on connect, then every 1 s. Payloads are JSON in `event.data`.

| Event | Payload | What the old UI does (keep) |
|---|---|---|
| `metrics` | §9.1: `{mode, cameras: {camN: {capture_fps, det_fps, yolo_ms_p50, keep_up, status, people, now: {text, ts, source: "model" \| "detector"} \| null}}, vlm: {model, p50_ms, p95_ms, alert_p95_ms, queue_depth, calls_total, gate_yield_pct, cache_hit_tokens, preemptions, errors, gpu_duty_pct, baselines_skipped, vetoes}, latency: {onset_to_alert_ms: {last, p50, p95, n}, store_to_card_ms: {last, p50, p95, n}}, system: {mem_used_pct, uptime_s}}` | Compute `k = Object.entries(x.cameras).map(([id, c]) => id + c.status).join()`; if `k` differs from the last `k` (a local variable, starts `""`), reload cameras (E-1). Then store the whole payload as `m` (replace, not merge). |
| `alert` | `{event_id, camera_id, category, severity, confidence, rating: "High" \| "Medium" \| "Low", top3: [[category, c] ×3], trigger_to_alert_ms, t_stored (epoch s, float), onset_to_alert_ms: number \| null}` | 1. Inside `flushSync`: merge into the store under `event_id`: `{id: event_id, alert: <the whole message>, camera_id, category, severity, peak_confidence: confidence, time_to_alert_ms: trigger_to_alert_ms, status: "open"}`. 2. `requestAnimationFrame(() => setTimeout(() => POST /api/ui/latency {event_id, ms: performance.timeOrigin + performance.now() - t_stored * 1000}, 0))` (fire and forget). 3. If `severity === "critical"` and sound is armed: beep (B-60). |
| `event_open` | Event (+ `camera_name`), sent right after `alert` | Shallow-merge into the store by `id`. |
| `event_update` | Event (pipeline: + `camera_name`; after ack/dismiss: DB row, no `camera_name`) | Shallow-merge by `id`. |
| `event_close` | Event (+ `camera_name`) | Shallow-merge by `id`. |
| `trace` | `{camera_id, trigger, ts, stages: [{name, ms}], model_tta_ms, mosaic_url, hints, raw_json}`; stage names in order: `capture → gate`, `queue`, `prefill → 1st token`, `1st token → category`, `category → done`, `store (SQLite)` (a stage with no timing is omitted) | `traces[camera_id] = msg` (newest per camera, replace). |
| `camera_status` | `{camera_id, status}` | Reload cameras (E-1). |
| `observation` | Observation | Ignored (the "Now" line comes from `metrics`). Keep ignoring it. |
| `onopen` / `onerror` | — | `conn = true` / `conn = false`. `EventSource` reconnects by itself; nothing is refetched on reconnect (old behaviour). |

The `alert` message keeps its `alert` key on the event forever (later merges never carry `alert`), and that key is how the UI tells a live alert from history (B-25, B-29, B-31).

---

## 3. Behaviours of the old UI

### 3.1 App state and store

- **B-1 Boot.** On mount: load cameras (E-1), load events (E-10, `limit=50`), open SSE (§2). Event load state is `loading` → `ok` | `error`.
- **B-2 Camera list.** `cams` = the last successful E-1 result; a failed reload keeps the previous list (errors swallowed). Reload triggers: boot, `metrics` camKeys change, `camera_status`, after every play/upload/add/stop/mode switch.
- **B-3 Boot merge.** When E-10 resolves: `events = fromEntries([...rows.map(e => [e.id, e]), ...entries(events)])`: an entry already in the store (from SSE that arrived first) wins whole over the fetched row.
- **B-4 Merge rule.** Every update is `events[id] = {...events[id], ...patch}` (shallow). Sources: `alert` (B-row in §2), `event_open|update|close`, and the JSON returned by ack/dismiss with `observations` stripped.
- **B-5 Feed.** `feed = all events with status !== "dismissed", sorted by id descending, first 50`. Every alert list uses this feed.
- **B-6 Open count.** `nOpen = feed.filter(status === "open").length`; shown next to the Alerts tab label when > 0 (nothing when 0).
- **B-7 camName fallback.** `e.camera_name ?? cams.find(c => c.id === e.camera_id)?.name ?? name(e.camera_id)`.
- **B-8 Camera events.** `camEvents(id)` = all store events (including dismissed) of that camera, sorted by id ascending.
- **B-9 Mode.** `mode = m?.mode` (from `metrics`). Before the first `metrics`, `mode == null`: the feed area shows two 16:9 skeletons.
- **B-10 Switch mode.** `switchMode(k)`: no-op if `k === mode`; else `POST /api/mode {mode: k}`, then set `m.mode = k` locally at once, then reload cameras. No error handling. Server effect: every source in either mode stops; history stays. (Trigger rule changes, §4.2.)

### 3.2 Top bar (navbar in the new UI)

- **B-11 Brand.** Hexagon logo (`Hive` icon: two nested hexagons) + `HackHive`, and `Incident console` on wide screens only.
- **B-12 Model.** `m.vlm.model` or `—`; tooltip `Vision-language model, running in Ollama on this machine`.
- **B-13 GPU.** `GPU ` + `${Math.round(gpu_duty_pct)}%` or `—`; tooltip `Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras.`
- **B-14 Onset → alert.** `onset→alert p50 ` + (`latency.onset_to_alert_ms.n` ? `ms(p50)` : `—`); tooltip `Labelled incident onset in the clip → alert (§12), p50. Only for labelled clips played once.`
- **B-15 Connection badge.** Green dot + `Local · offline` with tooltip `Connected to the local server; no network needed`, or red dot + `Reconnecting` with tooltip `Lost the local server; retrying`.
- **B-16 Clock.** `${ist(now)} IST`, ticking every 1 s.
- **B-17 Sound control.** Unarmed: a primary (filled accent) button, bell-off icon + `Arm sound`. Armed: a quiet icon-only bell button, `aria-label` and tooltip `Alert sound on, click to test`; clicking it again plays the test beep. See B-60.

### 3.3 Feed area header

- **B-18** Label `Live sources` in live mode, `Now playing` in clips mode, followed by the camera count.
- **B-19 Overload warning.** Live mode and more than 2 cameras: amber warning icon + `3+ live cameras: alerts may slow`, tooltip `P2b: 3 busy sources pushed GPU duty above 90 %`. (D82 extends this to Clips, §4.3.)

### 3.4 Camera tile

- **B-20 Status.** `status = metrics.cameras[id].status ?? camera.status`.
- **B-21 Status label.** `status === "live" && source_type === "file"` → green dot `Playing`; else the STATE map: `live` green `Live` · `connecting` amber `Connecting` · `reconnecting` amber `Reconnecting` · `down` red `Down` · `ended` grey `Finished` · `stopped` grey `Stopped` · anything else amber + the raw status.
- **B-22 Overlays.** `connecting`: black 16:9 box with a skeleton and `Connecting…` centred; the live image is NOT mounted (no snapshot fetch). `down`: dimmed frame with `Source down` / `Stop it, then add it again.`
- **B-23 Badges.** Top right: `CLIP` (file) or `LIVE` (anything else), and a stop button (■) with tooltip `Stop and release this source`, `aria-label` `Stop <name>`. Bottom left: status dot, camera name, status label.
- **B-24 Stop.** One click: `DELETE /api/cameras/{id}` (E-8), then reload cameras. No confirm, no error message.
- **B-25 Hot event.** `hot` = the newest (highest id) event of this camera with `status === "open"` and severity `critical` or `high`. When present: a chip top left `<Title category> · <pc(alert?.confidence ?? peak_confidence)>` (critical: solid red, white text; high: amber, dark text) and an inset 2 px ring round the whole tile in the same colour. Closing, acking or dismissing the event removes both.
- **B-26 Now line.** `Now ` + `metrics.cameras[id].now.text` or `—` (full text as tooltip; one line, truncated).
- **B-27 Meta line.** `` `${id} · ${v(people)} ppl · YOLO ${ms(yolo_ms_p50)} · keep-up ${pc(keep_up)} · as of ${ist(now?.ts)} ${now?.source ?? ""}` `` (mono, small).
- **B-28 Live image (D72 double buffer).** Mounted when `status !== "connecting"`, keyed by camera id. Loop:
  1. `t0 = performance.now()`; `fetch("/snapshot/{id}", {cache: "no-store"})`; read the whole body as bytes `b` (length `n`).
  2. Accept only if `r.ok && n > 4 && b[0] === 0xFF && b[1] === 0xD8 && b[n-2] === 0xFF && b[n-1] === 0xD9` (JPEG SOI and EOI).
  3. `url = URL.createObjectURL(new Blob([b], {type: "image/jpeg"}))`; decode off-screen (`new Image(); im.src = url; await im.decode()`).
  4. If still mounted: set the visible `<img>`'s `src = url`, revoke the previously shown URL, remember `url` as shown.
  5. Any failure (404, truncated, decode error, network) is swallowed: the last good frame stays; a URL that was created but not shown is revoked.
  6. If still mounted: schedule the next tick after `max(0, 100 - (performance.now() - t0))` ms (≈ 10 fps, never two fetches in flight).
  7. On unmount: stop the loop, revoke the shown URL.
  The image is 16:9, `object-contain` on black (letterboxed, never stretched or cropped). Never use the MJPEG stream or set `src` straight to `/snapshot/...`.

### 3.5 Verdict (Clips mode, one per clip)

- **B-29 Placement and status.** One Verdict per clip camera; `status = metrics.cameras[id].status ?? camera.status`; `evs = camEvents(id)` minus dismissed (id ascending). `done = status === "ended"`.
- **B-30 Empty.** No clip: a placeholder feed with play icon, `No clip playing` / `Play a clip from the library below, or upload a video.`, and an empty Verdict `No verdict yet` / `Play a labelled clip to see expected against detected, and the onset → alert time.` (Copy of the first one changes with the dropdown, §4.3.)
- **B-31 Helpers.** `at(e)`: `ts = e.alert?.t_stored ?? e.start_ts`; `ts && c.t_first` ? `${(ts - c.t_first).toFixed(1)} s` : `—`. `hit` = first event in `evs` whose `category === c.label`. `o2a = hit?.alert?.onset_to_alert_ms`.
- **B-32 State word (chip in the header next to `Verdict`).** In order: not done → amber `Running`; no label → grey `Unlabelled`; label `normal` → (any event ? red `False alarm` : green `Correct`); `hit` → green `Detected`; any event → amber `Wrong category`; else red `Missed`.
- **B-33 Big number.** Label `Onset → alert`, value `ms(o2a)` if `o2a != null` else `—`. (D50: this is the one large number.)
- **B-34 Hint (under the big number), first match wins:**
  1. `o2a != null` → `` `Alert at ${at(hit)} in the clip, onset at ${c.onset_s} s` ``
  2. `hit` → `` `Alert at ${at(hit)} in the clip` `` + (`c.onset_s == null` ? `; no labelled onset` : ``)
  3. no label → `Unlabelled clip: no onset to time from`
  4. label `normal` → `Normal clip: no incident to time`
  5. done → `No matching alert`
  6. else → `Waiting for the alert`
- **B-35 Expected.** `Expected`: `title(label)` or `No label`; below `` `onset ${onset_s} s` `` or `no onset`.
- **B-36 Detected.** `Detected`: the last 3 of `evs`, each: severity dot + `title(category)` + `` `${pc(alert?.confidence ?? peak_confidence)} · ${at(e)}` ``. None: `No incidents` when done, else `Nothing yet`.
- **B-37 Summary.** `top = hit ?? last of evs`; its `summary` (2 lines max) or a 2-line skeleton while null; nothing if no `top`.
- **B-38 Footer.** `` `${c.name} · played once` ``.

### 3.6 Clip library and upload

- **B-39 Load.** `GET /api/clips` once; states: loading (4 skeleton rows) · error `Could not load clips` / `Check the server is running, then reload the page.` · empty `No clips found` / `Copy videos into data/demo/ or data/dev/<category>/, or upload one (mp4, mov, avi, mkv, up to 500 MB).` · list. Count shown beside the label `Clip library`.
- **B-40 Clip fields.** Each clip shows: `name` (mono), label `title(label)` or `Unlabelled`, onset `` `${onset_s} s` `` or `—`, `folder`. The playing clip is marked (`aria-current`).
- **B-41 Play.** Choosing a clip: `POST /api/clips/play`; on non-2xx the message becomes `` `Rejected: ${detail}` `` (red), on success it clears; then reload cameras either way. Choosing the clip that is already playing restarts it (a new play replaces the old one, a DEMO_SCRIPT fallback).
- **B-42 Upload.** Via a file input (`accept=".mp4,.mov,.avi,.mkv"`, label `Upload video`, upload icon) or drag-and-drop of a file onto the library. Message `` `Uploading ${f.name}…` `` while sending; then `` `${j.id} added: ${j.name}` `` or `` `Rejected: ${j.detail}` `` (red when it starts with `Rejected`); then reload cameras. Body = the raw `File` (E-5).
- **B-43 Default caption.** With no message: `One at a time, played once. Drop a video here to upload.` (Replaced, §4.3.)

### 3.7 Add source (Live mode)

- **B-44 Devices.** `GET /api/devices` on mount, on the `Rescan` button, and on every window `focus` event (the usual flow is unlock the phone, come back to the Mac). States: loading (skeleton buttons) · error (red) `Could not list cameras. Rescan, or reload the page.` · empty `No cameras found. Check camera permission, or add a stream URL.` · one button per device (plus icon + `name`).
- **B-45 Running devices disabled.** A device whose `source` equals a running camera's `source` is disabled.
- **B-46 iPhone hint.** When the list loaded and no device is named exactly `iPhone (live)`: `No iPhone listed: it must be on this Mac's Apple Account with Bluetooth and Wi‑Fi on, unlocked nearby or on a USB cable, and not in use by another Mac. Then Rescan.` (the hyphen in Wi‑Fi is U+2011).
- **B-47 Stream URL.** Label `Stream URL`, mono input, placeholder `rtsp://… or http://192.168.43.20:8080/video`, button `Add URL`, caption `http, https or rtsp`. Submit (Enter or button) with a non-blank trimmed value → add with `name: null`.
- **B-48 Add.** `POST /api/cameras {source, name}`; message `` `Rejected: ${detail}` `` (red) on non-2xx, cleared on success; reload cameras either way. The URL input is not cleared.

### 3.8 Top-3 probabilities

- **B-49 useTop3(e).** If `e.alert` exists: use `e.alert.top3`. Otherwise fetch `GET /api/events/{id}` (again whenever `e.id` or `e.n_obs` changes): take the observations that have `probs`, pick the one with the highest `probs[e.category]`, show its 3 highest entries sorted descending. No such observation, or the fetch fails → `false` (render nothing). While pending → `null` (render a thin skeleton bar).
- **B-50 Top3 display.** A thin segmented bar, each segment `c × 100 %` wide, neutral greys (first darkest), not severity colours; below, 3 columns `` `${pc(c)} ${name(k)}` `` (first one emphasised).

### 3.9 Alerts list and alert card

- **B-51 List states.** Loading: 3 skeleton cards. Error: `Could not load alerts` / `Check the server is running, then reload the page.` Empty: check icon, `No alerts` / `Incidents appear here the moment the model confirms one.` List: `aria-live="polite"`, `aria-label="Alerts"`, newest first (B-5).
- **B-52 Card visuals.** Left stripe in severity colour (critical red, high amber, medium grey, unknown grey). Background tinted red when `status === "open" && severity === "critical"`. Enter animation only for live alerts (`e.alert` set).
- **B-53 Thumbnail.** `keyframe_paths[0]` via `media()`; none and `seeded` → no thumbnail at all (seeded history is text only); none otherwise → a skeleton (it arrives with the next update).
- **B-54 Title row.** `title(category)` (clicking anywhere on the card opens it), severity chip (critical: solid red + white `CRITICAL`; high: amber + dark `HIGH`; medium: no chip), a `History` chip for seeded rows with tooltip `Seeded demo history (E-19)`, time `ist(start_ts ?? alert?.t_stored)` (no ` IST` suffix on the card).
- **B-55 Second row.** camName (B-7), then mono `pc(alert?.confidence ?? peak_confidence)` + (`alert.rating` ? ` ${rating}` : ``) + (`alert && peak_confidence > alert.confidence` ? ` (peak ${pc(peak_confidence)})` : ``).
- **B-56 Summary.** 2 lines max, or a 2-line skeleton while `summary` is null.
- **B-57 Top 3.** B-49/B-50 unless `false`.
- **B-58 Footer.** `` `trigger → alert ${ms(time_to_alert_ms)}` `` if `time_to_alert_ms != null`; `` `onset → alert ${ms(alert.onset_to_alert_ms)}` `` if not null; then the actions (changed to exactly two, §4.5). Old: `False alarm` (ghost, tooltip `Not an incident: hide it, count it in Report, keep it as a labelled example (FR-25)`) shown for every non-seeded card; `Ack` shown only when `status === "open"`, otherwise the status word (`Open` / `Closed` / `Acknowledged` / `Dismissed`, raw value if unknown). The buttons act without opening the card.
- **B-59 Ack / dismiss.** `ack(id)`: `POST /api/events/{id}/ack`; on 2xx strip `observations` and merge. `dismiss(id)`: `POST /api/events/{id}/dismiss`; on 2xx strip `observations`, merge, and close the open report if it is this event. Failures are silent. A dismissed event disappears from every list (B-5), from the hot rule (B-25) and from the Verdict (B-29). Seeded rows can never be dismissed from the UI.

### 3.10 Sound

- **B-60 Arming and beep.** `Arm sound` (a user gesture) creates one `AudioContext` (once per page), calls `resume()`, marks armed and plays a test beep. Beep: an oscillator at 880 Hz, gain 0.25, 0.5 s, straight to the destination. Played for every `alert` with `severity === "critical"` while armed; never for high/medium; never before arming. Arming is lost on reload (the team re-arms; the brief's tab switches must not reload).

### 3.11 Critical banner (replaced by notifications, §4.4)

- **B-61 Which.** `critical = feed.filter(severity === "critical" && (e.alert || status === "open") && status !== "acknowledged")`: every live critical alert stays until acknowledged, even after the event closes; a dismissed one leaves (feed excludes it); history criticals show only while open.
- **B-62 Look and actions.** Solid red, white text, `role="alert"`, warning icon. Shows `critical[0]` (newest): `` `Critical · ${title(category)}` `` and `` `${ist(start_ts ?? alert?.t_stored)} IST · ${pc(alert?.confidence ?? peak_confidence)} · ${camName}` ``. Clicking the text opens the event. `False alarm` (not for seeded) and `Ack`. More than one: `` `${n - 1} more unacknowledged` ``.

### 3.12 Event detail (dialog → Alerts report, §4.6)

- **B-63 Data.** The opened object merged with the store entry (`{...opened, ...events[id]}`), so an event opened from chat that is not in the store still shows (from the chat payload), and a store entry stays live (summary, status, keyframe update in place).
- **B-64 Header.** severity dot, `title(category)`, severity chip, `#<id>` (mono), `History` chip if seeded, close button (×, `aria-label="Close"`) focused on open.
- **B-65 Image.** `keyframe_paths[0]`, 16:9 contain on black, alt `` `Key frame of event ${id}` ``; none and not seeded → `No key frame yet`; none and seeded → no image block.
- **B-66 Body.** summary (or skeleton), Top 3 (B-49), then six facts: `Camera` camName · `Time` `` `${ist(start_ts ?? alert?.t_stored)} IST` `` · `Confidence` `pc(alert?.confidence ?? peak_confidence)` + ` ${rating}` if any · `Trigger → alert` `ms(time_to_alert_ms)` · `Onset → alert` `ms(alert?.onset_to_alert_ms)` · `Status` status word.
- **B-67 Actions.** `Mark false alarm` when not seeded and not dismissed; `Ack` (primary) when open (two buttons, §4.5).
- **B-68 Hook.** The detail container carries `data-event-card="<id>"` (keep the attribute).

### 3.13 Ask (chat)

- **B-69 Session.** `SESSION = Math.random().toString(36).slice(2)` once per page load; every question sends it (follow-ups use the last 3 turns server-side). Tab switches must not change it or clear the log.
- **B-70 Empty state.** `Ask about incidents` / `Answers come only from stored events. Every #id opens that event.`, label `Try`, four one-click suggestions, verbatim: `Show all tailgating events from camera 2 today` · `What incidents happened in the last 10 minutes?` · `Summarise the incidents in the lobby today` · `How many fights were there?` Clicking one asks it at once.
- **B-71 Ask.** Trim; blank or a question already in flight → no-op. While in flight: the question bubble + a 3-line skeleton. `POST /api/chat {session_id, question}`. 2xx → append `{question, ...response}`; non-2xx → append `{question, answer: "error <status>", events: [], error: true}`; either way clear the input. Network failure → append `{question, answer: "Could not reach the server", events: [], error: true}` (input kept). The log keeps the last 20 entries. Auto-scroll to the newest on every change.
- **B-72 Input.** `aria-label` and placeholder `Ask about incidents`, a `/` key hint, button `Ask` (send icon), disabled while busy or blank. Enter submits.
- **B-73 Answer text.** `answer` split on `/(\[#\d+\])/`; a `[#id]` whose id is in `events` becomes a chip `#<id>` (tooltip `Open event <id>`) that opens that event; other text (and unknown ids) stays plain; newlines kept (`white-space: pre-wrap`). Error answers in red, followed by `Reload the page (⌘R) and ask again.`
- **B-74 Key-frame strip.** If any cited event has `keyframe_paths[0]`: a horizontal strip, one per such event: thumbnail, `` `#${id} · ${ist(start_ts)}` ``, `` `${title(category)} · ${camera_name}` ``, tooltip = summary; click opens the event. Hook `data-frames`.
- **B-75 How line.** Not on error answers: `` `${how(a.how)} · as of ${ist(a.as_of)} IST · ${a.latency_ms} ms` ``, hook `data-how`. `how(h)`: empty if no `h`; prefix `shift-handover digest · ` if `h.digest`, else `` `question read by the model (${h.read_ms} ms) · ` `` if `h.read_by === "model"`, else `question read by rules · `; then `template answer` if `h.mode === "template"`, else `` `model answer, ${h.rows} rows, ${h.dropped} sentence${h.dropped === 1 ? "" : "s"} dropped` `` + (`h.fallback` ? ` → template` : ``). Each answer block carries `data-answer="<n>"` (1-based).
- **B-76 Shift handover.** Button `Shift handover` (clock icon), tooltip `Shift-handover report: incidents first, what needs follow-up, then notable activity`, disabled while busy; a segmented control `Handover window` with `1 h` · `8 h` · `24 h` (default 8). Click → question `` `Shift handover · last ${hours} h · all cameras` ``, `GET /api/digest?hours=<hours>`, answer = these parts joined by a blank line: `headline`; `narrative`; if incidents: `Incidents, most severe first:` + newline + the first 15 `line`s joined by newlines + (more than 15 ? `` `\n… and ${n - 15} more` `` : ``); if activity: `Notable normal activity:` + newline + one line per camera `` `${camera}: ${notes.join(" · ")}` ``. Entry carries `events`, `how`, `as_of`, `latency_ms` (so citations, frames and the how line work). Failure → `Could not build the handover report` (error).

### 3.14 Pipeline

- **B-77 Camera choice.** A segmented control `Camera` with each camera id, shown only with more than one camera. Default (until the user picks): the camera with the newest trace `ts`, else the first camera. A picked id that disappears falls back to the default.
- **B-78 Empty.** No cameras: `No sources running` / `Play a clip or add a camera. Every model call is traced here, stage by stage.` System (B-84) shows either way.
- **B-79 Header.** camera name; `` `${id} · ${t ? ist(t.ts) : "—"}` ``; the trigger as a mono chip (e.g. `gate:fighting`). Right: label `Frame → category`, value `ms(t.model_tta_ms)`, under it `onset → alert p50 ` + (`n` ? `ms(p50)` : `—`) with tooltip `Never quote the model time alone (D50)`.
- **B-80 Five nodes.** `n(x)` = `—` or `Math.round(x).toLocaleString("en-US")`. Stage map `st[name] = ms`. `vlm = (st["prefill → 1st token"] ?? 0) + (st["1st token → category"] ?? 0)` if either exists, else null. Nodes (label · value · sub-label · tooltip), with an arrow between each:
  - `Frame` · `n(capture_fps)` · `fps` · `Capture rate`
  - `YOLO` · `n(yolo_ms_p50)` · `ms p50` · `YOLO + ByteTrack per frame, p50`
  - `Gate` · `n(st["capture → gate"])` · `ms` · `Frame captured → gate fired, this call (includes detection)`
  - `VLM` · `n(vlm)` · `ms` · `Prefill + first token → category known, this call`
  - `Event` · `n(st["store (SQLite)"])` · `ms` · `Event row stored in SQLite, this call`
- **B-81 Trace bars.** Label `Trace`, right `` `${ms(total)} total` `` (total = sum of stage ms). One row per stage: name, a bar offset by the cumulative ms before it and `max(ms/total, 0.75 %)` wide (a waterfall), the `1st token → category` bar emphasised, `ms(stage)` at the right; axis `0` … `ms(total)`. No trace: `Waiting for the first model call` / `The gate wakes the model on motion; baselines run when the scene changes.`
- **B-82 Model input.** Only with a trace: label `Model input`, caption `mosaic · letterboxed`, the image `mosaic_url` (alt `Mosaic of recent frames sent to the VLM`, never stretched), `Hints` with `hints` or `None`, `Raw VLM output` with `raw_json` pretty-printed (`JSON.stringify(JSON.parse(s), null, 2)`, raw string if it does not parse), scrollable, max ~12 lines tall.
- **B-83 Live.** The view follows SSE: a new `trace` or `metrics` re-renders without user action.
- **B-84 System grid.** Label `System`; rows (label · value · tooltip · red when):
  - `GPU duty (60 s)` · `v(gpu_duty_pct, "%")` · `Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras.`
  - `Onset → alert` · (`n` ? `` `${ms(last)} · p50 ${p50}` `` : `—`) · `Labelled incident onset in the clip → alert (§12). Only for labelled clips played once (uploads, bench/labels.csv); live onset is measured from 240 fps phone video.`
  - `Model time-to-alert p95` · `ms(alert_p95_ms)` · `Newest frame captured → category known, p95 over all calls. Never quoted alone (D50).`
  - `VLM call p50 / p95` · `` `${v(p50_ms)} / ${v(p95_ms)} ms` `` · —
  - `Store → card p95` · (`n` ? `` `${ms(p95)} · n ${n}` `` : `—`) · `Event row stored → card painted in this browser; budget ≤ 100 ms. Valid only when the browser runs on the server machine (it compares the two clocks); readings from other devices are ignored.` · red when p95 > 100
  - `Queue` · `v(queue_depth)` · — · `Calls` · `v(calls_total)` · — · `Preempted` · `v(preemptions)` · —
  - `Baselines skipped` · `v(baselines_skipped)` · `Baseline calls skipped because the scene had not changed (D42).`
  - `Vetoes` · `v(vetoes)` · `Detector cross-check vetoes (E-7).`
  - `VLM errors` · `v(errors)` · `The server log prints each [vlm_error] line.` · red when > 0
  - `Memory` · `v(mem_used_pct, "%")` · —

### 3.15 Report

- **B-85 Load and poll.** `GET /api/report` when the Report view mounts and every 10 s while it is visible (no polling when hidden). Loading: skeletons. Any failed load (including a later poll) → `Could not load the report` / `Check the server is running.`
- **B-86 Accuracy header.** `Accuracy · dev set`, right `` `${tag} · ${ist(run_at)} IST` ``. No run: `No dev-set run yet` / `Run: uv run python -m bench.ab --dev --tag NAME`.
- **B-87 Accuracy tiles.** `p(x)` = `—` or `${Math.round(x*100)}%`; `pair(x)` = `—` if `x?.[0] == null` else `` `${ms(x[0])} / ${ms(x[1])}` ``. Tiles: `Clips right` `` `${right} / ${n}` `` · `Incident recall` `p(incident_recall)` · `Incident precision` `p(incident_precision)` · `False alarms, normal clips` `v(false_alarms_normal)` · `Onset → alert p50 / p95` `pair(onset_to_alert_p50_p95)` · `Trigger → alert p50 / p95` `pair(trigger_to_alert_p50_p95)` · `Onset → alert, clip starts mid-incident` `pair(onset_to_alert_mid_start_p50_p95)` · `GPU duty, mean` `p(gpu_duty_mean)`.
- **B-88 Accuracy caption (verbatim, with the two counts filled in):** `Each clip played once, alone, at real-time speed. Onset → alert over ${onset_to_alert_n} clips whose incident starts after the first 2 s; ${onset_to_alert_mid_start_n} clips that start mid-incident also time the buffer filling and are shown apart. Thresholds were tuned on these clips, so this is a training-set result; the held-out test split is reported separately.`
- **B-89 Per-clip table.** Columns `Clip` · `Label` · `Detected` · `Onset→alert`. Row: clip (mono), `name(label)`, dot + `name(pred)` (green dot when `label === pred`, else red dot and red text), `onset_to_alert_ms` truthy ? `ms(+onset_to_alert_ms)` : `—`; row tooltip = clip summary.
- **B-90 Errors.** When `errors` has keys: `Errors by confusion pair`, then per pair: the key in red mono, ` · ` + the clip names (each entry's text before the first space) joined by `, `.
- **B-91 Operator.** `Operator · since server start`; tiles: `Events (real, not seeded)` `v(events)` · `Marked false alarm` `v(false_alarms)` · `Monitored camera-hours` `camera_hours.toFixed(2)` · `False alarms / camera-hour` raw value or `—` · `Onset → alert p50 (live)` (`latency.onset_to_alert_ms.n` ? `ms(p50)` : `—`) · `Store → card p95` (`latency.store_to_card_ms.n` ? `ms(p95)` : `—`).
- **B-92 Operator caption (verbatim):** `Camera-hours run from each source's first to last observation; live rows reset when the server starts, the exported labels don't. A rate needs at least 3 camera-minutes; the target is ≤ 1 per camera-hour.`
- **B-93 Export.** A link `Export operator labels (CSV)` to `/api/report/feedback.csv` (plain `<a href>`, browser download).

### 3.16 Keyboard, focus, accessibility

- **B-94 "/" to Ask.** On `keydown` `/` while the focused element is not `INPUT`, `TEXTAREA` or `SELECT`: `preventDefault`, go to Ask, focus the question input (after the view renders). A visible hint shows the key (old rail: `/` + ` to ask`; the input also shows `/`).
- **B-95 Esc.** Closes the open event detail (§4.6: returns from the report to the list).
- **B-96 A11y.** Tabs are real tabs (`role="tab"`/`aria-selected`, or links with `aria-current="page"`); radio-style segmented controls (`role="radiogroup"`, `role="radio"`, `aria-checked`); visible focus ring on every control; `prefers-reduced-motion: reduce` turns animation and transitions off; text contrast ≥ 4.5:1; tabular numbers for every figure.
- **B-97 Colour meaning.** Red = critical and errors only, amber = high / pending, green = ok; never decoration (brief + D76). Severity colours are fixed, not generated from the seed (§4.8).

### 3.17 Build and serving (runtime contract, not UI behaviour, still must hold)

- **B-98** `web/dist/index.html` exists after `cd web && npm run build` and contains the exact string `<div id="root">` (no other attributes on that div): `run_demo.sh` greps `id="root"` and the server self-check asserts `b'<div id="root">'`.
- **B-99** FastAPI serves `web/dist` with `StaticFiles(html=True)`: a path is served as a file, or as `<dir>/index.html` for a directory. So every route must exist as a directory with `index.html` (Next.js `output: "export"` + `trailingSlash: true`), and `/` must be a real page. Unknown paths get `404.html`.
- **B-100** Offline: no CDN, no `fonts.googleapis.com`, no network request other than same-origin; fonts and icons self-hosted from `node_modules`.
- **B-101** `run_demo.sh` rebuilds only when something under `web/src` (or `web/index.html`) is newer than `web/dist/index.html`. Keep all UI sources under `web/src/` or a rebuild will be missed.

---

## 4. Changed by the new brief

What the captain's brief deliberately replaces, and what replaces it. Everything not listed here stays as in §3.

### 4.1 Right rail → six route tabs

- Old: top bar + camera grid + 400 px right rail with tabs Alerts | Ask | Pipeline | Report (hidden panels, all mounted except Report).
- New: one navbar (logo B-11, six uniform tabs, status cluster B-12…B-17, theme toggle) over a full-width page. Tabs in order: **Clips, Live, Alerts, Ask, Pipeline, Report**, each a route (`/clips/`, `/live/`, `/alerts/`, `/ask/`, `/pipeline/`, `/report/`). `/` shows the tab matching the current backend mode (Clips at boot).
- Must hold across tab switches (client-side navigation, never a full reload): the SSE connection (§2), the event store, `m`, traces, the chat log and SESSION (B-69), sound arming (B-60), the Pipeline camera pick, the theme. Report polls only while its tab is shown (B-85).
- Alerts tab label carries the open count (B-6).

### 4.2 Clips | Live segmented control → Clips and Live tabs

- Old: a centre toggle called `POST /api/mode`, which stops every source.
- New rule: entering the Clips or Live tab whose mode differs from `m.mode`:
  - no camera in `cams` (any status, including `ended`) → switch automatically (B-10);
  - otherwise → a confirm dialog before switching: it names the cost (every running source stops, finished verdicts clear, history is kept), with Cancel (stay on the current tab) and a confirm action. Cancel leaves the backend untouched.
- Alerts, Ask, Pipeline and Report never change the mode.
- While on the Clips or Live tab and `m.mode` is the other mode (changed from another browser tab), show an inline notice with a switch button (same confirm rule), never a silent switch.
- DEMO_SCRIPT Act 3 "click Clips first (stops the live cameras so the model is free)" maps to: click the Clips tab → confirm.

### 4.3 One clip at a time → three slots (Clips and Live)

- Old: Clips played one clip (play without `slot`); tiles and Verdicts in a 2-column grid; the library below.
- New: Clips and Live are each a 3-column frame, column k = slot k. Column k shows the camera whose `slot === k` (from E-1), else an empty state. Each column, top to bottom: a source dropdown with the details needed to choose, the feed tile (§3.4 unchanged, including stop ■, hot ring, Now and meta lines), then everything about that feed below it (Clips: the Verdict, §3.5; Live: nothing extra beyond the tile lines unless the designer adds existing data).
- **Clips dropdown**: the E-3 clips, each option showing name, label (`title(label)` / `Unlabelled`), onset (`n s` / `—`) and folder (B-40), grouped by folder; plus an `Upload video` entry. Choosing a clip → `POST /api/clips/play {path, slot: k}` (B-41 messages per column). Upload or drop a file on column k → `POST /api/cameras/upload?name=…&slot=k` (B-42 messages per column). Always send `slot`: never call play without it (that would stop the other two columns). The dropdown shows the slot's current clip (matched by `source === path`). Loading/error/empty copy of B-39 moves into the dropdown.
- **Live dropdown**: per slot, choose a device or a URL, then it starts: devices from E-6 grouped as iPhone (name `iPhone (live)`), webcams (other integer sources) and preset stream URLs (string sources), plus `Stream URL…` which reveals the B-47 input. Choosing → `POST /api/cameras {source, name: <device name> | null, slot: k}` (B-48). B-44 (Rescan, focus rescan, states), B-45 (a source running in another slot is disabled; the same slot may re-pick it, which restarts it) and B-46 (iPhone hint, verbatim) stay.
- A camera with `slot: null` (only possible from an older client) must still be visible and stoppable (an overflow strip under the columns); nothing may run on the GPU unseen.
- Overload warning (B-19) now shows in both tabs when 3 sources run: Live `3+ live cameras: alerts may slow` (tooltip as B-19). D82 says the UI must also tell the cost in Clips: same wording rule, e.g. `3 clips at once: alerts may slow` with the same tooltip; the Report caption (B-88) stays "played once, alone".
- B-43 caption `One at a time, played once. …` is retired (no longer true); B-38 `played once` stays.
- B-18 header count: per-tab header shows the running count.

### 4.4 Critical banner → notifications

- Old: B-61/B-62, a red banner over the rail, critical only.
- New: notifications pop up while on the Clips and Live tabs (open question: also on Ask/Pipeline/Report).
  - Critical: the B-61 set, unchanged rule; each stays until acknowledged or marked false alarm (also after the event closes); stacked newest first with a `` `${n - 1} more unacknowledged` `` count when collapsed. Solid red, white text, `role="alert"`. Content as B-62 (`Critical · <Title>`, `<time> IST · <conf> · <camera>`).
  - High: an amber notification for live `alert`s with severity high (SPEC §6.3 "critical and high → sound + toast"), auto-hiding; no beep (B-60 unchanged). Medium: none (feed card only).
  - Clicking a notification's body → `/alerts/?id=<event_id>` (that alert's report).
  - Actions on a notification: exactly the two of §4.5.
- The store→card measurement (§2 `alert`, step 2) must still run after the commit that first paints the alert (the notification or the Alerts row): merge the event and push the notification inside the same `flushSync`; the entrance animation must start visible (transform/scale, not a long fade from opacity 0) so "painted" stays true.

### 4.5 Exactly two actions per alert

- Every alert (card, report, notification) shows exactly two actions: **Acknowledge** and **False alarm**.
- Acknowledge → `ack` (B-59); enabled when `status === "open"`, or when `severity === "critical"` and `status === "closed"` (the old banner acked those); otherwise disabled and the status word (`Closed` / `Acknowledged`) shown beside or instead of its label.
- False alarm → `dismiss` (B-59); enabled when not seeded and not dismissed; disabled for seeded history (old UI hid it; the brief wants both buttons present), tooltip as B-58.
- The label `Ack` becomes `Acknowledge` (DEMO_SCRIPT quotes `Ack`; it needs a docs update).

### 4.6 Event dialog → Alerts tab report

- Old: a modal (B-63…B-68) opened by a card, the banner, a chat citation or a key frame.
- New: `/alerts/?id=<id>` shows that alert's individual report beside (or in place of) the list, with every B-63…B-67 field and the two actions; `data-event-card` kept (B-68). Opening from Ask (citation chip B-73, key frame B-74) and from a notification navigates there.
- Data: store entry, else the object it was opened from (chat payload), else `GET /api/events/{id}` (a deep link to an id not in the store, e.g. seeded or older than 50). Unknown id (404): an empty state, not a crash.
- Esc (B-95) and the close control clear `?id=` (back to the list). After False alarm on the shown alert, the report closes (B-59).
- Old `Mark false alarm` label becomes `False alarm` (§4.5).

### 4.7 Visual system

- Inline SVG icons → Material Symbols Rounded (self-hosted). The `Hive` logo mark stays the brand mark.
- System fonts → the self-hosted M3 typeface + mono face; numbers stay tabular.
- Old dark zinc tokens → M3 colour roles from seed `#1A73E8`, light and dark themes, default dark, toggle in the navbar, `?theme=light|dark` override on any URL.
- 150 ms ease-out enter → M3 Expressive spring motion; `prefers-reduced-motion` still disables it (B-96).

### 4.8 Severity colours (fixed, not from the seed)

critical = vivid red fill (`#D93025` family, white text; reads as a warning at a glance; never muted or dark red) · high = amber (`#F9AB00` family, dark text) · ok = green (`#1E8E3E` family). Red is for critical and errors only.

---

## 5. Verification checklist

"Real server" = http://localhost:8000. "Seeded" = `uv run python -m scripts.seed_history` history present. Never open a camera device while testing (no device clicks in Live; use a stream URL from `scripts/rtsp_sim.sh <clip>`). Stop every source you start (E-8) and confirm with E-1.

| B-id | How to verify in the new UI |
|---|---|
| B-1 | Network panel on load: one `/api/cameras`, one `/api/events?limit=50`, one `/sse`. |
| B-2 | Stop the server for a moment: tiles keep their list (no empty flash); restart: list reloads. |
| B-3 | Code review: SSE entries win over fetched rows at boot. |
| B-4 | Ack an alert: card status changes without a reload; summary arriving via `event_update` fills in. |
| B-5 | Dismiss an alert: it leaves the list; order is id descending; never more than 50. |
| B-6 | Alerts tab shows the open count, nothing at 0. |
| B-7 | An `event_update` after ack (no `camera_name`) keeps the camera name on the card. |
| B-8, B-25 | Play v011.avi in a slot: red ring + `Fighting · N%` chip on that tile only; Ack → both disappear. |
| B-9 | Throttle/delay SSE: skeletons before the first `metrics`. |
| B-10 | Mode switch calls `POST /api/mode` once and reloads cameras (with §4.2 rule). |
| B-11…B-17 | Navbar: logo + `HackHive`, model, `GPU N%`, `onset→alert p50`, badge text and tooltips verbatim, IST clock ticks, sound button states. |
| B-18, B-19 | Header count; 3 sources → amber warning + tooltip verbatim. |
| B-20, B-21 | A clip playing shows `Playing`; when it ends, `Finished`; a dead `rtsp://127.0.0.1:9/x` stream shows `Connecting`. |
| B-22 | Dead stream: `Connecting…` overlay and no `/snapshot` requests in the Network panel. |
| B-23, B-24 | `CLIP`/`LIVE` badge; ■ tooltip and aria-label; ■ stops (E-1 no longer lists it). |
| B-26, B-27 | Now line and meta line match the old format exactly. |
| B-28 | Network: `/snapshot/camN` about every 100 ms, never two at once; frames never grey/half; a 404 keeps the last frame; blob URLs are revoked (memory flat over a minute). |
| B-29…B-38 | Play v011.avi (`Running` → `Detected`, hint `Alert at X s in the clip, onset at 2 s`, big number ms), sample_bus.mp4 (`Correct`, `No incidents`), an unlabelled upload (`Unlabelled`, `Unlabelled clip: no onset to time from`); footer `<name> · played once`. |
| B-39, B-40 | Dropdown lists clips with label/onset/folder; stop the server → error copy; empty copy verbatim. |
| B-41 | Pick a clip in slot 2: only slot 2 changes (slots 1 and 3 keep playing); `POST /api/clips/play` body has `slot: 2`; a 409 shows `Rejected: switch to clips mode first`. |
| B-42 | Upload `x.txt` → `Rejected: file must be .mp4, .mov, .avi or .mkv`; a real clip → `camN added: <name>` in that column; drag-and-drop works on a column. |
| B-44…B-48 | Live: Rescan and window focus refetch `/api/devices`; iPhone hint verbatim when absent; add the rtsp_sim URL into slot 1 → tile appears in slot 1; same URL in slot 2 → `Rejected: already running`; bad scheme `ftp://x` → `Rejected: source must be …`. Do not click device entries. |
| B-49, B-50 | Live alert shows top-3 from the SSE message; a seeded/history card fetches `/api/events/{id}` and shows its peak observation's top 3, or nothing. |
| B-51 | Alerts states: skeleton, error (server down at load), `No alerts` copy. |
| B-52…B-58 | Card: stripe colour, red tint for open critical, thumbnail rules (seeded: none), chips, `ist` time, confidence `N% High (peak M%)`, `trigger → alert`/`onset → alert` lines. |
| B-59 | Ack and False alarm work from card, report and notification without opening anything else; failure is silent; dismissed vanishes everywhere. |
| B-60 | Before arming: no sound. Arm: test beep (880 Hz, 0.5 s). Critical alert → beep; high → none. Navigate tabs → still armed. |
| B-61, B-62 → §4.4 | Critical alert on Clips/Live → red notification that stays after the event closes until Acknowledge/False alarm; second critical → stack + `1 more unacknowledged`; click body → `/alerts/?id=N`. |
| B-63…B-68 → §4.6 | `/alerts/?id=N` shows all six facts verbatim labels, image rules, `#N`, `History` chip, `data-event-card`; deep link to a seeded id works; unknown id shows an empty state; Esc returns to the list. |
| B-69 | Ask, switch to Pipeline and back: log still there; same `session_id` in both requests. |
| B-70…B-72 | Empty state copy and the four suggestions verbatim; suggestion asks at once; Ask disabled when blank/busy; a 501-char question shows `error 400`. |
| B-73 | Answer with `[#id]` → chips; click → that alert's report; unknown ids stay text. |
| B-74, B-75 | Key-frame strip under answers that cite frames; how line text e.g. `question read by rules · template answer · as of 14:03:27 IST · 12 ms`. |
| B-76 | Shift handover with 1 h / 8 h / 24 h; question text and answer sections verbatim; how line starts `shift-handover digest · `. |
| B-77…B-83 | Pipeline: camera picker only with 2+ cameras; nodes and tooltips verbatim; waterfall bars; mosaic, hints, pretty raw JSON; updates live. |
| B-84 | System labels/tooltips verbatim; `VLM errors` red when > 0; `Store → card p95` red when > 100. |
| B-85 | Report: one `/api/report` per 10 s only while on the tab; stop server → error copy. |
| B-86…B-93 | Report labels, captions (B-88, B-92) and table verbatim against the old UI on the same data; CSV link downloads. |
| B-94, B-95 | Press `/` on any tab (not in an input) → Ask with the input focused; Esc closes the report detail. |
| B-96, B-97 | Keyboard-only pass; reduced-motion on → no animation; contrast check in both themes; red appears only on critical/errors. |
| B-98 | `grep -c '<div id="root">' web/dist/index.html` ≥ 1; `uv run python -m app.server --selfcheck` passes (uses the GPU briefly: run it only when the orchestrator allows). |
| B-99 | `curl -sI localhost:8000/alerts/` 200; `curl -sI localhost:8000/alerts` redirects to `/alerts/`; reload on every tab works. |
| B-100 | Offline: DevTools Network shows only `localhost:8000` requests; `grep -r "googleapis\|cdn" web/dist` empty. |
| B-101 | `touch web/src/<any file>` → `run_demo.sh`'s staleness test would rebuild. |
| §4.2 | With nothing running, click Live → switches with no dialog; with a clip in a slot, click Live → confirm dialog; Cancel keeps the clip playing. |
| §4.3 | Three clips in slots 1-3 simultaneously; each Verdict under its own feed; Clips 3-source warning. |
| §4.5 | Every alert surface shows exactly two buttons; Acknowledge disabled on acknowledged; False alarm disabled on seeded. |
| §4.7, §4.8 | `?theme=light` and `?theme=dark`; toggle persists across tabs; severity colours match the fixed families in both themes. |

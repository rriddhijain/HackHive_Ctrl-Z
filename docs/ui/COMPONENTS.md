# HackHive web: shared components, hooks and store (foundation API)

Status: foundation build of the UI overhaul on branch `ui-next` (2026-10-16). This is the contract between the foundation and the six page builders. Companions: `docs/ui/CONTRACT.md` (behaviour and verbatim copy) and `docs/ui/DESIGN.md` (look, motion, layout).

Everything below already exists, typechecks (`npm run typecheck`) and builds (`npm run build` → `web/dist`). Import paths use the `@/` alias (`web/src/`).

## 0. Rules for page builders

1. **Shared folders are frozen.** Do not edit `src/lib/`, `src/styles/`, `src/components/m3/`, `src/components/shell/`, `src/components/feed/`, `src/components/alert-bits/`, `src/app/layout.tsx`, `src/app/template.tsx`, `src/app/page.tsx`, `scripts/gen-theme.mjs`, `next.config.ts`, `package.json` or `tsconfig.json`. If you need a change there, do not make it: return it as a `shared_request` (file, change, why) and work around it locally until the orchestrator merges it.
2. **Ownership map** (each builder writes only its own two folders):

   | Builder | Owns |
   |---|---|
   | Clips | `src/app/clips/`, `src/components/clips/` |
   | Live | `src/app/live/`, `src/components/live/` |
   | Alerts | `src/app/alerts/`, `src/components/alerts/` |
   | Ask | `src/app/ask/`, `src/components/ask/` |
   | Pipeline | `src/app/pipeline/`, `src/components/pipeline/` |
   | Report | `src/app/report/`, `src/components/report/` |

   The current `src/app/<tab>/page.tsx` files are placeholders: replace them.
3. Colours, radii, type and shadows come only from tokens (`bg-surface-container`, `text-on-surface-variant`, `rounded-xl`, `text-title-m-em`, `shadow-level-2`). There is no Tailwind default palette (no `bg-zinc-800`, no `text-red-500`) and no raw hex. `className` on shared components is for layout only (margin, width, grid placement).
4. Motion comes only from `motionTokens` (`@/lib/motion`) and only where §1.3 allows it.
5. Copy is verbatim from CONTRACT.md (the B-ids). Red (`critical*`) is for critical and errors only.
6. Pages are `"use client"`. Do not touch `window`, `localStorage`, `EventSource` or `performance` during render: only in effects and handlers. Pages are prerendered at build time.
7. Never call `fetch` for an endpoint directly. Use the store actions, or `api.*` for reads the store does not hold (for example `api.clips()` and `api.report()`).
8. Never call a play, upload or add-source action without `slot`. The store's signatures require it.
9. No new npm packages. No CDN.

## 1. Tokens

### 1.1 Colours (Tailwind utilities `bg-*`, `text-*`, `border-*`, `ring-*`, `fill-*`, `stroke-*`, `outline-*`)

- M3 roles (seed `#1A73E8`, SchemeContent, dark default, light via `data-theme="light"`): `primary`, `on-primary`, `primary-container`, `on-primary-container`, `inverse-primary`, `primary-fixed`, `primary-fixed-dim`, `on-primary-fixed`, `on-primary-fixed-variant`, the same for `secondary-*` and `tertiary-*`, plus `surface`, `surface-dim`, `surface-bright`, `surface-container-lowest`, `surface-container-low`, `surface-container`, `surface-container-high`, `surface-container-highest`, `on-surface`, `on-surface-variant`, `surface-variant`, `outline`, `outline-variant`, `inverse-surface`, `inverse-on-surface`, `scrim`, `shadow`, `surface-tint`, and `error`, `on-error`, `error-container`, `on-error-container` (all mapped onto critical).
- Fixed severity colours, the same vivid fills in both themes:
  - critical: `critical`, `on-critical`, `critical-container`, `on-critical-container`, `critical-text`
  - high: `high`, `on-high`, `high-container`, `on-high-container`, `high-text`
  - ok: `ok`, `on-ok`, `ok-dot`, `ok-container`, `on-ok-container`, `ok-text`
- Others: `black` and `white` (video letterbox only), `transparent`, `current`. Opacity modifiers work: `bg-on-surface/12`, `bg-scrim/56`.
- The surface ladder: page `surface` → section `surface-container-low` → card `surface-container` → control `surface-container-high` → selected or skeleton `surface-container-highest`.

### 1.2 Type, shape, elevation, breakpoints

- Type: `text-{display|headline|title|body|label}-{l|m|s}` plus an emphasized `-em` twin for each, e.g. `text-title-m-em`. Do not add `font-bold` or `tracking-*`. Mono: `font-mono` (Google Sans Code). Every figure is tabular already.
- Radius: `rounded-xs` 4, `sm` 8, `md` 12, `lg` 16, `lg-plus` 20, `xl` 28, `xl-plus` 32, `2xl` 48, `full`.
- Shadow: `shadow-level-1` … `shadow-level-5`. Surfaces are separated by tone, not by shadow.
- Breakpoints: Tailwind defaults (`lg` 1024, `xl` 1280), plus `wide:` 1600, `cluster:` 1680 and `huge:` 1800.
- Utility classes: `state-layer` (hover 8 %, focus 10 %, pressed 10 % of `currentColor`; use it on anything clickable that is not one of the components below; `data-active` forces the focus layer), `hh-skeleton` (shimmer).
- Theme CSS is generated: `npm run theme` writes `src/styles/theme.css` from `scripts/gen-theme.mjs`.

### 1.3 Motion (`@/lib/motion`)

Basic motion only (captain, 19:15). `motionTokens.{fast 150 ms, default 200 ms, slow 250 ms}` are short tweens on the M3 standard easing, no springs.
Allowed: state layers, the nav pill sliding between tabs, notifications sliding/fading in and out, menus/dialogs/tooltips fading open. Nothing else animates: no route transition, no press morph, no list enter, no number tweening.

## 2. `@/lib`

### 2.1 `types.ts`

`Mode` (`"clips" | "live"`) · `Slot` (`1 | 2 | 3`) · `SLOTS` (`[1, 2, 3]`) · `Severity` · `EventStatus` · `CamStatus` · `Camera` (E-1 row, including `slot: Slot | null`) · `Clip` · `Device` · `AlertMsg` (SSE `alert`) · `Event` (store entry: a partial merge, so most fields are optional; `alert?` marks a live alert; `seeded` is truthy/falsy) · `Observation` · `EventDetail` · `Pctl` · `CamMetrics` · `Metrics` · `Trace` · `ChatHow` · `ChatAnswer` · `Digest` · `ChatEntry` · `Report` · `Started`.

### 2.2 `format.ts` (exact old outputs)

| Function | Output |
|---|---|
| `ist(ts)` | `14:03:27` (Asia/Kolkata, 24 h), falsy → `—` |
| `ms(x)` | `2,526 ms`, null → `—` |
| `pc(c)` | `91%`, null → `—` |
| `v(x, unit?)` | `${x}${unit}`, null → `—` |
| `name(c)` / `title(c)` | `person down` / `Person down` |
| `n(x)` | Pipeline node number `1,137` or `—` |
| `media(p)` | `data/keyframes/x.jpg` → `/media/keyframes/x.jpg` |
| `pretty(s)` | JSON pretty-printed, or the raw string |
| `conf(e)` | `e.alert?.confidence ?? e.peak_confidence` |
| `startTs(e)` | `e.start_ts ?? e.alert?.t_stored` |
| `statusWord(s)` / `STATUS_WORD` | `Open`, `Closed`, `Acknowledged`, `Dismissed`, or the raw value |
| `camState(status, sourceType)` | `[tone, label]`: `["ok","Playing"]`, `["ok","Live"]`, `["high","Connecting"]` … (B-21) |
| `how(h)` | the B-75 how-line prefix (`question read by rules · template answer`) |

```ts
import { ist, ms, pc, title, conf, startTs } from "@/lib/format";
`${ist(startTs(e))} IST · ${pc(conf(e))}`
```

### 2.3 `api.ts`

`api.cameras()`, `api.setMode(mode)`, `api.clips()`, `api.playClip(path, slot)`, `api.upload(file, slot)`, `api.devices()`, `api.addSource(source, name, slot)`, `api.removeSource(id)`, `api.events(limit = 50)`, `api.event(id)`, `api.ack(id)`, `api.dismiss(id)`, `api.chat(session, q)`, `api.digest(hours)`, `api.report()`, `api.feedbackCsv` (a URL string for a plain link), `api.uiLatency(id, ms)` (fire and forget), `api.snapshotUrl(id)`.

A non-2xx response rejects with `ApiError { status, detail }`, where `detail` is always a string (a 422 array becomes its messages). `detailText(d)` is exported for the same conversion.

```ts
import { api, ApiError } from "@/lib/api";
const [clips, setClips] = useState<Clip[] | null | false>(null);   // null loading · false error (B-39)
useEffect(() => { api.clips().then(setClips).catch(() => setClips(false)); }, []);
```

### 2.4 `sound.ts`

`arm()` creates the one AudioContext (call it in a click handler) and plays the test beep. `beep()` plays the 880 Hz, 0.5 s beep when armed. Use the store's `armSound` rather than these directly.

### 2.5 `shapes.ts`

`SHAPES`, `ShapeName` (`circle`, `cookie4`, `cookie6`, `cookie9`, `cookie12`, `sunny`, `softBurst`, `clover4`, `clover8`, `pill`), `radii(name, rot?)`, `mix(a, b, p)`, `toPath(r, size)`, `shapePath(name, size)` (memoised). Self-check: `node src/lib/shapes.ts`.

### 2.6 `store.tsx`: `useStore()` (one provider in the root layout, survives tab switches)

```ts
const { feed, camName, ack, dismiss, openEvent } = useStore();
```

**State**

| Key | Type | Notes |
|---|---|---|
| `cams` | `Camera[]` | last good E-1 list (B-2) |
| `events` | `Record<id, Event>` | the merged store (B-3, B-4) |
| `evLoad` | `"loading" \| "ok" \| "error"` | boot load of events (B-51) |
| `m` | `Metrics \| null` | last SSE `metrics`, replaced every second |
| `traces` | `Record<camId, Trace>` | newest trace per camera |
| `conn` | `boolean` | SSE connected |
| `sound` | `boolean` | armed |
| `devices` | `Device[] \| null \| false` | null loading · false error; fetched on entering `/live/` and on window focus while there (B-44) |
| `chat` | `ChatEntry[]` | Ask log, last 20 (B-71) |
| `busy` | `string \| null` | the question in flight |
| `hours` | `1 \| 8 \| 24` | handover window (default 8) |
| `theme` | `"dark" \| "light"` | |
| `pick` | `string \| null` | Pipeline camera the user picked (B-77) |
| `gate` | `Mode \| null` | the mode the confirm dialog is asking for |
| `opened` | `Record<id, Event>` | objects events were opened from (chat payloads) |
| `session` | `string` | chat SESSION (B-69) |
| `askRef` | `RefObject<HTMLInputElement>` | **Ask must attach it to its input** (`inputRef={askRef}`) so "/" can focus it |

**Derived**

| Key | Meaning |
|---|---|
| `mode` | `m?.mode` (undefined before the first metrics; show skeletons, B-9) |
| `feed` | non-dismissed events, id descending, first 50 (B-5); every alert list uses it |
| `nOpen` / `anyOpenCritical` | open count (B-6) / whether any open alert is critical |
| `notifications` | events the notification stack shows (B-61 critical set + live high alerts, minus closed) |
| `camName(e)` | B-7 fallback chain |
| `camEvents(camId)` | all events of a camera, including dismissed, id ascending (B-8) |
| `hot(camId)` | newest open critical or high event of the camera (B-25) |
| `camStatus(c)` | `m.cameras[id].status ?? c.status` (B-20) |
| `camInSlot(k)` | the camera with `slot === k` |
| `overflow` | cameras with `slot == null` |

**Actions** (stable identities)

| Action | Behaviour |
|---|---|
| `loadCams()` | reload E-1 (errors keep the old list) |
| `ack(id)` / `dismiss(id)` | B-59; silent on failure; `dismiss` also leaves `/alerts/?id=<id>` |
| `switchMode(k)` | B-10, unconditional (prefer `requestMode`) |
| `requestMode(k)` | §4.2 rule: switches at once when `cams` is empty, else opens the confirm dialog |
| `confirmGate()` / `cancelGate()` | dialog buttons (ModeGate already wires them) |
| `playClip(path, slot)` | resolves `""` on success, else `Rejected: <detail>`; reloads cameras |
| `uploadClip(file, slot)` | resolves `camN added: <name>` or `Rejected: <detail>`. Show `` `Uploading ${f.name}…` `` yourself while it runs |
| `addSource(source, name, slot)` | resolves `""` or `Rejected: <detail>` (B-48; does not clear your URL input) |
| `removeSource(id)` | DELETE, then reload (B-24) |
| `rescan()` | refetch devices |
| `ask(q)` | B-71; resolves `true` when you should clear the input (any HTTP answer), `false` on a network failure |
| `handover()` | B-76 using `hours` |
| `setHours(h)` / `setPick(id)` | |
| `armSound()` | arm, or test beep when armed |
| `toggleTheme()` | persists `hh-theme` |
| `openEvent(e \| id)` | stashes the object (when given one) and routes to `/alerts/?id=<id>` |
| `pushNotification(id)` / `closeNotification(id)` | close hides a notification for the rest of the session |

**`useEvent(id)`**: `{ event, state: "none" | "loading" | "ok" | "missing" }`. It returns the store entry merged over the object the event was opened from, or else fetches `GET /api/events/{id}`. A 404 gives `missing`, which should show an empty state (§4.6).

```tsx
const id = Number(useSearchParams().get("id")) || null;   // inside <Suspense>!
const { event, state } = useEvent(id);
```

## 3. `@/components/m3` (M3 Expressive library)

All components are typed. Interactive ones have the state layer, the focus ring and a 48 px hit area. A disabled Button or IconButton uses `aria-disabled`, so it stays focusable and a Tooltip can explain why.

| Component | Props (defaults first) | Example |
|---|---|---|
| `Icon` | `name`, `size=24`, `fill=false`, `weight=400`, `className` | `<Icon name="videocam" size={20} fill />` |
| `Shape` | `name: ShapeName`, `size`, `className` (colour via `text-*`), `rotate?`, `children?` (centred) | `<Shape name="cookie9" size={40} className="text-primary-fixed"><Icon name="timer" size={20} /></Shape>` |
| `Button` | `variant="filled"\|tonal\|outlined\|text\|elevated`, `size="s"\|xs\|m\|l`, `shape="round"\|square`, `icon?`, `trailingIcon?`, `selected?` (toggle), `tone="default"\|critical\|high`, `href?` + `download?` (renders `<a>`), `disabled?`, native button props | `<Button variant="tonal" icon="refresh" onClick={rescan}>Rescan</Button>` |
| `IconButton` | `icon`, `aria-label` (required; also the tooltip), `variant="standard"\|filled\|tonal\|outlined`, `size="s"\|xs`, `width="default"\|narrow\|wide`, `selected?` (toggle, morphs to a square), `tooltip?: string \| false`, `tone="default"\|critical\|high\|scrim` | `<IconButton icon="close" aria-label="Close" onClick={close} />` |
| `ButtonGroup` | `options: {value,label,icon?,disabled?}[]`, `value`, `onChange`, `aria-label`, `mono?` | `<ButtonGroup aria-label="Handover window" value={hours} onChange={setHours} options={[{value:1,label:"1 h"},{value:8,label:"8 h"},{value:24,label:"24 h"}]} />` |
| `Fab` | `icon`, `label?`, `onClick` | not used in v1 (needs captain approval) |
| `Card` | `variant="filled"\|outlined\|elevated`, `radius="md"\|lg\|lg-plus\|xl\|xl-plus`, `level="default"\|low\|high\|highest`, `interactive?`, `as="div"\|section\|article\|li`, `className` (padding allowed) | `<Card radius="lg-plus" className="p-4">…</Card>` |
| `Chip` | `type="assist"\|filter\|input\|suggestion`, `dense?`, `mono?`, `icon?`, `selected?`, `onClick`, `onRemove?`, `title?` | `<Chip dense mono title={`Open event ${id}`} onClick={() => openEvent(ev)}>#{id}</Chip>` |
| `StatusChip` | `variant: critical\|high\|ok\|pending\|error\|neutral\|mono\|scrim`, `dot?: ok\|high\|critical\|neutral`, `title?` | `<StatusChip variant="pending" dot="high">Running</StatusChip>` |
| `Dot` | `tone: ok\|high\|critical\|neutral`, `size=6` | `<Dot tone="ok" />` |
| `Badge` | `count?` (omit for the dot; hidden at 0; 99+), `tone="primary"\|critical` | `<Badge count={n} tone="critical" className="absolute -right-2 -top-1" />` |
| `Divider` | `vertical?`, `inset?` | `<Divider />` |
| `Select<V>` | `label`, `value`, `groups: {label?, options: {value,label,supporting?,meta?,icon?,disabled?,mono?}[]}[]`, `onChange(value, option)`, `placeholder="Choose…"`, `valueLabel?`, `supporting?` (second line), `leading?`, `status?: {kind: loading\|error\|empty, title, body?}` (replaces the options with one row), `disabled?`, `mono?`, `onOpenChange?` | see below |
| `Menu`, `MenuGroup`, `MenuItem` | `Menu {open, onClose, anchor: RefObject, role="menu"\|listbox, minWidth=280, children}` · `MenuGroup {header?, children}` · `MenuItem {label, supporting?, meta?, icon?, selected?, disabled?, active?, mono?, onSelect, role="menuitem"\|option, tone="default"\|error}` | standalone menus: arrows move focus, Esc returns focus to the anchor |
| `TextField` | `value`, `onChange(string)`, `variant="outlined"\|filled\|search`, `label?` (floating), `placeholder?`, `leadingIcon?`, `trailingIcon?`, `trailing?` (node), `supporting?`, `error?: boolean\|string`, `mono?`, `dense?` (48 px), `onEnter?`, `inputRef?`, native input props | `<TextField label="Stream URL" mono dense value={url} onChange={setUrl} onEnter={add} placeholder="rtsp://… or http://192.168.43.20:8080/video" supporting="http, https or rtsp" />` |
| `Dialog` | `open`, `onClose` (Esc, scrim), `headline`, `children` (body), `actions` (mark the safe button `data-autofocus`), `icon?`, `role="dialog"\|alertdialog` | only ModeGate uses one |
| `Tooltip` | `content?` (plain) or `rich?: {subhead?, body}`, `children` (one element), `delay=500`, `className` | `<Tooltip content="Stop and release this source"><span tabIndex={0}>…</span></Tooltip>` |
| `List`, `ListItem` | `List {children, aria-*}` (wrap it in `<LayoutGroup>`) · `ListItem {selected?, tone="default"\|critical, enter?` (live alerts only), `onClick?`, `data?: {"data-event-card": id}`, `className}` | see below |
| `DataTable<T>` | `columns: {key, header, render(row), align?, mono?, width?}[]`, `rows`, `rowKey`, `rowTitle?`, `maxHeight?`, `aria-label` | Report per-clip table |
| `LinearProgress` | `value?` (0..1; omit for indeterminate), `wavy?`, `aria-label` | `<LinearProgress wavy aria-label="Asking" />` |
| `LoadingIndicator` | `aria-label`, `size=48`, `contained?` | `<LoadingIndicator aria-label="Loading the report" />` |
| `Skeleton` / `SkeletonLines` | `className` (size), `radius="full"\|none\|sm\|md\|lg\|lg-plus\|xl` / `lines=2` | `<SkeletonLines lines={2} />` (summary placeholder) |
| `EmptyState` | `icon`, `title`, `body?`, `action?`, `compact?` (feed column), `shape="softBurst"`, `tone="default"\|error` | `<EmptyState icon="check_circle" title="No alerts" body="Incidents appear here the moment the model confirms one." />` |
| `StatTile` | `label`, `value` (formatted), `sub?`, `icon?`, `shape="cookie9"` (operator `clover8`, latency `pill`), `tone="accuracy"\|operator\|latency`, `critical?`, `mono?`, `tooltip?` | `<StatTile label="Clips right" value={`${a.right} / ${a.n}`} icon="check_circle" />` |
| `PageHeader` | `title`, `supporting?`, `actions?` | `<PageHeader title="Report" actions={<Button variant="text" icon="download" href={api.feedbackCsv}>Export operator labels (CSV)</Button>} />` |

Select example (a Clips column):
```tsx
<Select label={`Slot ${k} source`} value={cam?.source as string} mono placeholder="Choose a clip"
  status={clips === null ? { kind: "loading", title: "Loading clips" } : clips === false ? { kind: "error", title: "Could not load clips", body: "Check the server is running, then reload the page." } : undefined}
  groups={[...byFolder.map(([folder, list]) => ({ label: folder, options: list.map((c) => ({ value: c.path, label: c.name, mono: true,
    supporting: `${c.label ? title(c.label) : "Unlabelled"} · ${c.onset_s != null ? `${c.onset_s} s` : "—"}` })) })),
    { options: [{ value: "__upload", label: "Upload video", icon: "upload" }] }]}
  onChange={(v) => v === "__upload" ? fileInput.current?.click() : playClip(v, k).then(setMsg)} />
```

Alert list row example:
```tsx
<LayoutGroup><List aria-label="Alerts" aria-live="polite">
  {feed.map((e) => (
    <ListItem key={e.id} enter={!!e.alert} selected={e.id === id} tone={e.status === "open" && e.severity === "critical" ? "critical" : "default"}
      onClick={() => openEvent(e.id)}>
      …<AlertActions event={e} />
    </ListItem>
  ))}
</List></LayoutGroup>
```

## 4. `@/components/alert-bits` (Alerts and notifications)

| Export | API |
|---|---|
| `AlertActions` | `{event, size="xs", tone="default"\|critical\|high, className}`: the two buttons, `False alarm` (outlined; disabled for seeded, with the tooltip `Seeded demo history (E-19)`, else the B-58 tooltip) and `Acknowledge` (filled; when it cannot act it is disabled and shows the status word, with a check for `Acknowledged`). Clicks do not bubble. |
| `canAck(e)` / `canDismiss(e)` | the §4.5 rules |
| `FALSE_ALARM_TIP`, `SEEDED_TIP` | verbatim tooltip strings |
| `SeverityChip` | `{severity}`: `CRITICAL` / `HIGH` chip; medium has none |
| `sevTone(s)` | `critical` / `high` / `neutral` (stripe and dot tone) |
| `useTop3(e)` | B-49: `Top3 \| null` (pending) `\| false` (none) |
| `Top3Bar` | `{top3, className}`: B-50 bar and labels; nothing for `false`, a skeleton for `null` |

```tsx
const t3 = useTop3(e);
<Top3Bar top3={t3} className="mt-3" />
<AlertActions event={e} size="s" />
```

## 5. `@/components/feed` (Clips and Live)

| Export | API |
|---|---|
| `SlotColumn` | `{slot, controls, cam?, empty?, children?, onDropFile?, className}`: the column surface; a header with the slot badge and `controls`; the `FeedTile`; then, with a camera, `NowLine`; then `children` (Clips: the Verdict). `onDropFile` turns on drag-and-drop and highlights the tile while a file is dragged over. |
| `FeedTile` | `{cam?, empty?, dropTarget?, className}`: 16:9 letterboxed live image (or the `empty` content), status pill, `CLIP`/`LIVE`, stop button, hot chip and ring, connecting and down overlays. It reads the store itself. |
| `LiveImage` | `{id, alt, className}`: the D72 double-buffered snapshot loop (do not reimplement it) |
| `NowLine` | `{cam}`: B-26 and B-27 lines |
| `SlotBadge` | `{slot, size=28}` |
| `FeedHeader` | `{mode}`: B-18 label and count, the 3-source warning (`3+ live cameras: alerts may slow` / `3 clips at once: alerts may slow`), and the mode-mismatch notice with its switch button |
| `OtherSources` | slot-null cameras strip; renders nothing when there are none |

```tsx
<Page wide className="pb-6 pt-4">
  <FeedHeader mode="clips" className="mb-3" />
  <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3 xl:gap-6">
    {SLOTS.map((k) => (
      <SlotColumn key={k} slot={k} cam={camInSlot(k)} onDropFile={(f) => upload(f, k)}
        controls={<ClipSelect slot={k} />} empty={<EmptyState compact icon="movie" title="…" body="…" />}>
        {camInSlot(k) && <Verdict cam={camInSlot(k)!} />}
      </SlotColumn>
    ))}
  </div>
  <OtherSources className="mt-6" />
</Page>
```

## 6. `@/components/shell` (already mounted by the root layout)

| Export | What it does |
|---|---|
| `AppBar` (+ `TABS`, `TabKey`) | logo, wordmark, six tabs with the spring pill, Alerts badge, the mode dot, `StatusCluster` |
| `StatusCluster` | model, GPU, onset→alert p50, connection, IST clock, sound, theme (B-12…B-17) |
| `Notifications` / `Notification` | stack top-right on every route except `/alerts/`; a card body opens `/alerts/?id=`; critical cards stay, high cards hide after 8 s |
| `ModeGate` | §4.2: auto-switch or confirm on entering `/clips/` or `/live/`; Cancel returns to the previous tab |
| `Keyboard` | "/" → `/ask/` and focuses `askRef`; Esc closes `/alerts/?id=` when no overlay is open (overlays carry `data-overlay`) |
| `Page` | `{wide?, className}`: page frame; `wide` for Clips and Live, otherwise centred at 1600 px with 24 px margins |
| `Logo`, `Providers` | brand mark; store and MotionConfig (layout only) |

## 7. Page notes

- **Alerts**: `useSearchParams()` must sit inside `<Suspense>`, or the static build fails. Open with `router.push("/alerts/?id=N")` or `openEvent`; close with `router.push("/alerts/")`. Put `data-event-card={id}` on the report surface. Use `useEvent(id)` for the data. Notifications are hidden on this route.
- **Ask**: `inputRef={askRef}`; `ask(q).then((clear) => clear && setQ(""))`; the log is `chat` and the in-flight question is `busy`.
- **Report**: poll `api.report()` every 10 s inside the page's effect, so it runs only while mounted (B-85).
- **Pipeline**: `pick ?? newest-trace camera ?? cams[0]`, through `setPick` (B-77).
- **Live**: `devices` loads by itself on this route. Never click device entries while testing; use a stream URL from `scripts/rtsp_sim.sh`.
- **Clips / Live**: the backend mode is handled by ModeGate; render `FeedHeader` for the notice. Before the first metrics (`mode === undefined`), show skeleton columns (B-9).

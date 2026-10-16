# HackHive design spec: Material 3 Expressive

Status: Design phase of the UI overhaul on branch `ui-next` (2026-10-16). Companion to `docs/ui/CONTRACT.md` (what the UI must do) and SPEC.md §9 (the wire). This file says how it looks, moves and is built. If the two disagree, CONTRACT.md wins on words, numbers and behaviour; this file wins on colour, type, shape, motion and layout.

Rules for the seven engineers:
- Use only the tokens and components defined here. No raw hex, no raw `px` radius, no Tailwind default palette (it is deleted, §9.6), no ad-hoc easing curves.
- One component per concept (§5), in `web/src/components/`. A screen composes components; it does not restyle them.
- Every value below was checked against a source in §10. Where Material gives a choice, the choice is made here; do not re-decide it.

Contents: 1 Motion · 2 Shape · 3 Type · 4 Colour · 5 Components · 6 Layout · 7 Icons · 8 Tone · 9 Implementation · 10 Sources.

---

## 1. Motion

> **Cut back to basic on the captain's request (19:15).** Only state layers, the nav pill slide, notification slide/fade and menu/dialog/tooltip fades remain, as 150-250 ms tweens; the springs, press morphs, morphing loader, wavy progress, list enter and number tweening below are not used.

### 1.1 The system

M3 Expressive replaced easing-and-duration with a **motion physics system**: every animation is a spring. Two schemes exist, **expressive** (overshoots, bounces into place; Material's default "for most situations, particularly hero moments and key interactions") and **standard** (functional, minimal bounce). Each scheme has six springs: **spatial** (position, size, rotation, rounded corners; may overshoot) and **effects** (colour, opacity; never overshoot), each at three speeds, **fast** (small components: buttons, switches, chips), **default** (things that partly cover the screen: menus, panes, the tab indicator), **slow** (full-screen). On Compose, "all component motion is driven by two tokens: expressive fast spatial and expressive fast effects".

HackHive uses the **expressive** scheme everywhere except where §1.4 says standard (data that must not wobble).

### 1.2 Exact values (Compose source) and the motion/react conversion

Compose `spring(dampingRatio ζ, stiffness k)` uses mass 1. motion/react takes `stiffness`, `damping`, `mass`; the damping coefficient is `damping = 2·ζ·√(k·m)`. Overshoot and settle time (to within 1 % of the target, from rest) were simulated from these numbers.

| Token | ζ | k | motion `damping` | Overshoot | Settles in |
|---|---|---|---|---|---|
| expressive fast spatial | 0.6 | 800 | 33.94 | 9.3 % | 220 ms |
| expressive default spatial | 0.8 | 380 | 31.19 | 1.4 % | 323 ms |
| expressive slow spatial | 0.8 | 200 | 22.63 | 1.5 % | 446 ms |
| standard fast spatial | 0.9 | 1400 | 67.35 | 0.1 % | 139 ms |
| standard default spatial | 0.9 | 700 | 47.62 | 0.1 % | 195 ms |
| standard slow spatial | 0.9 | 300 | 31.18 | 0.1 % | 298 ms |
| fast effects (both schemes) | 1.0 | 3800 | 123.29 | 0 | 109 ms |
| default effects (both schemes) | 1.0 | 1600 | 80.00 | 0 | 168 ms |
| slow effects (both schemes) | 1.0 | 800 | 56.57 | 0 | 236 ms |
| LoadingIndicator morph (Compose `LoadingIndicator.kt`) | 0.6 | 200 | 16.97 | 9.4 % | 442 ms |

Ready to paste as `web/src/lib/motion.ts`:

```ts
import type { Transition } from "motion/react";

// M3 Expressive motion physics (androidx ExpressiveMotionTokens / StandardMotionTokens v0_14_0).
// damping = 2 * dampingRatio * sqrt(stiffness * mass), mass = 1.
const spring = (dampingRatio: number, stiffness: number): Transition => ({
  type: "spring", stiffness, damping: 2 * dampingRatio * Math.sqrt(stiffness), mass: 1,
});

export const motionTokens = {
  // expressive (default scheme)
  fastSpatial: spring(0.6, 800),      // buttons, chips, icon buttons, toggles, badges, press morph
  defaultSpatial: spring(0.8, 380),   // tab indicator, menus, notifications, list reflow, dialogs
  slowSpatial: spring(0.8, 200),      // page-level moves (rare), empty-state art
  // standard (no wobble; for data)
  stdFastSpatial: spring(0.9, 1400),  // bars and numbers that change with live data
  stdDefaultSpatial: spring(0.9, 700),// trace waterfall, top-3 bar
  stdSlowSpatial: spring(0.9, 300),
  // effects: colour and opacity, never overshoot
  fastEffects: spring(1, 3800),
  defaultEffects: spring(1, 1600),
  slowEffects: spring(1, 800),
  // LoadingIndicator shape morph (Compose LoadingIndicator.kt)
  loadingMorph: spring(0.6, 200),
} as const;
```

Never pass `duration`, `ease` or `bounce` anywhere in the app. The only non-spring timings allowed are the LoadingIndicator rotation (linear, 4666 ms per turn), the skeleton shimmer (linear, 1500 ms) and the wavy progress phase (linear).

### 1.3 Which spring when

- **Spatial** for `x`, `y`, `scale`, `width`, `height`, `rotate`, `borderRadius`, `layout` and shape morphs. **Effects** for `opacity`, `color`, `backgroundColor`, `borderColor`, `boxShadow`, `filter`. In one `transition` object: `{ default: motionTokens.fastSpatial, opacity: motionTokens.fastEffects, backgroundColor: motionTokens.fastEffects }`.
- Speed by size: component-sized (≤ 56 px tall) → fast; panes, menus, dialogs, cards, the tab indicator (it travels up to ~600 px) → default; anything full-width → slow.
- Data values (numbers, bars, the trace waterfall, the top-3 bar) use **standard** springs: a bar that overshoots looks like a wrong reading.
- Hover and focus are effects only (state layer opacity, §4.5). Nothing moves on hover.

### 1.4 Recipes

All recipes use `motion/react`. Wrap the app once in `<MotionConfig reducedMotion="user" transition={motionTokens.defaultSpatial}>` (§1.5).

**Button press shape morph** (every button and icon button, §5.3). The corner radius goes from the resting shape to the pressed shape and springs back. Animate a number of pixels, never `9999px`; "full" means `height / 2`.

```tsx
const SHAPE = { xs: { rest: 16, pressed: 8 }, s: { rest: 20, pressed: 8 }, m: { rest: 28, pressed: 12 }, l: { rest: 48, pressed: 16 } };
<motion.button
  style={{ borderRadius: SHAPE[size].rest }}
  whileTap={{ borderRadius: SHAPE[size].pressed }}
  transition={motionTokens.fastSpatial}
/>
```
Square variants rest at the square radius (§2.2) and press to the same pressed value.

**Toggle / selection morph** (icon toggle, connected button group, sound and theme toggles): selected state changes shape and fill together. Shape (`borderRadius`) on `fastSpatial`, container colour on `fastEffects`, the icon's `FILL` axis 0 → 1 via a CSS transition on `font-variation-settings` driven by the same state (CSS transitions are allowed for `font-variation-settings` only: 120 ms linear, off under reduced motion).

**Nav tab active indicator** (§5.1): one `motion.span` per tab, rendered only in the active tab, `layoutId="nav-pill"`, `transition={motionTokens.defaultSpatial}`. Label colour change on `fastEffects`. The pill sits behind the label (`absolute inset-0 -z-0`, content `relative`).

**List item enter** (new alert row, new chat answer, new trace row): `initial={{ y: -12, scale: 0.98 }} animate={{ y: 0, scale: 1 }}` with `defaultSpatial`, plus `layout` on the siblings so the list reflows with `defaultSpatial`. **Opacity starts at 1.** The store → card latency probe (CONTRACT §2 `alert`, §4.4) measures the first paint; an element fading in from 0 is not "painted". Wrap lists in `<LayoutGroup>`; use `layout="position"` on rows that contain images (avoids image squash).

**Notification enter / exit** (§5.10): enter `initial={{ x: 32, scale: 0.92 }} animate={{ x: 0, scale: 1 }}` (`defaultSpatial`, opacity 1 from the first frame); exit `exit={{ opacity: 0, scale: 0.96, transition: motionTokens.fastEffects }}` inside `<AnimatePresence mode="popLayout">`; the stack reflows with `layout`.

**Menu open** (§5.7): container `initial={{ opacity: 0, scaleY: 0.85 }} animate={{ opacity: 1, scaleY: 1 }} exit={{ opacity: 0, scaleY: 0.95 }}`, `transformOrigin` at the anchor edge, `scaleY` on `defaultSpatial`, `opacity` on `fastEffects`. Items do not stagger (a stagger on a 30-item clip list feels slow). The anchor's chevron rotates 0 → 180° on `fastSpatial`.

**Dialog**: scrim opacity 0 → 0.32 on `defaultEffects`; container `initial={{ opacity: 0, scale: 0.9 }}` → 1 on `defaultSpatial` (opacity on `fastEffects`).

**Route change** (fade-through, enter only, keep it fast): `web/src/app/template.tsx` re-mounts on every navigation; it renders `<motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ default: motionTokens.defaultSpatial, opacity: motionTokens.fastEffects }}>`. No exit animation: the App Router unmounts the old page at once, and an exit would delay the next tab. Feeds and the store live in the layout, so they never re-animate.

**Number / metric change** (Report KPI tiles on poll, Verdict big number when it first gets a value, Pipeline node values): key the `<motion.span>` on the formatted value, `initial={{ y: 6, opacity: 0.4 }} animate={{ y: 0, opacity: 1 }}` with `stdFastSpatial` / `fastEffects`. Do **not** animate values that tick every second or every frame (clock, GPU %, now line, meta line, people count): they just update.

**Hot ring** (feed tile, B-25): the inset ring's colour and opacity on `fastEffects`; the tile does not move or pulse.

**Loading indicator**: §2.4.

### 1.5 Reduced motion

- `<MotionConfig reducedMotion="user">` at the root: with `prefers-reduced-motion: reduce`, motion disables transform and layout animations but keeps opacity and colour ones (motion.dev docs). CONTRACT B-96 wants motion off, so also:
- CSS in `globals.css`:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { transition-duration: 0s !important; animation-duration: 0s !important; animation-iteration-count: 1 !important; }
  }
  ```
- `LoadingIndicator`, the wavy progress and the skeleton shimmer read `useReducedMotion()` and render static (the indicator shows its first shape, the wave becomes a flat bar, the skeleton a flat block).
- Route-change opacity is allowed to remain (it is a 109 ms effect, not motion).

---

## 2. Shape

### 2.1 Corner scale (androidx `ShapeTokens.kt` 14_1_0, names as on m3.material.io)

| Token | Value | Tailwind | Used by |
|---|---|---|---|
| none | 0 | `rounded-none` | video frame inside a tile edge-to-edge only when the tile clips it; app bar |
| extra-small | 4 px | `rounded-xs` | plain tooltip, inner corners of segmented list items and menu items, text-field (outlined) |
| small | 8 px | `rounded-sm` | chips, inner corners of connected button groups, pressed shape of XS/S buttons, key-frame thumbnails |
| medium | 12 px | `rounded-md` | cards (M3 default), rich tooltip, selected menu item, square XS/S buttons, hovered list item |
| large | 16 px | `rounded-lg` | feed video tile, notification cards, menus (segmented menu container), FAB, selected/pressed list item, square M button, Select anchor |
| large-increased | 20 px | `rounded-lg-plus` | KPI tiles, Verdict panel, Pipeline node cards |
| extra-large | 28 px | `rounded-xl` | dialogs, feed column container, page section surfaces, square L button |
| extra-large-increased | 32 px | `rounded-xl-plus` | Ask conversation surface, Alerts report surface |
| extra-extra-large | 48 px | `rounded-2xl` | empty-state art container only |
| full | 50 % | `rounded-full` | buttons (round), icon buttons, nav pill, badges, status cluster, search-bar input, switches |

Rule of thumb: a surface's radius is one step larger than the radius of the items inside it (column 28 → tile 16 → chip 8).

### 2.2 Component shapes from the Compose tokens

| Component | Rest (round / square) | Pressed | Selected (round / square) |
|---|---|---|---|
| Button XS (32 px) | full / medium 12 | small 8 | full / medium 12 |
| Button S (40 px) | full / medium 12 | small 8 | full / medium 12 |
| Button M (56 px) | full / large 16 | medium 12 | full / large 16 |
| Button L (96 px) | full / extra-large 28 | large 16 | full / extra-large 28 |
| Icon button XS (32) / S (40) | full / medium 12 | small 8 | **medium 12 / full** (toggle morphs round → square when selected) |
| Connected button group S (40) | outer full, inner small 8 | inner extra-small 4 | selected item becomes full (all four corners) |
| FAB (56) | large 16 | — | — |
| Chips (32) | small 8 | — | — |
| Cards | medium 12 | — | — |
| Dialog | extra-large 28 | — | — |
| Snackbar / plain tooltip | extra-small 4 | — | — |
| Rich tooltip | medium 12 | — | — |
| Segmented menu | container large 16, items extra-small 4, first/last item medium 12 on the outer side, selected item medium 12, 2 px gap between groups | — | — |
| Expressive list | group large 16, items extra-small 4, 2 px between items; hovered medium 12; pressed / focused / selected large 16 | — | — |

### 2.3 Expressive shape set (polar generator)

Material's shape library (`MaterialShapes.kt`: 35 `RoundedPolygon`s) is built from rounded stars and custom polygons, and Compose morphs between any two with `Morph`. The web has no `RoundedPolygon`, so HackHive samples each shape as a **polar radius function r(θ) with the same point count N**: any two shapes then morph by interpolating radii index by index. The parameters below approximate the Material shapes at the sizes we use (checked visually against `MaterialShapes.kt`: `Cookie9Sided` = 9-point star, inner radius 0.8, rounding 0.5; `Sunny` = 8-point star, inner 0.8, rounding 0.15; `Clover4Leaf` = 4 lobes; `SoftBurst` = 10 soft points; `Pill` = rounded capsule).

`web/src/lib/shapes.ts` (erasable TypeScript only, so `node web/src/lib/shapes.ts` runs its self-check on Node 26):

```ts
export const N = 120; // samples per shape; every shape uses the same N so any two can morph

type R = (t: number) => number; // radius at angle t, 1 = outer edge
const lobes = (k: number, p: number, min: number): R => (t) => min + (1 - min) * ((1 + Math.cos(k * t)) / 2) ** p;

export const SHAPES = {
  circle: (() => 1) as R,
  cookie4: lobes(4, 1, 0.84),
  cookie6: lobes(6, 1, 0.88),
  cookie9: lobes(9, 1, 0.9),
  cookie12: lobes(12, 1, 0.92),
  sunny: lobes(8, 2.2, 0.86),
  softBurst: lobes(10, 1.6, 0.8),
  clover4: lobes(4, 0.35, 0.62),
  clover8: lobes(8, 0.5, 0.78),
  pill: ((t) => (Math.abs(Math.cos(t)) ** 4 + Math.abs(Math.sin(t) / 0.62) ** 4) ** -0.25) as R, // superellipse, 1 : 0.62
} as const;
export type ShapeName = keyof typeof SHAPES;

// Radii of a shape, starting at 12 o'clock, optionally rotated (radians).
export const radii = (name: ShapeName, rot = 0): number[] =>
  Array.from({ length: N }, (_, i) => SHAPES[name]((2 * Math.PI * i) / N - Math.PI / 2 - rot));

export const mix = (a: number[], b: number[], p: number): number[] => a.map((r, i) => r + (b[i] - r) * p);

// SVG path for radii, scaled so the largest radius touches the box edge.
export const toPath = (r: number[], size: number): string => {
  const max = Math.max(...r), c = size / 2;
  return r.map((ri, i) => {
    const t = (2 * Math.PI * i) / N - Math.PI / 2, s = (ri / max) * c;
    return `${i ? "L" : "M"}${(c + s * Math.cos(t)).toFixed(2)} ${(c + s * Math.sin(t)).toFixed(2)}`;
  }).join("") + "Z";
};

// Self-check (node web/src/lib/shapes.ts): every shape is positive and every pair morphs to a valid path.
// The guard keeps it out of the browser bundle, where process.argv does not exist.
if (typeof process !== "undefined" && process.argv?.[1] && import.meta.url === `file://${process.argv[1]}`) {
  const names = Object.keys(SHAPES) as ShapeName[];
  for (const a of names) for (const b of names) {
    const p = toPath(mix(radii(a), radii(b), 0.5), 48);
    if (p.includes("NaN") || !radii(a).every((x) => x > 0)) throw new Error(`bad shape ${a}->${b}`);
  }
  console.log(`ok: ${names.length} shapes, ${N} points, all pairs morph`);
}
```

A `<Shape name size className>` component renders `<svg viewBox="0 0 size size"><path d={toPath(radii(name), size)} fill="currentColor"/></svg>` with `aria-hidden`; colour comes from the text colour class. Memoise paths per `(name, size)`.

### 2.4 Where shapes appear (and only here)

Tasteful means few, small, and always holding meaning. No shape decoration on data surfaces.

| Place | Shape | Size | Colour | Motion |
|---|---|---|---|---|
| Logo mark (navbar) | `cookie9` container with the existing Hive hexagon glyph (CONTRACT B-11, two nested hexagons) on top | 36 px container, 20 px glyph | container `primary-container` (#1A73E8 in both themes), glyph `on-primary-container` | on hover the container rotates 40° (1/9 turn) on `fastSpatial`; the glyph does not |
| Slot-number badges (Clips and Live columns) | slot 1 `cookie4`, slot 2 `clover4`, slot 3 `sunny`, number centred | 28 px | `secondary-container`, number `on-secondary-container`, `text-title-s-em` | none |
| KPI tile icon containers (Report, Pipeline system grid header) | Accuracy tiles `cookie9`, Operator tiles `clover8`, latency tiles `pill` (horizontal) | 40 px | Accuracy: `primary-fixed` / `on-primary-fixed-variant`; Operator: `tertiary-fixed` / `on-tertiary-fixed-variant` (fixed roles are identical in both themes) | none |
| Empty states | one large `softBurst` (or `cookie12`) holding a 40 px icon, plus a 16 px `circle` accent offset to the top-right | 96 px art in a 120 px area | big shape `surface-container-highest`, icon `on-surface-variant`, accent `tertiary-container` | none (calm) |
| LoadingIndicator | morphs `softBurst → cookie9 → pill → sunny → cookie4 → circle → …` (Material's indeterminate sequence minus pentagon and oval) | 48 px container, 38 px indicator (Compose `LoadingIndicatorDefaults`) | uncontained: `primary`; contained: `primary-container` circle with `on-primary-container` shape | below |

**LoadingIndicator** (from `LoadingIndicator.kt`): a new morph starts every **650 ms**; each morph animates progress 0 → 1 on `loadingMorph` (ζ 0.6, k 200); each completed morph adds a quarter turn (90°) of rotation; on top, a global rotation of 360° every **4666 ms**, linear. Implementation: `useAnimationFrame` for the global angle, a `setInterval(650)` that advances the index and fires `animate(progress, 1, motionTokens.loadingMorph)` from 0; `d = toPath(mix(radii(seq[i]), radii(seq[i+1]), progress), 38)`; `rotate = global + 90 * (i + progress)`. `role="progressbar"`, `aria-label` from the caller. Use it for: page-level loading (first `GET /api/report`, first chat answer > 1 s), the `connecting` overlay of a feed tile (B-22, contained variant, beside `Connecting…`). Skeletons (§5.20) stay the default for list and text placeholders.

---

## 3. Type

### 3.1 Typefaces (verified on npm, 2026-10-16)

| Role | Package | Version | CSS family | Axes |
|---|---|---|---|---|
| Brand and plain (all text) | `@fontsource-variable/google-sans-flex` | 5.3.2 (OFL-1.1) | `"Google Sans Flex Variable"` | `full.css`: wght 1–1000, wdth 25–151 %, slnt 0–10°, plus opsz (used automatically via `font-optical-sizing: auto`) |
| Mono (ids, timestamps, latencies, URLs, raw JSON, clip file names) | `@fontsource-variable/google-sans-code` | 5.3.2 | `"Google Sans Code Variable"` | wght 300–800 |

Google Sans Flex exists on npm, so Roboto Flex (5.3.0) and Roboto Mono (5.3.0) are **not** used. Import `@fontsource-variable/google-sans-flex/full.css` (the full-axis file, ~1.4 MB Latin, served from localhost, so size does not matter; it buys optical sizing at display sizes) and `@fontsource-variable/google-sans-code` (index.css). Tested in headless Chrome: Google Sans Flex has tabular figures (`tnum`): "1111" and "0000" are both 103.2 px wide with `tabular-nums`, 58.9 / 101.5 px without.

Global rules: `font-variant-numeric: tabular-nums` on `body` (every figure in the app is tabular, B-96); `font-optical-sizing: auto`; `-webkit-font-smoothing: antialiased`. Mono is used through the `font-mono` utility only.

### 3.2 Scale (androidx `TypeScaleTokens.kt` v0_103; Expressive emphasized variants from the same file)

Sizes in px (1 rem = 16 px). Tracking in px. "Brand" and "plain" are the same face here.

| Style | Size / line | Weight | Tracking | Emphasized weight / tracking | Tailwind |
|---|---|---|---|---|---|
| Display L | 57 / 64 | 400 | −0.2 | 500 / 0 | `text-display-l` / `-em` |
| Display M | 45 / 52 | 400 | 0 | 500 / 0 | `text-display-m` |
| Display S | 36 / 44 | 400 | 0 | 500 / 0 | `text-display-s` |
| Headline L | 32 / 40 | 400 | 0 | 500 / 0 | `text-headline-l` |
| Headline M | 28 / 36 | 400 | 0 | 500 / 0 | `text-headline-m` |
| Headline S | 24 / 32 | 400 | 0 | 500 / 0 | `text-headline-s` |
| Title L | 22 / 28 | 400 | 0 | 500 / 0 | `text-title-l` |
| Title M | 16 / 24 | 500 | 0.2 | 700 / 0.15 | `text-title-m` |
| Title S | 14 / 20 | 500 | 0.1 | 700 / 0.1 | `text-title-s` |
| Body L | 16 / 24 | 400 | 0.5 | 500 / 0.15 | `text-body-l` |
| Body M | 14 / 20 | 400 | 0.2 | 500 / 0.25 | `text-body-m` |
| Body S | 12 / 16 | 400 | 0.4 | 500 / 0.4 | `text-body-s` |
| Label L | 14 / 20 | 500 | 0.1 | 700 / 0.1 | `text-label-l` |
| Label M | 12 / 16 | 500 | 0.5 | 700 / 0.5 | `text-label-m` |
| Label S | 11 / 16 | 500 | 0.5 | 700 / 0.5 | `text-label-s` |

Every style has an `-em` utility (`text-title-m-em` etc.) with the emphasized weight and tracking. Do not combine a scale utility with `font-bold` or `tracking-*`; pick the `-em` variant instead.

### 3.3 Which style where

| Surface | Style |
|---|---|
| Navbar wordmark `HackHive` | `text-title-l-em`; `Incident console` (≥ 1600 px only) `text-body-m` on-surface-variant |
| Nav tabs | `text-label-l` (active `text-label-l-em`) |
| Status cluster items | `text-label-m`, values in mono `text-label-m` |
| Page header title (Alerts, Ask, Pipeline, Report) | `text-headline-s-em`; supporting line `text-body-m` |
| Section label (`Clip library`, `Trace`, `System`, `Accuracy · dev set`) | `text-title-s-em` |
| Card / alert title (`title(category)`) | `text-title-m-em` |
| Body copy, summaries, chat answers | `text-body-l` (answers) / `text-body-m` (cards) |
| Captions, honesty captions (B-88, B-92), hints | `text-body-s` on-surface-variant |
| Verdict big number (`Onset → alert`) and the Pipeline `Frame → category` value | `text-display-s-em`, tabular |
| KPI tile value | `text-headline-m-em`; tile label `text-label-l` on-surface-variant |
| Severity and state chips (`CRITICAL`, `HIGH`, `Running`, `Detected`) | `text-label-m-em` (critical/high are uppercase because CONTRACT B-54 says so; everything else sentence case) |
| Buttons | XS/S `text-label-l`; M `text-title-m`; L `text-headline-s` |
| Mono: event ids `#12`, camera ids, `ist()` times, `ms()` values in meta lines, URLs, clip file names, raw JSON, trigger chips | `font-mono` at the size of the surrounding style (usually `text-body-s` or `text-label-m`) |
| Notification title / meta | `text-title-m-em` / `text-body-m` |
| Dialog headline / body | `text-headline-s` / `text-body-m` |

---

## 4. Colour

### 4.1 Library API (`@material/material-color-utilities` 0.4.0, read from its `index.d.ts`)

- `Hct.fromInt(argbFromHex("#1A73E8"))` → hue 265.6, chroma 65.1, tone 49.9.
- Scheme classes, all `new SchemeX(sourceColorHct: Hct, isDark: boolean, contrastLevel: number, specVersion?: "2021" | "2025", platform?: "phone" | "watch")`: `SchemeTonalSpot`, `SchemeVibrant`, `SchemeExpressive`, `SchemeFidelity`, `SchemeContent`, `SchemeNeutral`, `SchemeMonochrome`, `SchemeRainbow`, `SchemeFruitSalad`. All extend `DynamicScheme` (options: `sourceColorHct, variant: Variant, contrastLevel, isDark, platform?, specVersion?, primaryPalette?…errorPalette?`; `DynamicScheme.DEFAULT_SPEC_VERSION = "2021"`).
- Roles: static `DynamicColor`s on `MaterialDynamicColors` (`MaterialDynamicColors.primary.getArgb(scheme)`), or `scheme.primary` getters; `new MaterialDynamicColors().allColors` lists them. `hexFromArgb()` converts.

### 4.2 Variant evaluation for #1A73E8 (computed, light / dark)

| Variant (spec 2021) | primary | primary-container | secondary | tertiary | Verdict |
|---|---|---|---|---|---|
| TonalSpot | #435E91 / #ADC7FF | #D8E2FF / #2A4678 | #565E71 | #715574 mauve | primary is a dull slate, not Google blue |
| Vibrant | #005BC0 / #ADC7FF | #D8E2FF / #004493 | #585C7E | #615789 violet | blue, but secondary and tertiary are both blue-violet: no accent |
| Expressive | #366A34 green | #B7F1AE | #7D5262 | #555B8B | hue-rotates primary to green: rejected |
| Fidelity | #005BBF / #ADC7FF | **#1A73E8** both | #475E8C | #9E4300 orange | tertiary orange collides with the amber "high" severity |
| **Content** | **#005BBF / #ADC7FF** | **#1A73E8 both, white text** | #475E8C / #AFC7FB | **#8C36AB / #EFB0FF purple** | chosen |
| Vibrant / Expressive / TonalSpot, spec 2025 | — | — | — | — | 2025 dark surfaces are saturated navy (#020A2F Vibrant) or near-black; Expressive 2025 tertiary is mint green (reads as "ok"). Not used |

**Choice: `SchemeContent`, spec "2021", contrast 0.** Primary container is exactly Google blue #1A73E8 in both themes (white text 4.51:1), primary stays a recognisable Google blue, surfaces are low-chroma blue-greys (premium, calm), and tertiary is a purple/orchid: the one playful accent, never confused with red, amber or green. Contrast level 0 keeps #1A73E8 exact (0.5 shifts it to #0069DC) and every on-colour pair still passes 4.5:1 (checked: on-secondary-container 4.55 / 4.57, on-tertiary-container 4.51, outline is non-text).

### 4.3 Roles exported as CSS variables

Generated by `web/src/theme/gen-tokens.mjs` (run with `npm run tokens`; writes `web/src/styles/tokens.css`, which is committed so the build never needs the library). Values:

| Role | Light | Dark |
|---|---|---|
| primary / on-primary | #005BBF / #FFFFFF | #ADC7FF / #002E68 |
| primary-container / on-primary-container | #1A73E8 / #FFFFFF | #1A73E8 / #FFFFFF |
| inverse-primary | #ADC7FF | #005BC0 |
| primary-fixed / -dim / on-primary-fixed / on-primary-fixed-variant | #D8E2FF / #ADC7FF / #001A41 / #004493 | same |
| secondary / on-secondary | #475E8C / #FFFFFF | #AFC7FB / #15305B |
| secondary-container / on-secondary-container | #B2C9FE / #3D5481 | #2E4673 / #9EB5E8 |
| secondary-fixed / -dim / on-secondary-fixed / on-secondary-fixed-variant | #D8E2FF / #AFC7FB / #001A41 / #2E4673 | same |
| tertiary / on-tertiary | #8C36AB / #FFFFFF | #EFB0FF / #53006E |
| tertiary-container / on-tertiary-container | #A851C6 / #FFFFFF | #A851C6 / #FFFFFF |
| tertiary-fixed / -dim / on-tertiary-fixed / on-tertiary-fixed-variant | #FAD7FF / #EFB0FF / #330045 / #721791 | same |
| surface | #F9F9FF | #10131A |
| surface-dim / surface-bright | #D8D9E3 / #F9F9FF | #10131A / #363941 |
| surface-container-lowest / -low / (default) / -high / -highest | #FFFFFF / #F2F3FD / #ECEDF7 / #E6E8F2 / #E0E2EC | #0B0E15 / #191C23 / #1D2027 / #272A31 / #32353C |
| on-surface / on-surface-variant | #191C23 / #414754 | #E0E2EC / #C1C6D6 |
| surface-variant | #DEE2F2 | #414754 |
| outline / outline-variant | #727785 / #C1C6D6 | #8B909F / #414754 |
| inverse-surface / inverse-on-surface | #2D3038 / #EFF0FA | #E0E2EC / #2D3038 |
| scrim / shadow | #000000 / #000000 | #000000 / #000000 |
| surface-tint | #005BC0 | #ADC7FF |

The generator (verified: it prints exactly the table above):

```js
// Generates the M3 colour roles for HackHive (seed #1A73E8, SchemeContent, spec 2021, contrast 0).
import { Hct, argbFromHex, hexFromArgb, SchemeContent, MaterialDynamicColors as M } from "@material/material-color-utilities";
const ROLES = ["primary","onPrimary","primaryContainer","onPrimaryContainer","inversePrimary",
  "primaryFixed","primaryFixedDim","onPrimaryFixed","onPrimaryFixedVariant",
  "secondary","onSecondary","secondaryContainer","onSecondaryContainer",
  "secondaryFixed","secondaryFixedDim","onSecondaryFixed","onSecondaryFixedVariant",
  "tertiary","onTertiary","tertiaryContainer","onTertiaryContainer",
  "tertiaryFixed","tertiaryFixedDim","onTertiaryFixed","onTertiaryFixedVariant",
  "surface","surfaceDim","surfaceBright","surfaceContainerLowest","surfaceContainerLow","surfaceContainer",
  "surfaceContainerHigh","surfaceContainerHighest","onSurface","onSurfaceVariant","surfaceVariant",
  "outline","outlineVariant","inverseSurface","inverseOnSurface","scrim","shadow","surfaceTint"];
const kebab = (s) => s.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());
const seed = Hct.fromInt(argbFromHex("#1A73E8"));
for (const dark of [false, true]) {
  const s = new SchemeContent(seed, dark, 0, "2021");
  const lines = ROLES.map((r) => { if (!M[r]) throw new Error("missing role " + r); return `  --md-sys-color-${kebab(r)}: ${hexFromArgb(M[r].getArgb(s))};`; });
  console.log(`${dark ? ':root[data-theme="dark"]' : ":root"} {\n  color-scheme: ${dark ? "dark" : "light"};\n${lines.join("\n")}\n}`);
}
// After the two blocks, the script appends the fixed severity tokens of §4.4 (--hh-critical, --hh-on-critical, …)
// to the same two selectors, and --md-sys-color-error* mapped onto them.
```

Names: `--md-sys-color-<role>` (Material Web's convention), e.g. `--md-sys-color-surface-container-high`. Light values live on `:root`, dark on `:root[data-theme="dark"]` (§9.7). The generated **error** roles are not exported: error is the critical palette (§4.4), so there is one red in the product.

### 4.4 Fixed severity palette (not generated from the seed)

Google's red / yellow / green families. Fills are vivid in **both** themes: the captain rejected muted and dark reds. Contrast ratios are WCAG 2 relative-luminance ratios, computed.

| Token | Light | Dark | Use | Checked |
|---|---|---|---|---|
| `critical` / `on-critical` | #D93025 / #FFFFFF | #D93025 / #FFFFFF | critical chip, notification, card stripe, hot ring, Alerts badge when any open critical | white on #D93025 = **4.77** |
| `critical-container` / `on-critical-container` | #FCE8E6 / #A50E0E | #4A1512 / #F6AEA9 | tinted background of an open critical card (B-52), error message boxes | 6.68 / 8.21 |
| `critical-text` | #C5221F | #F28B82 | red text and icons on surfaces (`Rejected: …`, `Missed`, red table cells, `VLM errors` > 0) | 5.53 on surface (light), 7.78 on surface (dark); allowed up to surface-container-high |
| `high` / `on-high` | #F9AB00 / #202124 | #F9AB00 / #202124 | high chip, notification, stripe, ring, overload warning icon | 8.32 |
| `high-container` / `on-high-container` | #FEF7E0 / #8C4A00 | #3D2E00 / #FDD663 | warning notices (overload, mode mismatch) | 6.33 / 9.42 |
| `high-text` | #8C4A00 | #FDD663 | amber text on surfaces (`Running`, `Wrong category`, `Connecting`) | ≥ 6.3 / 8.76 on surface-container-highest |
| `ok` / `on-ok` | #188038 / #FFFFFF | #188038 / #FFFFFF | ok chip fill (`Correct`, `Detected`) | 5.02 (#1E8E3E with white is 4.21, fails, so the fill is green 700) |
| `ok-dot` | #1E8E3E | #81C995 | status dots, check icons (non-text, ≥ 3:1) | 4.01 / 9.49 |
| `ok-container` / `on-ok-container` | #E6F4EA / #0D652D | #0F3D1E / #A8DAB5 | `Local · offline` badge background | 6.34 / 7.83 |
| `ok-text` | #137333 | #81C995 | green text | 5.68 / 9.49 |
| `neutral-sev` | `outline` | `outline` | medium severity stripe and dot, `Finished`/`Stopped` dots, `Unlabelled` chip (outlined) | — |

Error roles map onto these: `--md-sys-color-error: critical-text`, `on-error: #FFFFFF` (light) / `#601410` (dark), `error-container: critical-container`, `on-error-container: on-critical-container`.

Red is for critical and errors only, never decoration, never hover, never a brand accent (B-97). Amber is high and pending; green is ok. Medium is neutral grey. A severity is always shown with **text or an icon as well as colour** (chip label, stripe plus chip), never by colour alone.

### 4.5 State layers (androidx `StateTokens.kt`)

A state layer is the content colour (`currentColor` of the element's on-colour) laid over the container at a fixed opacity: **hover 8 %, focus 10 %, pressed 10 %, dragged 16 %**. Disabled: container `on-surface` at 12 %, content `on-surface` at 38 %. Implementation: one utility `state-layer` (`position: relative; isolation: isolate` plus a `::before` with `background: currentColor; opacity: 0; transition: opacity` driven by `:hover`, `:focus-visible`, `:active`, `[data-dragged]`); the transition is the one CSS transition allowed besides `font-variation-settings` (`opacity 100ms linear`, ≈ `fastEffects`). On a critical red container the layer is white (its on-colour), so hover never darkens red into "dark red".

Focus indicator (Material Web): `outline: 3px solid var(--md-sys-color-secondary); outline-offset: 2px` on `:focus-visible`, with the element's own radius. On a critical fill the ring is `on-critical` (white).

### 4.6 Elevation (androidx `ElevationTokens.kt`; shadows from the M3 design kit / Material Web)

| Level | dp | Shadow (`--shadow-level-n`) | Use |
|---|---|---|---|
| 0 | 0 | none | everything by default: M3 separates surfaces by tone (`surface-container-*`), not shadow |
| 1 | 1 | `0 1px 2px 0 rgb(0 0 0/.3), 0 1px 3px 1px rgb(0 0 0/.15)` | elevated card (not used), elevated button |
| 2 | 3 | `0 1px 2px 0 rgb(0 0 0/.3), 0 2px 6px 2px rgb(0 0 0/.15)` | menus, rich tooltips, app bar once content scrolls under it |
| 3 | 6 | `0 1px 3px 0 rgb(0 0 0/.3), 0 4px 8px 3px rgb(0 0 0/.15)` | notifications, dialogs, FAB |
| 4 | 8 | `0 2px 3px 0 rgb(0 0 0/.3), 0 6px 10px 4px rgb(0 0 0/.15)` | dragged file over a column (upload drop target) |
| 5 | 12 | `0 4px 4px 0 rgb(0 0 0/.3), 0 8px 12px 6px rgb(0 0 0/.15)` | not used |

Tonal ladder for surfaces (low → high emphasis): page `surface` → section `surface-container-low` → card `surface-container` → control and input `surface-container-high` → selected / skeleton `surface-container-highest`. Do not stack more than three levels.

---

## 5. Components

One file each in `web/src/components/` (PascalCase). Props are typed; colour and size come from props, never from a `className` override (a `className` prop is allowed for layout only: margin, grid placement, width). Every interactive component has the state layer and focus ring of §4.5, a 48 × 48 px minimum hit area (pad with an invisible extension when the visual is 32 or 40 px), and a `disabled` state.

### 5.1 Top app bar (`AppBar`)

- 64 px tall (Compose `AppBarSmallTokens`), full width, `surface` background; when the page is scrolled > 0 it becomes `surface-container` with elevation 2 (effects spring). Sticky top, `z-30`.
- Three zones on a 24 px side margin: **brand** (left), **tabs** (directly after the brand with a 32 px gap; centred on the bar only at ≥ 1800 px, where it cannot collide with the cluster: at 1512 px the tabs span 216–830 px and the compact cluster starts at ~908 px), **status cluster + toggles** (right).
- Brand: logo mark (§2.4) + 12 px + `HackHive` + (≥ 1600 px) 8 px + `Incident console`. The brand is a link to `/`.
- **Tabs** (six, in order Clips, Live, Alerts, Ask, Pipeline, Report; real links with `aria-current="page"`): each 40 px tall, padding 0 16 px, icon 20 px + 8 px + label. Inactive: icon (FILL 0) and label `on-surface-variant`. Active: a pill behind it in `secondary-container`, icon FILL 1 and label `on-secondary-container` `text-label-l-em`; the pill slides between tabs with `layoutId="nav-pill"` on `defaultSpatial`. Hover: 8 % state layer on a full-radius shape the same size as the pill. 4 px gap between tabs. Pressing a tab squashes its pill to `scale: 0.96` on `fastSpatial`.
- **Alerts badge** (B-6): large badge (16 px tall, min 16 px wide, full radius, `text-label-s`, 4 px horizontal padding) anchored to the top-right of the Alerts icon (offset +6 px x, −4 px y). Count of open alerts; hidden at 0. Colour: `critical`/`on-critical` when any open alert is critical, else `primary`/`on-primary`. It scales in from 0 on `fastSpatial` and its number changes with the metric recipe (§1.4).

### 5.2 Status cluster (`StatusCluster`, `StatusItem`)

- A 40 px pill (`surface-container`, full radius, 4 px inner padding) holding items separated by 1 px × 20 px `outline-variant` dividers; to its right, two 40 px icon buttons (sound, theme) with 4 px gaps.
- `StatusItem`: 32 px tall, padding 0 10 px, full radius, icon 18 px (`on-surface-variant`) + 6 px + label `text-label-m` (`on-surface-variant`) + value (mono `text-label-m`, `on-surface`). Hover state layer; each carries the CONTRACT tooltip text verbatim as a **rich tooltip** (§5.15).
- Items, left to right: Model (`neurology`, B-12) · GPU (`memory`, B-13) · Onset → alert p50 (`timer`, B-14) · Connection (B-15: an 8 px dot `ok-dot` or `critical`, label `Local · offline` / `Reconnecting`; while reconnecting the item gets `critical-container` background) · Clock (`schedule`, mono `14:03:27 IST`, B-16).
- Compact below 1680 px wide: Model and Connection collapse to icon/dot only (the label moves into the tooltip and `aria-label`). Nothing else is ever hidden.
- Sound (B-17): unarmed = filled S button `Arm sound` with `notifications_off`; armed = standard icon toggle (`notifications_active`, selected, square-morph) with `aria-label` and tooltip `Alert sound on, click to test`.
- Theme toggle: standard icon button, `dark_mode` in light theme / `light_mode` in dark theme, `aria-label="Switch to light theme"` / `"Switch to dark theme"`; the icon swaps with a 90° rotate + scale 0.6 → 1 on `fastSpatial`.

### 5.3 Buttons (`Button`)

Props: `variant: "filled" | "tonal" | "outlined" | "text" | "elevated"`, `size: "xs" | "s" | "m" | "l"`, `shape: "round" | "square"`, `icon?`, `trailingIcon?`, `selected?` (toggle buttons), `tone?: "default" | "critical" | "high"` (only inside notifications, §5.10).

| Size | Height | Padding | Icon | Icon gap | Label |
|---|---|---|---|---|---|
| XS | 32 | 12 px (16 with no icon) | 20 | 8 | `text-label-l` |
| S (default) | 40 | 16 px | 20 | 8 | `text-label-l` |
| M | 56 | 24 px | 24 | 8 | `text-title-m` |
| L | 96 | 48 px | 32 | 12 | `text-headline-s` |

Colours: filled `primary`/`on-primary`; tonal `secondary-container`/`on-secondary-container`; outlined transparent, 1 px `outline-variant` border (2 px on L), `on-surface-variant` label; text transparent, `primary` label; elevated `surface-container-low`, `primary` label, elevation 1 (2 on hover). Shapes and the press morph: §2.2, §1.4. Disabled: §4.5. HackHive uses XS and S almost everywhere; M only for the empty-state call to action; L is not used.

Which variant where: the one primary action of a region is filled (`Ask`, `Add URL`, `Upload video` in an empty column, dialog confirm, notification `Acknowledge`); secondary actions tonal (`Rescan`, `Shift handover`); `False alarm` is outlined; dismissive and inline actions are text (`Cancel`, `Export operator labels (CSV)` is a text button styled link).

### 5.4 Icon buttons (`IconButton`)

Props: `variant: "standard" | "filled" | "tonal" | "outlined"`, `size: "xs" | "s"` (32 / 40 px; icon 20 / 24 px), `width: "default" | "narrow" | "wide"` (side space 8 / 4 / 14 px at S), `toggle?: boolean`, `selected?`, `aria-label` (required). Standard: transparent, `on-surface-variant` icon, selected `primary` icon FILL 1. Filled: `primary`/`on-primary` (unselected toggle: `surface-container-highest` / `primary`). Tonal: `secondary-container`/`on-secondary-container`. Outlined: 1 px `outline-variant`, selected `inverse-surface`/`inverse-on-surface`. Toggle morph: round → medium-12 square when selected (§2.2) on `fastSpatial`. Every icon button has a plain tooltip with its `aria-label`.

The feed tile stop button (B-23) is a filled XS icon button on a `scrim`-at-48 % backdrop, icon `stop` FILL 1, tooltip `Stop and release this source`, `aria-label` `Stop <name>`.

### 5.5 Connected button group (`ButtonGroup`, replaces segmented buttons)

M3 Expressive's connected button group (`ConnectedButtonGroupSmallTokens`): 40 px tall, buttons 2 px apart, outer corners full, inner corners small 8 (pressed: extra-small 4); the **selected** button morphs to fully round on all four corners, fill `secondary-container` → selected `primary`/`on-primary` (Material uses `secondary-container` for unselected tonal, `primary` for selected). Shape on `fastSpatial`, colour on `fastEffects`. `role="radiogroup"` with `aria-label`; each button `role="radio"` + `aria-checked`; Left/Right arrows move and select, Home/End jump, roving `tabIndex`. Selected button shows a leading `check` icon (16 px) that grows in on `fastSpatial` (width 0 → 16). Used for: `Handover window` 1 h · 8 h · 24 h (B-76), Pipeline `Camera` (B-77).

### 5.6 FAB / extended FAB (`Fab`)

56 × 56 px, large-16 radius, `primary-container`/`on-primary-container` (Google blue), icon 24, elevation 3 (4 on hover); extended: 56 px tall, 16 px side padding, icon + 8 px + `text-title-m`. **Not used in HackHive v1**: no view has a single creation action that floats. Do not add one without captain approval.

### 5.7 Menu and Select (`Menu`, `Select`)

Menu (M3 Expressive segmented menu, `SegmentedMenuTokens` / `StandardMenuTokens`): no outer frame; items are grouped into **groups**, each group a `surface-container-low` block with large-16 outer corners (first item medium-12 top corners, last item medium-12 bottom corners, inner items extra-small-4), groups 2 px apart, elevation 2, min width 280 px (the Select anchor width in Clips/Live), max height `min(60vh, 520px)` scrolling inside, 4 px inner padding per group. Item: 44 px min height (56 px for two-line), padding 0 16 px (12 px when it has a leading icon of 20 px), label `text-body-l`, supporting text `text-body-m` `on-surface-variant`, trailing supporting text `text-label-s` mono (onset), state layers, disabled 38 %. Selected item: `tertiary-container`/`on-tertiary-container`, medium-12 corners on all sides, leading `check` icon: this is the purple accent moment. Group headers: `text-label-m-em` `on-surface-variant`, 32 px, non-interactive (`role="presentation"`).

Select = an anchor + a Menu with `role="listbox"`:
- Anchor: 56 px tall, full width of its column, large-16 radius, `surface-container-high`, leading icon 24 (slot shape badge in Clips/Live, §2.4), a floating label `text-body-s` `on-surface-variant` (`Slot 1 source`), the value `text-body-l` (one line, truncated, full value in `title`), supporting details on a second line `text-body-s` (e.g. `Fighting · onset 4 s · dev/fighting`), trailing `keyboard_arrow_down` rotating 180° when open. Focus: 2 px `primary` bottom indicator inside plus the focus ring.
- Keyboard (WAI-ARIA listbox): Enter / Space / ArrowDown / ArrowUp open; ArrowUp/Down move the active option (skipping disabled and headers), Home/End first/last, Enter selects and closes, Esc closes and returns focus to the anchor, Tab closes; **typeahead**: printable keys within 500 ms build a prefix matched case-insensitively against option labels, cycling on repeated same letter. `aria-activedescendant` on the listbox, `aria-expanded` and `aria-controls` on the anchor. Clicking outside closes.
- Loading / error / empty states render as a single non-selectable item in the menu (spinner = LoadingIndicator 24 px; error in `critical-text`), copy from CONTRACT B-39/B-44.
- Clips Select content: groups by `folder`, each option two lines (name mono + `title(label) · onset n s`), then a final group with `Upload video` (`upload` icon). Live Select: groups `iPhone`, `Webcams`, `Stream URLs`, and a last group `Stream URL…` (`link` icon) which reveals the URL text field under the anchor. Disabled options (running in another slot, B-45) show `In slot n` as trailing text. The iPhone hint (B-46) sits under the anchor as a `text-body-s` supporting line, not inside the menu.

### 5.8 Text fields (`TextField`)

- Outlined (default): 56 px tall (48 px dense variant for the Stream URL row), extra-small-4 radius, 1 px `outline` (hover `on-surface`, focus 2 px `primary`), label floats to the border on focus/value (`text-body-s`, spatial `fastSpatial`), input `text-body-l`, supporting text `text-body-s` below, error → `critical-text` border and supporting text plus `error` trailing icon.
- Filled: `surface-container-highest`, top corners extra-small, 1 px `on-surface-variant` bottom indicator (2 px `primary` on focus). Not used.
- **Search-bar input** (Ask, B-72): 56 px, full radius, `surface-container-high`, leading `search`, placeholder `Ask about incidents`, a `/` key hint chip (`text-label-m` mono, `outline-variant` border, small-8 radius) while empty, trailing filled S icon button `send` (`aria-label="Ask"`), disabled while busy or blank.
- URL input (B-47) is mono.

### 5.9 Cards (`Card`)

`variant: "filled" | "outlined" | "elevated"`, medium-12 radius by default, `radius` prop allows `lg-plus` or `xl` for page surfaces. Filled: `surface-container-highest` (M3) — HackHive uses `surface-container` for cards on a `surface-container-low` section so the ladder stays three steps. Outlined: `surface` + 1 px `outline-variant`. Elevated: `surface-container-low` + elevation 1 (not used). Clickable cards get the state layer and `role="link"` or a full-cover `<a>`.

### 5.10 Notifications (`NotificationStack`, `Notification`)

Snackbar-like but richer (CONTRACT §4.4). Stack: fixed, top 80 px (64 bar + 16), right 24 px, width 400 px, gap 8 px, newest on top, at most 3 shown; above 3, a collapsed fourth row `` `${n - 1} more unacknowledged` `` (`text-label-l`, `inverse-surface` pill) expands the stack on click. Shown on Clips and Live (and on Ask/Pipeline/Report if the captain says so; CONTRACT open question).

Anatomy (large-16 radius, elevation 3, padding 16, min height 88): leading icon 24 (FILL 1), title `text-title-m-em`, meta line `text-body-m` (tabular; time and confidence mono), a trailing chevron `arrow_forward` hint, and the two actions on a row below, right-aligned, 8 px gap. The body (icon + text) is one button → `/alerts/?id=<id>`; the actions are separate buttons and stop propagation.

| Variant | Container | Content | Acknowledge | False alarm | Behaviour |
|---|---|---|---|---|---|
| Critical | `critical` #D93025 | `on-critical` white, icon `error` | filled XS, container white, label `on-critical-container` #A50E0E (7.87:1) | outlined XS, 1 px white at 72 %, white label | `role="alert"`; stays until acknowledged or false-alarmed, also after the event closes |
| High | `high` #F9AB00 | `on-high` #202124, icon `warning` | filled XS, container #202124, label #F9AB00 (8.32:1) | text XS, #202124 label | `role="status"`; auto-hides after 8 s (paused while hovered or focused); no beep |

Motion: §1.4. Disabled actions follow CONTRACT §4.5 (status word replaces the label; False alarm disabled for seeded).

### 5.11 Chips (`Chip`)

32 px (24 px `dense` inside cards and chat), small-8 radius, `text-label-l` (dense `text-label-m`), icon 18.
- **Assist**: 1 px `outline-variant`, `on-surface` label, `primary` icon. Used for citation chips `#12` in chat answers (B-73: dense, mono label, tooltip `Open event 12`, click → report).
- **Filter**: unselected outlined; selected `secondary-container` with leading `check`, no border. Not used in v1 (no filters exist in the old UI; adding them would change functionality).
- **Input**: outlined with trailing `close`. Not used.
- **Suggestion**: outlined, `on-surface-variant` label. Used for the four Ask suggestions (B-70).
- **Status chip** (HackHive, not an M3 chip type, non-interactive): 24 px, full radius, `text-label-m-em`, padding 0 10 px, optional 6 px leading dot. Variants: `critical` (solid red, white, `CRITICAL`), `high` (amber, dark, `HIGH`), `ok` (`ok`/`on-ok`), `pending` (`high-container`/`on-high-container`, e.g. `Running`), `error` (`critical-container`/`on-critical-container`, e.g. `Missed`, Verdict `False alarm`), `neutral` (`surface-container-highest`/`on-surface-variant`, e.g. `Unlabelled`, `History`), `mono` (neutral with mono label, e.g. `gate:fighting`, `CLIP`, `LIVE`).

### 5.12 Badges (`Badge`)

Small: 6 px dot. Large: 16 px tall, min 16 px wide, full radius, `text-label-s`, 4 px side padding, numbers > 99 show `99+`. Colours per §5.1. Placed with `absolute` on a `relative` icon wrapper.

### 5.13 Lists (`List`, `ListItem`) — Alerts list

M3 Expressive segmented list (`ListTokens`): items sit in one group with 2 px gaps; the group has large-16 outer corners, items extra-small-4 inner corners; hover morphs the item to medium-12, pressed / focused / selected to large-16 (`fastSpatial`). Item background `surface-container`, selected `secondary-container`. Item padding 12 px 16 px, min height 72 px. Alert item anatomy (B-52…B-58): 4 px × full-height **severity stripe** inside the left edge (full radius, severity colour; medium = `outline`), thumbnail 96 × 54 (16:9, small-8 radius, `object-contain` on black; skeleton or omitted per B-53), then title row (`text-title-m-em` + status chip + `History` chip + mono time right-aligned), second row (camera `text-body-m` + mono confidence), summary `text-body-m` 2 lines, top-3 bar (§5.14), footer (mono latencies `text-body-s` + the two actions as XS buttons right-aligned). Open critical item background: `critical-container`. `aria-live="polite"` on the list, `aria-label="Alerts"`.

### 5.14 Data tables and bars (`DataTable`, `Top3Bar`, `TraceWaterfall`)

- Table (Report per-clip, B-89): header row 40 px `text-label-l` `on-surface-variant` on `surface-container`, rows 44 px `text-body-m`, 1 px `outline-variant` dividers, no zebra, row hover state layer, row `title` = clip summary; numeric columns right-aligned tabular; mono for clip names. Wrong predictions: red dot + `critical-text`. Sticky header when the table scrolls inside its card.
- Top-3 bar (B-50): 6 px tall, full radius track, segments 2 px apart in `on-surface` at 100 % / 60 % / 32 % (neutral, never severity), widths on `stdDefaultSpatial`; three labels below `text-body-s`, first `-em`.
- Trace waterfall (B-81): one 28 px row per stage, bar 10 px tall full radius in `secondary` (the `1st token → category` bar `primary`), offset and width per CONTRACT, values mono right; axis ticks `text-label-s`.

### 5.15 Tooltips (`Tooltip`, `RichTooltip`)

Plain: `inverse-surface`/`inverse-on-surface`, extra-small-4 radius, `text-body-s`, padding 4 px 8 px, min height 24 px, max width 240 px, 8 px from the anchor, show after 500 ms hover or at once on keyboard focus, hide on leave / Esc; enter `opacity` + `scale 0.9 → 1` on `fastEffects`/`fastSpatial`. Rich: `surface-container`, medium-12 radius, elevation 2, padding 12 px 16 px, max width 320 px, optional subhead `text-title-s`, supporting `text-body-m` `on-surface-variant`. Status cluster and System grid explanations use rich tooltips; icon buttons use plain. All tooltip copy is verbatim from CONTRACT. `role="tooltip"` + `aria-describedby`.

### 5.16 Dialog (`Dialog`)

`surface-container-high`, extra-large-28 radius, elevation 3, padding 24, width 312–560 px, optional icon 24 `secondary` centred above the headline, headline `text-headline-s`, body `text-body-m` `on-surface-variant`, actions right-aligned 8 px apart (text `Cancel`, filled confirm), 24 px above them. Scrim `scrim` at 32 %. Focus trapped; initial focus on Cancel (the safe action); Esc = Cancel; `role="alertdialog"` for the mode-switch confirm (CONTRACT §4.2). Motion §1.4. Only one dialog exists: the mode switch.

### 5.17 Linear progress (`LinearProgress`)

4 px track and indicator (`LinearProgressIndicatorTokens`), full radius, indicator `primary`, track `secondary-container`, 4 px gap between indicator and track, 4 px stop dot at the track end (determinate). **Wavy** variant (M3 Expressive): the active indicator is a sine wave, amplitude 3 px, wavelength 40 px determinate / 20 px indeterminate, total height 10 px; drawn as an SVG path whose phase moves linearly (one wavelength per 1 s); flat under reduced motion. Indeterminate wavy is used for: Ask while a question is in flight (under the question bubble), upload in progress (under the column's Select). Determinate is not used (no playback progress in the wire).

### 5.18 LoadingIndicator

§2.4.

### 5.19 Empty states (`EmptyState`)

Centred in its region: shape art (§2.4, 120 × 120), 16 px, title `text-title-l`, 4 px, body `text-body-m` `on-surface-variant` (max 44 ch), optional action 24 px below (M tonal button). Copy verbatim from CONTRACT (B-30, B-51, B-70, B-78, B-81, B-86…). Inside a feed column the art shrinks to 64 px and the action is S.

### 5.20 Skeleton (`Skeleton`)

`surface-container-highest` block with the radius of what it stands for (text lines: full radius, 12 px tall for `text-body-m` lines with 8 px gaps; images: their radius). Shimmer: a 30 %-wide linear-gradient highlight (`surface-bright` at 40 % in dark, `surface-container-lowest` at 60 % in light) sweeping left → right, 1500 ms linear infinite, `background-attachment: fixed` so all skeletons shimmer in sync. Static under reduced motion. `aria-hidden`; the region carries `aria-busy="true"`.

### 5.21 KPI / stat tile (`StatTile`)

`surface-container`, large-increased-20 radius, padding 20 px, min height 128 px. Top row: shape icon container 40 px (§2.4) + label `text-label-l` `on-surface-variant` (2 lines max). Value `text-headline-m-em` tabular (mono only if the value is an id). Optional sub-value `text-body-s`. Optional `status` prop draws the value in `critical-text` (e.g. `Store → card p95` > 100 ms). Metric-change recipe on value change. Grid of tiles: 4 per row ≥ 1280 px (Report accuracy 8 tiles = 2 rows), 16 px gaps.

### 5.22 Page header (`PageHeader`)

For Alerts, Ask, Pipeline, Report: 32 px top padding, title `text-headline-s-em`, optional supporting line `text-body-m` `on-surface-variant`, right-aligned actions (e.g. Report `Export operator labels (CSV)`, Ask `Shift handover` + handover window group), 24 px below. Clips and Live have no page header: the three columns start 16 px under the app bar, with a 40 px **feed header row** above them (B-18 label + count `text-title-s-em`, the overload warning chip B-19 / §4.3 in `high-container`, and the mode-mismatch notice if any).

### 5.23 Feed column (`FeedColumn`, `FeedTile`, `Verdict`) — composition, not new primitives

Column: `surface-container-low`, extra-large-28 radius, padding 12 px, vertical gap 12 px. Top to bottom: `Select` (§5.7) · `FeedTile` · meta (Now line `text-body-m` 1 line truncated; meta line mono `text-body-s` `on-surface-variant`) · (Clips) `Verdict`.
- `FeedTile`: 16:9, large-16 radius, `overflow-hidden`, black background, image `object-contain` (never stretched, D44). Overlays: top-left hot chip (status chip critical/high, B-25), top-right `CLIP`/`LIVE` mono chip + stop icon button, bottom-left gradient-free scrim pill (`scrim` 56 %) with status dot + name + status label `text-label-m` white. Hot ring: `box-shadow: inset 0 0 0 2px var(--critical|--high)`. Drop target state (upload): 2 px dashed `primary` inset + `primary-container` at 16 % + elevation 4.
- `Verdict`: `surface-container`, large-increased-20 radius, padding 16. Header row: `Verdict` `text-title-s-em` + state chip (B-32 mapping: Running → pending, Unlabelled → neutral, False alarm → error, Correct/Detected → ok, Wrong category → pending, Missed → error). Big number block (B-33/34). Two-column facts `Expected` / `Detected` (`text-label-m` labels, `text-body-m` values). Summary (2 lines). Footer `text-body-s` mono name.

---

## 6. Layout

### 6.1 Frame

- App bar 64 px, sticky. Content area = viewport − 64 px. Page side margin **24 px** at ≥ 1280 px (M3 expanded/large window classes), 16 px below 1280.
- Spacing scale: Tailwind's default 4 px step (`--spacing: 0.25rem`). Use only 2 (0.5), 4 (1), 8 (2), 12 (3), 16 (4), 20 (5), 24 (6), 32 (8), 40 (10), 48 (12), 64 (16). Gutters between columns and panes **24 px**; gaps inside a surface 12 or 16 px; between sections 32 px.
- Max content width for Alerts, Ask, Pipeline, Report: **1600 px**, centred (at 1512 the page uses the full 1464 px; at 1920 it centres with 136 px extra each side). Clips and Live use the full width at every size.

### 6.2 Clips and Live: the 3-column frame

`grid grid-cols-3 gap-6` (24 px), columns equal, each column a `FeedColumn` (§5.23).

| Viewport | Content width | Column width | 16:9 tile height | Column budget (Clips) |
|---|---|---|---|---|
| 1512 × 982 (MacBook Pro 14", the demo Mac) | 1464 | 472 | 265 | Select 56 + 12 + tile 265 + 12 + meta 44 + 12 + Verdict ~280 + padding 24 = ~705 of 902 available (982 − 64 bar − 16) |
| 1920 × 1080 | 1872 | 608 | 342 | ~790 of 1000 |
| 1280–1511 | 1232–1463 | 395–472 | 222–265 | fits; Verdict facts stack to one column below 420 px column width |
| < 1280 (fallback) | — | 3 columns kept down to 1024 px with 16 px margins and gaps (≈ 320 px columns); below 1024 px the columns stack (one per row, full width) | — | — |

The feed header row (40 px) sits above the grid. A camera with `slot: null` (CONTRACT §4.3) appears in an "Other sources" strip under the grid: a row of compact tiles (240 px wide) with the same stop control.

Live columns have no Verdict; the column ends after the meta lines (the Select's supporting area carries Rescan, the URL field and the iPhone hint). Columns are top-aligned (`items-start`), so a short Live column does not stretch.

### 6.3 Alerts (master-detail)

Two panes, 24 px gap, max width 1600: list pane **440 px** fixed (scrolls independently, full height below the page header), detail pane fluid (min 560 px). With no `?id=`, the detail pane shows an `EmptyState` with the title `No alert selected` and no body (the one new string this spec adds; captain to confirm). It never auto-opens an alert: opening is always the operator's click. When the list itself is empty, the list pane shows the B-51 empty state and the detail pane is hidden. The report surface: `surface-container-low`, extra-large-increased-32 radius, padding 24: header (severity dot, title `text-headline-s-em`, severity chip, mono `#id`, `History` chip, close icon button), the key frame 16:9 (large-16 radius, max 720 px wide), summary `text-body-l`, top-3, the six facts as a 3 × 2 grid of label/value pairs, the two actions (S buttons) right-aligned at the bottom. `data-event-card="<id>"` on the surface. Below 1280 px the list pane narrows to 360 px.

### 6.4 Ask (conversation + side panel)

Two columns, 24 px gap, max width 1600: conversation **fluid, max 880 px** (answers at ~72 characters per line), side panel **360 px** on the right. Conversation surface `surface-container-low`, extra-large-increased-32 radius, padding 24, scrolls internally; the search-bar input pinned at its bottom (sticky, 16 px from the bottom edge). Question bubbles right-aligned, `primary-container`/`on-primary-container`, large-16 radius with the bottom-right corner extra-small-4, max 80 %; answers left-aligned on no bubble, `text-body-l`, with the how-line `text-body-s` mono below and the key-frame strip (thumbs 160 × 90). Side panel (`surface-container`, extra-large-28, padding 20): `Shift handover` tonal button + `Handover window` group, then `Try` suggestions (suggestion chips, wrap), then the `/` hint.

### 6.5 Pipeline

Max width 1600, 12-column grid, 24 px gaps. Row 1 (12 cols): camera group (B-77) + header (B-79) with the `Frame → category` big value right. Row 2 (12 cols): the five nodes as `StatTile`-like cards (each 1/5 width) joined by 24 px `arrow_forward` connectors (`outline`). Row 3: Trace waterfall (8 cols) + Model input (4 cols: mosaic 16:9 letterboxed, hints, raw JSON in a `surface-container-highest` mono block, max 12 lines, scroll). Row 4 (12 cols): System grid, 4 columns of label/value rows (`text-body-m` / mono value), red values in `critical-text`.

### 6.6 Report

Max width 1600. Section `Accuracy · dev set` (header row with tag and time right): 8 `StatTile`s in a 4 × 2 grid; caption B-88 below (`text-body-s`, max 120 ch). Then two columns 8 / 4: per-clip `DataTable` (8) and `Errors by confusion pair` (4, mono list). Section `Operator · since server start`: 6 tiles in a 3 × 2 grid (or 6 × 1 at ≥ 1800 px), caption B-92, export text button. 32 px between sections.

---

## 7. Icons

Material Symbols **Rounded**, self-hosted from `material-symbols@0.48.0` (`import "material-symbols/rounded.css"`: family `"Material Symbols Rounded"`, class `material-symbols-rounded`, ligatures, variable `woff2`, `font-display: block`). Names below were each checked against the package's `index.d.ts` type list.

Axes: `FILL` 0 by default, **1 for the active tab, a selected toggle, a severity icon and notification icons**; `wght` 400 (500 inside filled buttons and chips for optical match with medium labels); `GRAD` 0 in light theme, **−25 in dark theme** (light-on-dark glyphs look heavier); `opsz` equals the rendered size (20, 24 or 40). One `Icon` component: `<Icon name="videocam" size={20} fill />` → `<span class="material-symbols-rounded" aria-hidden style="font-size:20px;font-variation-settings:'FILL' 1,'wght' 400,'GRAD' var(--icon-grad),'opsz' 20">videocam</span>`. Icons are decorative (`aria-hidden`); the control carries the label.

| Meaning | Symbol |
|---|---|
| Clips tab | `video_library` |
| Live tab | `videocam` |
| Alerts tab | `notifications` |
| Ask tab | `forum` |
| Pipeline tab | `account_tree` |
| Report tab | `monitoring` |
| Play / restart a clip | `play_arrow` / `restart_alt` |
| Stop a source | `stop` |
| Upload video | `upload` |
| Rescan devices | `refresh` |
| Acknowledge | `check` |
| False alarm | `report_off` |
| Theme (shown in light / dark) | `dark_mode` / `light_mode` |
| Sound armed / not armed | `notifications_active` / `notifications_off` |
| Webcam device | `videocam` |
| iPhone | `mobile` |
| Stream URL | `link` |
| Warning, high severity, overload | `warning` |
| Critical severity, error | `error` |
| Ok, correct, detected | `check_circle` |
| Medium severity, info | `info` |
| Close (report, dialog) | `close` |
| Open in report (notification, key frame) | `arrow_forward` |
| Select chevron | `keyboard_arrow_down` |
| Send question | `send` |
| Shift handover | `schedule` |
| Ask input leading icon | `search` |
| Seeded history | `history` |
| Export CSV | `download` |
| Model | `neurology` |
| GPU | `memory` |
| Latency | `timer` |
| Connection lost | `cloud_off` |
| Clock | `schedule` |
| Pipeline nodes: Frame · YOLO · Gate · VLM · Event | `frame_inspect` · `person_search` · `filter_alt` · `neurology` · `notifications` |
| Key frames, mosaic | `photo_library` |
| Empty column (Clips) / (Live) | `movie` / `videocam_off` |
| Empty alerts | `check_circle` |
| Empty Ask | `forum` |

The brand mark is the existing Hive SVG (two nested hexagons, `main:web/src/icons.jsx`), not a Symbol.

---

## 8. Tone

- Premium and calm. The product is a security console: most of the screen is quiet neutral surfaces; colour is spent on state (severity) and on a few accents (Google-blue logo and primary actions, the purple tertiary for menu selection and operator KPIs).
- Playful only through colour accents, shape (logo, slot badges, KPI icons, empty states, the loading indicator) and spring motion. Never through copy, illustration or decoration on data.
- No gradients (the only gradient is the skeleton shimmer), no glassmorphism or backdrop blur, no glow, no drop shadows beyond §4.6, no emoji, no confetti, no Lottie.
- Sentence case everywhere (`Shift handover`, `False alarm`), except the two severity chips `CRITICAL` / `HIGH` and the source badges `CLIP` / `LIVE` that CONTRACT keeps verbatim. Copy is CONTRACT's, character for character.
- Tabular numbers everywhere; mono for ids, times, latencies, URLs, file names.
- Severity is unambiguous: critical = vivid red fill with white text, high = amber with dark text, ok = green, medium = grey. Red appears nowhere else. A screenshot in greyscale must still show which alert is critical (chip text + stripe + icon).
- Density: generous but efficient. 24 px between major blocks, 12–16 px inside them; no card inside a card inside a card.

---

## 9. Implementation notes (verified against current docs and packages)

### 9.1 Packages (`npm view`, 2026-10-16)

| Package | Version | Note |
|---|---|---|
| `next` | 16.4.2 | peer `react ^18.2 \|\| ^19`, node ≥ 20.9 (machine has 26.8.1) |
| `react`, `react-dom` | 19.3.1 | already 19 |
| `typescript` | **pin `~6.0.3`**, not 7.0.2 | `typescript@7.0.2` (latest) is the native port: its package `exports` expose only `./lib/version.cjs` and `./unstable/*`, no classic compiler API, which Next's build-time type check loads. 6.0.3 is the newest JS-API release |
| `@types/react`, `@types/react-dom` | 19.3.0 | |
| `@types/node` | 26.6.5 | |
| `tailwindcss`, `@tailwindcss/postcss` | 4.3.3 | |
| `motion` | 14.3.0 | import from `motion/react` |
| `@material/material-color-utilities` | 0.4.0 | dev only (token generator) |
| `material-symbols` | 0.48.0 | |
| `@fontsource-variable/google-sans-flex` | 5.3.2 | |
| `@fontsource-variable/google-sans-code` | 5.3.2 | |
| `@fontsource-variable/roboto-flex`, `roboto-mono` | 5.3.0 | not needed (Google Sans exists) |

Remove `vite` and `@tailwindcss/vite`.

### 9.2 Layout of `web/`

Everything the build reads stays under `web/src/` (run_demo.sh rebuilds only when `web/src` is newer than `web/dist/index.html`, B-101): `web/src/app/` (App Router: `layout.tsx`, `template.tsx`, `page.tsx` for `/`, `clips/page.tsx`, `live/`, `alerts/`, `ask/`, `pipeline/`, `report/`), `web/src/components/`, `web/src/lib/` (`motion.ts`, `shapes.ts`, `format.ts` with the CONTRACT helpers, `api.ts`, `store.tsx`), `web/src/styles/` (`globals.css`, `tokens.css`), `web/src/theme/gen-tokens.mjs`. Config files at `web/`: `next.config.ts`, `postcss.config.mjs`, `tsconfig.json` (path alias `@/*` → `src/*`).

### 9.3 `next.config.ts`

`output: "export"` is incompatible with rewrites (Next docs: "Rewrites … not supported", and using them with `next dev` errors), so the export settings apply to builds and the proxy only to dev:

```ts
import type { NextConfig } from "next";

const dev = process.env.NODE_ENV === "development";
const API = "http://127.0.0.1:8000";

const config: NextConfig = dev
  ? {
      trailingSlash: true,
      skipTrailingSlashRedirect: true, // else /api/x is 308'd to /api/x/ before the proxy
      async rewrites() {
        return ["/api/:path*", "/sse", "/snapshot/:path*", "/media/:path*"].map((source) => ({
          source, destination: `${API}${source}`,
        }));
      },
    }
  : { output: "export", trailingSlash: true, images: { unoptimized: true } };

export default config;
```
Dev is a convenience only; the truth is `npm run build` served by FastAPI on :8000 (if the dev proxy buffers SSE, test against the build).

`package.json` scripts: `"dev": "next dev"`, `"build": "next build && rm -rf dist && cp -R out dist"`, `"tokens": "node src/theme/gen-tokens.mjs > src/styles/tokens.css"`. `trailingSlash: true` emits `clips/index.html` etc., which `StaticFiles(html=True)` serves for `/clips/` (B-99); `out/404.html` serves unknown paths.

### 9.4 The exact `<div id="root">` (B-98)

`web/src/app/layout.tsx` (a Server Component, prerendered to static HTML):

```tsx
import "@fontsource-variable/google-sans-flex/full.css";
import "@fontsource-variable/google-sans-code";
import "material-symbols/rounded.css";
import "@/styles/globals.css";
import { Providers } from "@/components/Providers";

const THEME = `(()=>{try{var q=new URLSearchParams(location.search).get("theme");var t=q==="light"||q==="dark"?q:localStorage.getItem("hh-theme");document.documentElement.dataset.theme=t==="light"?"light":"dark"}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME }} /></head>
      <body>
        <div id="root"><Providers>{children}</Providers></div>
      </body>
    </html>
  );
}
```
React renders the bare `<div id="root">` with no other attributes. The build check: `grep -c '<div id="root">' web/dist/index.html` must print ≥ 1 (also check `clips/index.html`). Do not add `className` or `data-*` to that div; style `#root` from CSS if needed.

### 9.5 Client-only rendering

- `Providers` is `"use client"` and holds the event store, the SSE connection, `m` (metrics), traces, the chat log and SESSION, sound arming, the Pipeline camera pick, the theme state and `<MotionConfig reducedMotion="user">`. It lives in the root layout, so it survives every client-side tab navigation (CONTRACT §4.1); pages read it through hooks.
- Every page component that uses state is `"use client"`. Pages are prerendered at build time, so `EventSource`, `AudioContext`, `localStorage`, `window`, `matchMedia` and `performance` are touched only inside `useEffect` or event handlers, never at module scope or during render.
- `/alerts/?id=` uses `useSearchParams()`: the component that calls it must be inside `<Suspense>` or the static build fails ("useSearchParams() should be wrapped in a suspense boundary"). Navigate with `router.push("/alerts/?id=12")`; Esc / close → `router.push("/alerts/")`.
- `/` has no server redirect under export: `page.tsx` is a client component that `router.replace("/clips/")` (or `/live/` once `m.mode === "live"` is known).
- The store → card measurement and `flushSync` rule of CONTRACT §2/§4.4 apply unchanged; React 19's `flushSync` is imported from `react-dom`.

### 9.6 Tailwind v4 (`@tailwindcss/postcss`)

`postcss.config.mjs`: `export default { plugins: { "@tailwindcss/postcss": {} } };`

`globals.css` (abridged; the engineer writing it lists every role):

```css
@import "tailwindcss";
@import "./tokens.css";

@custom-variant dark (&:where([data-theme=dark], [data-theme=dark] *));

@theme {
  --color-*: initial;            /* delete the default palette: only M3 roles exist */
  --radius-*: initial;
  --text-*: initial;
  --font-*: initial;
  --shadow-*: initial;

  --font-sans: "Google Sans Flex Variable", system-ui, sans-serif;
  --font-mono: "Google Sans Code Variable", ui-monospace, monospace;

  --radius-xs: 4px; --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px;
  --radius-lg-plus: 20px; --radius-xl: 28px; --radius-xl-plus: 32px; --radius-2xl: 48px;

  --text-title-m: 1rem; --text-title-m--line-height: 1.5rem;
  --text-title-m--letter-spacing: 0.2px; --text-title-m--font-weight: 500;
  --text-title-m-em: 1rem; --text-title-m-em--line-height: 1.5rem;
  --text-title-m-em--letter-spacing: 0.15px; --text-title-m-em--font-weight: 700;
  /* …every style of §3.2 and its -em twin… */

  --shadow-level-1: 0 1px 2px 0 rgb(0 0 0 / .3), 0 1px 3px 1px rgb(0 0 0 / .15);
  /* …levels 2-5 of §4.6… */
}

@theme inline {
  --color-primary: var(--md-sys-color-primary);
  --color-on-primary: var(--md-sys-color-on-primary);
  --color-surface-container-high: var(--md-sys-color-surface-container-high);
  /* …every role of §4.3, plus the severity tokens of §4.4… */
  --color-critical: var(--hh-critical);
  --color-on-critical: var(--hh-on-critical);
  --color-black: #000; --color-white: #fff;   /* video letterbox and on-critical only */
}

body { @apply bg-surface text-on-surface font-sans text-body-m; font-variant-numeric: tabular-nums; font-optical-sizing: auto; }
```
`@theme inline` is required when a theme variable references another variable (Tailwind docs), so `bg-primary` compiles to `var(--md-sys-color-primary)` and follows `data-theme`. Tailwind's `rounded-full`, `rounded-none`, `bg-transparent` and `bg-current` keep working after the resets. Utilities then read like M3: `bg-surface-container-high text-on-surface-variant rounded-lg text-title-m-em`.

### 9.7 Theme switching without a flash

- Default dark: `<html data-theme="dark">` is in the static HTML, and the inline head script (§9.4) runs before first paint: `?theme=light|dark` wins (not persisted: it is for screenshots and links), else `localStorage["hh-theme"]`, else dark. `suppressHydrationWarning` on `<html>` because the attribute may differ from the prerendered one.
- `tokens.css` defines light on `:root` and dark on `:root[data-theme="dark"]`, each with `color-scheme` (native scrollbars and form controls follow).
- The toggle writes `localStorage["hh-theme"]` (in a try/catch) and sets `document.documentElement.dataset.theme`; it keeps any `?theme=` param out of the decision afterwards (toggle wins until reload).
- Severity tokens (`--hh-*`) are set in both blocks per §4.4; icon `--icon-grad` is 0 light / −25 dark.

### 9.8 Self-hosted fonts and icons

CSS imports in `layout.tsx` (§9.4) make Next copy the `woff2` files from `node_modules` into `out/_next/static/media/` with hashed names; nothing is fetched from a CDN (B-100). Do not use `next/font/google` (it downloads at build time and needs the network). `next/font/local` is not needed. Check after build: `grep -rE "googleapis|gstatic|unpkg|jsdelivr" web/dist` must print nothing.

### 9.9 Checks the implementation leaves behind

- `node web/src/lib/shapes.ts` (shape self-check, §2.3).
- `npm run build` then the B-98 grep and the CDN grep above.
- Contrast: every new foreground/background pair not in §4.3–4.4 gets a ratio check before it ships (≥ 4.5:1 text, ≥ 3:1 icons and dots).

---

## 10. Sources

- M3 motion physics system, how it works (schemes, spatial vs effects, speeds, "all component motion is driven by … expressive fast spatial and expressive fast effects"): https://m3.material.io/styles/motion/overview/how-it-works · specs: https://m3.material.io/styles/motion/overview/specs
- Start building with M3 Expressive: https://m3.material.io/blog/building-with-m3-expressive · Motion theming in Compose: https://m3.material.io/blog/m3-expressive-motion-theming
- Shape scale (token names): https://m3.material.io/styles/shape/corner-radius-scale · Typography: https://m3.material.io/styles/typography/type-scale-tokens · Colour roles: https://m3.material.io/styles/color/roles · Elevation: https://m3.material.io/styles/elevation · States: https://m3.material.io/foundations/interaction/states/state-layers
- androidx Compose Material3 source (androidx-main, `compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3/`): `MotionScheme.kt` (`standard()`, `expressive()`), `tokens/ExpressiveMotionTokens.kt` and `tokens/StandardMotionTokens.kt` (v0_14_0), `tokens/ShapeTokens.kt` (14_1_0), `tokens/TypeScaleTokens.kt` (v0_103), `tokens/StateTokens.kt`, `tokens/ElevationTokens.kt`, `MaterialShapes.kt`, `LoadingIndicator.kt`, and the component tokens `ButtonXSmall/Small/Medium/LargeTokens`, `XSmall/SmallIconButtonTokens`, `ConnectedButtonGroupSmallTokens`, `FabBaselineTokens`, `PrimaryNavigationTabTokens`, `BadgeTokens`, `SnackbarTokens`, `DialogTokens`, `PlainTooltipTokens`, `RichTooltipTokens`, `MenuTokens`, `StandardMenuTokens`, `SegmentedMenuTokens`, `ListTokens`, `Outlined/FilledTextFieldTokens`, `AssistChip/FilterChip/InputChip/SuggestionChipTokens`, `Elevated/Filled/OutlinedCardTokens`, `LinearProgressIndicatorTokens`, `AppBarTokens`, `AppBarSmallTokens`. Mirror: https://github.com/androidx/androidx/tree/androidx-main/compose/material3/material3/src/commonMain/kotlin/androidx/compose/material3
- `@material/material-color-utilities` 0.4.0 type declarations (`index.d.ts`, `dynamiccolor/dynamic_scheme.d.ts`, `dynamiccolor/color_spec.d.ts`, `scheme/*.d.ts`); variants computed locally with the library.
- Next.js static exports (config, unsupported features incl. rewrites, browser APIs in effects): https://nextjs.org/docs/app/guides/static-exports
- motion: transitions (spring `stiffness`/`damping`/`mass`): https://motion.dev/docs/react-transitions · `MotionConfig reducedMotion`: https://motion.dev/docs/react-motion-config
- Tailwind CSS v4: theme variables, `@theme inline`, namespace reset: https://tailwindcss.com/docs/theme · composite font-size variables: https://tailwindcss.com/docs/font-size · `@custom-variant dark` with `data-theme`: https://tailwindcss.com/docs/dark-mode
- Fontsource Google Sans Flex (import, family name, weight range): https://fontsource.org/fonts/google-sans-flex · `full.css` axes: https://unpkg.com/@fontsource-variable/google-sans-flex@5.3.2/full.css · Google Sans Code: https://unpkg.com/@fontsource-variable/google-sans-code@5.3.2/index.css
- Material Symbols npm (CSS, family, icon name list): https://unpkg.com/material-symbols@0.48.0/rounded.css · https://unpkg.com/material-symbols@0.48.0/index.d.ts
- Google colour families (red 600 #D93025, red 700 #C5221F, red 900 #A50E0E, yellow 600 #F9AB00, green 600 #1E8E3E, green 700 #188038): the captain's brief; contrast ratios computed with the WCAG 2 formula.

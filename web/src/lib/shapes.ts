// M3 Expressive shape set as polar radius functions with the same point count, so any two morph (DESIGN §2.3).
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

const cache = new Map<string, string>();
/** Memoised path of a shape at a size. */
export const shapePath = (name: ShapeName, size: number): string => {
  const k = `${name}:${size}`;
  let p = cache.get(k);
  if (!p) cache.set(k, (p = toPath(radii(name), size)));
  return p;
};

// Self-check (node src/lib/shapes.ts): every shape is positive and every pair morphs to a valid path.
// The guard keeps it out of the browser bundle, where process.argv does not exist.
if (typeof process !== "undefined" && process.argv?.[1] && import.meta.url === `file://${process.argv[1]}`) {
  const names = Object.keys(SHAPES) as ShapeName[];
  for (const a of names) for (const b of names) {
    const p = toPath(mix(radii(a), radii(b), 0.5), 48);
    if (p.includes("NaN") || !radii(a).every((x) => x > 0)) throw new Error(`bad shape ${a}->${b}`);
  }
  console.log(`ok: ${names.length} shapes, ${N} points, all pairs morph`);
}

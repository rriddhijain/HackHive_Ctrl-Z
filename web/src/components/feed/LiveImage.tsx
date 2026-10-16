"use client";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

/**
 * Live view at ~10 fps, double-buffered (D72, B-28, algorithm unchanged): each snapshot is fetched whole, checked for
 * the JPEG start/end markers, decoded off-screen, and only then swapped in. A failed or truncated frame is skipped, so
 * the tile keeps the last good one and never paints a half-loaded frame. Never two fetches in flight.
 */
export function LiveImage({ id, alt, className = "" }: { id: string; alt: string; className?: string }) {
  const ref = useRef<HTMLImageElement>(null);
  useEffect(() => {
    let alive = true, shown: string | null = null;
    const tick = async () => {
      const t0 = performance.now();
      let url: string | null = null;
      try {
        const r = await fetch(api.snapshotUrl(id), { cache: "no-store" });
        const b = new Uint8Array(await r.arrayBuffer()), n = b.length;
        if (r.ok && n > 4 && b[0] === 0xff && b[1] === 0xd8 && b[n - 2] === 0xff && b[n - 1] === 0xd9) {
          url = URL.createObjectURL(new Blob([b], { type: "image/jpeg" }));
          const im = new Image(); im.src = url; await im.decode();
          if (alive && ref.current) { ref.current.src = url; ref.current.dataset.ready = ""; if (shown) URL.revokeObjectURL(shown); shown = url; url = null; }
        }
      } catch { /* keep the last good frame */ }
      if (url) URL.revokeObjectURL(url);
      if (alive) setTimeout(tick, Math.max(0, 100 - (performance.now() - t0)));
    };
    void tick();
    return () => { alive = false; if (shown) URL.revokeObjectURL(shown); };
  }, [id]);
  // eslint-disable-next-line @next/next/no-img-element
  // Invisible until the first good frame, so a source with no frame yet shows a black tile, not a broken-image glyph.
  return <img ref={ref} alt={alt} className={`block aspect-video w-full bg-black object-contain opacity-0 data-[ready]:opacity-100 ${className}`} />;
}

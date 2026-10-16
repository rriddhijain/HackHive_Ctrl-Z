import { Shape } from "@/components/m3";

/** The Hive glyph (two nested hexagons, old icons.jsx) on a static cookie9 container (DESIGN §2.4). */
export function Logo({ size = 36 }: { size?: number }) {
  return (
    <span className="relative inline-grid shrink-0 place-items-center" style={{ width: size, height: size }}>
      <span className="absolute inset-0 text-primary-container">
        <Shape name="cookie9" size={size} />
      </span>
      <svg width={size * 0.56} height={size * 0.56} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"
        aria-hidden="true" className="relative text-on-primary-container">
        <path d="M12 2.5 20.5 7.25v9.5L12 21.5l-8.5-4.75v-9.5Z" /><path d="M12 8.5 15 10.25v3.5L12 15.5l-3-1.75v-3.5Z" />
      </svg>
    </span>
  );
}

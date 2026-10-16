// Inline icons (D76): 24 px viewBox, 1.5 stroke, Lucide-style paths. No icon font, no network.
const I = (d) => function Icon({ size = 16, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={`shrink-0 ${className}`}>{d}</svg>
  );
};

export const Hive = I(<><path d="M12 2.5 20.5 7.25v9.5L12 21.5l-8.5-4.75v-9.5Z" /><path d="M12 8.5 15 10.25v3.5L12 15.5l-3-1.75v-3.5Z" /></>);
export const Play = I(<path d="M7 4.5v15l12-7.5Z" />);
export const Stop = I(<rect x="6" y="6" width="12" height="12" rx="1.5" fill="currentColor" />);
export const Upload = I(<><path d="M12 15V3.5" /><path d="m7 8.5 5-5 5 5" /><path d="M20.5 15v3.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V15" /></>);
export const Plus = I(<><path d="M12 5v14" /><path d="M5 12h14" /></>);
export const Bell = I(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></>);
export const BellOff = I(<><path d="M8.7 3A6 6 0 0 1 18 8a21.3 21.3 0 0 0 .6 5" /><path d="M17 17H3s3-2 3-9a4.67 4.67 0 0 1 .3-1.7" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /><path d="m2 2 20 20" /></>);
export const Check = I(<path d="M20 6 9 17l-5-5" />);
export const X = I(<><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>);
export const Alert = I(<><path d="m21.73 18-8-14a2 2 0 0 0-3.46 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" /><path d="M12 9v4" /><path d="M12 17h.01" /></>);
export const Send = I(<><path d="m5 12 7-7 7 7" /><path d="M12 19V5" /></>);
export const Video = I(<><path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 11" /><rect x="2" y="6" width="14" height="12" rx="2" /></>);
export const Chevron = I(<path d="m9 18 6-6-6-6" />);

// UI primitives and formatters (D76). Colours come only from the tokens in index.css.

export const ist = (ts) => (ts ? new Date(ts * 1000).toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour12: false }) : "—");
export const media = (p) => "/" + p.replace(/^data\//, "media/");
export const v = (x, unit = "") => (x == null ? "—" : `${x}${unit}`);
export const ms = (x) => (x == null ? "—" : `${Math.round(x).toLocaleString("en-US")} ms`);
export const pc = (c) => (c == null ? "—" : `${Math.round(c * 100)}%`);
export const name = (c) => c?.replaceAll("_", " ");
export const title = (c) => (c ? name(c)[0].toUpperCase() + name(c).slice(1) : "");
export const getJSON = (u) => fetch(u).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${u}: ${r.status}`))));
export const post = (u, body) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// Red, amber and green mean severity or state, nothing else.
export const SEV_BG = { critical: "bg-crit", high: "bg-high", medium: "bg-fg-3" };
export const SEV_TEXT = { critical: "text-crit", high: "text-high", medium: "text-fg-2" };
export const STATE = {
  live: ["bg-ok", "Live"], connecting: ["bg-high", "Connecting"], reconnecting: ["bg-high", "Reconnecting"],
  down: ["bg-crit", "Down"], ended: ["bg-fg-3", "Finished"], stopped: ["bg-fg-3", "Stopped"],
};

const BTN = {
  primary: "bg-accent text-white hover:bg-accent-hover",
  secondary: "border border-line-strong bg-surface text-fg hover:bg-raised",
  ghost: "text-fg-2 hover:bg-raised hover:text-fg",
};
export function Button({ variant = "secondary", size = "md", className = "", ...p }) {
  const sz = size === "sm" ? "h-6 px-2 text-12" : "h-8 px-3 text-13";
  return <button {...p} className={`inline-flex shrink-0 items-center justify-center gap-1.5 rounded font-medium
    disabled:pointer-events-none disabled:opacity-50 ${sz} ${BTN[variant]} ${className}`} />;
}

export const Dot = ({ className }) => <span aria-hidden="true" className={`inline-block size-1.5 shrink-0 rounded-full ${className}`} />;

export function Chip({ className = "", children, ...p }) {
  return <span {...p} className={`inline-flex h-5 shrink-0 items-center gap-1 rounded px-1.5 text-11 font-medium ${className}`}>{children}</span>;
}

export const Label = ({ children, className = "" }) => <h2 className={`label ${className}`}>{children}</h2>;

export const Skeleton = ({ className = "" }) => <div aria-hidden="true" className={`animate-pulse rounded bg-raised ${className}`} />;

export function Empty({ icon: Icon, title, hint, children, className = "" }) {
  return (
    <div className={`flex flex-col items-center justify-center gap-1 px-6 py-8 text-center ${className}`}>
      {Icon && <Icon size={20} className="mb-1 text-fg-3" />}
      <div className="text-13 font-medium text-fg-2">{title}</div>
      {hint && <div className="max-w-72 text-12 text-fg-3">{hint}</div>}
      {children}
    </div>
  );
}

export function Segmented({ value, options, onChange, label }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex h-8 rounded border border-line-strong bg-surface p-0.5">
      {options.map(([k, text]) => (
        <button key={k} role="radio" aria-checked={value === k} onClick={() => onChange(k)}
          className={`rounded-[3px] px-3 text-13 font-medium ${value === k ? "bg-raised text-fg" : "text-fg-3 hover:text-fg"}`}>{text}</button>
      ))}
    </div>
  );
}

// Top-3 probability bar: neutral greys (data, not controls).
export function Top3({ t3 }) {
  if (t3 === false) return null;
  if (!t3) return <Skeleton className="h-1 w-full" />;
  return (
    <div>
      <div className="flex h-1 gap-px overflow-hidden rounded-full bg-raised">
        {t3.map(([k, c], i) => <div key={k} style={{ width: `${c * 100}%` }} className={i === 0 ? "bg-fg-2" : i === 1 ? "bg-fg-3" : "bg-line-strong"} />)}
      </div>
      <div className="mt-1 grid grid-cols-3 gap-3 font-mono text-11 text-fg-3">
        {t3.map(([k, c], i) => <span key={k} className={`truncate ${i ? "" : "text-fg-2"}`}>{pc(c)} {name(k)}</span>)}
      </div>
    </div>
  );
}

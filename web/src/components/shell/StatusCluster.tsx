"use client";
import { useEffect, useState, type ReactNode } from "react";
import { Button, Divider, Dot, Icon, IconButton, Tooltip } from "@/components/m3";
import { ist, ms } from "@/lib/format";
import { useLive, useStore } from "@/lib/store";

/** compact: icon only below 1680 px · terse: icon + value below 1680 px (label hidden). */
function Item({ icon, label, value, tip, compact, terse, wideIcon, className = "", lead }: {
  icon?: string; label?: string; value?: ReactNode; tip: string; compact?: boolean; terse?: boolean; className?: string; lead?: ReactNode;
  /** Show the icon only at ≥ 1680 px (the value is self-explanatory). */ wideIcon?: boolean;
}) {
  return (
    <Tooltip rich={{ subhead: compact || terse ? label : undefined, body: tip }}>
      <span tabIndex={0} aria-label={compact || terse ? [label, typeof value === "string" ? value : ""].filter(Boolean).join(": ") : undefined}
        className={`state-layer inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-full px-2 text-label-m cluster:px-2.5 text-on-surface-variant ${className}`}>
        {lead ?? (icon && (wideIcon ? <span className="hidden cluster:inline-flex"><Icon name={icon} size={18} /></span> : <Icon name={icon} size={18} />))}
        {label && <span className={compact || terse ? "hidden cluster:inline" : ""}>{label}</span>}
        {value != null && <span className={`font-mono text-on-surface ${compact ? "hidden cluster:inline" : ""}`}>{value}</span>}
      </span>
    </Tooltip>
  );
}

function Clock() {
  const [t, setT] = useState<number | null>(null);   // null on the prerender: no clock until the client ticks
  useEffect(() => { setT(Date.now() / 1000); const i = setInterval(() => setT(Date.now() / 1000), 1000); return () => clearInterval(i); }, []);
  return <span className="whitespace-nowrap font-mono text-label-m text-on-surface">{t ? `${ist(t)} IST` : "—"}</span>;
}

function formatModel(raw?: string | null): string {
  if (!raw) return "—";
  if (raw.toLowerCase().includes("qwen")) {
    if (raw.includes("2.5")) return "Qwen2.5-VL 4B";
    if (raw.includes("3.5")) return "Qwen3.5 4B";
    return "Qwen-VL";
  }
  return raw.split(":")[0];
}

/** Status cluster (B-12..B-17, DESIGN §5.2) plus the sound and theme toggles. Below 1680 px the Model / GPU / onset labels move into the tooltips; values and the connection text stay. */
export function StatusCluster() {
  const { sound, armSound, theme, toggleTheme } = useStore();
  const { m, conn } = useLive();
  const x = m?.vlm, o2a = m?.latency?.onset_to_alert_ms;
  const modelDisplay = formatModel(x?.model);
  return (
    <div className="flex shrink-0 items-center gap-1">
      <div className="flex h-10 items-center rounded-full bg-surface-container p-1">
        <Item icon="neurology" label="Model" terse wideIcon value={<span className="max-w-[120px] 2xl:max-w-none truncate inline-block align-bottom">{modelDisplay}</span>} tip={`Model: ${x?.model ?? "—"} (Vision-language model, running locally)`} />
        <Divider vertical inset />
        <Item icon="memory" label="GPU" terse value={x?.gpu_duty_pct == null ? "—" : `${Math.round(x.gpu_duty_pct)}%`}
          tip="Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras." />
        <Divider vertical inset className="hidden sm:block" />
        <div className="hidden sm:flex items-center">
          <Item icon="timer" label="onset→alert p50" terse value={o2a?.n ? ms(o2a.p50) : "—"}
            tip="Labelled incident onset in the clip → alert (§12), p50. Only for labelled clips played once." />
        </div>
        <Divider vertical inset className="hidden lg:block" />
        <div className="hidden lg:flex items-center">
          <Item label={conn ? "Local · offline" : "Reconnecting"} lead={<Dot tone={conn ? "ok" : "critical"} size={8} />}
            className={conn ? "" : "bg-critical-container text-on-critical-container"}
            tip={conn ? "Connected to the local server; no network needed" : "Lost the local server; retrying"} />
        </div>
        <Divider vertical inset className="hidden xl:block" />
        <span className="hidden xl:inline-flex h-8 items-center gap-1.5 rounded-full px-2 text-on-surface-variant cluster:px-2.5">
          <Icon name="schedule" size={18} /><Clock />
        </span>
      </div>
      <div className="ml-1 flex items-center shrink-0">
        <IconButton
          icon={sound ? "notifications_active" : "notifications"}
          selected={sound}
          aria-label={sound ? "Alert sound on, click to test" : "Arm alert sound"}
          onClick={armSound}
        />
      </div>
      <IconButton icon={theme === "dark" ? "light_mode" : "dark_mode"} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} onClick={toggleTheme} className="shrink-0" />
    </div>
  );
}

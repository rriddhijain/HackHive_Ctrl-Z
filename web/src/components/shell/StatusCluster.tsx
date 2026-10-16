"use client";
import { useEffect, useState, type ReactNode } from "react";
import { Button, Divider, Dot, Icon, IconButton, Tooltip } from "@/components/m3";
import { api, type NotifyStatus } from "@/lib/api";
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

/** D89: opt-in phone notifications. Hidden until the server reports a channel; off at boot; one click turns it on. */
function NotifyToggle() {
  const [st, setSt] = useState<NotifyStatus | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const load = () => api.notify().then(setSt).catch(() => setSt(null));
    load(); const i = setInterval(load, 10000); return () => clearInterval(i);
  }, []);
  if (!st || st.channels.length === 0) return null;
  const last = st.recent[st.recent.length - 1];
  const tip = st.enabled
    ? `Phone alerts ON via ${st.channels.join(" + ")}: critical alerts, metadata only, max one per camera and category per ${st.cooldown_s} s.` +
      (last ? ` Last: ${last.ok ? "delivered" : "failed (" + last.error + ")"} in ${last.ms} ms.` : "") + " Click to turn off."
    : "Phone alerts OFF (the system is fully offline). Click to send critical alerts to subscribed phones.";
  const flip = () => { setBusy(true); api.setNotify(!st.enabled).then(setSt).catch(() => {}).finally(() => setBusy(false)); };
  return (
    <Tooltip rich={{ subhead: "Phone alerts", body: tip }}>
      <IconButton icon={st.enabled ? "phonelink_ring" : "phonelink_erase"} selected={st.enabled} disabled={busy}
        aria-label={st.enabled ? "Phone alerts on, click to turn off" : "Phone alerts off, click to turn on"} onClick={flip} />
    </Tooltip>
  );
}

/** Status cluster (B-12..B-17, DESIGN §5.2) plus the sound and theme toggles. Below 1680 px the Model / GPU / onset labels move into the tooltips; values and the connection text stay. */
export function StatusCluster() {
  const { sound, armSound, theme, toggleTheme } = useStore();
  const { m, conn } = useLive();
  const x = m?.vlm, o2a = m?.latency?.onset_to_alert_ms;
  return (
    <div className="flex shrink-0 items-center gap-1">
      <div className="flex h-10 items-center rounded-full bg-surface-container p-1">
        <Item icon="neurology" label="Model" terse wideIcon value={x?.model ?? "—"} tip="Vision-language model, running in Ollama on this machine" />
        <Divider vertical inset />
        <Item icon="memory" label="GPU" terse value={x?.gpu_duty_pct == null ? "—" : `${Math.round(x.gpu_duty_pct)}%`}
          tip="Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras." />
        <Divider vertical inset />
        <Item icon="timer" label="onset→alert p50" terse value={o2a?.n ? ms(o2a.p50) : "—"}
          tip="Labelled incident onset in the clip → alert (§12), p50. Only for labelled clips played once." />
        <Divider vertical inset />
        <Item label={conn ? "Local · offline" : "Reconnecting"} lead={<Dot tone={conn ? "ok" : "critical"} size={8} />}
          className={conn ? "" : "bg-critical-container text-on-critical-container"}
          tip={conn ? "Connected to the local server; no network needed" : "Lost the local server; retrying"} />
        <Divider vertical inset />
        <span className="inline-flex h-8 items-center gap-1.5 rounded-full px-2 text-on-surface-variant cluster:px-2.5">
          <span className="hidden cluster:inline-flex"><Icon name="schedule" size={18} /></span><Clock />
        </span>
      </div>
      <div className="ml-1 flex items-center">
        {sound
          ? <IconButton icon="notifications_active" selected aria-label="Alert sound on, click to test" onClick={armSound} />
          : <Button variant="filled" size="s" icon="notifications_off" onClick={armSound}>Arm sound</Button>}
      </div>
      <NotifyToggle />
      <IconButton icon={theme === "dark" ? "light_mode" : "dark_mode"} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} onClick={toggleTheme} />
    </div>
  );
}

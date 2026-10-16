"use client";
import { useState } from "react";
import { Button, Select, TextField, type SelectGroup } from "@/components/m3";
import { useStore } from "@/lib/store";
import type { Camera, Device, Slot } from "@/lib/types";

export const IPHONE = "iPhone (live)";
const URL_OPT = "__url";   // the `Stream URL…` entry; a real source is a device index or an http/https/rtsp URL, never this
type Val = number | string;

/**
 * Header controls of one Live column (CONTRACT §4.3, B-44…B-48): the source Select (iPhone, webcams, preset stream
 * URLs, `Stream URL…`), the URL field it reveals with Add URL, and the per-column `Rejected: …` message.
 * Choosing a device or preset starts it in this slot at once (§4.3); a typed URL starts on Add URL or Enter.
 * The device-list copy is page-level (DeviceNotice).
 */
export function LiveControls({ slot, cam }: { slot: Slot; cam?: Camera }) {
  const { devices, cams, addSource } = useStore();
  const [pick, setPick] = useState<Device | null>(null);
  const [urlMode, setUrlMode] = useState(false);
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  // B-45: a source running in another slot (or in no slot) is disabled; this slot may re-pick its own (restart).
  const elsewhere = (d: Device) => cams.find((c) => c.source === d.source && c.slot !== slot);
  const opt = (d: Device, icon: string) => {
    const o = elsewhere(d);
    return { value: d.source as Val, label: d.name, icon, mono: typeof d.source === "string",
      disabled: !!o, meta: o ? (o.slot ? `In slot ${o.slot}` : "Running") : undefined };
  };
  const list = Array.isArray(devices) ? devices : [];
  const groups: SelectGroup<Val>[] = [
    { label: "iPhone", options: list.filter((d) => d.name === IPHONE).map((d) => opt(d, "mobile")) },
    { label: "Webcams", options: list.filter((d) => d.name !== IPHONE && typeof d.source === "number").map((d) => opt(d, "videocam")) },
    { label: "Stream URLs", options: list.filter((d) => typeof d.source === "string").map((d) => opt(d, "link")) },
    ...(devices === null ? [{ options: [{ value: "__loading" as Val, label: "Looking for cameras…", icon: "hourglass_empty", disabled: true }] }] : []),
    { options: [{ value: URL_OPT, label: "Stream URL…", icon: "link" }] },
  ].filter((g) => g.options.length);

  const start = async (source: Val, name: string | null) => {
    setBusy(true);
    const r = await addSource(source, name, slot);   // "" or `Rejected: …` (B-48); the URL is kept either way
    setMsg(r);
    setBusy(false);
    setPick(null);
  };
  const go = () => { const u = url.trim(); if (!busy && u) void start(u, null); };
  const value: Val | null = urlMode ? URL_OPT : pick?.source ?? cam?.source ?? null;
  const known = list.some((d) => d.source === value) || value === URL_OPT;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
      <Select<Val> className="min-w-0 flex-1" label={`Slot ${slot} source`} value={value} groups={groups} placeholder="Choose a camera or stream"
        valueLabel={!known && cam ? (typeof cam.source === "string" ? cam.source : cam.name) : undefined}
        mono={typeof value === "string" && value !== URL_OPT}
        supporting={busy && pick ? "Starting…" : undefined}
        onChange={(v, o) => {
          setMsg("");
          if (v === URL_OPT) { setUrlMode(true); setPick(null); return; }
          setUrlMode(false);
          if (busy) return;
          setPick({ source: v, name: o.label });
          void start(v, o.label);
        }} />
        {urlMode && <Button icon="add_link" disabled={!url.trim() || busy} onClick={go}>Add URL</Button>}
      </div>
      {urlMode && (
        <TextField label="Stream URL" mono dense value={url} onChange={setUrl} onEnter={go}
          placeholder="rtsp://… or http://192.168.43.20:8080/video" supporting="http, https or rtsp" />
      )}
      {msg && <p role="alert" className="px-1 text-body-s text-critical-text">{msg}</p>}
    </div>
  );
}

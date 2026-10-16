"use client";
import { useRef, useState } from "react";
import { SlotColumn } from "@/components/feed";
import { EmptyState, IconButton, Select, StatusChip, type SelectGroup } from "@/components/m3";
import { title } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Clip, Slot } from "@/lib/types";
import { Verdict, VerdictEmpty } from "./Verdict";

const UPLOAD = "__upload";

/** null loading · false error (B-39). */
export type Clips = Clip[] | null | false;

function groupsOf(clips: Clip[]): SelectGroup<string>[] {
  const by = new Map<string, Clip[]>();
  for (const c of clips) by.set(c.folder, [...(by.get(c.folder) ?? []), c]);
  return [
    ...[...by].map(([folder, list]) => ({
      label: folder,
      options: list.map((c) => ({ value: c.path, label: c.name, mono: true,
        badge: <StatusChip variant="neutral">{c.label ? title(c.label) : "Unlabelled"}</StatusChip>,
        meta: c.onset_s != null ? `${c.onset_s} s` : "—" })),
    })),
    { options: [{ value: UPLOAD, label: "Upload video", icon: "upload" }] },
  ];
}

/**
 * One Clips column (CONTRACT §4.3): the clip dropdown (choosing plays into THIS slot, B-41), upload by the dropdown
 * entry or by dropping a file on the column (B-42), per-column messages, the feed tile, and the Verdict below it.
 */
export function ClipSlot({ slot: k, clips }: { slot: Slot; clips: Clips }) {
  const { camInSlot, playClip, uploadClip } = useStore();
  const cam = camInSlot(k);
  const file = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const play = (path: string) => { setBusy(true); void playClip(path, k).then(setMsg).finally(() => setBusy(false)); };
  const upload = (f: File) => {
    setMsg(`Uploading ${f.name}…`); setBusy(true);
    void uploadClip(f, k).then(setMsg).finally(() => setBusy(false));
  };

  const list = clips || [];
  const path = typeof cam?.source === "string" ? cam.source : undefined;
  const inLibrary = !!path && list.some((c) => c.path === path);
  const status = clips === null ? { kind: "loading" as const, title: "Loading clips" }
    : clips === false ? { kind: "error" as const, title: "Could not load clips", body: "Check the server is running, then reload the page." }
    : undefined;
  // Empty library still offers the upload entry, under the B-39 empty copy (shown in the column).
  const groups = groupsOf(list);

  const controls = (
    <div className="min-w-0">
      <div className="flex items-center gap-1">
        <Select<string> className="min-w-0 flex-1" label={`Slot ${k} clip`} mono placeholder="Choose a clip" disabled={busy}
          value={cam ? (inLibrary ? path : null) : null}
          valueLabel={cam && !inLibrary ? cam.name : undefined}
          supporting={cam ? `${cam.label ? title(cam.label) : "Unlabelled"} · ${cam.onset_s != null ? `onset ${cam.onset_s} s` : "no onset"}` : undefined}
          status={status} groups={groups}
          onChange={(v) => (v === UPLOAD ? file.current?.click() : play(v))} />
        {inLibrary && <IconButton icon="replay" aria-label={`Play ${cam!.name} again`} tooltip="Play again from the start" disabled={busy} onClick={() => play(path!)} />}
      </div>
      <input ref={file} type="file" hidden accept=".mp4,.mov,.avi,.mkv,.m4v,.webm,.mpg,.mpeg,.wmv,.flv,.3gp,.ts,.mts,.m2ts"
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
      {msg && <p role="status" className={`mt-1.5 px-1 text-body-s ${msg.startsWith("Rejected") ? "text-critical-text" : "text-on-surface-variant"}`}>{msg}</p>}
      {clips && !clips.length && (
        <p className="mt-1.5 px-1 text-body-s text-on-surface-variant">
          <span className="text-on-surface">No clips found</span> · Copy videos into data/demo/ or data/dev/&lt;category&gt;/, or upload any video (mp4, mov, avi, mkv, webm, mpg and more, up to 500 MB).
        </p>
      )}
    </div>
  );

  return (
    <SlotColumn slot={k} cam={cam} controls={controls} onDropFile={upload}
      empty={<EmptyState compact icon="movie" title="No clip playing" body="Pick a clip from the dropdown above, or drop a video here." />}>
      {cam ? (cam.source_type === "file" && <Verdict cam={cam} />) : <VerdictEmpty />}
    </SlotColumn>
  );
}

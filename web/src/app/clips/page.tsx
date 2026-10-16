"use client";
import { useEffect, useState } from "react";
import { ClipSlot, type Clips } from "@/components/clips/ClipSlot";
import { FeedHeader, OtherSources } from "@/components/feed";
import { PageHeader, Skeleton, SkeletonLines } from "@/components/m3";
import { Page } from "@/components/shell";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { SLOTS } from "@/lib/types";

/** Placeholder column before the first metrics (B-9). */
function SkeletonColumn() {
  return (
    <div aria-busy="true" className="flex flex-col gap-3 rounded-xl bg-surface-container-low p-3">
      <Skeleton className="h-14 w-full" radius="lg" />
      <Skeleton className="aspect-video w-full" radius="lg" />
      <SkeletonLines lines={2} className="px-1" />
      <Skeleton className="h-64 w-full" radius="lg-plus" />
    </div>
  );
}

export default function ClipsPage() {
  const { mode } = useStore();
  const [clips, setClips] = useState<Clips>(null);
  useEffect(() => { api.clips().then(setClips).catch(() => setClips(false)); }, []);

  return (
    <Page wide className="pb-6">
      <PageHeader title="Clips"
        supporting="Play a labelled clip in any slot to see expected against detected, and the onset → alert time."
        actions={<FeedHeader mode="clips" />} />
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3 xl:gap-6">
        {SLOTS.map((k) => (mode === undefined ? <SkeletonColumn key={k} /> : <ClipSlot key={k} slot={k} clips={clips} />))}
      </div>
      <OtherSources className="mt-6" />
    </Page>
  );
}

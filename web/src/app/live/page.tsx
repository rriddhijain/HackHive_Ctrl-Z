"use client";
import { FeedHeader, OtherSources, SlotColumn } from "@/components/feed";
import { CameraDetails } from "@/components/live/CameraDetails";
import { DeviceNotice } from "@/components/live/DeviceNotice";
import { LiveControls } from "@/components/live/LiveControls";
import { Button, EmptyState, PageHeader, Skeleton } from "@/components/m3";
import { Page } from "@/components/shell";
import { useStore } from "@/lib/store";
import { SLOTS } from "@/lib/types";

/** Live tab (CONTRACT §4.3): three slots, each a webcam, the iPhone or a stream URL; details of each feed below it. */
export default function LivePage() {
  const { mode, camInSlot, rescan } = useStore();
  return (
    <Page wide className="pb-6">
      <PageHeader title="Live"
        supporting="Watch up to three cameras at once: pick a webcam, the iPhone or a stream URL for each slot and it starts."
        actions={<><Button variant="text" icon="refresh" onClick={rescan}>Rescan</Button><FeedHeader mode="live" /></>} />
      <DeviceNotice className="-mt-2 mb-4" />
      <div aria-busy={mode === undefined} className="grid grid-cols-1 items-start gap-4 lg:grid-cols-3 xl:gap-6">
        {SLOTS.map((k) => {
          if (mode === undefined) return (   // B-9: no metrics yet
            <div key={k} className="flex flex-col gap-3 rounded-xl bg-surface-container-low p-3">
              <Skeleton className="h-14 w-full" radius="lg" />
              <Skeleton className="aspect-video w-full" radius="lg" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          );
          const cam = camInSlot(k);
          return (
            <SlotColumn key={k} slot={k} cam={cam} controls={<LiveControls slot={k} cam={cam} />}
              empty={<EmptyState compact icon="videocam_off" title="Nothing running" body="Choose a camera or a stream URL above." />}>
              {cam && <CameraDetails cam={cam} />}
            </SlotColumn>
          );
        })}
      </div>
      <OtherSources className="mt-6" />
    </Page>
  );
}

"use client";
// Pipeline (FR-15, CONTRACT §3.14): the newest model call on one camera, stage by stage, then what the model saw and said.
import { ButtonGroup, EmptyState, PageHeader } from "@/components/m3";
import { Hero, HeroSkeleton } from "@/components/pipeline/Hero";
import { ModelInput } from "@/components/pipeline/ModelInput";
import { SystemGrid } from "@/components/pipeline/SystemGrid";
import { Waterfall } from "@/components/pipeline/Waterfall";
import { Page } from "@/components/shell";
import { useLive, useStore } from "@/lib/store";

export default function PipelinePage() {
  const { cams, pick, setPick } = useStore();
  const { traces, m } = useLive();
  // B-77: the picked camera, else the one with the newest trace, else the first; a vanished pick falls back.
  const newest = cams.filter((c) => traces[c.id]).sort((a, b) => traces[b.id].ts - traces[a.id].ts)[0];
  const cam = cams.find((c) => c.id === pick) ?? newest ?? cams[0];
  const t = cam ? traces[cam.id] : undefined;

  return (
    <Page className="pb-10">
      <PageHeader title="Pipeline" actions={cams.length > 1 && (
        <ButtonGroup aria-label="Camera" mono value={cam?.id} onChange={setPick}
          options={cams.map((c) => ({ value: c.id, label: c.id }))} />
      )} />
      <div className="flex flex-col gap-6">
        {cam ? (
          <>
            <Hero cam={cam} t={t} cm={m?.cameras?.[cam.id]} o2a={m?.latency?.onset_to_alert_ms} />
            <Waterfall t={t} />
            {t && <ModelInput t={t} />}
          </>
        ) : !m ? <HeroSkeleton /> : (
          <div className="rounded-xl-plus bg-surface-container-low">
            <EmptyState icon="account_tree" title="No sources running"
              body="Play a clip or add a camera. Every model call is traced here, stage by stage." />
          </div>
        )}
        <SystemGrid m={m} />
      </div>
    </Page>
  );
}

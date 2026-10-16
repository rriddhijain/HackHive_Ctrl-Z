"use client";
import { Button, ButtonGroup, Card, Chip, Icon, Shape, Tooltip } from "@/components/m3";
import { useStore } from "@/lib/store";
import { KeyHint } from "./Conversation";

/** B-70 suggestions, verbatim. */
export const SUGGEST = ["Show all tailgating events from camera 2 today", "What incidents happened in the last 10 minutes?",
  "Summarise the incidents in the lobby today", "How many fights were there?"];

const HANDOVER_TIP = "Shift-handover report: incidents first, what needs follow-up, then notable activity";
const WINDOWS = [{ value: 1 as const, label: "1 h" }, { value: 8 as const, label: "8 h" }, { value: 24 as const, label: "24 h" }];

/** Ask side panel (DESIGN §6.4): Shift handover (B-76), Try suggestions (B-70), the `/` hint (B-94). */
export function AskPanel({ send }: { send: (s: string) => void }) {
  const { busy, hours, setHours, handover } = useStore();
  return (
    <aside className="flex min-w-0 flex-col gap-4">
      <Card radius="xl" className="flex flex-col gap-5 p-5">
        <div className="flex items-start gap-4">
          <Shape name="clover4" size={44} className="shrink-0 text-tertiary-container">
            <Icon name="schedule" size={22} fill className="text-on-tertiary-container" />
          </Shape>
          <p className="pt-0.5 text-body-m text-on-surface-variant">{HANDOVER_TIP}</p>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-label-l text-on-surface-variant">Handover window</span>
          <ButtonGroup aria-label="Handover window" value={hours} onChange={setHours} options={WINDOWS} />
        </div>
        <Tooltip content={HANDOVER_TIP} className="w-full">
          <Button variant="tonal" icon="schedule" disabled={!!busy} onClick={() => void handover()} className="w-full">Shift handover</Button>
        </Tooltip>
      </Card>

      <Card radius="xl" className="flex flex-col gap-3 p-5">
        <span className="text-title-s-em text-on-surface">Try</span>
        <div className="flex flex-col items-start gap-2">
          {SUGGEST.map((s) => <Chip key={s} type="suggestion" wrap icon="arrow_outward" onClick={() => send(s)}>{s}</Chip>)}
        </div>
      </Card>

      <div className="flex items-center gap-2 px-2 text-body-s text-on-surface-variant">
        <KeyHint /> to ask
      </div>
    </aside>
  );
}

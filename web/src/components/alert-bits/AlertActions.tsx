"use client";
import { Button, Tooltip, type ButtonSize } from "@/components/m3";
import { statusWord } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Event } from "@/lib/types";

export const FALSE_ALARM_TIP = "Not an incident: hide it, count it in Report, keep it as a labelled example (FR-25)";
export const SEEDED_TIP = "Seeded demo history (E-19)";

/** §4.5: Acknowledge is enabled for open alerts and for closed critical ones (the old banner acked those). */
export const canAck = (e: Event) => e.status === "open" || (e.severity === "critical" && e.status === "closed");
/** §4.5: False alarm is enabled unless seeded or already dismissed. */
export const canDismiss = (e: Event) => !e.seeded && e.status !== "dismissed";

export interface AlertActionsProps {
  event: Event;
  size?: ButtonSize;
  /** Colour set: default surfaces, or inside a critical / high notification. */
  tone?: "default" | "critical" | "high";
  className?: string;
}

/**
 * The exactly-two actions of every alert (CONTRACT §4.5): False alarm, then Acknowledge. Disabled ones stay visible;
 * Acknowledge shows the status word (`Acknowledged` with a check, `Closed`) when it cannot act. Clicks never bubble,
 * so a card or notification does not open when an action is pressed.
 */
export function AlertActions({ event: e, size = "xs", tone = "default", className = "" }: AlertActionsProps) {
  const { ack, dismiss } = useStore();
  const okAck = canAck(e), okDis = canDismiss(e);
  return (
    <div className={`flex shrink-0 items-center gap-2 ${className}`} onClick={(x) => x.stopPropagation()}>
      <Tooltip content={FALSE_ALARM_TIP}>
        <Button size={size} tone={tone} variant={tone === "high" ? "text" : "outlined"} icon="report_off" disabled={!okDis}
          onClick={() => void dismiss(e.id)}>False alarm</Button>
      </Tooltip>
      <Button size={size} tone={tone} variant="filled" icon={okAck || e.status === "acknowledged" ? "check" : undefined} disabled={!okAck} onClick={() => void ack(e.id)}>
        {okAck ? "Acknowledge" : statusWord(e.status)}
      </Button>
    </div>
  );
}

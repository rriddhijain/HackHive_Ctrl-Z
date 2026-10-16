"use client";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AlertActions } from "@/components/alert-bits";
import { Icon, IconButton } from "@/components/m3";
import { conf, ist, pc, startTs, title } from "@/lib/format";
import { motionTokens } from "@/lib/motion";
import { useStore } from "@/lib/store";
import type { Event } from "@/lib/types";

const HIDE_MS = 8000;

/** One notification card (critical red / high amber) with the two actions; the body opens the alert's report. High also has a close. */
export function Notification({ e }: { e: Event }) {
  const { camName, openEvent, closeNotification } = useStore();
  const crit = e.severity === "critical";
  const [hold, setHold] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => {   // high auto-hides after 8 s, paused while hovered or focused
    if (crit || hold) return;
    timer.current = setTimeout(() => closeNotification(e.id), HIDE_MS);
    return () => clearTimeout(timer.current);
  }, [crit, hold, e.id, closeNotification]);
  const tone = crit ? "critical" : "high";
  return (
    <motion.div layout role={crit ? "alert" : "status"} data-notification={e.id}
      initial={{ x: 32 }} animate={{ x: 0 }} exit={{ x: 32, opacity: 0 }} transition={motionTokens.default}
      onMouseEnter={() => setHold(true)} onMouseLeave={() => setHold(false)} onFocus={() => setHold(true)} onBlur={() => setHold(false)}
      className={`pointer-events-auto w-full rounded-lg p-4 shadow-level-3 ${crit ? "bg-critical text-on-critical" : "bg-high text-on-high"}`}>
      <div className="flex items-start gap-1">
        <button type="button" onClick={() => openEvent(e.id)} aria-label={`Open the report of event ${e.id}`}
          className="state-layer -m-2 flex min-w-0 flex-1 items-start gap-3 rounded-md p-2 text-left focus-visible:outline-current">
          <Icon name={crit ? "error" : "warning"} size={24} fill />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-title-m-em">{`${crit ? "Critical" : "High"} · ${title(e.category)}`}</span>
            <span className="mt-0.5 block truncate text-body-m opacity-90">
              <span className="font-mono">{ist(startTs(e))} IST</span> · <span className="font-mono">{pc(conf(e))}</span> · {camName(e)}
            </span>
          </span>
          <Icon name="arrow_forward" size={20} className="mt-0.5 opacity-80" />
        </button>
        {/* A critical stays until Acknowledge or False alarm (§4.4, B-61): no close. */}
        {!crit && <IconButton icon="close" size="xs" tone={tone} aria-label="Close" tooltip={false} onClick={() => closeNotification(e.id)} className="-mr-2 -mt-1" />}
      </div>
      <AlertActions event={e} tone={tone} className="mt-3 justify-end" />
    </motion.div>
  );
}

/**
 * Notification stack (CONTRACT §4.4): bottom-right on every route except /alerts/, clear of the page-header actions.
 * Critical: the B-61 set, sticky until acknowledged or marked false alarm; collapsed to the newest with a
 * `${n - 1} more unacknowledged` pill that expands the rest. High: live alerts, auto-hide after 8 s, listed below.
 */
export function Notifications() {
  const path = usePathname() ?? "";
  const { notifications } = useStore();
  const [all, setAll] = useState(false);
  if (path.startsWith("/alerts")) return null;
  const crit = notifications.filter((e) => e.severity === "critical");
  const high = notifications.filter((e) => e.severity !== "critical");
  const shown = all ? crit : crit.slice(0, 1);
  const hidden = crit.length - shown.length;
  return (
    <div aria-label="Notifications" className="pointer-events-none fixed bottom-6 right-6 z-40 flex max-h-[calc(100vh-96px)] w-100 flex-col justify-end gap-2 overflow-y-auto overflow-x-hidden p-1">
      <LayoutGroup>
        <AnimatePresence mode="popLayout" initial={false}>
          {shown.map((e) => <Notification key={e.id} e={e} />)}
          {hidden > 0 && (
            <motion.button key="more" layout type="button" onClick={() => setAll(true)}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={motionTokens.default}
              className="state-layer pointer-events-auto self-end rounded-full bg-inverse-surface px-4 py-2 text-label-l text-inverse-on-surface shadow-level-2">
              {`${hidden} more unacknowledged`}
            </motion.button>
          )}
          {high.map((e) => <Notification key={e.id} e={e} />)}
        </AnimatePresence>
      </LayoutGroup>
    </div>
  );
}

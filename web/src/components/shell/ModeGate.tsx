"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { Button, Dialog } from "@/components/m3";
import { useStore } from "@/lib/store";
import type { Mode } from "@/lib/types";

const routeMode = (p: string): Mode | null => (p.startsWith("/clips") ? "clips" : p.startsWith("/live") ? "live" : null);
const Name = { clips: "Clips", live: "Live" };

/**
 * CONTRACT §4.2: entering /clips/ or /live/ when the backend is in the other mode switches at once if no source is
 * listed (any status), else asks first. Cancel leaves the backend alone and returns to the previous tab.
 */
export function ModeGate() {
  const path = usePathname() ?? "";
  const router = useRouter();
  const { mode, ready, cams, gate, requestMode, confirmGate, cancelGate } = useStore();
  const prev = useRef<string | null>(null);
  const last = useRef(path);
  useEffect(() => {
    if (last.current !== path) { prev.current = last.current; last.current = path; }
    const want = routeMode(path);
    if (want && ready) requestMode(want);   // waits for both the mode and the camera list (no silent switch on a cold load)
  }, [path, ready, requestMode]);
  const cancel = () => {
    cancelGate();
    const back = prev.current && routeMode(prev.current) !== gate ? prev.current : mode ? `/${mode}/` : "/alerts/";
    router.replace(back);
  };
  const n = cams.length;
  return (
    <Dialog open={gate != null} onClose={cancel} role="alertdialog" icon="swap_horiz"
      headline={gate ? `Switch to ${Name[gate]} mode?` : ""}
      actions={<>
        <Button variant="text" data-autofocus onClick={cancel}>Cancel</Button>
        <Button variant="filled" onClick={confirmGate}>{gate ? `Switch to ${Name[gate]}` : ""}</Button>
      </>}>
      {`This stops ${n} source${n === 1 ? "" : "s"} and clears their verdicts. Alert history is kept.`}
    </Dialog>
  );
}

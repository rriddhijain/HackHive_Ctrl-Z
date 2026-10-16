"use client";
import { Icon } from "@/components/m3";
import { useStore } from "@/lib/store";
import { IPHONE } from "./LiveControls";

/** B-44 error / empty copy and the B-46 iPhone hint, once for the page rather than once per column. */
export function DeviceNotice({ className = "" }: { className?: string }) {
  const { devices } = useStore();
  if (devices === null) return null;
  const line = (icon: string, text: string, err = false) => (
    <p key={icon} className={`flex items-start gap-2 text-body-m ${err ? "text-critical-text" : "text-on-surface-variant"}`}>
      <Icon name={icon} size={20} className="shrink-0" />{text}
    </p>
  );
  const rows = devices === false ? [line("error", "Could not list cameras. Rescan, or reload the page.", true)] : [
    ...(!devices.length ? [line("videocam_off", "No cameras found. Check camera permission, or add a stream URL.")] : []),
    ...(!devices.some((d) => d.name === IPHONE)
      ? [line("mobile", "No iPhone listed: it must be on this Mac's Apple Account with Bluetooth and Wi‑Fi on, unlocked nearby or on a USB cable, and not in use by another Mac. Then Rescan.")]
      : []),
  ];
  return rows.length ? <div className={`flex flex-col gap-1 ${className}`}>{rows}</div> : null;
}

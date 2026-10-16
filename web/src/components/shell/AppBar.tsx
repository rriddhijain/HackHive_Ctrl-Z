"use client";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Badge, Icon } from "@/components/m3";
import { motionTokens } from "@/lib/motion";
import { useStore } from "@/lib/store";
import { Logo } from "./Logo";
import { StatusCluster } from "./StatusCluster";

export const TABS = [
  { key: "clips", label: "Clips", icon: "video_library" },
  { key: "live", label: "Live", icon: "videocam" },
  { key: "alerts", label: "Alerts", icon: "notifications" },
  { key: "ask", label: "Ask", icon: "forum" },
  { key: "pipeline", label: "Pipeline", icon: "account_tree" },
  { key: "report", label: "Report", icon: "monitoring" },
] as const;
export type TabKey = (typeof TABS)[number]["key"];

/**
 * Top app bar (DESIGN §5.1): logo + wordmark, six route tabs with a sliding pill (layoutId), filled icon when active,
 * the open-alert badge on Alerts, a dot on the tab whose mode the backend is in, and the status cluster.
 */
export function AppBar() {
  const path = usePathname() ?? "/";
  const { nOpen, anyOpenCritical, mode } = useStore();
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const f = () => setScrolled(window.scrollY > 0);
    f(); window.addEventListener("scroll", f, { passive: true });
    return () => window.removeEventListener("scroll", f);
  }, []);
  return (
    <header className={`sticky top-0 z-30 flex h-16 shrink-0 items-center gap-3 px-4 transition-[background-color,box-shadow] duration-200 xl:px-6
      ${scrolled ? "bg-surface-container shadow-level-2" : "bg-surface"}`}>
      <Link href="/" className="flex shrink-0 items-center gap-3 rounded-full focus-visible:outline-offset-4" aria-label="HackHive home">
        <Logo />
        <span className="text-title-l-em text-on-surface">HackHive</span>
        <span className="hidden text-body-m text-on-surface-variant min-[2000px]:inline">Incident console</span>
      </Link>
      <nav aria-label="Main" className="flex min-w-0 items-center gap-0.5 cluster:gap-1">
        {TABS.map((t) => {
          const on = path.startsWith(`/${t.key}`);
          return (
            <div key={t.key} className="relative">
              <Link href={`/${t.key}/`} aria-current={on ? "page" : undefined} aria-keyshortcuts={t.key === "ask" ? "/" : undefined}
                className={`state-layer relative flex h-10 items-center gap-1.5 rounded-full px-2.5 cluster:gap-2 cluster:px-4 ${on ? "text-label-l-em text-on-secondary-container" : "text-label-l text-on-surface-variant"}`}>
                {on && <motion.span layoutId="nav-pill" transition={motionTokens.default} className="absolute inset-0 -z-[1] rounded-full bg-secondary-container" />}
                <span className={`relative ${t.key === "alerts" && nOpen > 0 ? "mr-1.5" : ""}`}>
                  <Icon name={t.icon} size={20} fill={on} />
                  {t.key === "alerts" && <Badge count={nOpen} tone={anyOpenCritical ? "critical" : "primary"} className="absolute -right-2.5 -top-1.5" />}
                  {(t.key === "clips" || t.key === "live") && mode === t.key && <Badge className="absolute -right-0.5 -top-0.5" />}
                </span>
                <span className="relative">{t.label}</span>
                {t.key === "ask" && !on && (   // B-94: the "/" key is always visible
                  <kbd aria-hidden="true" className="relative -mr-1 inline-grid h-5 min-w-5 place-items-center rounded-xs border border-outline-variant px-1 font-mono text-label-s text-on-surface-variant">/</kbd>
                )}
                {t.key === "alerts" && nOpen > 0 && <span className="sr-only">{`, ${nOpen} open`}</span>}
              </Link>
            </div>
          );
        })}
      </nav>
      <div className="ml-auto shrink-0"><StatusCluster /></div>
    </header>
  );
}

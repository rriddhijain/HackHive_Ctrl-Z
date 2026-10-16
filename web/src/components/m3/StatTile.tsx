"use client";
import type { ReactNode } from "react";
import type { ShapeName } from "@/lib/shapes";
import { Icon } from "./Icon";
import { Shape } from "./Shape";
import { Tooltip } from "./Tooltip";

export interface StatTileProps {
  label: string;
  /** Formatted value (already through ms / pc / v). */
  value: string;
  sub?: ReactNode;
  icon?: string;
  /** Accuracy tiles cookie9, operator clover8, latency pill (DESIGN §2.4). */
  shape?: ShapeName;
  tone?: "accuracy" | "operator" | "latency";
  /** Draw the value in critical-text (e.g. store → card p95 over budget). */
  critical?: boolean;
  /** Value in mono (ids). */
  mono?: boolean;
  /** Rich tooltip body (verbatim CONTRACT copy). */
  tooltip?: string;
  className?: string;
}

const TONE = {
  accuracy: "text-primary-fixed [&_.ic]:text-on-primary-fixed-variant",
  operator: "text-tertiary-fixed [&_.ic]:text-on-tertiary-fixed-variant",
  latency: "text-secondary-fixed [&_.ic]:text-on-secondary-fixed-variant",
};

/** KPI tile (DESIGN §5.21). Static value (no number tweening); focusable when it has a tooltip. */
export function StatTile({ label, value, sub, icon, shape = "cookie9", tone = "accuracy", critical, mono, tooltip, className = "" }: StatTileProps) {
  const tile = (
    <div tabIndex={tooltip ? 0 : undefined}
      className={`flex min-h-32 w-full flex-col justify-between gap-3 rounded-lg-plus bg-surface-container p-5 ${tooltip ? "state-layer" : ""} ${className}`}>
      <div className="flex items-start gap-3">
        {icon && <span className={TONE[tone]}><Shape name={shape} size={40}><Icon name={icon} size={20} className="ic" /></Shape></span>}
        <span className="line-clamp-2 pt-0.5 text-label-l text-on-surface-variant">{label}</span>
      </div>
      <div>
        <div className={`text-headline-m-em ${mono ? "font-mono" : ""} ${critical ? "text-critical-text" : "text-on-surface"}`}>{value}</div>
        {sub && <div className="mt-0.5 text-body-s text-on-surface-variant">{sub}</div>}
      </div>
    </div>
  );
  return tooltip ? <Tooltip rich={{ body: tooltip }} className="w-full">{tile}</Tooltip> : tile;
}

import { StatusChip } from "@/components/m3";

/** CRITICAL (solid red, white) or HIGH (amber, dark); medium has no chip (B-54). */
export function SeverityChip({ severity, className = "" }: { severity: string; className?: string }) {
  if (severity === "critical") return <StatusChip variant="critical" className={className}>CRITICAL</StatusChip>;
  if (severity === "high") return <StatusChip variant="high" className={className}>HIGH</StatusChip>;
  return null;
}

/** Severity → dot / stripe tone: critical red, high amber, medium and unknown grey. */
export const sevTone = (s: string): "critical" | "high" | "neutral" => (s === "critical" ? "critical" : s === "high" ? "high" : "neutral");

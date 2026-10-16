import type { ReactNode } from "react";

/**
 * Page frame under the app bar (DESIGN §6.1): 24 px side margins (16 below 1280 px). `wide` = full width (Clips, Live);
 * otherwise centred at 1600 px max (Alerts, Ask, Pipeline, Report).
 */
export function Page({ wide, children, className = "" }: { wide?: boolean; children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full px-4 xl:px-6 ${wide ? "" : "max-w-[1648px]"} ${className}`}>{children}</div>;
}

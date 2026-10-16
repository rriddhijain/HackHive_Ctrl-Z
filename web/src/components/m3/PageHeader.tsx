import type { ReactNode } from "react";

export interface PageHeaderProps {
  title: ReactNode;
  supporting?: ReactNode;
  /** Right-aligned actions. */
  actions?: ReactNode;
  className?: string;
}

/** Page header for Alerts, Ask, Pipeline, Report (DESIGN §5.22): 32 px top, headline-s emphasized, 24 px below. */
export function PageHeader({ title, supporting, actions, className = "" }: PageHeaderProps) {
  return (
    <header className={`flex flex-wrap items-end justify-between gap-x-6 gap-y-3 pb-6 pt-8 ${className}`}>
      <div className="min-w-0">
        <h1 className="text-headline-s-em text-on-surface">{title}</h1>
        {supporting && <p className="mt-1 text-body-m text-on-surface-variant">{supporting}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

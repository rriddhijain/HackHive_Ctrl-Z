import type { ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "right";
  mono?: boolean;
  /** CSS width, e.g. "38%" or "80px". */
  width?: string;
}
export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  /** Row tooltip (e.g. the clip summary, B-89). */
  rowTitle?: (row: T) => string | undefined;
  /** Max height with a sticky header that stays while the body scrolls. */
  maxHeight?: number | string;
  "aria-label"?: string;
  className?: string;
}

/** M3 data table (DESIGN §5.14): 40 px header, 44 px rows, outline-variant dividers, no zebra, row hover tint (no state-layer: a ::before on <tr> becomes an extra cell). */
export function DataTable<T>({ columns, rows, rowKey, rowTitle, maxHeight, className = "", ...aria }: DataTableProps<T>) {
  return (
    <div className={`overflow-auto ${className}`} style={maxHeight != null ? { maxHeight } : undefined}>
      <table aria-label={aria["aria-label"]} className="w-full table-fixed border-collapse text-body-m">
        <thead className="sticky top-0 z-10 bg-surface-container">
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" style={c.width ? { width: c.width } : undefined}
                className={`h-10 px-4 text-label-l font-medium text-on-surface-variant ${c.align === "right" ? "text-right" : "text-left"}`}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} title={rowTitle?.(r)} className="border-t border-outline-variant hover:bg-on-surface/8">
              {columns.map((c) => (
                <td key={c.key} className={`h-11 truncate px-4 ${c.align === "right" ? "text-right" : ""} ${c.mono ? "font-mono text-body-s" : ""}`}>{c.render(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

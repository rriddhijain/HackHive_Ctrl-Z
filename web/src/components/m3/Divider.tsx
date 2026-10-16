export interface DividerProps { vertical?: boolean; inset?: boolean; className?: string }

/** 1 px outline-variant divider. */
export function Divider({ vertical, inset, className = "" }: DividerProps) {
  return vertical
    ? <span role="separator" aria-orientation="vertical" className={`inline-block w-px shrink-0 self-stretch bg-outline-variant ${inset ? "my-2.5" : ""} ${className}`} />
    : <hr className={`h-px border-0 bg-outline-variant ${inset ? "mx-4" : ""} ${className}`} />;
}

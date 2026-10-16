"use client";
import { motion } from "motion/react";
import { useId, useState, type InputHTMLAttributes, type KeyboardEvent, type ReactNode, type Ref } from "react";
import { motionTokens } from "@/lib/motion";
import { Icon } from "./Icon";

type Native = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "size" | "className" | "style">;

export interface TextFieldProps extends Native {
  value: string;
  onChange: (value: string) => void;
  /** outlined (default) · filled · search (Ask: 56 px pill on surface-container-high). */
  variant?: "outlined" | "filled" | "search";
  /** Floating label (outlined / filled). */
  label?: string;
  leadingIcon?: string;
  trailingIcon?: string;
  /** Trailing content, e.g. the `/` hint and the send icon button. */
  trailing?: ReactNode;
  /** Supporting text under the field. */
  supporting?: ReactNode;
  /** Error: true or a message (replaces the supporting text, critical-text). */
  error?: boolean | string;
  mono?: boolean;
  /** 48 px instead of 56. */
  dense?: boolean;
  onEnter?: () => void;
  inputRef?: Ref<HTMLInputElement>;
  className?: string;
}

/** M3 text field (DESIGN §5.8): outlined with a floating label, filled, or the Ask search bar. */
export function TextField({ value, onChange, variant = "outlined", label, leadingIcon, trailingIcon, trailing, supporting, error, mono, dense,
  onEnter, inputRef, className = "", id: idProp, placeholder, onKeyDown, onFocus, onBlur, disabled, ...rest }: TextFieldProps) {
  const auto = useId(), id = idProp ?? auto;
  const [focus, setFocus] = useState(false);
  const float = focus || value !== "";
  const err = !!error;
  const keys = (e: KeyboardEvent<HTMLInputElement>) => { onKeyDown?.(e); if (e.key === "Enter" && onEnter && !e.defaultPrevented) { e.preventDefault(); onEnter(); } };
  const h = dense ? "h-12" : "h-14";
  const frame = variant === "search"
    ? `${h} rounded-full bg-surface-container-high ${focus ? "ring-2 ring-primary" : ""}`
    : variant === "filled"
      ? `${h} rounded-t-xs bg-surface-container-highest border-b ${err ? "border-critical-text" : focus ? "border-b-2 border-primary" : "border-on-surface-variant"}`
      : `${h} rounded-xs border ${err ? "border-2 border-critical-text" : focus ? "border-2 border-primary" : "border-outline hover:border-on-surface"}`;
  const input = (
    <input {...rest} id={id} ref={inputRef} value={value} disabled={disabled} onChange={(e) => onChange(e.target.value)} onKeyDown={keys}
      onFocus={(e) => { setFocus(true); onFocus?.(e); }} onBlur={(e) => { setFocus(false); onBlur?.(e); }}
      placeholder={variant === "search" || !label || float ? placeholder : undefined} aria-invalid={err || undefined}
      aria-describedby={supporting || typeof error === "string" ? `${id}-sup` : undefined}
      className={`h-full min-w-0 flex-1 bg-transparent text-on-surface outline-none placeholder:text-on-surface-variant disabled:text-on-surface/38
        ${mono ? "font-mono text-body-m" : "text-body-l"} ${label && variant !== "search" ? "pt-3" : ""} focus-visible:outline-none`} />
  );
  return (
    <div className={className}>
      <div className={`relative flex items-center gap-3 ${frame} ${leadingIcon ? "pl-3" : "pl-4"} ${trailing || trailingIcon || err ? "pr-2" : "pr-4"}`}>
        {leadingIcon && <Icon name={leadingIcon} size={24} className="text-on-surface-variant" />}
        <div className="relative flex h-full min-w-0 flex-1 items-center">
          {label && variant !== "search" && (
            <motion.label htmlFor={id} initial={false} animate={{ y: float ? -11 : 0, scale: float ? 0.75 : 1 }} transition={motionTokens.fast}
              style={{ originX: 0 }}
              className={`pointer-events-none absolute left-0 top-1/2 -mt-3 truncate text-body-l leading-6 ${err ? "text-critical-text" : focus ? "text-primary" : "text-on-surface-variant"}`}>
              {label}
            </motion.label>
          )}
          {input}
        </div>
        {err ? <Icon name="error" size={24} className="text-critical-text" /> : trailingIcon && <Icon name={trailingIcon} size={24} className="text-on-surface-variant" />}
        {trailing}
      </div>
      {(supporting || typeof error === "string") && (
        <div id={`${id}-sup`} className={`mt-1 px-4 text-body-s ${err ? "text-critical-text" : "text-on-surface-variant"}`}>
          {typeof error === "string" ? error : supporting}
        </div>
      )}
    </div>
  );
}

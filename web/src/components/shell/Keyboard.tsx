"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useStore } from "@/lib/store";

/**
 * Global keys (B-94, B-95): "/" (outside inputs) goes to Ask and focuses its input; Esc closes the alert report
 * (/alerts/?id= → /alerts/) when no menu or dialog is open: those handle their own Esc. A tooltip does not block
 * either key (it hides itself on Esc alongside).
 */
export function Keyboard() {
  const router = useRouter();
  const path = usePathname() ?? "";
  const { askRef } = useStore();
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      const overlay = document.querySelector("[data-overlay]:not([data-overlay=tooltip])");
      const el = document.activeElement as HTMLElement | null;
      if (e.key === "/" && !overlay && !/^(INPUT|TEXTAREA|SELECT)$/.test(el?.tagName ?? "") && !el?.isContentEditable) {
        e.preventDefault();
        if (!path.startsWith("/ask")) router.push("/ask/");
        const focus = (n: number) => (askRef.current ? askRef.current.focus() : n > 0 && setTimeout(() => focus(n - 1), 50));
        focus(40);
      } else if (e.key === "Escape" && !overlay && path.startsWith("/alerts") && new URLSearchParams(window.location.search).has("id")) {
        router.push("/alerts/");
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [router, path, askRef]);
  return null;
}

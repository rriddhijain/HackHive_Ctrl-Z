"use client";
import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";
import { motionTokens } from "@/lib/motion";
import { StoreProvider } from "@/lib/store";

/** Root client providers: the store and motion config (reduced motion follows the OS, B-96). */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <StoreProvider>
      <MotionConfig reducedMotion="user" transition={motionTokens.default}>{children}</MotionConfig>
    </StoreProvider>
  );
}

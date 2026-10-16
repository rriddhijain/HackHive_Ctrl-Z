import type { Transition } from "motion/react";

// Basic motion (captain, 19:15): short, non-bouncy tweens only. Fades for menus/dialogs/tooltips/notifications,
// the nav pill slide; no springs, no press morph, no number tweening. M3 standard easing.
const tween = (duration: number): Transition => ({ type: "tween", duration, ease: [0.2, 0, 0, 1] });

export const motionTokens = {
  fast: tween(0.15),
  default: tween(0.2),
  slow: tween(0.25),
} as const;

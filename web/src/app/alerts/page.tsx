"use client";
import { Suspense } from "react";
import { AlertsView } from "@/components/alerts/AlertsView";

// useSearchParams (?id=) must sit inside <Suspense> or the static build fails (COMPONENTS §7).
export default function AlertsPage() {
  return <Suspense><AlertsView /></Suspense>;
}

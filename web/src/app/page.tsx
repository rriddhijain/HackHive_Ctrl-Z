"use client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingIndicator } from "@/components/m3";
import { useStore } from "@/lib/store";

// "/" has no server redirect under static export: go to the tab of the backend's mode (Clips until metrics say otherwise).
export default function Home() {
  const router = useRouter();
  const { mode } = useStore();
  useEffect(() => {
    if (mode) { router.replace(`/${mode}/`); return; }
    const t = setTimeout(() => router.replace("/clips/"), 1500);
    return () => clearTimeout(t);
  }, [mode, router]);
  return <div className="grid flex-1 place-items-center"><LoadingIndicator aria-label="Loading" /></div>;
}

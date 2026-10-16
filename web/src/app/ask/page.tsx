"use client";
import { useEffect, useState } from "react";
import { AskPanel } from "@/components/ask/AskPanel";
import { Conversation } from "@/components/ask/Conversation";
import { PageHeader } from "@/components/m3";
import { Page } from "@/components/shell";
import { useStore } from "@/lib/store";

/** Ask (B-69…B-76): conversation + side panel. The log, session and busy state live in the store (survive tab switches). */
export default function AskPage() {
  const { ask, askRef } = useStore();
  const [q, setQ] = useState("");
  const send = (text: string) => { void ask(text).then((clear) => clear && setQ("")); };
  useEffect(() => {   // "/" from another tab focuses via Keyboard; ?focus=1 deep links focus here
    if (new URLSearchParams(window.location.search).get("focus") === "1") askRef.current?.focus();
  }, [askRef]);
  return (
    <Page className="pb-6">
      <PageHeader title="Ask" />
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <Conversation q={q} setQ={setQ} send={send} />
        <AskPanel send={send} />
      </div>
    </Page>
  );
}

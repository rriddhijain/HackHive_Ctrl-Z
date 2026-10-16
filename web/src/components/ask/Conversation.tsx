"use client";
import { useEffect, useRef, type ReactElement } from "react";
import { Button, Chip, EmptyState, Icon, Shape, SkeletonLines, TextField, Tooltip } from "@/components/m3";
import { how, ist, media, title } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { ChatEntry, Event } from "@/lib/types";

/** `/` key hint (B-72, B-94). */
export const KeyHint = () => (
  <kbd className="inline-grid h-6 min-w-6 place-items-center rounded-sm border border-outline-variant px-1.5 font-mono text-label-m text-on-surface-variant">/</kbd>
);

const withTip = (tip: string | null | undefined, el: ReactElement, key: number) =>
  tip ? <Tooltip key={key} content={tip}>{el}</Tooltip> : <span key={key} className="inline-flex">{el}</span>;

const Question = ({ text }: { text: string }) => (
  <div className="flex justify-end">
    <div className="max-w-[80%] whitespace-pre-wrap rounded-lg rounded-br-xs bg-primary-container px-4 py-2.5 text-body-l text-on-primary-container">{text}</div>
  </div>
);

/** Leading mark of an answer: a static expressive shape (no motion). */
const Mark = ({ error }: { error?: boolean }) => (
  <Shape name="cookie9" size={36} className={`shrink-0 ${error ? "text-surface-container-highest" : "text-secondary-container"}`}>
    <Icon name={error ? "error" : "forum"} size={18} fill className={error ? "text-critical-text" : "text-on-secondary-container"} />
  </Shape>
);

/** B-73 citations: a `[#id]` whose id is in `events` becomes a chip that opens that alert's report. */
function Cited({ a }: { a: ChatEntry }) {
  const { openEvent } = useStore();
  return (
    <>
      {a.answer.split(/(\[#\d+\])/).map((s, i) => {
        const e = /^\[#\d+\]$/.test(s) && a.events.find((ev) => ev.id === +s.slice(2, -1));
        return e ? (
          <Chip key={i} dense mono title={`Open event ${e.id}`} onClick={() => openEvent(e)} className="mx-0.5">#{e.id}</Chip>
        ) : s;
      })}
    </>
  );
}

/** B-74 key-frame strip, one thumbnail per cited event with a key frame. */
function Frames({ events }: { events: Event[] }) {
  const { openEvent } = useStore();
  const withFrame = events.filter((e) => e.keyframe_paths?.[0]);
  if (!withFrame.length) return null;
  return (
    <div data-frames className="mt-4 flex gap-3 overflow-x-auto pb-1">
      {withFrame.map((e) => withTip(e.summary, (
        <button type="button" onClick={() => openEvent(e)} className="state-layer w-40 shrink-0 rounded-md p-0 text-left">
          <img src={media(e.keyframe_paths![0])} alt="" className="block h-[90px] w-40 rounded-md bg-surface-container-highest object-cover" />
          <div className="mt-1.5 truncate px-0.5 font-mono text-label-m text-on-surface">{`#${e.id} · ${ist(e.start_ts)}`}</div>
          <div className="truncate px-0.5 text-body-s text-on-surface-variant">{`${title(e.category)} · ${e.camera_name}`}</div>
        </button>
      ), e.id))}
    </div>
  );
}

function Answer({ a, n }: { a: ChatEntry; n: number }) {
  return (
    <div data-answer={n} className="flex flex-col gap-4">
      <Question text={a.question} />
      <div className="flex gap-3">
        <Mark error={a.error} />
        <div className="min-w-0 flex-1 pt-1.5">
          <div className={`whitespace-pre-wrap text-body-l ${a.error ? "text-critical-text" : "text-on-surface"}`}><Cited a={a} /></div>
          {a.error && <div className="mt-1 text-body-m text-on-surface-variant">Reload the page (⌘R) and ask again.</div>}
          <Frames events={a.events} />
          {!a.error && (
            <div data-how className="mt-3 font-mono text-body-s text-on-surface-variant">
              {`${how(a.how)} · as of ${ist(a.as_of)} IST · ${a.latency_ms} ms`}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Conversation surface (DESIGN §6.4): scrolling log over the docked search-bar input (B-70…B-75). */
export function Conversation({ q, setQ, send }: { q: string; setQ: (s: string) => void; send: (s: string) => void }) {
  const { chat, busy, askRef } = useStore();
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {   // B-71: newest in view on every change (also when returning to the tab)
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat, busy]);
  const empty = !chat.length && !busy;
  return (
    <section aria-label="Conversation"
      className="flex h-[max(480px,70dvh)] min-w-0 flex-col overflow-hidden rounded-xl-plus bg-surface-container-low lg:h-[max(520px,calc(100dvh-176px))]">
      <div ref={scroller} className="mt-2 min-h-0 flex-1 overflow-y-auto px-4 pt-4 [mask-image:linear-gradient(to_bottom,transparent_0,black_24px)] sm:px-6" aria-live="polite" aria-busy={!!busy || undefined}>
        {empty ? (
          <div className="flex h-full items-center justify-center">
            <EmptyState icon="forum" title="Ask about incidents" body="Answers come only from stored events. Every #id opens that event." />
          </div>
        ) : (
          <div className="mx-auto flex max-w-[880px] flex-col gap-8 pb-6">
            {chat.map((a, i) => <Answer key={i} a={a} n={i + 1} />)}
            {busy && (
              <div className="flex flex-col gap-4">
                <Question text={busy} />
                <div className="flex gap-3">
                  <Mark />
                  <SkeletonLines lines={3} className="min-w-0 flex-1 pt-3" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <div className="shrink-0 px-4 pb-4 pt-2 sm:px-6">
        <TextField variant="search" leadingIcon="search" className="mx-auto max-w-[880px]" aria-label="Ask about incidents"
          placeholder="Ask about incidents" value={q} onChange={setQ} onEnter={() => send(q)} inputRef={askRef}
          trailing={(
            <>
              {!q && <KeyHint />}
              <Button icon="send" disabled={!!busy || !q.trim()} onClick={() => send(q)}>Ask</Button>
            </>
          )} />
      </div>
    </section>
  );
}

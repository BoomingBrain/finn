import { useEffect, useSyncExternalStore } from "react";
import { apiBase, loadData } from "../api/client";
import type { Dossier, SectionEvent } from "../api/types";

export type ResearchError = { code: string; message: string };
export type BuildProgress = { done: number; total: number; label: string };
export type Research = {
  sections: SectionEvent[];
  done: boolean;
  waking: boolean;
  error: ResearchError | null;
  progress: BuildProgress | null; // live builds only: completed steps, reported by the server as they happen
  ahead: number | null; // live builds waiting in line: analyses that must finish first
  live: boolean; // built on the server now, not a bundled file
};

const EMPTY: Research = { sections: [], done: false, waking: false, error: null, progress: null, ahead: null, live: false };
const WAKING_AFTER_MS = 5_000;

export function unreachable(symbol: string): ResearchError {
  return { code: "sources_unreachable", message: `Couldn't fetch sources for ${symbol} from the server.` };
}

/** Fixed copy for the server's refusals (decided before any work starts). */
export function refusal(symbol: string, status: number, code: string | undefined): ResearchError {
  if (status === 404) return { code: "unknown_symbol", message: `FINN can't find ${symbol} on NSE.` };
  if (code === "rate_limited")
    return { code, message: "You've started 20 new analyses this hour. Try again later; ready companies still open instantly." };
  if (code === "budget_exhausted")
    return { code, message: "Today's AI budget for live research is used up. Precomputed tickers still work." };
  return unreachable(symbol);
}

export type SSEMessage = { event: string; data: string };

/** Splits a text/event-stream body into complete messages; returns them plus the unfinished tail. */
export function parseSSE(buffer: string): { messages: SSEMessage[]; rest: string } {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  const messages = blocks
    .map((block) => {
      let event = "message";
      const data: string[] = [];
      for (const line of block.split("\n")) {
        if (line.startsWith(":")) continue; // keep-alive comment
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data.push(line.slice(6));
      }
      return { event, data: data.join("\n") };
    })
    .filter((m) => m.data !== "" || m.event !== "message");
  return { messages, rest };
}

/** How one server message changes a build's state. Pure, so it can be tested. */
export function applyMessage(state: Research, m: SSEMessage): Research {
  switch (m.event) {
    case "queued":
      return { ...state, waking: false, ahead: JSON.parse(m.data).ahead };
    case "progress":
      return { ...state, waking: false, ahead: null, progress: JSON.parse(m.data) };
    case "done":
      return { ...state, done: true, ahead: null };
    case "error":
      return { ...state, waking: false, ahead: null, error: JSON.parse(m.data), done: true };
    default:
      return { ...state, waking: false, ahead: null, sections: [...state.sections, JSON.parse(m.data) as SectionEvent] };
  }
}

/*
 * One store for the whole app, outside any screen: a live build keeps streaming while the investor reads the Brief,
 * and the app can say when it finishes. Each symbol is fetched once per visit.
 */
type Listener = () => void;
type ReadyListener = (symbol: string, name: string) => void;
const builds = new Map<string, Research>();
const listeners = new Set<Listener>();
const readyListeners = new Set<ReadyListener>();
let version = 0;

function set(symbol: string, next: Research) {
  builds.set(symbol, next);
  version += 1;
  listeners.forEach((l) => l());
}

function update(symbol: string, fn: (s: Research) => Research) {
  set(symbol, fn(builds.get(symbol) ?? EMPTY));
}

/** Called when a live build finishes with every section delivered (not for bundled dossiers). */
export function onResearchReady(fn: ReadyListener): () => void {
  readyListeners.add(fn);
  return () => {
    readyListeners.delete(fn);
  };
}

/*
 * A phone that backgrounds the page cuts the stream, but the server keeps building. So a stream that ends before
 * "done" or "error" is rejoined; the server replays the build from the start, which `replay` clears the way for.
 */
const MAX_DROPS = 8;
const RECONNECT_MS = 3_000;

type BuildHandlers = {
  replay: () => void;
  message: (m: SSEMessage) => void;
  refused: (res: Response) => Promise<void>;
};

/** Follows a live build until it ends (true) or the server stays unreachable for `maxDrops` reconnects (false). */
export async function followBuild(
  open: () => Promise<Response>,
  on: BuildHandlers,
  ended: () => boolean,
  pause: () => Promise<void>,
  maxDrops = MAX_DROPS,
): Promise<boolean> {
  for (let drops = 0; ; drops++) {
    try {
      const res = await open();
      if (!res.ok || !res.body) {
        await on.refused(res);
        return true;
      }
      on.replay();
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        const parsed = parseSSE(buffer + decoder.decode(value, { stream: true }));
        buffer = parsed.rest;
        for (const m of parsed.messages) on.message(m);
      }
    } catch {
      // dropped: rejoin below
    }
    if (ended()) return true;
    if (drops >= maxDrops) return false;
    await pause();
  }
}

/** Waits until the page is on screen (a hidden page's requests are cut again), then a moment more. */
function untilVisibleThenWait(): Promise<void> {
  return new Promise((resolve) => {
    const go = () => setTimeout(resolve, RECONNECT_MS);
    if (document.visibilityState === "visible") return go();
    const onChange = () => {
      if (document.visibilityState !== "visible") return;
      document.removeEventListener("visibilitychange", onChange);
      go();
    };
    document.addEventListener("visibilitychange", onChange);
  });
}

async function streamLive(symbol: string) {
  if (!apiBase) return update(symbol, (s) => ({ ...s, error: unreachable(symbol), done: true }));
  update(symbol, (s) => ({ ...s, live: true }));
  const wakeTimer = setTimeout(
    () => update(symbol, (s) => (s.sections.length || s.progress || s.ahead !== null ? s : { ...s, waking: true })),
    WAKING_AFTER_MS,
  );
  const ended = await followBuild(
    () => fetch(`${apiBase}/api/research/${encodeURIComponent(symbol)}`),
    {
      replay: () => update(symbol, (s) => ({ ...s, sections: [] })),
      message: (m) => update(symbol, (s) => applyMessage(s, m)),
      refused: async (res) => {
        const body = await res.json().catch(() => ({}));
        update(symbol, (s) => ({ ...s, waking: false, error: refusal(symbol, res.status, body.error), done: true }));
      },
    },
    () => builds.get(symbol)?.done ?? false,
    untilVisibleThenWait,
  );
  clearTimeout(wakeTimer);
  if (!ended) update(symbol, (s) => ({ ...s, error: s.error ?? unreachable(symbol), done: true }));
  const final = builds.get(symbol)!;
  if (!final.error) {
    const name = (final.sections[0]?.data as { name?: string } | null)?.name ?? symbol;
    readyListeners.forEach((l) => l(symbol, name));
  }
}

/** Starts research on `symbol` unless it is already loaded or running. A failed attempt is retried. */
export function startResearch(symbol: string) {
  const existing = builds.get(symbol);
  if (existing && !existing.error) return;
  set(symbol, EMPTY);
  loadData<Dossier>(`dossiers/${symbol}.json`)
    .then((d) => set(symbol, { ...EMPTY, sections: d.sections, done: true }))
    // NotFound, or a host that answers a missing file with the app's HTML: either way, research it live.
    .catch(() => streamLive(symbol));
}

function subscribe(l: Listener) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

export function useResearch(symbol: string | null): Research {
  useEffect(() => {
    if (symbol) startResearch(symbol);
  }, [symbol]);
  return useSyncExternalStore(subscribe, () => (symbol ? builds.get(symbol) ?? EMPTY : EMPTY));
}

/** Symbols with a live build still running, re-rendered as builds change. */
export function useRunningBuilds(): string[] {
  useSyncExternalStore(subscribe, () => version);
  return [...builds.entries()].filter(([, s]) => s.live && !s.done).map(([sym]) => sym);
}

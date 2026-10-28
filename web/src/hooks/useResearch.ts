import { useEffect, useState } from "react";
import { apiBase, loadData } from "../api/client";
import type { Dossier, SectionEvent } from "../api/types";

export type ResearchError = { code: string; message: string };
export type Research = { sections: SectionEvent[]; done: boolean; waking: boolean; error: ResearchError | null };

const WAKING_AFTER_MS = 5_000;

export function unreachable(symbol: string): ResearchError {
  return { code: "sources_unreachable", message: `Couldn't fetch sources for ${symbol} from the server.` };
}

/** Fixed copy for the server's refusals (Task 12 decides them before any work starts). */
export function refusal(symbol: string, status: number, code: string | undefined): ResearchError {
  if (status === 404) return { code: "unknown_symbol", message: `FINN can't find ${symbol} on NSE.` };
  if (code === "rate_limited")
    return { code, message: "Live research is limited to 3 new tickers an hour. Precomputed tickers are always instant." };
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

/**
 * The dossier for `symbol`: the bundled static file when one exists, otherwise a live build streamed from the
 * Render service. fetch + a stream reader instead of EventSource, because EventSource can't see 404/429 statuses.
 */
export function useResearch(symbol: string | null): Research {
  const [state, setState] = useState<Research>({ sections: [], done: false, waking: false, error: null });

  useEffect(() => {
    setState({ sections: [], done: false, waking: false, error: null });
    if (!symbol) return;
    const ctrl = new AbortController();
    let cancelled = false;
    const update = (fn: (s: Research) => Research) => !cancelled && setState(fn);
    let wakeTimer: ReturnType<typeof setTimeout> | undefined;

    async function live(sym: string) {
      if (!apiBase) return update((s) => ({ ...s, error: unreachable(sym), done: true }));
      wakeTimer = setTimeout(() => update((s) => (s.sections.length ? s : { ...s, waking: true })), WAKING_AFTER_MS);
      let res: Response;
      try {
        res = await fetch(`${apiBase}/api/research/${encodeURIComponent(sym)}`, { signal: ctrl.signal });
      } catch {
        return update((s) => ({ ...s, waking: false, error: unreachable(sym), done: true }));
      }
      if (!res.ok || !res.body) {
        const body = await res.json().catch(() => ({}));
        return update((s) => ({ ...s, waking: false, error: refusal(sym, res.status, body.error), done: true }));
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        for (;;) {
          const { value, done } = await reader.read();
          if (done) break;
          const parsed = parseSSE(buffer + decoder.decode(value, { stream: true }));
          buffer = parsed.rest;
          for (const m of parsed.messages) {
            if (m.event === "done") update((s) => ({ ...s, done: true }));
            else if (m.event === "error") update((s) => ({ ...s, waking: false, error: JSON.parse(m.data), done: true }));
            else update((s) => ({ ...s, waking: false, sections: [...s.sections, JSON.parse(m.data) as SectionEvent] }));
          }
        }
      } catch {
        if (!ctrl.signal.aborted) update((s) => ({ ...s, error: unreachable(sym), done: true }));
        return;
      }
      update((s) => (s.done ? s : { ...s, error: s.error ?? unreachable(sym), done: true }));
    }

    loadData<Dossier>(`dossiers/${symbol}.json`)
      .then((d) => update(() => ({ sections: d.sections, done: true, waking: false, error: null })))
      // NotFound, or a host that answers a missing file with the app's HTML: either way, research it live.
      .catch(() => live(symbol));

    return () => {
      cancelled = true;
      clearTimeout(wakeTimer);
      ctrl.abort();
    };
  }, [symbol]);

  return state;
}

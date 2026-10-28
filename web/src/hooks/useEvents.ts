import { useEffect, useState } from "react";
import { dataUrl } from "../api/client";
import type { EventsFile } from "../api/types";

export type EventsState = { status: "loading" } | { status: "empty" } | { status: "error" } | { status: "ok"; feed: EventsFile };

export function useEvents(): EventsState {
  const [state, setState] = useState<EventsState>({ status: "loading" });
  useEffect(() => {
    let cancelled = false;
    fetch(dataUrl("events.json"), { cache: "no-cache" })
      .then(async (r) => {
        if (cancelled) return;
        if (r.status === 404) return setState({ status: "empty" });
        if (!r.ok) return setState({ status: "error" });
        setState({ status: "ok", feed: (await r.json()) as EventsFile });
      })
      .catch(() => !cancelled && setState({ status: "error" }));
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}

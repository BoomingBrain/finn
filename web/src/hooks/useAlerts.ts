import type { EventsFile, SignalsFile } from "../api/types";
import { alertsFor, signalsFor, type Alert, type Settings } from "../lib/signals";
import { useData } from "./useData";
import { useStoredState } from "./useStoredState";

export const INBOX_DAYS = 7;

export interface Inbox {
  alerts: Alert[] | null;
  unread: number;
  isSeen: (id: string) => boolean;
  markSeen: (ids: string[]) => void;
}

/** Alerts from the last week under the given settings, with seen state kept on this device. Call once (in App). */
export function useAlerts(settings: Settings): Inbox {
  const events = useData<EventsFile>("events.json");
  const signals = useData<SignalsFile>("signals.json");
  const [seen, setSeen] = useStoredState<string[]>("finn.seen", []);
  const seenSet = new Set(seen);
  const markSeen = (ids: string[]) => setSeen([...new Set([...seen, ...ids])].slice(-500));
  if (events.status === "loading" || signals.status === "loading")
    return { alerts: null, unread: 0, isSeen: () => true, markSeen };
  const cutoff = Date.now() - INBOX_DAYS * 86_400_000;
  const recentEvents = events.status === "ok" ? events.data.events.filter((e) => Date.parse(e.first_at) >= cutoff) : [];
  const recentSignals = signals.status === "ok" ? signalsFor(signals.data, settings, INBOX_DAYS) : [];
  const alerts = alertsFor(recentEvents, recentSignals, settings);
  return { alerts, unread: alerts.filter((a) => !seenSet.has(a.id)).length, isSeen: (id) => seenSet.has(id), markSeen };
}

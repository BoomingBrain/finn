import type { Event, EventsFile } from "../api/types";

export const WINDOWS = [
  { hours: 24, short: "24h", label: "24 hours" },
  { hours: 72, short: "3d", label: "3 days" },
  { hours: 168, short: "7d", label: "7 days" },
  { hours: 720, short: "30d", label: "30 days" },
] as const;

export const STALE_AFTER_HOURS = 36;

export interface Digest {
  asOf: string;
  hours: number;
  stale: boolean;
  quiet: boolean;
  critical: Event[];
  notable: Event[];
  routine: { count: number; items: Event[] };
}

/** Everything in the window, newest first within each tier; routine collapsed behind a count. */
export function buildDigest(feed: EventsFile, now: Date, hours: number): Digest {
  const cutoff = now.getTime() - hours * 3_600_000;
  const inWindow = feed.events
    .filter((e) => Date.parse(e.last_at) >= cutoff)
    .sort((a, b) => Date.parse(b.last_at) - Date.parse(a.last_at));
  const critical = inWindow.filter((e) => e.tier === "critical");
  const notable = inWindow.filter((e) => e.tier === "notable");
  const routine = inWindow.filter((e) => e.tier === "routine");
  return {
    asOf: feed.as_of,
    hours,
    stale: now.getTime() - Date.parse(feed.as_of) > STALE_AFTER_HOURS * 3_600_000,
    quiet: critical.length === 0 && notable.length === 0,
    critical,
    notable,
    routine: { count: routine.length, items: routine },
  };
}

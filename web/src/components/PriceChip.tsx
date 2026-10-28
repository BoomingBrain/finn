import type { Event } from "../api/types";
import { directionClass, formatPct } from "../lib/format";

const day = (iso: string) => new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(iso));

/** The market's reaction on the first session that could trade on the filing. */
export function PriceChip({ event }: { event: Event }) {
  if (event.price_change_pct === null || !event.price_date) return null;
  const heavy = event.volume_multiple !== null && event.volume_multiple >= 1.5;
  return (
    <p className="mt-2 text-[13px]">
      <span className={directionClass(event.price_change_pct)}>{formatPct(event.price_change_pct)}</span>
      <span className="text-muted"> on {day(event.price_date)}</span>
      {heavy && <span className="text-muted">, volume {event.volume_multiple!.toFixed(1)}× usual</span>}
    </p>
  );
}

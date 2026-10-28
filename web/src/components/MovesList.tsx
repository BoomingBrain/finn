import { directionClass, formatPct } from "../lib/format";
import type { Signal } from "../lib/signals";

const day = (d: string) => new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(d));

/** Price and volume moves that crossed the investor's own thresholds. */
export function MovesList({ moves }: { moves: Signal[] }) {
  if (moves.length === 0) return null;
  return (
    <section aria-labelledby="moves" className="border-t border-line py-4">
      <h2 id="moves" className="mb-2 text-[13px] text-muted">Unusual moves, by your thresholds</h2>
      <ul className="space-y-1.5">
        {moves.map((m) => (
          <li key={m.id} className="flex items-baseline gap-3">
            <span className="min-w-0 flex-1 truncate">{m.name}</span>
            {m.kind === "price_move" ? (
              <span className={directionClass(m.value)}>{formatPct(m.value)}</span>
            ) : (
              <span>Volume {m.value.toFixed(1)}×</span>
            )}
            <span className="w-14 shrink-0 text-right text-[12px] text-muted">{day(m.date)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

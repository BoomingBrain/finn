import type { SignalsFile } from "../api/types";
import { Statement } from "../components/Statement";
import { useData } from "../hooks/useData";
import { useStoredState } from "../hooks/useStoredState";
import { directionClass, formatPct } from "../lib/format";
import { holdingRows, portfolioMove, RANGES, type HoldingRow } from "../lib/portfolio";

const price = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });
const day = (d: string) => new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(d)).replace(" ", "\u00a0");

/** Closing prices over the range; the dotted line is where the range started, so above/below reads at a glance. */
function PriceLine({ row }: { row: HoldingRow }) {
  const { closes } = row;
  const w = 96, h = 30, pad = 2.5;
  const [min, max] = [Math.min(...closes), Math.max(...closes)];
  const y = (v: number) => pad + (1 - (v - min) / (max - min || 1)) * (h - 2 * pad);
  const x = (i: number) => (i / (closes.length - 1)) * w;
  const path = closes.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const tone = row.rangePct > 0 ? "text-up" : row.rangePct < 0 ? "text-down" : "text-muted";
  return (
    <svg viewBox={`-3 0 ${w + 6} ${h}`} className={`h-[30px] w-[76px] shrink-0 min-[380px]:w-[96px] ${tone}`} aria-hidden="true">
      <line x1="0" x2={w} y1={y(closes[0])} y2={y(closes[0])} stroke="var(--line)" strokeWidth="1" strokeDasharray="2 3" />
      <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(closes.length - 1)} cy={y(closes[closes.length - 1])} r="2.5" fill="currentColor" />
    </svg>
  );
}

function headline(move: number | null, rangeLabel: string): string {
  if (move === null) return "No prices yet.";
  const size = Math.abs(move);
  if (size < 0.05) return `Your holdings are flat over ${rangeLabel}.`;
  return `Your holdings are ${move > 0 ? "up" : "down"} ${size.toFixed(1)}% over ${rangeLabel}.`;
}

export function Portfolio() {
  const signals = useData<SignalsFile>("signals.json");
  const [sessions, setSessions] = useStoredState("finn.portfolio.sessions", 21);
  const range = RANGES.find((r) => r.sessions === sessions) ?? RANGES[1];

  if (signals.status === "loading") return <Statement>Reading closing prices…</Statement>;
  if (signals.status !== "ok")
    return <Statement detail="Prices arrive with the next data run. Check your connection and reload.">Couldn't load prices.</Statement>;

  const rows = holdingRows(signals.data, range.sessions);
  const up = rows.filter((r) => r.dayPct > 0).length;
  const lastDate = rows[0]?.lastDate;
  return (
    <>
      <Statement
        detail={`Equal-weighted across your ${rows.length} holdings. Today ${up} rose and ${rows.length - up} fell${lastDate ? `, closing prices to ${day(lastDate)}` : ""}.`}
      >
        {headline(portfolioMove(rows), range.phrase)}
      </Statement>

      <div role="radiogroup" aria-label="Price range" className="mb-4 inline-flex rounded-md border border-line p-0.5">
        {RANGES.map((r) => {
          const selected = r.sessions === range.sessions;
          return (
            <button
              key={r.sessions}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={`Last ${r.label}`}
              onClick={() => setSessions(r.sessions)}
              className={`min-w-12 rounded px-3 py-1.5 text-[13px] ${selected ? "bg-surface font-semibold text-text" : "text-muted"}`}
            >
              {r.short}
            </button>
          );
        })}
      </div>

      <p className="mb-1 text-[12px] text-muted">Biggest moves first. Tap a company to research it.</p>
      <ul>
        {rows.map((r) => (
          <li key={r.symbol} className="border-t border-line">
            <a
              href={`#/ask/${encodeURIComponent(r.symbol)}`}
              className="flex items-center gap-3 py-3"
              aria-label={`${r.name}, ${formatPct(r.rangePct)} over ${range.phrase}, ${formatPct(r.dayPct)} today. Open research.`}
            >
              <span className="min-w-0 flex-1">
                <span className="block truncate font-serif text-[17px] leading-tight font-medium">{r.name}</span>
                <span className="text-[12px] text-muted">
                  {r.symbol} <span className="ml-1">₹{price.format(r.last)}</span>
                </span>
              </span>
              <PriceLine row={r} />
              <span className="shrink-0 text-right whitespace-nowrap">
                <span className={`block text-[15px] font-medium ${directionClass(r.rangePct)}`}>{formatPct(r.rangePct)}</span>
                <span className={`block text-[12px] ${directionClass(r.dayPct)}`}>{formatPct(r.dayPct)} today</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}

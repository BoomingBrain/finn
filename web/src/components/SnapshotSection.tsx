import type { Citation, QuarterPoint, SnapshotData } from "../api/types";
import { directionClass, formatCrore, formatPct, toneAbove, toneBelow } from "../lib/format";
import { Chips } from "./CitationChip";
import { Clamp } from "./Clamp";
import { StatBox, StatGrid } from "./StatBox";

const pct = (v: number | null) => (v === null ? "—" : `${v.toFixed(1)}%`);
const cr = (v: number | null) => (v === null ? "—" : `₹${formatCrore(v)} Cr`);
const ratio = (v: number | null) => (v === null ? "—" : `${v.toFixed(2)}×`);

/** One series of the last 8 quarters, scaled to its own range; gaps break the line. */
export function Sparkline({ label, points }: { label: string; points: (number | null)[] }) {
  const values = points.filter((v): v is number => v !== null);
  if (values.length < 2) return null;
  const [min, max] = [Math.min(...values), Math.max(...values)];
  const w = 120, h = 32, step = w / (points.length - 1);
  const y = (v: number) => h - 2 - ((v - min) / (max - min || 1)) * (h - 4);
  const path = points
    .map((v, i) => (v === null ? null : `${i === 0 || points[i - 1] === null ? "M" : "L"}${(i * step).toFixed(1)},${y(v).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
  const last = points[points.length - 1];
  return (
    <figure className="min-w-0">
      <figcaption className="text-[12px] text-muted">{label}, {points.length} qtrs</figcaption>
      <svg viewBox={`-2 0 ${w + 4} ${h}`} className="mt-1 h-8 w-full max-w-[160px]" role="img" aria-label={`${label} trend, latest ${cr(last)}`}>
        <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        {last !== null && <circle cx={(points.length - 1) * step} cy={y(last)} r="2.5" fill="currentColor" />}
      </svg>
    </figure>
  );
}

export function SnapshotSection({ data, citations }: { data: SnapshotData; citations: Citation[] }) {
  const q: QuarterPoint[] = data.quarterly;
  const marginMove = data.opm_latest !== null && data.opm_3y_ago !== null ? data.opm_latest - data.opm_3y_ago : null;
  return (
    <>
      {data.about && <Clamp text={data.about.replace(/\[\d+\]/g, "")} lines={3} className="mt-2 text-[14px] text-muted" />}
      <StatGrid className="mt-3">
        <StatBox label="Revenue, last 4 qtrs" value={cr(data.revenue_ttm)}>
          {data.revenue_cagr_3y !== null && (
            <><span className={directionClass(data.revenue_cagr_3y)}>{formatPct(data.revenue_cagr_3y)}</span><span className="text-muted"> a year, 3 yrs</span></>
          )}
        </StatBox>
        <StatBox label="Profit, last 4 qtrs" value={cr(data.pat_ttm)}>
          {data.pat_cagr_3y !== null && (
            <><span className={directionClass(data.pat_cagr_3y)}>{formatPct(data.pat_cagr_3y)}</span><span className="text-muted"> a year, 3 yrs</span></>
          )}
        </StatBox>
        {data.lender ? (
          <StatBox label="Return on equity" value={pct(data.roe_latest)} tone={toneAbove(data.roe_latest, 10, 15)} />
        ) : (
          <>
            <StatBox label="Operating margin" value={pct(data.opm_latest)}>
              {marginMove !== null && (
                <><span className={directionClass(marginMove)}>{formatPct(marginMove).replace("%", " pts")}</span><span className="text-muted"> vs 3 yrs ago</span></>
              )}
            </StatBox>
            <StatBox label="Return on capital" value={pct(data.roce_latest)} tone={toneAbove(data.roce_latest, 10, 18)} />
            <StatBox label="Debt to equity" value={ratio(data.debt_to_equity)} tone={toneBelow(data.debt_to_equity, 0.5, 1)} />
            <StatBox label="Cash ÷ profit, 3 yrs" value={ratio(data.cfo_to_pat_3y)} tone={toneAbove(data.cfo_to_pat_3y, 0.7, 1)} />
          </>
        )}
      </StatGrid>
      <div className="mt-2 grid grid-cols-2 gap-2">
        <div className="rounded-md bg-surface px-3 py-2.5"><Sparkline label="Revenue" points={q.map((p) => p.revenue)} /></div>
        <div className="rounded-md bg-surface px-3 py-2.5"><Sparkline label="Profit" points={q.map((p) => p.pat)} /></div>
      </div>
      {data.flags.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-2">
          {data.flags.map((f) => (
            <li key={f} className="rounded-sm border border-critical px-2 py-0.5 text-[12px] text-critical">{f}</li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[12px] text-muted">
        {data.basis === "standalone" ? "Standalone" : "Consolidated"}, computed from reported numbers
        <Chips ids={["SCR"]} citations={citations} />
      </p>
    </>
  );
}

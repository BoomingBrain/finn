import type { Citation, QuarterPoint, SnapshotData } from "../api/types";
import { formatCrore, formatPct } from "../lib/format";
import { Chips } from "./CitationChip";

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
      <figcaption className="text-[12px] text-muted">{label}, last {points.length} quarters</figcaption>
      <svg viewBox={`-2 0 ${w + 4} ${h}`} className="mt-1 h-8 w-full max-w-[160px]" role="img" aria-label={`${label} trend, latest ${cr(last)}`}>
        <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        {last !== null && <circle cx={(points.length - 1) * step} cy={y(last)} r="2.5" fill="currentColor" />}
      </svg>
    </figure>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="py-2">
      <dt className="text-[12px] text-muted">{label}</dt>
      <dd className="text-[17px] font-medium">{value}</dd>
      {note && <dd className="text-[12px] text-muted">{note}</dd>}
    </div>
  );
}

export function SnapshotSection({ data, citations }: { data: SnapshotData; citations: Citation[] }) {
  const q: QuarterPoint[] = data.quarterly;
  return (
    <>
      {data.about && <p className="mt-2 max-w-[60ch] text-muted">{data.about.replace(/\[\d+\]/g, "")}</p>}
      <dl className="mt-3 grid grid-cols-2 gap-x-4 border-t border-line sm:grid-cols-3">
        <Tile label="Revenue, last 4 quarters" value={cr(data.revenue_ttm)} note={data.revenue_cagr_3y === null ? undefined : `${formatPct(data.revenue_cagr_3y)} a year over 3 years`} />
        <Tile label="Profit, last 4 quarters" value={cr(data.pat_ttm)} note={data.pat_cagr_3y === null ? undefined : `${formatPct(data.pat_cagr_3y)} a year over 3 years`} />
        {data.lender ? (
          <Tile label="Return on equity" value={pct(data.roe_latest)} />
        ) : (
          <>
            <Tile label="Operating margin" value={pct(data.opm_latest)} note={data.opm_3y_ago === null ? undefined : `${pct(data.opm_3y_ago)} three years ago`} />
            <Tile label="Return on capital" value={pct(data.roce_latest)} />
            <Tile label="Debt to equity" value={ratio(data.debt_to_equity)} />
            <Tile label="Cash from operations ÷ profit" value={ratio(data.cfo_to_pat_3y)} note="over 3 years" />
          </>
        )}
      </dl>
      <div className="mt-3 grid grid-cols-2 gap-4">
        <Sparkline label="Revenue" points={q.map((p) => p.revenue)} />
        <Sparkline label="Profit" points={q.map((p) => p.pat)} />
      </div>
      {data.flags.length > 0 && (
        <ul className="mt-3 space-y-1">
          {data.flags.map((f) => (
            <li key={f} className="text-critical">{f}</li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[12px] text-muted">
        {data.basis === "standalone" ? "Standalone" : "Consolidated"} figures computed by FINN from the company's reported numbers.
        <Chips ids={["SCR"]} citations={citations} />
      </p>
    </>
  );
}

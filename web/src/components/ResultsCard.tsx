import type { ResultsCard as Card } from "../api/types";
import { directionClass, fiscalQuarter, formatCrore, formatPct } from "../lib/format";
import { StatBox, StatGrid } from "./StatBox";

const UNREADABLE = "Couldn't read the numbers — open filing";

export function ResultsCard({ card, filingUrl }: { card: Card; filingUrl: string | null }) {
  if (card.status === "unreadable") {
    return filingUrl ? (
      <a href={filingUrl} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[13px] text-muted underline underline-offset-2">
        {UNREADABLE}
      </a>
    ) : (
      <p className="mt-3 text-[13px] text-muted">Couldn't read the numbers from this filing.</p>
    );
  }
  const caption = [fiscalQuarter(card.period_end), card.basis, "₹ crore"].filter(Boolean).join(", ");
  return (
    <div className="mt-3">
      <p className="mb-1.5 flex items-center gap-2 text-[12px] text-muted">
        {caption}
        {card.verified === true && <span className="text-up">Matches reported</span>}
        {card.verified === false && (
          <span className="rounded-sm border border-critical px-1 text-critical" title={`Differs from reported financials: ${card.mismatches.join(", ")}`}>
            Unverified
          </span>
        )}
      </p>
      <StatGrid>
        {Object.entries(card.metrics).map(([name, m]) => (
          <StatBox key={name} label={name} value={formatCrore(m.current)}>
            <span className={directionClass(m.qoq_pct)}>{formatPct(m.qoq_pct)}</span>
            <span className="text-muted"> QoQ</span>
            <span className={`ml-2 ${directionClass(m.yoy_pct)}`}>{formatPct(m.yoy_pct)}</span>
            <span className="text-muted"> YoY</span>
          </StatBox>
        ))}
      </StatGrid>
      {card.layout === "lender" && card.not_applicable.includes("EBITDA") && (
        <p className="mt-1.5 text-[12px] text-muted">EBITDA n/a for lenders</p>
      )}
      {(card.missing ?? []).length > 0 && (
        <p className="mt-1.5 text-[12px] text-muted">{card.missing.join(", ")} couldn't be read from this filing.</p>
      )}
    </div>
  );
}

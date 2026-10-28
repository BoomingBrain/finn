import type { ResultsCard as Card } from "../api/types";
import { directionClass, fiscalQuarter, formatCrore, formatPct } from "../lib/format";

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
      <table className="w-full text-[14px]">
        <caption className="mb-1 text-left text-[12px] text-muted">
          {caption}
          {card.verified === false && (
            <span className="ml-2 rounded-sm border border-critical px-1 text-critical" title={`Differs from reported financials: ${card.mismatches.join(", ")}`}>
              Unverified
            </span>
          )}
        </caption>
        <thead>
          <tr className="text-[12px] text-muted">
            <th scope="col" className="py-1 text-left font-normal"><span className="sr-only">Metric</span></th>
            <th scope="col" className="py-1 text-right font-normal">This quarter</th>
            <th scope="col" className="py-1 text-right font-normal">QoQ</th>
            <th scope="col" className="py-1 text-right font-normal">YoY</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(card.metrics).map(([name, m]) => (
            <tr key={name} className="border-t border-line">
              <th scope="row" className="py-1.5 text-left font-medium">{name}</th>
              <td className="py-1.5 text-right">{formatCrore(m.current)}</td>
              <td className={`py-1.5 text-right ${directionClass(m.qoq_pct)}`}>{formatPct(m.qoq_pct)}</td>
              <td className={`py-1.5 text-right ${directionClass(m.yoy_pct)}`}>{formatPct(m.yoy_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {card.layout === "lender" && card.not_applicable.includes("EBITDA") && (
        <p className="mt-1 text-[12px] text-muted">EBITDA n/a for lenders</p>
      )}
    </div>
  );
}

import type { Citation, DeliveryData, Verdict } from "../api/types";
import { deliveredText, deliverySummary, targetText } from "../lib/research";
import { CitationChip } from "./CitationChip";

const VERDICT: Record<Verdict, { label: string; className: string }> = {
  met: { label: "Met", className: "text-up" },
  partly: { label: "Partly", className: "text-critical" },
  missed: { label: "Missed", className: "text-down" },
  pending: { label: "In progress", className: "text-notable" },
  not_checkable: { label: "Can't check", className: "text-muted" },
};
const ORDER: Verdict[] = ["met", "partly", "missed", "pending", "not_checkable"];

export function DeliveryScorecard({ data, citations }: { data: DeliveryData; citations: Citation[] }) {
  if (data.rows.length === 0)
    return <p className="mt-2 text-muted">No explicit numeric targets in the last {data.transcripts.length} earnings calls.</p>;
  const counts = ORDER.map((v) => [v, data.rows.filter((r) => r.verdict === v).length] as const).filter(([, n]) => n > 0);
  return (
    <>
      <p className="sr-only">{deliverySummary(data.rows)}</p>
      <dl className="mt-2 flex flex-wrap gap-2">
        {counts.map(([v, n]) => (
          <div key={v} className="min-w-[64px] rounded-md bg-surface px-3 py-2">
            <dd className={`text-[18px] leading-tight font-semibold ${VERDICT[v].className}`}>{n}</dd>
            <dt className="text-[12px] text-muted">{VERDICT[v].label}</dt>
          </div>
        ))}
      </dl>
      <ul className="mt-3">
        {data.rows.map((r) => {
          const v = VERDICT[r.verdict];
          const delivered = deliveredText(r);
          const muted = r.verdict === "not_checkable";
          return (
            <li key={`${r.target.metric}-${r.target.raw_metric}-${r.target.period}`} className={`border-t border-line py-2.5 ${muted ? "text-muted" : ""}`}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 text-[15px] font-medium">
                  {r.target.raw_metric.charAt(0).toUpperCase() + r.target.raw_metric.slice(1)}{" "}
                  <span className="whitespace-nowrap">{targetText(r.target)}</span>
                  <span className="text-muted">, {r.target.period}</span>
                </p>
                <span className={`shrink-0 text-[13px] font-semibold ${v.className}`}>{v.label}</span>
              </div>
              {delivered && (
                <p className="text-[14px]">
                  <span className="text-muted">Delivered </span>
                  <span className={`font-semibold ${v.className}`}>{delivered}</span>
                </p>
              )}
              <details className="mt-1 text-[13px]">
                <summary className="cursor-pointer text-notable">Details</summary>
                {!muted && r.explanation && <p className="mt-1 text-muted">{r.explanation}</p>}
                <blockquote className="mt-1 border-l-2 border-line pl-3 font-serif text-[15px] italic">
                  “{r.target.quote}”
                  <CitationChip id={r.target.source_id} citations={citations} />
                </blockquote>
              </details>
            </li>
          );
        })}
      </ul>
    </>
  );
}

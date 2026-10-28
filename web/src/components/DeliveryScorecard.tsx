import type { Citation, DeliveryData, Verdict } from "../api/types";
import { deliveredText, deliverySummary, targetText } from "../lib/research";
import { CitationChip } from "./CitationChip";

const VERDICT: Record<Verdict, { label: string; className: string }> = {
  met: { label: "Met", className: "text-up" },
  partly: { label: "Partly", className: "text-text" },
  missed: { label: "Missed", className: "text-down" },
  pending: { label: "In progress", className: "text-muted" },
  not_checkable: { label: "Can't check", className: "text-muted" },
};

export function DeliveryScorecard({ data, citations }: { data: DeliveryData; citations: Citation[] }) {
  if (data.rows.length === 0)
    return (
      <p className="mt-2 text-muted">
        Management gave no explicit numeric targets in the last {data.transcripts.length} earnings calls.
      </p>
    );
  return (
    <>
      <p className="mt-2 font-serif text-[20px] leading-snug">{deliverySummary(data.rows)}</p>
      <p className="mt-1 text-[12px] text-muted">
        FINN compares each target with the reported quarters itself; the model only explains the result.
      </p>
      <ul className="mt-3">
        {data.rows.map((r) => {
          const v = VERDICT[r.verdict];
          const delivered = deliveredText(r);
          const muted = r.verdict === "not_checkable";
          return (
            <li key={`${r.target.metric}-${r.target.raw_metric}-${r.target.period}`} className={`border-t border-line py-3 ${muted ? "text-muted" : ""}`}>
              <div className="flex items-baseline justify-between gap-3">
                <p className="min-w-0 font-medium">
                  {r.target.raw_metric.charAt(0).toUpperCase() + r.target.raw_metric.slice(1)} {targetText(r.target)}, {r.target.period}
                </p>
                <span className={`shrink-0 text-[13px] font-semibold ${v.className}`}>{v.label}</span>
              </div>
              {delivered && <p className="text-[14px]">Delivered {delivered}</p>}
              {!muted && <p className="mt-0.5 text-[14px] text-muted">{r.explanation}</p>}
              <details className="mt-1 text-[13px]">
                <summary className="cursor-pointer text-notable">What management said</summary>
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

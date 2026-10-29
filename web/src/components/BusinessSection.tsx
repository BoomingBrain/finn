import type { BusinessData, Citation } from "../api/types";
import { Chips } from "./CitationChip";

export function BusinessSection({ data, citations }: { data: BusinessData; citations: Citation[] }) {
  return (
    <>
      <p className="mt-2 max-w-[60ch] text-[15px]">
        {data.what_it_does}
        <Chips ids={data.source_ids} citations={citations} />
      </p>
      {data.segments.length > 0 && (
        <ul className="mt-3 space-y-2">
          {data.segments.map((s) => (
            <li key={s.name} className="rounded-md bg-surface px-3 py-2">
              <div className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 text-[14px]">{s.name}</span>
                {s.share_pct !== null && <span className="shrink-0 text-[15px] font-semibold">{s.share_pct}%</span>}
              </div>
              {s.share_pct !== null && (
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line" aria-hidden="true">
                  <div className="h-full rounded-full bg-notable" style={{ width: `${Math.min(100, s.share_pct)}%` }} />
                </div>
              )}
              <div className="mt-1 -ml-1"><Chips ids={s.source_ids} citations={citations} /></div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

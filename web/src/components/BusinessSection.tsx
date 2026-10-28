import type { BusinessData, Citation } from "../api/types";
import { Chips } from "./CitationChip";

export function BusinessSection({ data, citations }: { data: BusinessData; citations: Citation[] }) {
  return (
    <>
      <p className="mt-2 max-w-[60ch]">
        {data.what_it_does}
        <Chips ids={data.source_ids} citations={citations} />
      </p>
      {data.segments.length > 0 && (
        <ul className="mt-3">
          {data.segments.map((s) => (
            <li key={s.name} className="flex items-baseline justify-between gap-3 border-t border-line py-2">
              <span className="min-w-0">
                {s.name}
                <Chips ids={s.source_ids} citations={citations} />
              </span>
              <span className="shrink-0 text-muted">{s.share_pct === null ? "" : `${s.share_pct}% of revenue`}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

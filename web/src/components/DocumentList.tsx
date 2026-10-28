import type { DocRef } from "../api/types";
import { formatWhen } from "../lib/format";

/** Every filing folded into the event. A single filing is just a link. */
export function DocumentList({ documents }: { documents: DocRef[] }) {
  const withUrl = documents.filter((d) => d.url);
  if (withUrl.length === 0) return null;
  if (withUrl.length === 1)
    return (
      <a href={withUrl[0].url!} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[13px] text-notable underline-offset-2 hover:underline">
        Open filing
      </a>
    );
  return (
    <details className="mt-3 text-[13px]">
      <summary className="cursor-pointer text-notable">{withUrl.length} filings</summary>
      <ul className="mt-2 space-y-1.5">
        {withUrl.map((d) => (
          <li key={d.url} className="flex justify-between gap-3">
            <a href={d.url!} target="_blank" rel="noreferrer" className="min-w-0 underline-offset-2 hover:underline">{d.title}</a>
            <span className="shrink-0 text-muted">{formatWhen(d.filed_at)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

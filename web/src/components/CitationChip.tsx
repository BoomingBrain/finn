import type { Citation } from "../api/types";
import { citationHref, citationLabel } from "../lib/research";

/** A source link that opens the PDF on the cited page. Ids the section didn't resolve render nothing. */
export function CitationChip({ id, citations }: { id: string; citations: Citation[] }) {
  const c = citations.find((x) => x.source_id === id);
  if (!c) return null;
  return (
    <a
      href={citationHref(c)}
      target="_blank"
      rel="noreferrer"
      title={citationLabel(id).startsWith("AR") ? "Annual report" : undefined}
      className="ml-1 inline-block rounded-sm border border-line px-1.5 py-px align-[1px] text-[11px] whitespace-nowrap text-muted hover:text-text"
    >
      {citationLabel(id)}
    </a>
  );
}

export function Chips({ ids, citations }: { ids: string[]; citations: Citation[] }) {
  return (
    <>
      {[...new Set(ids)].map((id) => (
        <CitationChip key={id} id={id} citations={citations} />
      ))}
    </>
  );
}

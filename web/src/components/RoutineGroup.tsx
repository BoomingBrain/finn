import { useState } from "react";
import type { Event } from "../api/types";
import { formatWhen } from "../lib/format";

export function RoutineGroup({ items }: { items: Event[] }) {
  const [open, setOpen] = useState(false);
  if (items.length === 0) return null;
  return (
    <section className="border-t border-line py-3">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full items-center justify-between text-left text-muted">
        <span>{items.length} routine {items.length === 1 ? "filing" : "filings"}</span>
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true"
          className={open ? "rotate-180" : undefined}>
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open && (
        <ul className="mt-2 space-y-2 text-[13px]">
          {items.map((e) => (
            <li key={e.id} className="flex gap-3">
              <span className="w-20 shrink-0 text-muted">{e.symbol}</span>
              <span className="min-w-0 flex-1">
                {e.documents[0]?.url ? (
                  <a href={e.documents[0].url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">{e.headline}</a>
                ) : e.headline}
                <span className="block text-muted">{formatWhen(e.last_at)}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

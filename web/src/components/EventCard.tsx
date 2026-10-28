import type { Event } from "../api/types";
import { CATEGORY_LABEL, formatWhen } from "../lib/format";
import { ResultsCard } from "./ResultsCard";

const RULE: Record<Event["tier"], string> = { critical: "bg-critical", notable: "bg-notable", routine: "bg-line" };

export function EventCard({ event }: { event: Event }) {
  const filing = event.documents[0]?.url ?? null;
  const showHeadline = !event.results || event.results.status !== "ok";
  return (
    <article className="relative border-t border-line py-4 pl-4">
      <span aria-hidden="true" className={`absolute top-4 bottom-4 left-0 w-[3px] rounded-full ${RULE[event.tier]}`} />
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-serif text-[19px] leading-tight font-medium">{event.company}</h3>
        <time dateTime={event.last_at} className="shrink-0 text-[12px] text-muted">{formatWhen(event.last_at)}</time>
      </header>
      <p className="mt-0.5 text-[13px] text-muted">{CATEGORY_LABEL[event.category]}</p>
      {showHeadline && <p className="mt-2">{event.headline}</p>}
      {event.summary && <p className="mt-1 text-muted">{event.summary}</p>}
      {event.results && <ResultsCard card={event.results} filingUrl={filing} />}
      {filing && (
        <a href={filing} target="_blank" rel="noreferrer" className="mt-3 inline-block text-[13px] text-notable underline-offset-2 hover:underline">
          Open filing
        </a>
      )}
    </article>
  );
}

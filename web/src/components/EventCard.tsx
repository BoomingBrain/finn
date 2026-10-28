import type { Event } from "../api/types";
import { CATEGORY_LABEL, formatWhen } from "../lib/format";
import { DocumentList } from "./DocumentList";
import { PriceChip } from "./PriceChip";
import { ProfileCard } from "./ProfileCard";
import { ResultsCard } from "./ResultsCard";

const RULE: Record<Event["tier"], string> = { critical: "bg-critical", notable: "bg-notable", routine: "bg-line" };

export function EventCard({ event }: { event: Event }) {
  const leadUrl = event.documents.find((d) => d.title === event.headline)?.url ?? event.documents[0]?.url ?? null;
  const hasCard = event.results?.status === "ok";
  return (
    <article className="relative border-t border-line py-4 pl-4">
      <span aria-hidden="true" className={`absolute top-4 bottom-4 left-0 w-[3px] rounded-full ${RULE[event.tier]}`} />
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-serif text-[19px] leading-tight font-medium">{event.company}</h3>
        <time dateTime={event.first_at} className="shrink-0 text-[12px] text-muted">{formatWhen(event.first_at)}</time>
      </header>
      <p className="mt-0.5 text-[13px] text-muted">{CATEGORY_LABEL[event.category]}</p>
      {!hasCard && <p className="mt-2">{event.headline}</p>}
      {event.summary && event.category !== "management_change" && <p className="mt-1 text-muted">{event.summary}</p>}
      {event.results && <ResultsCard card={event.results} filingUrl={leadUrl} />}
      {event.category === "management_change" && <ProfileCard profile={event.profile} filingUrl={leadUrl} />}
      <PriceChip event={event} />
      <DocumentList documents={event.documents} />
    </article>
  );
}

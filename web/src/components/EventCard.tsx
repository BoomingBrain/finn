import type { Event } from "../api/types";
import { CATEGORY_LABEL, companyName, formatWhen } from "../lib/format";
import { Clamp } from "./Clamp";
import { DocumentList } from "./DocumentList";
import { PriceChip } from "./PriceChip";
import { ProfileCard } from "./ProfileCard";
import { ResultsCard } from "./ResultsCard";

const RULE: Record<Event["tier"], string> = { critical: "bg-critical", notable: "bg-notable", routine: "bg-line" };

export function EventCard({ event, focused = false }: { event: Event; focused?: boolean }) {
  const leadUrl = event.documents.find((d) => d.title === event.headline)?.url ?? event.documents[0]?.url ?? null;
  const hasCard = event.results?.status === "ok";
  return (
    <article id={`event-${event.id}`} className={`relative scroll-mt-4 border-t border-line py-4 pl-4 ${focused ? "bg-surface" : ""}`}>
      <span aria-hidden="true" className={`absolute top-4 bottom-4 left-0 w-[3px] rounded-full ${RULE[event.tier]}`} />
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-serif text-[19px] leading-tight font-medium">{companyName(event.company)}</h3>
        <time dateTime={event.first_at} className="shrink-0 text-[12px] text-muted">{formatWhen(event.first_at)}</time>
      </header>
      <p className="mt-0.5 text-[13px] text-muted">{CATEGORY_LABEL[event.category]}</p>
      {/* The AI one-liner says it best; the filing's own subject is shown only when there is no summary. */}
      {event.summary && event.category !== "management_change" ? (
        <p className="mt-1.5">{event.summary}</p>
      ) : (
        !hasCard && !(event.category === "management_change" && event.profile) && <Clamp text={event.headline} className="mt-1.5" />
      )}
      {event.results && <ResultsCard card={event.results} filingUrl={leadUrl} />}
      {event.category === "management_change" && <ProfileCard profile={event.profile} filingUrl={leadUrl} />}
      <PriceChip event={event} />
      <div className="flex flex-wrap items-baseline gap-x-5">
        <DocumentList documents={event.documents} />
        <a href={`#/ask/${encodeURIComponent(event.symbol)}?event=${encodeURIComponent(event.id)}`} className="mt-3 inline-block text-[13px] text-notable underline-offset-2 hover:underline">
          Ask about this
        </a>
      </div>
    </article>
  );
}

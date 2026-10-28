import type { EventsFile } from "../api/types";
import { useData } from "../hooks/useData";
import { CATEGORY_LABEL, formatWhen } from "../lib/format";
import { ResultsCard } from "./ResultsCard";

/** The Brief card that sent the user here, pinned above the dossier. */
export function ContextStrip({ eventId }: { eventId: string }) {
  const events = useData<EventsFile>("events.json");
  const event = events.status === "ok" ? events.data.events.find((e) => e.id === eventId) : undefined;
  if (!event) return null;
  return (
    <aside className="mb-6 rounded-md bg-surface p-3" aria-label="The update you asked about">
      <p className="text-[12px] text-muted">
        {CATEGORY_LABEL[event.category]}, {formatWhen(event.first_at)}
      </p>
      <p className="mt-1">{event.headline}</p>
      {event.results?.status === "ok" && <ResultsCard card={event.results} filingUrl={null} />}
      <a href={`#/brief/${event.id}`} className="mt-2 inline-block text-[13px] text-notable">Back to the brief</a>
    </aside>
  );
}

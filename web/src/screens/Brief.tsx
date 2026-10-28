import { useEffect } from "react";
import type { EventsFile, SignalsFile } from "../api/types";
import { EventCard } from "../components/EventCard";
import { MovesList } from "../components/MovesList";
import { RoutineGroup } from "../components/RoutineGroup";
import { StaleBanner } from "../components/StaleBanner";
import { Statement } from "../components/Statement";
import { WindowChips } from "../components/WindowChips";
import { useData } from "../hooks/useData";
import { useStoredState } from "../hooks/useStoredState";
import { buildDigest, WINDOWS } from "../lib/digest";
import { formatWhen } from "../lib/format";
import { signalsFor, type Settings } from "../lib/signals";

function headlineFor(critical: number, glance: number, windowLabel: string): string {
  if (critical > 0) return `${critical} ${critical === 1 ? "update needs" : "updates need"} your attention.`;
  if (glance > 0) return `Nothing critical. ${glance} worth a glance.`;
  return `Nothing material in the last ${windowLabel}.`;
}

export function Brief({ settings, focusId }: { settings: Settings; focusId: string | null }) {
  const events = useData<EventsFile>("events.json");
  const signals = useData<SignalsFile>("signals.json");
  const [storedHours, setHours] = useStoredState("finn.brief.hours", 24);

  const feed = events.status === "ok" ? events.data : null;
  const focused = focusId && feed ? feed.events.find((e) => e.id === focusId) : undefined;
  // An alert opens its card even when it is older than the chosen window.
  const hours = focused && Date.now() - Date.parse(focused.last_at) > storedHours * 3_600_000 ? 720 : storedHours;

  useEffect(() => {
    if (focused) document.getElementById(`event-${focused.id}`)?.scrollIntoView({ block: "start" });
  }, [focused]);

  if (events.status === "loading") return <Statement>Reading your filings…</Statement>;
  if (events.status === "error")
    return <Statement detail="Check your connection and reload the page.">Couldn't load your brief.</Statement>;
  if (!feed)
    return (
      <Statement detail="FINN reads every filing from your 18 holdings and keeps only what changes the picture. Your digest appears here after the first data run.">
        Your first brief is on its way.
      </Statement>
    );

  const window = WINDOWS.find((w) => w.hours === hours) ?? WINDOWS[0];
  const d = buildDigest(feed, new Date(), window.hours);
  const moves = signals.status === "ok" ? signalsFor(signals.data, settings, Math.ceil(window.hours / 24)) : [];
  return (
    <>
      <Statement detail={`Updated ${formatWhen(d.asOf)}.`}>
        {headlineFor(d.critical.length, d.notable.length + moves.length, window.label)}
      </Statement>
      <WindowChips hours={window.hours} onChange={setHours} />
      {d.stale && <StaleBanner asOf={d.asOf} />}
      {d.critical.map((e) => <EventCard key={e.id} event={e} focused={e.id === focusId} />)}
      <MovesList moves={moves} />
      {d.notable.map((e) => <EventCard key={e.id} event={e} focused={e.id === focusId} />)}
      <RoutineGroup items={d.routine.items} />
    </>
  );
}

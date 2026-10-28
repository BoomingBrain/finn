import { EventCard } from "../components/EventCard";
import { RoutineGroup } from "../components/RoutineGroup";
import { StaleBanner } from "../components/StaleBanner";
import { Statement } from "../components/Statement";
import { WindowChips } from "../components/WindowChips";
import { useEvents } from "../hooks/useEvents";
import { useStoredState } from "../hooks/useStoredState";
import { buildDigest, WINDOWS } from "../lib/digest";
import { formatWhen } from "../lib/format";

function headlineFor(critical: number, notable: number, windowLabel: string): string {
  if (critical > 0) return `${critical} ${critical === 1 ? "update needs" : "updates need"} your attention.`;
  if (notable > 0) return `Nothing critical. ${notable} worth a glance.`;
  return `Nothing material in the last ${windowLabel}.`;
}

export function Brief() {
  const state = useEvents();
  const [hours, setHours] = useStoredState("finn.brief.hours", 24);

  if (state.status === "loading") return <Statement>Reading your filings…</Statement>;
  if (state.status === "error")
    return <Statement detail="Check your connection and reload the page.">Couldn't load your brief.</Statement>;
  if (state.status === "empty")
    return (
      <Statement detail="FINN reads every filing from your 18 holdings and keeps only what changes the picture. Your digest appears here after the first data run.">
        Your first brief is on its way.
      </Statement>
    );

  const window = WINDOWS.find((w) => w.hours === hours) ?? WINDOWS[0];
  const d = buildDigest(state.feed, new Date(), window.hours);
  return (
    <>
      <Statement detail={`Updated ${formatWhen(d.asOf)}.`}>{headlineFor(d.critical.length, d.notable.length, window.label)}</Statement>
      <WindowChips hours={window.hours} onChange={setHours} />
      {d.stale && <StaleBanner asOf={d.asOf} />}
      {d.critical.map((e) => <EventCard key={e.id} event={e} />)}
      {d.notable.map((e) => <EventCard key={e.id} event={e} />)}
      <RoutineGroup items={d.routine.items} />
    </>
  );
}

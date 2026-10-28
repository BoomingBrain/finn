import type { EventsFile, SignalsFile } from "../api/types";
import { AlertRow } from "../components/AlertRow";
import { CategoryToggles } from "../components/CategoryToggles";
import { Statement } from "../components/Statement";
import { ThresholdSliders } from "../components/ThresholdSliders";
import { INBOX_DAYS, type Inbox } from "../hooks/useAlerts";
import { useData } from "../hooks/useData";
import type { Settings } from "../lib/signals";

export function Watch({ inbox, settings, onSettings }: { inbox: Inbox; settings: Settings; onSettings: (s: Settings) => void }) {
  const signals = useData<SignalsFile>("signals.json");
  const events = useData<EventsFile>("events.json");
  const names: Record<string, string> = signals.status === "ok" ? signals.data.names : {};
  if (events.status === "ok") for (const e of events.data.events) names[e.symbol] ??= e.company;
  const alerts = inbox.alerts ?? [];
  const title = inbox.alerts === null ? "Checking for alerts…" : inbox.unread > 0 ? `${inbox.unread} new ${inbox.unread === 1 ? "alert" : "alerts"}.` : "No new alerts.";

  return (
    <>
      <Statement detail={`From the last ${INBOX_DAYS} days, using your thresholds and the filing types you chose below.`}>{title}</Statement>
      {alerts.length > 0 && (
        <section aria-label="Alerts" className="mb-10">
          <ul>
            {alerts.map((a) => (
              <AlertRow key={a.id} alert={a} name={names[a.symbol] ?? a.symbol} seen={inbox.isSeen(a.id)}
                onOpen={() => {
                  inbox.markSeen([a.id]);
                  if (a.source === "announcement") window.location.hash = `#/brief/${encodeURIComponent(a.refId)}`;
                }} />
            ))}
          </ul>
          {inbox.unread > 0 && (
            <button type="button" onClick={() => inbox.markSeen(alerts.map((a) => a.id))} className="mt-3 text-[13px] text-notable">
              Mark all as seen
            </button>
          )}
        </section>
      )}
      <ThresholdSliders file={signals.status === "ok" ? signals.data : null} settings={settings} onChange={onSettings} />
      <CategoryToggles settings={settings} onChange={onSettings} />
    </>
  );
}

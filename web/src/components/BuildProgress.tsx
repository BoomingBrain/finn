import { useState } from "react";
import type { BuildProgress as Progress } from "../hooks/useResearch";
import { enableNotifications, notificationsSupported } from "../lib/notify";

function NotifyButton() {
  const [state, setState] = useState<"idle" | "on" | "off">(() =>
    notificationsSupported() && Notification.permission === "granted" ? "on" : "idle",
  );
  if (state === "on")
    return <p className="mt-3 text-[13px] text-muted">FINN will notify you when it's ready. You can keep using the app.</p>;
  if (state === "off")
    return <p className="mt-3 text-[13px] text-muted">Notifications are blocked; FINN will show a banner in the app instead.</p>;
  return (
    <p className="mt-3 text-[13px] text-muted">
      You can keep using the app; a banner appears when it's ready.{" "}
      {notificationsSupported() && (
        <button type="button" onClick={async () => setState((await enableNotifications()) ? "on" : "off")} className="font-semibold text-notable">
          Notify me when it's ready
        </button>
      )}
    </p>
  );
}

/** What the server is doing right now and how many of its steps are complete. Only real, reported steps move it. */
export function BuildProgress({ progress, waking, ahead }: { progress: Progress | null; waking: boolean; ahead: number | null }) {
  const label =
    ahead !== null && ahead > 0
      ? `Waiting for ${ahead} ${ahead === 1 ? "analysis" : "analyses"} ahead of yours to finish`
      : waking && !progress
        ? "Waking the research server — about a minute."
        : progress?.label ?? "Starting…";
  const pct = progress && progress.total ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <div className="mb-6">
      <div className="flex items-baseline justify-between gap-3 text-[14px]">
        <p className="min-w-0 text-muted" aria-live="polite">{label}</p>
        {progress && (
          <span className="shrink-0 text-[12px] text-muted">
            {progress.done} of {progress.total} steps
          </span>
        )}
      </div>
      <div
        role="progressbar"
        aria-label="Research progress"
        aria-valuemin={0}
        aria-valuemax={progress?.total ?? 1}
        aria-valuenow={progress?.done ?? 0}
        className="mt-2 h-[3px] overflow-hidden rounded-full bg-line"
      >
        <div className="h-full rounded-full bg-text transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
      </div>
      <p className="mt-2 text-[12px] text-muted">Sections appear below as each one is ready. A new company usually takes 10–30 minutes on the free AI tier.</p>
      <NotifyButton />
    </div>
  );
}

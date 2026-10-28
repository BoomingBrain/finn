import type { BuildProgress as Progress } from "../hooks/useResearch";

/** What the server is doing right now and how many of its steps are complete. Only real, reported steps move it. */
export function BuildProgress({ progress, waking }: { progress: Progress | null; waking: boolean }) {
  const label = waking && !progress ? "Waking the research server — about a minute." : progress?.label ?? "Starting…";
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
      <p className="mt-2 text-[12px] text-muted">Sections appear below as each one is ready. Usually 3–7 minutes.</p>
    </div>
  );
}

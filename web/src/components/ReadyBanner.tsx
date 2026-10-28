import { useEffect, useState } from "react";
import { onResearchReady } from "../hooks/useResearch";
import { shouldAnnounce, systemNotify } from "../lib/notify";

/** Says when a live analysis finishes while the investor is elsewhere in the app (or in another tab). */
export function ReadyBanner() {
  const [ready, setReady] = useState<{ symbol: string; name: string } | null>(null);

  useEffect(
    () =>
      onResearchReady((symbol, name) => {
        if (!shouldAnnounce(symbol, window.location.hash, document.hidden)) return;
        setReady({ symbol, name });
        systemNotify(symbol, name);
      }),
    [],
  );

  if (!ready) return null;
  return (
    <div role="status" className="fixed inset-x-0 bottom-[calc(env(safe-area-inset-bottom)+64px)] z-10 px-4">
      <div className="mx-auto flex max-w-xl items-center gap-3 rounded-md border border-line bg-surface px-4 py-3 shadow-lg">
        <p className="min-w-0 flex-1 text-[14px]">
          <span className="font-serif text-[16px]">{ready.name}</span> research is ready.
        </p>
        <a href={`#/ask/${encodeURIComponent(ready.symbol)}`} onClick={() => setReady(null)} className="shrink-0 font-semibold text-notable">
          Open
        </a>
        <button type="button" onClick={() => setReady(null)} aria-label="Dismiss" className="shrink-0 px-1 text-muted">
          ✕
        </button>
      </div>
    </div>
  );
}

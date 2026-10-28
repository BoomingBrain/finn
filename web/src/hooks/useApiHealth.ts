import { useEffect, useState } from "react";
import { apiBase } from "../api/client";

export type ApiHealth = "unset" | "checking" | "ok" | "down";

/** Whether the Render live-research service answers. A sleeping free instance can take ~1 minute to wake. */
export function useApiHealth(timeoutMs = 75_000): ApiHealth {
  const [state, setState] = useState<ApiHealth>(apiBase ? "checking" : "unset");
  useEffect(() => {
    if (!apiBase) return;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    fetch(`${apiBase}/api/health`, { signal: ctrl.signal })
      .then((r) => setState(r.ok ? "ok" : "down"))
      .catch(() => setState("down"))
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [timeoutMs]);
  return state;
}

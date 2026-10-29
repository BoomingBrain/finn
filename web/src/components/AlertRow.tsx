import type { Alert } from "../lib/signals";
import { companyName, directionClass, formatWhen } from "../lib/format";

export function AlertRow({ alert, name, seen, onOpen }: { alert: Alert; name: string; seen: boolean; onOpen: () => void }) {
  const when = alert.source === "signal" ? formatWhen(alert.at).replace(/ \d.*$/, "") : formatWhen(alert.at);
  return (
    <li className="border-t border-line">
      <button type="button" onClick={onOpen} className="flex w-full items-start gap-3 py-2.5 text-left">
        <span aria-hidden="true" className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${seen ? "bg-transparent" : "bg-critical"}`} />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className={`truncate ${seen ? "text-muted" : "font-semibold"}`}>{companyName(name)}</span>
            <span className="shrink-0 text-[12px] text-muted">{when}</span>
          </span>
          <span className="flex items-baseline gap-2">
            <span className="shrink-0 text-[12px] text-muted">{alert.label}</span>
            <span className={`min-w-0 truncate text-[14px] ${alert.change !== null ? directionClass(alert.change) : ""}`}>{alert.title}</span>
          </span>
          {!seen && <span className="sr-only"> (new)</span>}
        </span>
      </button>
    </li>
  );
}

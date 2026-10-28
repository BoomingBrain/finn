import type { Alert } from "../lib/signals";
import { formatWhen } from "../lib/format";

export function AlertRow({ alert, name, seen, onOpen }: { alert: Alert; name: string; seen: boolean; onOpen: () => void }) {
  return (
    <li className="border-t border-line">
      <button type="button" onClick={onOpen} className="flex w-full items-start gap-3 py-3 text-left">
        <span aria-hidden="true" className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${seen ? "bg-transparent" : "bg-critical"}`} />
        <span className="min-w-0 flex-1">
          <span className={`block ${seen ? "text-muted" : "font-semibold"}`}>{name}</span>
          <span className="line-clamp-2">{alert.title}</span>
          <span className="block text-[12px] text-muted">
            {alert.source === "signal" ? `Session of ${formatWhen(alert.at).replace(/ \d.*$/, "")}` : formatWhen(alert.at)}
            {!seen && <span className="sr-only"> (new)</span>}
          </span>
        </span>
      </button>
    </li>
  );
}

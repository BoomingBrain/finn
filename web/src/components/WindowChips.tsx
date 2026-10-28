import { WINDOWS } from "../lib/digest";

export function WindowChips({ hours, onChange }: { hours: number; onChange: (hours: number) => void }) {
  return (
    <div role="radiogroup" aria-label="Time window" className="mb-5 inline-flex rounded-md border border-line p-0.5">
      {WINDOWS.map((w) => {
        const selected = w.hours === hours;
        return (
          <button
            key={w.hours}
            type="button"
            role="radio"
            aria-checked={selected}
            aria-label={`Last ${w.label}`}
            onClick={() => onChange(w.hours)}
            className={`min-w-12 rounded px-3 py-1.5 text-[13px] ${selected ? "bg-surface font-semibold text-text" : "text-muted"}`}
          >
            {w.short}
          </button>
        );
      })}
    </div>
  );
}

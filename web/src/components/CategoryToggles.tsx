import type { Category } from "../api/types";
import { CATEGORY_LABEL } from "../lib/format";
import type { Settings } from "../lib/signals";

const OFFERED: Category[] = ["results", "M&A", "management_change", "fund_raise", "litigation", "pledging",
  "credit_rating", "insider_trading", "capex", "dividend", "bonus_split", "press_release"];

export function CategoryToggles({ settings, onChange }: { settings: Settings; onChange: (s: Settings) => void }) {
  const toggle = (c: Category) =>
    onChange({ ...settings, alert_categories: settings.alert_categories.includes(c) ? settings.alert_categories.filter((x) => x !== c) : [...settings.alert_categories, c] });
  return (
    <fieldset className="mt-3">
      <legend className="mb-2 text-[13px] font-semibold text-muted">Filings that alert you</legend>
      <div className="flex flex-wrap gap-2">
        {OFFERED.map((c) => {
          const on = settings.alert_categories.includes(c);
          return (
            <button key={c} type="button" aria-pressed={on} onClick={() => toggle(c)}
              className={`rounded-full border px-3 py-1.5 text-[13px] ${on ? "border-text bg-surface text-text" : "border-line text-muted"}`}>
              {CATEGORY_LABEL[c]}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

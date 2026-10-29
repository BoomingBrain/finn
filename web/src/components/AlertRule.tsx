import { useId, useState } from "react";
import type { SignalsFile } from "../api/types";
import { ruleParts } from "../lib/rule";
import { backtest, type Settings } from "../lib/signals";
import { CategoryToggles } from "./CategoryToggles";
import { ThresholdSliders } from "./ThresholdSliders";

/** The alert settings, collapsed to the rule they express; "Change" opens the controls in place. */
export function AlertRule({ file, settings, onChange }: { file: SignalsFile | null; settings: Settings; onChange: (s: Settings) => void }) {
  const [open, setOpen] = useState(false);
  const panel = useId();
  const parts = ruleParts(settings);
  const fired = file ? backtest(file, settings, 30) : null;
  const total = fired ? fired.price + fired.volume : null;

  return (
    <section aria-label="Alert rule" className="mb-6 rounded-md bg-surface px-4 py-3.5">
      <div className="flex items-start gap-3">
        <p className="min-w-0 flex-1 font-serif text-[17px] leading-[1.45]">
          Alert me when a stock moves <b className="font-semibold">{parts.price}</b> in a day or trades at{" "}
          <b className="font-semibold">{parts.volume}</b> its 20-day average volume
          {parts.filings ? (
            <>
              , and when a holding files about <b className="font-semibold">{parts.filings}</b>.
            </>
          ) : (
            "; filings won't alert you."
          )}
        </p>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={panel}
          onClick={() => setOpen((o) => !o)}
          className="-mr-1 shrink-0 rounded px-1 py-0.5 text-[13px] font-semibold text-notable"
        >
          {open ? "Done" : "Change"}
        </button>
      </div>
      {total !== null && (
        <p className="mt-1.5 text-[12px] text-muted">
          Price and volume would have fired {total === 1 ? "once" : `${total} times`} in the last 30 days.
        </p>
      )}
      <div id={panel} className={`grid transition-[grid-template-rows] duration-300 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        {/* inert while collapsed, so keyboard focus can't land on hidden controls (React 18 types lack the prop) */}
        <div className="min-h-0 overflow-hidden" ref={(el) => el?.toggleAttribute("inert", !open)}>
          <div className="mt-3 border-t border-line pt-1">
            <ThresholdSliders file={file} settings={settings} onChange={onChange} />
            <CategoryToggles settings={settings} onChange={onChange} />
            <button type="button" onClick={() => setOpen(false)} className="mt-4 mb-1 text-[13px] font-semibold text-notable">
              Done
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

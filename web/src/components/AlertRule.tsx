import { useId, useState } from "react";
import type { SignalsFile } from "../api/types";
import { ruleParts } from "../lib/rule";
import { backtest, type Settings } from "../lib/signals";
import { CategoryToggles } from "./CategoryToggles";
import { StatBox, StatGrid } from "./StatBox";
import { ThresholdSliders } from "./ThresholdSliders";

/** The alert settings, collapsed to the rule they express; "Change" opens the controls in place. */
export function AlertRule({ file, settings, onChange }: { file: SignalsFile | null; settings: Settings; onChange: (s: Settings) => void }) {
  const [open, setOpen] = useState(false);
  const panel = useId();
  const parts = ruleParts(settings);
  const fired = file ? backtest(file, settings, 30) : null;
  const total = fired ? fired.price + fired.volume : null;

  return (
    <section aria-label="Alert rule" className="mb-5">
      <div className="flex items-center justify-between">
        <h2 className="text-[13px] font-semibold text-muted">You're alerted on</h2>
        <button type="button" aria-expanded={open} aria-controls={panel} onClick={() => setOpen((o) => !o)}
          className="rounded px-1 py-0.5 text-[13px] font-semibold text-notable">
          {open ? "Done" : "Change"}
        </button>
      </div>
      <button type="button" onClick={() => setOpen(true)} aria-label="Change alert settings" className="mt-1.5 block w-full text-left">
        <StatGrid cols={3}>
          <StatBox label="Price move" value={parts.price} />
          <StatBox label="Volume" value={parts.volume} />
          <StatBox label="Filing types" value={String(settings.alert_categories.length)} />
        </StatGrid>
      </button>
      {total !== null && <p className="mt-1.5 text-[12px] text-muted">{total} price and volume alerts in the last 30 days</p>}
      <div id={panel} className={`grid transition-[grid-template-rows] duration-300 ease-out ${open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
        {/* inert while collapsed, so keyboard focus can't land on hidden controls (React 18 types lack the prop) */}
        <div className="min-h-0 overflow-hidden" ref={(el) => el?.toggleAttribute("inert", !open)}>
          <div className="mt-2 rounded-md bg-surface px-3 pb-2">
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

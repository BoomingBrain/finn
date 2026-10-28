import type { SignalsFile } from "../api/types";
import { backtest, LIMITS, type Settings } from "../lib/signals";

const BACKTEST_DAYS = 30;

function firedText(count: number, top: string[]): string {
  const times = count === 1 ? "once" : `${count} times`;
  const base = count === 0 ? `Would not have fired in the last ${BACKTEST_DAYS} days.` : `Would have fired ${times} in the last ${BACKTEST_DAYS} days.`;
  return top.length ? `${base} Mostly ${top.join(", ")}.` : base;
}

function topSymbols(file: SignalsFile, settings: Settings, kind: "price" | "volume"): string[] {
  const only = kind === "price" ? { ...settings, volume_multiple: Infinity } : { ...settings, price_move_pct: Infinity };
  return Object.entries(backtest(file, only, BACKTEST_DAYS).bySymbol)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([s, n]) => `${file.names[s] ?? s} (${n})`);
}

function Slider(props: { id: string; label: string; value: number; display: string; min: number; max: number; step: number; onChange: (v: number) => void; evidence: string }) {
  return (
    <div className="border-t border-line py-4">
      <div className="flex items-baseline justify-between">
        <label htmlFor={props.id}>{props.label}</label>
        <output htmlFor={props.id} className="font-semibold">{props.display}</output>
      </div>
      <input
        id={props.id} type="range" min={props.min} max={props.max} step={props.step} value={props.value}
        onChange={(e) => props.onChange(Number(e.target.value))}
        className="mt-3 w-full accent-[var(--notable)]"
      />
      <p className="mt-1 text-[13px] text-muted" aria-live="polite">{props.evidence}</p>
    </div>
  );
}

/** Thresholds with evidence: each change shows how often it would have fired over the last 30 days. */
export function ThresholdSliders({ file, settings, onChange }: { file: SignalsFile | null; settings: Settings; onChange: (s: Settings) => void }) {
  const result = file ? backtest(file, settings, BACKTEST_DAYS) : null;
  const evidence = (kind: "price" | "volume") =>
    file && result ? firedText(kind === "price" ? result.price : result.volume, topSymbols(file, settings, kind)) : "Price history isn't available yet.";
  return (
    <section aria-labelledby="thresholds">
      <h2 id="thresholds" className="mb-1 font-serif text-[20px] font-medium">What counts as unusual</h2>
      <Slider
        id="price" label="Price move in a day" value={settings.price_move_pct} display={`±${settings.price_move_pct.toFixed(1)}%`}
        {...LIMITS.price_move_pct} onChange={(v) => onChange({ ...settings, price_move_pct: v })} evidence={evidence("price")}
      />
      <Slider
        id="volume" label="Volume against its 20-day average" value={settings.volume_multiple} display={`${settings.volume_multiple.toFixed(1)}×`}
        {...LIMITS.volume_multiple} onChange={(v) => onChange({ ...settings, volume_multiple: v })} evidence={evidence("volume")}
      />
    </section>
  );
}

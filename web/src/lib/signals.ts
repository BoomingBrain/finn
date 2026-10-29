/** Applies the investor's thresholds to precomputed per-day metrics. Measurement lives in the backend
 * (finn/push/signals.py, tested there); the browser only compares numbers. */
import type { Category, Event, SignalsFile } from "../api/types";
import { CATEGORY_LABEL } from "./format";

export interface Settings {
  price_move_pct: number;
  volume_multiple: number;
  alert_categories: Category[];
}

export const DEFAULT_SETTINGS: Settings = {
  price_move_pct: 5,
  volume_multiple: 2,
  alert_categories: ["results", "M&A", "management_change", "fund_raise", "litigation", "pledging"],
};

export const LIMITS = {
  price_move_pct: { min: 0.5, max: 50, step: 0.5 },
  volume_multiple: { min: 1.1, max: 10, step: 0.1 },
} as const;

export interface Signal {
  id: string;
  symbol: string;
  name: string;
  date: string; // YYYY-MM-DD trading session
  kind: "price_move" | "volume_spike";
  value: number; // % move, or volume multiple
  threshold: number;
}

export interface Alert {
  id: string;
  symbol: string;
  title: string;
  label: string; // filing type, or "Price move" / "Volume"
  change: number | null; // a price move's direction, for colour
  source: "announcement" | "signal";
  refId: string;
  at: string;
}

const DAY_MS = 86_400_000;
const sessionEnd = (date: string) => `${date}T15:30:00+05:30`;

/** Sessions within `days` calendar days of the newest session in the file, newest first. */
export function signalsFor(file: SignalsFile, settings: Settings, days: number): Signal[] {
  const dates = Object.values(file.series).flatMap((s) => s.map((m) => m.date));
  if (dates.length === 0) return [];
  const newest = Math.max(...dates.map((d) => Date.parse(d)));
  const out: Signal[] = [];
  for (const [symbol, series] of Object.entries(file.series)) {
    const name = file.names[symbol] ?? symbol;
    for (const m of series) {
      if (newest - Date.parse(m.date) >= days * DAY_MS) continue;
      if (Math.abs(m.change_pct) >= settings.price_move_pct)
        out.push({ id: `${symbol}:${m.date}:price_move`, symbol, name, date: m.date, kind: "price_move", value: m.change_pct, threshold: settings.price_move_pct });
      if (m.volume_multiple !== null && m.volume_multiple >= settings.volume_multiple)
        out.push({ id: `${symbol}:${m.date}:volume_spike`, symbol, name, date: m.date, kind: "volume_spike", value: m.volume_multiple, threshold: settings.volume_multiple });
    }
  }
  return out.sort((a, b) => b.date.localeCompare(a.date) || a.kind.localeCompare(b.kind));
}

export interface Backtest {
  total: number;
  price: number;
  volume: number;
  bySymbol: Record<string, number>;
}

/** How many alerts these thresholds would have raised over the last `days` days. */
export function backtest(file: SignalsFile, settings: Settings, days = 30): Backtest {
  const signals = signalsFor(file, settings, days);
  const bySymbol: Record<string, number> = {};
  for (const s of signals) bySymbol[s.symbol] = (bySymbol[s.symbol] ?? 0) + 1;
  return {
    total: signals.length,
    price: signals.filter((s) => s.kind === "price_move").length,
    volume: signals.filter((s) => s.kind === "volume_spike").length,
    bySymbol,
  };
}

/** Critical events in the chosen categories plus every price signal, newest first. Notable items in those
 * categories (e.g. setting up a subsidiary) stay in the Brief without pinging the investor. */
export function alertsFor(events: Event[], signals: Signal[], settings: Settings): Alert[] {
  const fromEvents: Alert[] = events
    .filter((e) => e.tier === "critical" && settings.alert_categories.includes(e.category))
    .map((e) => ({
      id: `event:${e.id}`, symbol: e.symbol, title: e.summary ?? e.headline, label: CATEGORY_LABEL[e.category], change: null,
      source: "announcement", refId: e.id, at: e.first_at,
    }));
  const fromSignals: Alert[] = signals.map((s) => ({
    id: `signal:${s.id}`, symbol: s.symbol, source: "signal", refId: s.id, at: sessionEnd(s.date),
    label: s.kind === "price_move" ? "Price move" : "Volume",
    change: s.kind === "price_move" ? s.value : null,
    title: s.kind === "price_move" ? `${s.value > 0 ? "Up" : "Down"} ${Math.abs(s.value).toFixed(1)}% in a day` : `${s.value.toFixed(1)}× its 20-day average`,
  }));
  return [...fromEvents, ...fromSignals].sort((a, b) => Date.parse(b.at) - Date.parse(a.at));
}

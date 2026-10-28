import type { SignalsFile } from "../api/types";

export const RANGES = [
  { label: "1 week", phrase: "the past week", short: "1W", sessions: 5 },
  { label: "1 month", phrase: "the past month", short: "1M", sessions: 21 },
  { label: "3 months", phrase: "the past 3 months", short: "3M", sessions: 60 },
] as const;

export interface HoldingRow {
  symbol: string;
  name: string;
  closes: number[]; // range start (the close before the window) .. latest
  last: number;
  rangePct: number;
  dayPct: number;
  lastDate: string;
}

/** One row per holding over the last `sessions` sessions, biggest absolute move first. */
export function holdingRows(signals: SignalsFile, sessions: number): HoldingRow[] {
  const rows: HoldingRow[] = [];
  for (const [symbol, series] of Object.entries(signals.series)) {
    if (series.length < 2) continue;
    const window = series.slice(-(sessions + 1)); // the extra close is the range's starting point
    const first = window[0].close, latest = window[window.length - 1];
    rows.push({
      symbol,
      name: signals.names[symbol] ?? symbol,
      closes: window.map((d) => d.close),
      last: latest.close,
      rangePct: ((latest.close - first) / first) * 100,
      dayPct: latest.change_pct,
      lastDate: latest.date,
    });
  }
  return rows.sort((a, b) => Math.abs(b.rangePct) - Math.abs(a.rangePct));
}

/** Equal-weighted average move (the mock portfolio has no position sizes). */
export function portfolioMove(rows: HoldingRow[]): number | null {
  return rows.length ? rows.reduce((sum, r) => sum + r.rangePct, 0) / rows.length : null;
}

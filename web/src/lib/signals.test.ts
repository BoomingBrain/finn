import { describe, expect, it } from "vitest";
import type { DayMetric, Event, SignalsFile } from "../api/types";
import { alertsFor, backtest, DEFAULT_SETTINGS, signalsFor } from "./signals";

const day = (date: string, change_pct: number, volume_multiple: number | null): DayMetric => ({ date, close: 100, change_pct, volume_multiple });
const file = (series: Record<string, DayMetric[]>): SignalsFile => ({ as_of: "2026-10-28T18:00:00+05:30", names: { INFY: "Infosys", TCS: "TCS" }, series });

describe("signalsFor", () => {
  it("fires at and above the thresholds and not below", () => {
    const f = file({ INFY: [day("2026-10-20", -5.0, 2.0), day("2026-10-21", 4.99, 1.99), day("2026-10-22", 7.2, null)] });
    const s = signalsFor(f, DEFAULT_SETTINGS, 30);
    expect(s.map((x) => `${x.date} ${x.kind}`)).toEqual(["2026-10-22 price_move", "2026-10-20 price_move", "2026-10-20 volume_spike"]);
    expect(s[0].value).toBe(7.2);
  });
});

describe("backtest", () => {
  const f = file({
    INFY: [day("2026-09-01", 0, 9.0), day("2026-10-05", 0, 2.5), day("2026-10-20", 1, 3.0)],
    TCS: [day("2026-10-27", -1, 2.1)],
  });

  it("counts what would have fired in the last 30 days", () => {
    const r = backtest(f, DEFAULT_SETTINGS, 30);
    expect(r.volume).toBe(3); // 1 Sep is outside the window
    expect(r.price).toBe(0);
    expect(r.total).toBe(3);
    expect(r.bySymbol).toEqual({ INFY: 2, TCS: 1 });
  });

  it("drops to zero at a very high volume threshold", () => {
    expect(backtest(f, { ...DEFAULT_SETTINGS, volume_multiple: 10 }, 30).total).toBe(0);
  });
});

describe("alertsFor", () => {
  const ev = (id: string, category: Event["category"], tier: Event["tier"], at: string): Event => ({
    id, symbol: "INFY", company: "Infosys", category, tier, first_at: at, last_at: at, headline: id, summary: null,
    results: null, profile: null, documents: [], price_change_pct: null, volume_multiple: null, price_date: null,
  });

  it("alerts on critical events in chosen categories, includes price signals, newest first", () => {
    const events = [
      ev("dividend", "dividend", "notable", "2026-10-23T16:10:00+05:30"),
      ev("cfo", "management_change", "critical", "2026-10-24T10:00:00+05:30"),
      ev("notice", "results", "routine", "2026-10-25T10:00:00+05:30"),
      ev("subsidiary", "M&A", "notable", "2026-10-25T11:00:00+05:30"), // chosen category, but not material
    ];
    const signals = signalsFor(file({ INFY: [day("2026-10-26", -6, null)] }), DEFAULT_SETTINGS, 30);
    const alerts = alertsFor(events, signals, DEFAULT_SETTINGS);
    expect(alerts.map((a) => a.refId)).toEqual([signals[0].id, "cfo"]);
  });
});

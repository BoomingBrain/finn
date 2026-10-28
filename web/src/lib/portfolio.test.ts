import { describe, expect, it } from "vitest";
import type { SignalsFile } from "../api/types";
import { holdingRows, portfolioMove } from "./portfolio";

const day = (date: string, close: number, change_pct = 0) => ({ date, close, change_pct, volume_multiple: 1 });
const signals: SignalsFile = {
  as_of: "2026-10-28T14:36:00+05:30",
  names: { INFY: "Infosys", TCS: "TCS" },
  series: {
    INFY: [day("2026-10-23", 100), day("2026-10-26", 104), day("2026-10-27", 102, -1.9)],
    TCS: [day("2026-10-23", 200), day("2026-10-26", 180), day("2026-10-27", 190, 5.6)],
  },
};

describe("holdingRows", () => {
  it("measures the move from the close before the window and sorts the biggest movers first", () => {
    const rows = holdingRows(signals, 2);
    expect(rows.map((r) => r.symbol)).toEqual(["TCS", "INFY"]);
    expect(rows[0].rangePct).toBeCloseTo(-5); // 200 -> 190
    expect(rows[1]).toMatchObject({ name: "Infosys", last: 102, dayPct: -1.9, closes: [100, 104, 102] });
    expect(rows[1].rangePct).toBeCloseTo(2);
  });

  it("uses only the last sessions of a long series", () => {
    expect(holdingRows(signals, 1)[0].closes).toEqual([180, 190]);
  });

  it("averages the moves equally across holdings", () => {
    expect(portfolioMove(holdingRows(signals, 2))).toBeCloseTo(-1.5);
    expect(portfolioMove([])).toBeNull();
  });
});

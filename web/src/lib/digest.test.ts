import { describe, expect, it } from "vitest";
import type { Event } from "../api/types";
import { buildDigest } from "./digest";

const now = new Date("2026-10-28T12:00:00+05:30");
const ev = (id: string, tier: Event["tier"], hoursAgo: number): Event => {
  const at = new Date(now.getTime() - hoursAgo * 3_600_000).toISOString();
  return { id, symbol: "INFY", company: "Infosys", category: "results", tier, first_at: at, last_at: at, headline: id,
    summary: null, results: null, profile: null, documents: [], price_change_pct: null, volume_multiple: null, price_date: null };
};

describe("buildDigest", () => {
  it("keeps the window, sorts newest first within tiers and collapses routine", () => {
    const feed = { as_of: now.toISOString(), events: [ev("old", "critical", 25), ev("c1", "critical", 5), ev("c2", "critical", 1), ev("r", "routine", 2)] };
    const d = buildDigest(feed, now, 24);
    expect(d.critical.map((e) => e.id)).toEqual(["c2", "c1"]);
    expect(d.routine.count).toBe(1);
    expect(buildDigest(feed, now, 48).critical.map((e) => e.id)).toEqual(["c2", "c1", "old"]);
  });

  it("is quiet when only routine filings are in the window", () => {
    expect(buildDigest({ as_of: now.toISOString(), events: [ev("r", "routine", 2)] }, now, 24).quiet).toBe(true);
  });

  it("is stale when the data is older than 36 hours", () => {
    const asOf = new Date(now.getTime() - 40 * 3_600_000).toISOString();
    expect(buildDigest({ as_of: asOf, events: [] }, now, 24).stale).toBe(true);
    expect(buildDigest({ as_of: now.toISOString(), events: [] }, now, 24).stale).toBe(false);
  });
});

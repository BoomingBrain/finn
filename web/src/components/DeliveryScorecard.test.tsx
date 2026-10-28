import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DeliveryData, DeliveryRow } from "../api/types";
import { DeliveryScorecard } from "./DeliveryScorecard";
import { matchSymbols } from "./SymbolSearch";

const row = (verdict: DeliveryRow["verdict"], raw_metric: string, value: number | null): DeliveryRow => ({
  target: { metric: "ebitda_margin", raw_metric, comparison: "between", value: 20, value_high: 24, unit: "pct",
    period: "FY26", quote: "We stay committed to our corridor of 20% to 24%.", source_id: "T:2025-11-01:p5", said_on: "2025-11-01" },
  actual: { value, quarters_in: 4, quarters_needed: 4 },
  verdict,
  explanation: "Margin came in at 24.1%, inside the band.",
});

describe("DeliveryScorecard", () => {
  it("summarises checkable promises, mutes uncheckable rows and links quotes to the page", () => {
    const data: DeliveryData = { transcripts: ["Transcript Nov 2025"], rows: [row("met", "EBITDA margin", 24.1), row("not_checkable", "A&SP", null)] };
    const citations = [{ source_id: "T:2025-11-01:p5", url: "https://bse/t.pdf", page: 5 }];
    render(<DeliveryScorecard data={data} citations={citations} />);
    expect(screen.getByText("1 of 1 checkable promise met.")).toBeTruthy();
    expect(screen.getByText("Met").className).toContain("text-up");
    expect(screen.getByText("Can't check").closest("li")!.className).toContain("text-muted");
    const chips = screen.getAllByRole("link", { name: "Nov 2025 call, p5" });
    expect(chips[0].getAttribute("href")).toBe("https://bse/t.pdf#page=5");
  });

  it("says so when management gave no numeric targets", () => {
    render(<DeliveryScorecard data={{ transcripts: ["a", "b", "c", "d"], rows: [] }} citations={[]} />);
    expect(screen.getByText(/no explicit numeric targets in the last 4 earnings calls/)).toBeTruthy();
  });
});

describe("matchSymbols", () => {
  const all = [
    { symbol: "KOTAKBANK", name: "Kotak Mahindra Bank Limited", precomputed: false },
    { symbol: "HDFCBANK", name: "HDFC Bank Limited", precomputed: true },
    { symbol: "BANKBARODA", name: "Bank of Baroda", precomputed: false },
  ];
  it("ranks symbol prefixes before name matches", () => {
    expect(matchSymbols(all, "bank").map((s) => s.symbol)).toEqual(["BANKBARODA", "KOTAKBANK", "HDFCBANK"]);
    expect(matchSymbols(all, "  ")).toEqual([]);
  });
});

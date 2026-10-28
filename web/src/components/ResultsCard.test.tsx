import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ResultsCard as Card } from "../api/types";
import { ResultsCard } from "./ResultsCard";

const row = (current: number, qoq: number | null, yoy: number | null) => ({
  current, prev_q: current, year_ago: current, qoq_pct: qoq, yoy_pct: yoy,
});
const corporate: Card = {
  status: "ok", layout: "corporate", basis: "consolidated", period_end: "2026-09-30",
  metrics: { Revenue: row(49244, 12.4, -3.1), EBITDA: row(11689, 2.5, 11), PBT: row(11063, 0.3, 8.2), PAT: row(7838, 0.8, 6.3) },
  not_applicable: [], missing: [], verified: null, mismatches: [], unit: "₹ Cr",
};

describe("ResultsCard", () => {
  it("formats QoQ gains as positive and YoY falls as negative", () => {
    render(<ResultsCard card={corporate} filingUrl="https://x/f.pdf" />);
    const up = screen.getByText("+12.4%");
    const down = screen.getByText("−3.1%");
    expect(up.className).toContain("text-up");
    expect(down.className).toContain("text-down");
  });

  it("shows NII for lenders and says EBITDA does not apply", () => {
    const lender: Card = { ...corporate, layout: "lender", not_applicable: ["EBITDA"],
      metrics: { NII: row(44464.2, 3.5, 10.5), PBT: row(28662.54, 5.4, 7.5), PAT: row(21537.09, 5.7, 5.8) } };
    render(<ResultsCard card={lender} filingUrl={null} />);
    expect(screen.getByText("NII")).toBeTruthy();
    expect(screen.getByText("EBITDA n/a for lenders")).toBeTruthy();
  });

  it("sends the reader to the filing when the numbers could not be read", () => {
    render(<ResultsCard card={{ ...corporate, status: "unreadable", metrics: {} }} filingUrl="https://x/f.pdf" />);
    const link = screen.getByRole("link", { name: "Couldn't read the numbers — open filing" });
    expect(link.getAttribute("href")).toBe("https://x/f.pdf");
  });

  it("marks numbers that disagree with reported financials", () => {
    render(<ResultsCard card={{ ...corporate, verified: false, mismatches: ["Revenue"] }} filingUrl={null} />);
    expect(screen.getByText("Unverified")).toBeTruthy();
  });
});

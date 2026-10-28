import { describe, expect, it } from "vitest";
import type { DeliveryRow } from "../api/types";
import { parseHash } from "../hooks/useHashRoute";
import { parseSSE, refusal } from "../hooks/useResearch";
import { citationHref, citationLabel, deliveredText, deliverySummary, targetText } from "./research";

const row = (verdict: DeliveryRow["verdict"], value: number | null = 24.1, quarters_in = 4): DeliveryRow => ({
  target: { metric: "ebitda_margin", raw_metric: "EBITDA margin", comparison: "between", value: 20, value_high: 24,
    unit: "pct", period: "FY26", quote: "corridor of 20% to 24%", source_id: "T:2025-11-01:p5", said_on: "2025-11-01" },
  actual: { value, quarters_in, quarters_needed: 4 },
  verdict,
  explanation: "",
});

describe("research helpers", () => {
  it("labels and links citations to the exact page", () => {
    expect(citationLabel("T:2026-08-01:p12")).toBe("Aug 2026 call, p12");
    expect(citationLabel("AR:2026:p73")).toBe("Annual report 2026, p73");
    expect(citationLabel("SCR")).toBe("screener.in");
    expect(citationHref({ source_id: "AR:2026:p73", url: "https://x/ar.pdf", page: 73 })).toBe("https://x/ar.pdf#page=73");
  });

  it("writes targets and delivered values", () => {
    expect(targetText(row("met").target)).toBe("20–24%");
    expect(deliveredText(row("pending", 26.2, 1))).toBe("tracking 26.2% after 1 of 4 quarters");
    expect(deliveredText(row("not_checkable", null))).toBeNull();
  });

  it("counts only checkable promises in the summary", () => {
    expect(deliverySummary([row("met"), row("missed"), row("pending"), row("not_checkable")]))
      .toBe("1 of 2 checkable promises met; 1 still in progress.");
    expect(deliverySummary([row("not_checkable")])).toBe("No promise can be checked yet.");
  });
});

describe("streaming", () => {
  it("parses SSE messages, skips keep-alives and keeps the unfinished tail", () => {
    const { messages, rest } = parseSSE(': building\n\ndata: {"a":1}\n\nevent: done\ndata: {}\n\ndata: {"b"');
    expect(messages).toEqual([{ event: "message", data: '{"a":1}' }, { event: "done", data: "{}" }]);
    expect(rest).toBe('data: {"b"');
  });

  it("maps server refusals to fixed copy", () => {
    expect(refusal("XYZ", 404, "unknown_symbol").message).toBe("FINN can't find XYZ on NSE.");
    expect(refusal("XYZ", 429, "rate_limited").message).toMatch(/3 new tickers an hour/);
  });

  it("reads the originating event from the hash", () => {
    expect(parseHash("#/ask/PIDILITIND?event=abc")).toEqual({ tab: "ask", param: "PIDILITIND", query: { event: "abc" } });
  });
});

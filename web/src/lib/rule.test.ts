import { describe, expect, it } from "vitest";
import { categoryPhrase, ruleParts } from "./rule";
import { DEFAULT_SETTINGS } from "./signals";

describe("alert rule sentence", () => {
  it("reads the settings back in words", () => {
    expect(ruleParts(DEFAULT_SETTINGS)).toEqual({
      price: `±${DEFAULT_SETTINGS.price_move_pct.toFixed(1)}%`,
      volume: `${DEFAULT_SETTINGS.volume_multiple.toFixed(1)}×`,
      filings: "results, M&A, management change or 3 more",
    });
  });

  it("lists short category sets in full", () => {
    expect(categoryPhrase(["results"])).toBe("results");
    expect(categoryPhrase(["results", "M&A"])).toBe("results or M&A");
    expect(categoryPhrase([])).toBe("");
  });
});

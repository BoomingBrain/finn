import type { Category } from "../api/types";
import { CATEGORY_LABEL } from "./format";
import type { Settings } from "./signals";

const lower = (c: Category) => (c === "M&A" ? "M&A" : CATEGORY_LABEL[c].toLowerCase());

/** "results, M&A, management change or 3 more" */
export function categoryPhrase(categories: Category[], shown = 3): string {
  if (categories.length === 0) return "";
  const names = categories.map(lower);
  if (names.length <= shown) return names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} or ${names[names.length - 1]}`;
  return `${names.slice(0, shown).join(", ")} or ${names.length - shown} more`;
}

/** The alert settings read back as one sentence; the parts are returned separately so values can be set in bold. */
export function ruleParts(s: Settings): { price: string; volume: string; filings: string } {
  return {
    price: `±${s.price_move_pct.toFixed(1)}%`,
    volume: `${s.volume_multiple.toFixed(1)}×`,
    filings: categoryPhrase(s.alert_categories),
  };
}

import type { Category } from "../api/types";

const IST = "Asia/Kolkata";
const crore = (digits: number) => new Intl.NumberFormat("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

/** ₹ crore with Indian grouping: 1,78,650 / 848.5 */
export function formatCrore(n: number): string {
  return crore(Math.abs(n) >= 1000 ? 0 : 1).format(n).replace("-", "−");
}

/** +12.4% / −3.1% / — (true minus sign) */
export function formatPct(v: number | null): string {
  if (v === null) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${sign}${Math.abs(v).toFixed(1)}%`;
}

export function directionClass(v: number | null): string {
  return v === null || v === 0 ? "text-muted" : v > 0 ? "text-up" : "text-down";
}

/** Indian fiscal quarter of a quarter-end date: 2026-09-30 -> Q2 FY27 */
export function fiscalQuarter(periodEnd: string | null): string | null {
  if (!periodEnd) return null;
  const [y, m] = periodEnd.split("-").map(Number);
  const q = { 6: 1, 9: 2, 12: 3, 3: 4 }[m];
  if (!q) return null;
  const fy = (m > 3 ? y + 1 : y) % 100;
  return `Q${q} FY${String(fy).padStart(2, "0")}`;
}

export function formatWhen(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit", timeZone: IST })
    .format(new Date(iso)).replace(",", "");
}

export function relativeTime(iso: string, now: Date = new Date()): string {
  const mins = Math.round((now.getTime() - new Date(iso).getTime()) / 60000);
  if (mins < 60) return `${Math.max(mins, 1)} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 36) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  return `${days} days ago`;
}

export const CATEGORY_LABEL: Record<Category, string> = {
  results: "Results", "M&A": "M&A", fund_raise: "Fund raise", management_change: "Management change",
  litigation: "Litigation or regulatory", insider_trading: "Insider trade", earnings_call: "Earnings call",
  investor_meetings: "Investor meeting", credit_rating: "Credit rating", dividend: "Dividend",
  bonus_split: "Bonus or split", capex: "Capex", press_release: "Company news", postal_ballot: "Postal ballot",
  agm_egm: "Shareholder meeting", pledging: "Promoter pledge", unclassified: "Routine filing",
};

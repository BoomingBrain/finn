import type { Citation, DeliveryRow, DossierSources } from "../api/types";
import { formatCrore } from "./format";

const MONTH = new Intl.DateTimeFormat("en-IN", { month: "short", year: "numeric", timeZone: "UTC" });

/** "T:2026-08-01:p12" -> "Aug 2026 call, p12"; "AR:2026:p73" -> "Annual report 2026, p73"; "SCR" -> "screener.in" */
export function citationLabel(sourceId: string): string {
  if (sourceId === "SCR") return "screener.in";
  const [kind, doc, page] = sourceId.split(":");
  const p = page ? `, ${page}` : "";
  if (kind === "T") return `${MONTH.format(new Date(`${doc}T00:00:00Z`))} call${p}`;
  if (kind === "AR") return `Annual report ${doc}${p}`;
  return sourceId;
}

/** Opens the PDF on the cited page (browsers' PDF viewers honour #page=N). */
export function citationHref(c: Citation): string {
  return c.page ? `${c.url}#page=${c.page}` : c.url;
}

function amount(v: number, unit: "pct" | "cr"): string {
  return unit === "pct" ? `${Number(v.toFixed(1))}%` : `₹${formatCrore(v)} Cr`;
}

const SIGN = { gte: "≥", lte: "≤", approx: "≈", between: "" } as const;

/** "≥ 12%", "20–24%", "≈ ₹1,200 Cr" */
export function targetText(t: DeliveryRow["target"]): string {
  if (t.comparison === "between" && t.value_high !== null)
    return t.unit === "pct" ? `${Number(t.value.toFixed(1))}–${amount(t.value_high, "pct")}` : `${amount(t.value, "cr")}–${amount(t.value_high, "cr")}`;
  return `${SIGN[t.comparison]} ${amount(t.value, t.unit)}`.trim();
}

export function deliveredText(row: DeliveryRow): string | null {
  const { value, quarters_in, quarters_needed } = row.actual;
  if (row.verdict === "not_checkable" || value === null) return null;
  const v = amount(value, row.target.unit);
  return row.verdict === "pending" ? `tracking ${v} after ${quarters_in} of ${quarters_needed} quarters` : v;
}

/** "2 of 3 checkable promises met" — only met / partly / missed are checkable so far. */
export function deliverySummary(rows: DeliveryRow[]): string {
  const checkable = rows.filter((r) => r.verdict === "met" || r.verdict === "partly" || r.verdict === "missed");
  const met = checkable.filter((r) => r.verdict === "met").length;
  const pending = rows.filter((r) => r.verdict === "pending").length;
  const head = checkable.length
    ? `${met} of ${checkable.length} checkable ${checkable.length === 1 ? "promise" : "promises"} met`
    : "No promise can be checked yet";
  return pending ? `${head}; ${pending} still in progress.` : `${head}.`;
}

const DAY = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });

/** "Covers results to Sep 2026, the Aug 2026 call and the FY26 annual report. Updated 28 Oct 2026." */
export function coverageText(sources: DossierSources | undefined, builtAt: string | undefined): string | null {
  if (!sources) return null;
  const parts = [
    sources.quarter && `results to ${sources.quarter}`,
    sources.transcript && `the ${MONTH.format(new Date(`${sources.transcript}T00:00:00Z`))} call`,
    sources.annual_report && `the FY${String(sources.annual_report % 100).padStart(2, "0")} annual report`,
  ].filter(Boolean) as string[];
  if (parts.length === 0) return null;
  const list = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
  return `Covers ${list}.${builtAt ? ` Updated ${DAY.format(new Date(builtAt))}.` : ""}`;
}

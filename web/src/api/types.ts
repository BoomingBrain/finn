/** Mirrors backend/finn/models.py (snake_case kept as in the JSON). */
export type Tier = "critical" | "notable" | "routine";
export type Category =
  | "results" | "M&A" | "fund_raise" | "management_change" | "litigation" | "insider_trading"
  | "earnings_call" | "investor_meetings" | "credit_rating" | "dividend" | "bonus_split" | "capex"
  | "press_release" | "postal_ballot" | "agm_egm" | "pledging" | "unclassified";

export interface MetricRow {
  current: number;
  prev_q: number;
  year_ago: number;
  qoq_pct: number | null;
  yoy_pct: number | null;
}

export interface ResultsCard {
  status: "ok" | "unreadable";
  layout: "corporate" | "lender";
  basis: "consolidated" | "standalone" | null;
  period_end: string | null;
  metrics: Record<string, MetricRow>;
  not_applicable: string[];
  missing: string[];
  verified: boolean | null;
  mismatches: string[];
  unit: string;
}

export interface PersonProfile {
  name: string;
  role: string;
  change: "appointed" | "resigned" | "retired";
  effective_date: string | null;
  background: string;
  prior_roles: string[];
}

export interface DocRef {
  title: string;
  url: string | null;
  filed_at: string;
}

export interface Event {
  id: string;
  symbol: string;
  company: string;
  category: Category;
  tier: Tier;
  first_at: string;
  last_at: string;
  headline: string;
  summary: string | null;
  results: ResultsCard | null;
  profile: PersonProfile | null;
  documents: DocRef[];
  price_change_pct: number | null;
  volume_multiple: number | null;
  price_date: string | null;
}

export interface EventsFile {
  as_of: string;
  events: Event[];
}

export interface DayMetric {
  date: string;
  close: number;
  change_pct: number;
  volume_multiple: number | null;
}

export interface SignalsFile {
  as_of: string;
  names: Record<string, string>;
  series: Record<string, DayMetric[]>;
}

/** Research dossiers: mirrors backend/finn/pull/{dossier,sections,guidance,metrics}.py */
export interface Citation {
  source_id: string; // "T:2026-08-01:p12" | "AR:2026:p73" | "SCR"
  url: string;
  page: number | null;
}

export type SectionName = "snapshot" | "delivery" | "business" | "bull_bear";

export interface SectionEvent {
  section: SectionName;
  status: "ready" | "unavailable";
  reason: string | null;
  data: Record<string, unknown> | null;
  citations: Citation[];
}

export interface Dossier {
  symbol: string;
  name: string;
  built_at: string;
  basis: string;
  sections: SectionEvent[];
}

export interface QuarterPoint {
  label: string;
  revenue: number | null;
  pat: number | null;
}

export interface DossierSources {
  quarter: string | null; // latest results quarter on screener, "Sep 2026"
  transcript: string | null; // latest concall, ISO date
  annual_report: number | null; // fiscal year of the latest annual report
}

export interface SnapshotData {
  name: string;
  built_at?: string;
  sources?: DossierSources;
  about: string;
  basis: string;
  lender: boolean;
  revenue_ttm: number | null;
  pat_ttm: number | null;
  revenue_cagr_3y: number | null;
  pat_cagr_3y: number | null;
  opm_latest: number | null;
  opm_3y_ago: number | null;
  roce_latest: number | null;
  roe_latest: number | null;
  debt_to_equity: number | null;
  cfo_to_pat_3y: number | null;
  quarterly: QuarterPoint[];
  flags: string[];
}

export type Verdict = "met" | "partly" | "missed" | "pending" | "not_checkable";

export interface DeliveryRow {
  target: {
    metric: string;
    raw_metric: string;
    comparison: "gte" | "lte" | "between" | "approx";
    value: number;
    value_high: number | null;
    unit: "pct" | "cr";
    period: string;
    quote: string;
    source_id: string;
    said_on: string;
  };
  actual: { value: number | null; quarters_in: number; quarters_needed: number };
  verdict: Verdict;
  explanation: string;
}

export interface DeliveryData {
  transcripts: string[];
  rows: DeliveryRow[];
}

export interface Cited {
  source_ids: string[];
}

export interface BusinessData extends Cited {
  what_it_does: string;
  segments: ({ name: string; share_pct: number | null } & Cited)[];
}

export interface BullBearData {
  bull: ({ text: string } & Cited)[];
  bear: ({ text: string } & Cited)[];
}

export interface SymbolEntry {
  symbol: string;
  name: string;
  precomputed: boolean;
}

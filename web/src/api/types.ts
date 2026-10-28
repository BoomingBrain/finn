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

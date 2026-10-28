"""Turns a results filing into the headline numbers: this quarter vs last quarter vs a year ago.
The vision model reads the statement page; code picks columns, converts units, checks the arithmetic
and computes every number shown. Numbers that don't add up are never shown."""
import re
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, field_validator

from finn.llm import LLM
from finn.models import MetricRow, ResultsCard
from finn.sources.documents import DocText, render_page_png

Layout = Literal["corporate", "lender"]
LENDER_SECTORS = {"Banks", "NBFC"}
TO_CRORE = {"crores": 1, "lakhs": 100, "millions": 10, "thousands": 10_000, "rupees": 10_000_000}
TOLERANCE = 0.005
VALUE_FIELDS = ("revenue", "other_income", "total_income", "finance_costs", "depreciation", "interest_earned",
                "interest_expended", "ppop", "provisions", "pbt", "tax", "tax_current", "tax_deferred",
                "after_tax_items", "pat")


class RawColumn(BaseModel):
    header: str = ""
    period_months: int | None = None
    period_end: date | None = None
    revenue: float | None = None
    other_income: float | None = None
    total_income: float | None = None
    finance_costs: float | None = None
    depreciation: float | None = None
    interest_earned: float | None = None
    interest_expended: float | None = None
    ppop: float | None = None
    provisions: float | None = None
    pbt: float | None = None
    tax: float | None = None
    tax_current: float | None = None
    tax_deferred: float | None = None
    after_tax_items: float | None = None
    pat: float | None = None

    @field_validator("period_end", mode="before")
    @classmethod
    def _lenient_date(cls, v):  # OCR-style garbage such as "2026-09-39" becomes unknown, not an error
        if v in (None, "") or isinstance(v, date):
            return v or None
        try:
            return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
        except ValueError:
            return None

    @field_validator(*VALUE_FIELDS, mode="before")
    @classmethod
    def _lenient_number(cls, v):  # "49,244" -> 49244, "(173)" -> -173, "-" -> None
        if v is None or isinstance(v, (int, float)):
            return v
        s = str(v).strip().replace(",", "")
        if s in ("", "-", "–", "—", "NA", "N.A.", "nil", "Nil"):
            return None
        negative = s.startswith("(") and s.endswith(")")
        try:
            n = float(s.strip("()"))
        except ValueError:
            return None
        return -n if negative else n


class RawResults(BaseModel):
    statement_type: Literal["corporate", "bank", "nbfc"] = "corporate"
    basis: Literal["consolidated", "standalone"] | None = None
    unit: Literal["crores", "lakhs", "millions", "thousands", "rupees"] = "crores"
    columns: list[RawColumn]


# --- page selection ---------------------------------------------------------------------------------------

_INCOME = re.compile(r"revenue from operations|interest earned|interest income|total income", re.I)
_PBT = re.compile(r"profit (from ordinary activities )?(\(loss\) )?before (exceptional items? and )?tax", re.I)
_TITLE = re.compile(r"(statement of|unaudited|audited)[^.]{0,60}results[^.]{0,20}(for the|quarter|period|half)", re.I)
_SKIP = re.compile(r"fact sheet|\bifrs\b|news release|press release|auditor'?s'? report", re.I)


def select_statement_page(doc: DocText) -> int | None:
    """Index of the results statement page: needs income and PBT rows; prefers a results title and consolidated."""
    best, best_score = None, 0
    for i, text in enumerate(doc.pages):
        if not (_INCOME.search(text) and _PBT.search(text)) or _SKIP.search(text):
            continue
        score = 1 + 2 * bool(_TITLE.search(text)) + 2 * ("consolidated" in text.lower())
        if score > best_score:
            best, best_score = i, score
    return best


# --- column selection -------------------------------------------------------------------------------------

def _months(c: RawColumn) -> int | None:
    if c.period_months:
        return c.period_months
    h = c.header.lower()
    if re.search(r"half|six months|6 months", h):
        return 6
    if re.search(r"year ended|twelve months|12 months|annual", h):
        return 12
    if re.search(r"quarter|three months|3 months", h):
        return 3
    return None


def select_quarter_columns(cols: list[RawColumn]) -> tuple[RawColumn, RawColumn, RawColumn] | None:
    """(current, prev_q, year_ago) among the 3-month columns."""
    quarters = [c for c in cols if _months(c) == 3]
    if len(quarters) < 3:
        return None
    dated = [c for c in quarters if c.period_end]
    if dated:
        current = max(dated, key=lambda c: c.period_end)
        prev = next((c for c in dated if 80 <= (current.period_end - c.period_end).days <= 100), None)
        year_ago = next((c for c in dated if 355 <= (current.period_end - c.period_end).days <= 375), None)
        if prev and year_ago:
            return current, prev, year_ago
    # Dates missing or inconsistent (OCR): SEBI's standard order is current, previous quarter, year-ago quarter.
    return quarters[0], quarters[1], quarters[2]


# --- arithmetic checks ------------------------------------------------------------------------------------

def detect_layout(raw: RawResults, sector: str | None) -> Layout:
    return "lender" if sector in LENDER_SECTORS or raw.statement_type in ("bank", "nbfc") else "corporate"


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(TOLERANCE * max(abs(a), abs(b)), 0.05)


def _tax(c: RawColumn) -> float | None:
    """Total tax. Printed component lines win: the model copies numbers, code adds them (Task 4 smoke)."""
    if c.tax_current is not None or c.tax_deferred is not None:
        return (c.tax_current or 0) + (c.tax_deferred or 0)
    return c.tax


def check_arithmetic(c: RawColumn, layout: Layout) -> list[str]:
    """Names of failed checks; a check is skipped when its inputs were not read."""
    failed = []
    top = c.revenue if layout == "corporate" else c.interest_earned
    if None not in (top, c.other_income, c.total_income) and not _close(top + c.other_income, c.total_income):
        failed.append("total_income")
    if layout == "lender" and None not in (c.ppop, c.provisions, c.pbt) and not _close(c.ppop - c.provisions, c.pbt):
        failed.append("pbt")
    tax = _tax(c)
    if None not in (c.pbt, tax, c.pat) and not _close(c.pbt - tax + (c.after_tax_items or 0), c.pat):
        failed.append("pat")
    return failed


# --- headline numbers -------------------------------------------------------------------------------------

def _pct(current: float, base: float) -> float | None:
    return None if base == 0 else round((current - base) / abs(base) * 100, 1)


def _row(values: list[float]) -> MetricRow:
    cur, prev, ya = (round(v, 2) for v in values)
    return MetricRow(current=cur, prev_q=prev, year_ago=ya, qoq_pct=_pct(cur, prev), yoy_pct=_pct(cur, ya))


def compute_results(raw: RawResults, sector: str | None = None) -> ResultsCard:
    layout = detect_layout(raw, sector)
    unreadable = ResultsCard(status="unreadable", layout=layout, basis=raw.basis, period_end=None, metrics={})
    triplet = select_quarter_columns(raw.columns)
    if not triplet or any(check_arithmetic(c, layout) for c in triplet):
        return unreadable
    divisor = TO_CRORE[raw.unit]

    def series(fn: Callable[[RawColumn], float | None]) -> list[float] | None:
        values = [fn(c) for c in triplet]
        return None if any(v is None for v in values) else [v / divisor for v in values]

    def diff(a, b):
        return lambda c: None if getattr(c, a) is None or getattr(c, b) is None else getattr(c, a) - getattr(c, b)

    pbt, pat = series(lambda c: c.pbt), series(lambda c: c.pat)
    if layout == "corporate":
        revenue = series(lambda c: c.revenue)
        ebitda = series(lambda c: None if None in (c.pbt, c.finance_costs, c.depreciation, c.other_income)
                        else c.pbt + c.finance_costs + c.depreciation - c.other_income)
        if None in (revenue, ebitda, pbt, pat) or any(abs(p) > abs(r) for p, r in zip(pat, revenue)):
            return unreadable
        metrics = {"Revenue": revenue, "EBITDA": ebitda, "PBT": pbt, "PAT": pat}
        not_applicable = []
    else:
        expense = "interest_expended" if all(c.interest_expended is not None for c in triplet) else "finance_costs"
        nii = series(diff("interest_earned", expense))
        ppop = series(lambda c: c.ppop)
        if None in (nii, pbt, pat):
            return unreadable
        metrics = {"NII": nii, **({"PPOP": ppop} if ppop else {}), "PBT": pbt, "PAT": pat}
        not_applicable = ["EBITDA"]
    return ResultsCard(status="ok", layout=layout, basis=raw.basis, period_end=triplet[0].period_end,
                       metrics={k: _row(v) for k, v in metrics.items()}, not_applicable=not_applicable)


# --- extraction -------------------------------------------------------------------------------------------

_SYSTEM = "You read financial statements of Indian listed companies from page images and copy numbers exactly."
_PROMPT = """This page is a quarterly results statement. Return ONLY JSON:
{"statement_type": "corporate|bank|nbfc", "basis": "consolidated|standalone", "unit": "crores|lakhs|millions|thousands|rupees",
 "columns": [{"header": "<column header as printed>", "period_months": 3|6|12, "period_end": "YYYY-MM-DD",
   "revenue": n, "other_income": n, "total_income": n, "finance_costs": n, "depreciation": n,
   "interest_earned": n, "interest_expended": n, "ppop": n, "provisions": n,
   "pbt": n, "tax_current": n, "tax_deferred": n, "tax": n, "after_tax_items": n, "pat": n}]}
Rules: include every numeric column, left to right. Copy numbers exactly as printed, without converting units;
parentheses mean negative; use null for a row that is not on the page.
revenue = revenue from operations (non-lenders). interest_earned = interest earned / interest income (banks, NBFCs).
interest_expended = interest expended (banks). ppop = operating profit before provisions and contingencies.
provisions = provisions (other than tax) and contingencies, or impairment on financial instruments.
pbt = profit before tax (after exceptional items). tax_current and tax_deferred = the current-tax and deferred-tax
lines exactly as printed. tax = a single printed total tax line, else null. Never add numbers yourself.
after_tax_items = net items between tax and profit for the period (share of profit of associates/JVs, discontinued
operations), else null. pat = profit for the period (total, before minority/non-controlling split)."""


def extract_results(pdf_path: Path, page: int, llm: LLM,
                    render: Callable[..., bytes] = render_page_png) -> RawResults:
    """Vision read of the statement page; one 200-dpi re-read if the arithmetic doesn't add up (Task 0)."""
    raw = llm.complete_json("vision", _SYSTEM, _PROMPT, RawResults, images=[render(pdf_path, page)], max_tokens=4000)
    layout: Layout = "lender" if raw.statement_type in ("bank", "nbfc") else "corporate"
    quarters = [c for c in raw.columns if _months(c) == 3] or raw.columns
    failures = {f"{c.header or 'column ' + str(i + 1)}: {', '.join(fails)}"
                for i, c in enumerate(quarters) if (fails := check_arithmetic(c, layout))}
    if not failures:
        return raw
    hint = ("\n\nA first reading did not add up (profit before tax − tax + after-tax items should equal profit for "
            "the period; operating profit − provisions should equal profit before tax; income rows should sum to "
            f"total income). Failed: {'; '.join(sorted(failures))}. Re-read those rows digit by digit.")
    return llm.complete_json("vision", _SYSTEM, _PROMPT + hint, RawResults, images=[render(pdf_path, page, dpi=200)],
                             max_tokens=4000)

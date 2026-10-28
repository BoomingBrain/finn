"""The hard numbers of a dossier, computed in code from screener.in's tables: growth, margins, leverage, returns,
cash conversion and plain-English red flags. No figure here comes from an LLM; a missing input gives None, never 0."""
import re

from pydantic import BaseModel

from finn.sources.screener import CompanyData, Table

# Bank rows differ: "Revenue" instead of "Sales". "Financing Profit" is NOT operating profit (it is negative for
# HDFCBANK, see docs/spikes.md), so lenders get no operating margin.
ROW_ALIASES = {
    "revenue": ["Sales", "Revenue"],
    "op_profit": ["Operating Profit"],
    "pat": ["Net Profit"],
    "cfo": ["Cash from Operating Activity"],
    "borrowings": ["Borrowings", "Borrowing"],
    "equity_capital": ["Equity Capital"],
    "reserves": ["Reserves"],
}


class QuarterPoint(BaseModel):
    label: str
    revenue: float | None
    pat: float | None


class FinancialSnapshot(BaseModel):
    lender: bool
    revenue_ttm: float | None
    pat_ttm: float | None
    revenue_cagr_3y: float | None
    pat_cagr_3y: float | None
    opm_latest: float | None
    opm_3y_ago: float | None
    roce_latest: float | None
    roe_latest: float | None
    debt_to_equity: float | None
    cfo_to_pat_3y: float | None
    quarterly: list[QuarterPoint]
    flags: list[str]


def _annual(table: Table, key: str) -> dict[int, float]:
    """Fiscal-year values ('Mar 2026' -> 2026), skipping TTM and missing cells."""
    row = table.row(*ROW_ALIASES[key])
    if not row:
        return {}
    out = {}
    for col, value in zip(table.columns, row):
        m = re.fullmatch(r"Mar (\d{4})", col)
        if m and value is not None:
            out[int(m.group(1))] = value
    return out


def _cagr(series: dict[int, float], years: int = 3) -> float | None:
    if not series:
        return None
    latest = max(series)
    start, end = series.get(latest - years), series[latest]
    if start is None or start <= 0 or end <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 1)


def _margin(op: dict[int, float], rev: dict[int, float], year: int | None) -> float | None:
    if year is None or op.get(year) is None or not rev.get(year):
        return None
    return round(op[year] / rev[year] * 100, 1)


def _last(table: Table, *names: str) -> float | None:
    row = table.row(*names)
    return row[-1] if row else None


def compute_snapshot(c: CompanyData) -> FinancialSnapshot:
    q = c.quarters
    lender = "Financing Profit" in q.rows or ("Revenue" in q.rows and "Sales" not in q.rows)

    def ttm(key: str) -> float | None:
        row = q.row(*ROW_ALIASES[key])
        last4 = row[-4:] if row and len(row) >= 4 else []
        return sum(last4) if last4 and None not in last4 else None

    revenue, pat, op = _annual(c.pnl, "revenue"), _annual(c.pnl, "pat"), _annual(c.pnl, "op_profit")
    latest_fy = max(revenue) if revenue else None
    opm_latest = None if lender else _margin(op, revenue, latest_fy)
    opm_3y_ago = None if lender else _margin(op, revenue, latest_fy - 3 if latest_fy else None)

    debt_to_equity = None
    if not lender:
        borrowings = _last(c.balance_sheet, *ROW_ALIASES["borrowings"])
        equity = [_last(c.balance_sheet, n) for n in ("Equity Capital", "Reserves")]
        if borrowings is not None and None not in equity and sum(equity) > 0:
            debt_to_equity = round(borrowings / sum(equity), 2)

    cfo_to_pat = None
    if not lender:
        cfo = _annual(c.cash_flow, "cfo")
        years = sorted(set(cfo) & set(pat))[-3:]
        if len(years) == 3 and sum(pat[y] for y in years) > 0:
            cfo_to_pat = round(sum(cfo[y] for y in years) / sum(pat[y] for y in years), 2)

    rev_row, pat_row = q.row(*ROW_ALIASES["revenue"]), q.row(*ROW_ALIASES["pat"])
    quarterly = [QuarterPoint(label=col, revenue=rev_row[i] if rev_row else None, pat=pat_row[i] if pat_row else None)
                 for i, col in enumerate(q.columns)][-8:]

    flags = []
    if cfo_to_pat is not None and cfo_to_pat < 0.7:
        flags.append("Profits not converting to cash")
    if debt_to_equity is not None and debt_to_equity > 1:
        flags.append("High leverage")
    if opm_latest is not None and opm_3y_ago is not None and opm_latest - opm_3y_ago < -3:
        flags.append("Margins compressing")

    return FinancialSnapshot(
        lender=lender, revenue_ttm=ttm("revenue"), pat_ttm=ttm("pat"), revenue_cagr_3y=_cagr(revenue),
        pat_cagr_3y=_cagr(pat), opm_latest=opm_latest, opm_3y_ago=opm_3y_ago,
        roce_latest=_last(c.ratios, "ROCE %"), roe_latest=_last(c.ratios, "ROE %"), debt_to_equity=debt_to_equity,
        cfo_to_pat_3y=cfo_to_pat, quarterly=quarterly, flags=flags)

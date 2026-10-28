from pathlib import Path

import pytest

from finn.pull.metrics import compute_snapshot
from finn.sources.screener import CompanyData, Table, parse_company

FIXTURES = Path(__file__).parent / "fixtures"


def company(symbol: str) -> CompanyData:
    return parse_company((FIXTURES / f"screener_{symbol}.html").read_text(), symbol, "consolidated")


@pytest.fixture(scope="module")
def pidilite():
    return compute_snapshot(company("PIDILITIND"))


def test_ttm(pidilite):
    assert pidilite.revenue_ttm == 15399.0  # 3554 + 3710 + 3583 + 4552 (Sep 2025 .. Jun 2026)
    assert pidilite.pat_ttm == 2677.0  # 585 + 624 + 584 + 884


def test_cagr_3y(pidilite):
    assert pidilite.revenue_cagr_3y == 7.4  # (14601 / 11799) ** (1/3) - 1, Mar 2026 vs Mar 2023
    assert pidilite.pat_cagr_3y == 24.2  # (2471 / 1289) ** (1/3) - 1


def test_margins_from_rows_not_rounded_opm(pidilite):
    assert pidilite.opm_latest == 24.1  # 3521 / 14601 (screener's OPM % row says 24)
    assert pidilite.opm_3y_ago == 16.8  # 1986 / 11799


def test_cfo_to_pat(pidilite):
    assert pidilite.cfo_to_pat_3y == 1.24  # (2724 + 2287 + 2828) / (1747 + 2096 + 2471), Mar 2024-26


def test_leverage_and_returns(pidilite):
    assert pidilite.debt_to_equity == 0.04  # 417 / (102 + 10730)
    assert pidilite.roce_latest == 31.0
    assert pidilite.flags == []


def test_quarterly_series(pidilite):
    assert [q.label for q in pidilite.quarterly][-2:] == ["Mar 2026", "Jun 2026"]
    assert len(pidilite.quarterly) == 8
    assert pidilite.quarterly[-1].revenue == 4552.0 and pidilite.quarterly[-1].pat == 884.0


def test_bank_layout():
    s = compute_snapshot(company("HDFCBANK"))
    assert s.lender is True
    assert s.revenue_ttm == 359956.0  # "Revenue" row: 87067 + 87182 + 90575 + 95132
    assert s.revenue_cagr_3y == 26.9  # (348615 / 170754) ** (1/3) - 1
    assert s.opm_latest is None and s.debt_to_equity is None and s.cfo_to_pat_3y is None
    assert s.roe_latest == 14.0
    assert "High leverage" not in s.flags


def table(columns, **rows):
    return Table(columns=columns, rows={k.replace("_", " "): v for k, v in rows.items()})


def synthetic(**overrides) -> CompanyData:
    years = ["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"]
    base = dict(
        symbol="X", name="X", about="", basis="consolidated", annual_reports=[], transcripts=[],
        quarters=table(["Dec 2025", "Mar 2026", "Jun 2026", "Sep 2026"], Sales=[100, 100, 100, 100],
                       Net_Profit=[10, 10, 10, 10]),
        pnl=Table(columns=years, rows={"Sales": [100, 110, 120, 130], "Operating Profit": [25, 24, 22, 20],
                                       "Net Profit": [10, 10, 10, 10]}),
        balance_sheet=Table(columns=["Mar 2026"], rows={"Equity Capital": [10], "Reserves": [90], "Borrowings": [150]}),
        cash_flow=Table(columns=years, rows={"Cash from Operating Activity": [5, 5, 5, 5]}),
        ratios=Table(columns=["Mar 2026"], rows={}))
    base.update(overrides)
    return CompanyData(**base)


def test_flags():
    s = compute_snapshot(synthetic())
    # CFO/PAT = 15 / 30 = 0.5; D/E = 150 / 100 = 1.5; OPM 25.0% (Mar 2023) -> 15.4% (Mar 2026)
    assert s.flags == ["Profits not converting to cash", "High leverage", "Margins compressing"]


def test_missing_rows_yield_none():
    empty = Table(columns=[], rows={})
    s = compute_snapshot(synthetic(quarters=empty, pnl=empty, balance_sheet=empty, cash_flow=empty, ratios=empty))
    assert (s.revenue_ttm, s.pat_ttm, s.revenue_cagr_3y, s.opm_latest, s.debt_to_equity, s.cfo_to_pat_3y) == (None,) * 6
    assert s.quarterly == [] and s.flags == []


def test_missing_values_are_none_not_zero():
    q = table(["Dec 2025", "Mar 2026", "Jun 2026", "Sep 2026"], Sales=[100, None, 100, 100], Net_Profit=[10, 10, 10, 10])
    assert compute_snapshot(synthetic(quarters=q)).revenue_ttm is None


def test_negative_base_has_no_cagr():
    pnl = Table(columns=["Mar 2023", "Mar 2024", "Mar 2025", "Mar 2026"],
                rows={"Sales": [100, 110, 120, 130], "Net Profit": [-5, 2, 4, 8]})
    assert compute_snapshot(synthetic(pnl=pnl)).pat_cagr_3y is None

from datetime import date

from datetime import datetime

from finn.models import IST, Announcement, EnrichedAnnouncement, MetricRow, ResultsCard
from finn.push.crosscheck import apply_crosscheck, crosscheck
from finn.sources.screener import CompanyData, Table


def row(v: float) -> MetricRow:
    return MetricRow(current=v, prev_q=v, year_ago=v, qoq_pct=0.0, yoy_pct=0.0)


def card(revenue=49244.0, pat=7838.0, layout="corporate", basis="consolidated", period=date(2026, 9, 30)):
    metrics = {"Revenue": row(revenue), "PAT": row(pat)} if layout == "corporate" else {"NII": row(44464.2), "PAT": row(pat)}
    return ResultsCard(status="ok", layout=layout, basis=basis, period_end=period, metrics=metrics)


def company(sales=49244.0, profit=7838.0, basis="consolidated", revenue_row="Sales") -> CompanyData:
    empty = Table(columns=[], rows={})
    quarters = Table(columns=["Jun 2026", "Sep 2026"], rows={revenue_row: [48211, sales], "Net Profit": [7775, profit]})
    return CompanyData(symbol="X", name="X", about="", basis=basis, quarters=quarters, pnl=empty, balance_sheet=empty,
                       cash_flow=empty, ratios=empty, annual_reports=[], transcripts=[])


def test_crosscheck_match_verified():
    out = crosscheck(card(), company(sales=49300, profit=7810))  # within 2%
    assert (out.verified, out.mismatches) == (True, [])


def test_crosscheck_revenue_off_by_5pct_unverified():
    out = crosscheck(card(), company(sales=49244 * 1.05))
    assert (out.verified, out.mismatches) == (False, ["Revenue"])


def test_crosscheck_missing_quarter_is_none():
    assert crosscheck(card(period=date(2026, 12, 31)), company()).verified is None


def test_crosscheck_lender_checks_pat_only():
    # screener's bank "Revenue" row is interest earned, not NII: only PAT is comparable
    out = crosscheck(card(layout="lender", pat=21537.09), company(sales=95132, profit=21540, revenue_row="Revenue"))
    assert (out.verified, out.mismatches) == (True, [])


def test_crosscheck_basis_mismatch_is_none():
    assert crosscheck(card(basis="standalone"), company(basis="consolidated")).verified is None


def test_crosscheck_unreadable_is_untouched():
    unreadable = ResultsCard(status="unreadable", layout="corporate", basis=None, period_end=None, metrics={})
    assert crosscheck(unreadable, company()).verified is None


def test_apply_crosscheck_survives_screener_failure():
    a = Announcement(id="a1", symbol="INFY", company="Infosys", subject="Results", body="", source="nse",
                     raw_category="Outcome of Board Meeting",
                     filed_at=datetime(2026, 10, 23, 16, 8, tzinfo=IST), attachment_url=None)
    good, broken = EnrichedAnnouncement(announcement=a, category="results", tier="critical", results=card()), \
        EnrichedAnnouncement(announcement=a.model_copy(update={"symbol": "TCS"}), category="results", tier="critical",
                             results=card())

    def fetch(symbol):
        if symbol == "TCS":
            raise ConnectionError("screener down")
        return company(sales=49244 * 1.05)

    apply_crosscheck([good, broken], fetch)
    assert (good.results.verified, good.results.mismatches) == (False, ["Revenue"])
    assert broken.results.verified is None

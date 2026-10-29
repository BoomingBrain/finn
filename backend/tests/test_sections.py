import asyncio
import json
import threading
from datetime import date, datetime, timezone

from finn.llm import LLM
from finn.pull import dossier
from finn.pull.dossier import Dossier, build_dossier, needs_build, source_fingerprint
from finn.snapshot import SnapshotStore
from finn.pull.sections import Point, business_pages, drop_uncited
from finn.sources.documents import DocText, DocumentError
from finn.sources.screener import CompanyData, DocLink, Table
from tests.fakes import Call, FakeCompleter

VALID = {"SCR", "T:2026-08-01:p3", "AR:2026:p73"}


def test_drop_uncited_removes_unknown_ids():
    items = [Point(text="Margins at a record", source_ids=["T:2099-01-01:p1"]),
             Point(text="Mixed", source_ids=["SCR", "T:2099-01-01:p1"])]
    assert drop_uncited(items, VALID, key=lambda p: p.source_ids) == []


def test_drop_uncited_removes_uncited():
    assert drop_uncited([Point(text="Strong brand", source_ids=[])], VALID, key=lambda p: p.source_ids) == []


def test_drop_uncited_keeps_valid():
    keep = Point(text="Debt-free", source_ids=["SCR", "AR:2026:p73"])
    assert drop_uncited([keep], VALID, key=lambda p: p.source_ids) == [keep]


QUARTERS = Table(columns=["Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026", "Jun 2026"],
                 rows={"Sales": [100, 100, 100, 100, 120], "Operating Profit": [20, 20, 20, 20, 30],
                       "Net Profit": [10, 10, 10, 10, 14]})


def company(transcripts=(), annual_reports=()) -> CompanyData:
    empty = Table(columns=[], rows={})
    return CompanyData(symbol="ACME", name="Acme Ltd", about="Makes glue.", basis="consolidated", quarters=QUARTERS,
                       pnl=empty, balance_sheet=empty, cash_flow=empty, ratios=empty,
                       transcripts=list(transcripts), annual_reports=list(annual_reports))


def run(llm, c, docs, progress=None, fetch_fn=None):
    async def collect():
        return [s async for s in build_dossier("ACME", llm, lambda _: c, fetch_fn or (lambda url: docs[url]),
                                               progress=progress)]
    return asyncio.run(collect())


TRANSCRIPT = DocLink(label="Transcript Aug 2026", date=date(2026, 8, 1), url="t1")
REPORT = DocLink(label="Annual Report 2026", date=date(2026, 3, 31), url="ar")
TRANSCRIPT_DOC = DocText(url="t1", pages=["Opening remarks. " * 20, "",
                                          "For FY27 we expect EBITDA margin of 20% to 24% for the full year."])
AR_DOC = DocText(url="ar", pages=["Contents"] * 72 + [
    "Our business segments: adhesives and sealants make up 80% of revenue; the rest is chemicals."])
TARGET = {"metric": "ebitda_margin", "raw_metric": "EBITDA margin", "comparison": "between", "value": 20,
          "value_high": 24, "unit": "pct", "period": "FY27", "forward_looking": True,
          "quote": "For FY27 we expect EBITDA margin of 20% to 24%", "source_id": "T:2026-08-01:p3"}
BUSINESS = {"what_it_does": "Acme makes adhesives and sealants.", "source_ids": ["AR:2026:p73"],
            "segments": [{"name": "Adhesives", "share_pct": 80, "source_ids": ["AR:2026:p73"]},
                         {"name": "Paints", "share_pct": 35, "source_ids": ["AR:2026:p73"]},
                         {"name": "Exports", "share_pct": None, "source_ids": ["AR:2026:p9"]}]}
BULL_BEAR = {"bull": [{"text": "Margin above the guided band", "source_ids": ["T:2026-08-01:p3", "SCR"]}],
             "bear": [{"text": "Concentrated in adhesives", "source_ids": ["AR:2026:p73"]}]}


class RoutingCompleter(FakeCompleter):
    """Answers by what is asked, not by call order: the business section and guidance extraction run concurrently."""

    def __call__(self, model, system, user, images, max_tokens, thinking):
        self.calls.append(Call(model, system, user, images, max_tokens, thinking))
        if "explicit numeric guidance" in system:
            reply = {"targets": [TARGET]}
        elif "explaining a guidance verdict" in system:
            reply = {"lines": [{"i": 0, "text": "Running at 25% after one quarter."}]}
        elif user.startswith("From the annual report pages"):
            reply = BUSINESS
        else:
            reply = BULL_BEAR
        return json.dumps(reply), 1, 1


def llm_with_replies(tmp_path) -> tuple[LLM, RoutingCompleter]:
    fake = RoutingCompleter([])
    return LLM(cache_path=tmp_path / "c.sqlite", completer=fake), fake


def test_missing_sources_give_fixed_reasons(tmp_path):
    bull_bear = {"bull": [{"text": "Revenue up 20% in the latest quarter", "source_ids": ["SCR"]},
                          {"text": "Market leader in adhesives", "source_ids": []}],
                 "bear": [{"text": "Analysts expect a slowdown", "source_ids": ["NEWS:1"]}]}
    llm = LLM(cache_path=tmp_path / "c.sqlite", completer=FakeCompleter([json.dumps(bull_bear)]))
    steps = []
    sections = run(llm, company(), {}, progress=steps.append)
    assert steps[-1]["done"] == steps[-1]["total"]  # missing sources still complete the bar
    assert [s.section for s in sections] == ["snapshot", "delivery", "business", "bull_bear"]
    assert sections[0].status == "ready" and sections[0].citations[0].source_id == "SCR"
    assert (sections[1].status, sections[1].reason) == ("unavailable", "No concall transcripts on screener.in")
    assert (sections[2].status, sections[2].reason) == ("unavailable", "No annual report on screener.in")
    assert sections[3].data == {"bull": [bull_bear["bull"][0]], "bear": []}


def test_full_dossier_cites_real_pages(tmp_path):
    llm, fake = llm_with_replies(tmp_path)
    steps = []
    sections = run(llm, company([TRANSCRIPT], [REPORT]), {"t1": TRANSCRIPT_DOC, "ar": AR_DOC}, progress=steps.append)
    assert all(s.status == "ready" for s in sections)
    # 1 financials + 1 call + delivery check + annual report + bull/bear = 5 real steps, never going backwards
    assert [(x["done"], x["total"]) for x in steps][-1] == (5, 5)
    assert all(a["done"] <= b["done"] for a, b in zip(steps, steps[1:]))
    assert "Read the Aug 2026 earnings call (1 of 1)" in [x["label"] for x in steps]

    delivery = sections[1]
    [row] = delivery.data["rows"]
    assert (row["verdict"], row["actual"]["value"]) == ("pending", 25.0)  # 30 / 120
    assert {c.source_id: (c.url, c.page) for c in delivery.citations} == {"T:2026-08-01:p3": ("t1", 3)}

    business_data = sections[2].data
    assert [s["name"] for s in business_data["segments"]] == ["Adhesives", "Paints"]  # uncited Exports dropped
    assert business_data["segments"][1]["share_pct"] is None  # 35% is not on the cited page
    assert any("[AR:2026:p73]" in c.user for c in fake.calls)

    assert {c.source_id for c in sections[3].citations} == {"T:2026-08-01:p3", "SCR", "AR:2026:p73"}


def test_business_pages_ignore_auditor_report_in_contents():
    pages = (["Contents: Independent Auditor's Report ... 156"] + ["Our business segments and brands"] * 3
             + ["Note"] * 20 + ["Independent Auditor's Report"] + ["Segment information note: segment revenue"] * 5)
    assert business_pages(DocText(url="ar", pages=pages)) == [2, 3, 4]


def test_business_pages_always_include_brsr_activities():
    pages = (["Contents"] * 3 + ["Our business segments and brands"] * 10 + ["Independent Auditor's Report"]
             + ["BRSR: Description of Business Activity | % of turnover"])
    assert business_pages(DocText(url="ar", pages=pages)) == [4, 5, 6, 7, 8, 9, 10, 15]


def test_needs_build_reasons():
    sources = {"quarter": "Sep 2026", "transcript": "2026-08-01", "annual_report": 2026}
    ok = {"sources": sources, "sections": [{"reason": None}, {"reason": "No concall transcripts on screener.in"}]}
    assert needs_build(None) == "missing"
    assert needs_build({"sections": [{"reason": "Analysis failed"}]}) == "a section failed"
    assert needs_build(ok) is None and needs_build(ok, sources) is None
    assert needs_build(ok, {**sources, "quarter": "Dec 2026"}) == "new sources"  # new results are out


def test_fingerprint_tracks_latest_inputs():
    c = company(transcripts=[DocLink(label="T", date=date(2026, 8, 1), url="t1"),
                             DocLink(label="T", date=date(2026, 5, 1), url="t0")],
                annual_reports=[DocLink(label="AR", date=date(2026, 3, 31), url="ar")])
    assert source_fingerprint(c) == {"quarter": "Jun 2026", "transcript": "2026-08-01", "annual_report": 2026}


def test_bull_bear_sees_plain_verdicts(tmp_path):
    from finn.pull.guidance import Actual, DeliveryRow, GuidanceTarget
    from finn.pull.metrics import FinancialSnapshot
    from finn.pull.sections import bull_bear

    t = GuidanceTarget(metric="other", raw_metric="capex", comparison="approx", value=20000, unit="cr", period="FY27",
                       quote="capex of about 20,000 crore", source_id="T:2026-02-01:p16", said_on=date(2026, 2, 1))
    row = DeliveryRow(target=t, actual=Actual(value=None, quarters_in=0, quarters_needed=0), verdict="not_checkable",
                      explanation="")
    snap = FinancialSnapshot(lender=False, revenue_ttm=None, pat_ttm=None, revenue_cagr_3y=None, pat_cagr_3y=None,
                             opm_latest=None, opm_3y_ago=None, roce_latest=None, roe_latest=None, debt_to_equity=None,
                             cfo_to_pat_3y=None, quarterly=[], flags=[])
    fake = FakeCompleter([json.dumps({"bull": [], "bear": []})])
    bull_bear(snap, [row], None, LLM(cache_path=tmp_path / "c.sqlite", completer=fake))
    sent = fake.calls[0].user
    assert "not_checkable" not in sent and "says nothing about delivery" in sent


def test_annual_report_is_read_while_calls_are_read(tmp_path):
    # fetching the transcript waits for the annual report: code that reads them one after the other times out
    ar_fetched = threading.Event()

    def fetch(url):
        if url == "ar":
            ar_fetched.set()
            return AR_DOC
        assert ar_fetched.wait(5), "annual report was not fetched in parallel"
        return TRANSCRIPT_DOC

    llm, _ = llm_with_replies(tmp_path)
    sections = run(llm, company([TRANSCRIPT], [REPORT]), {}, fetch_fn=fetch)
    assert [s.section for s in sections] == ["snapshot", "delivery", "business", "bull_bear"]
    assert sections[1].status == "ready"


def test_business_failure_does_not_touch_delivery(tmp_path):
    def fetch(url):
        if url == "ar":
            raise DocumentError("BSE down")
        return TRANSCRIPT_DOC

    llm, _ = llm_with_replies(tmp_path)
    sections = run(llm, company([TRANSCRIPT], [REPORT]), {}, fetch_fn=fetch)
    assert sections[1].status == "ready"
    assert (sections[2].status, sections[2].reason) == ("unavailable", "Analysis failed")


def test_limit_caps_new_builds(tmp_path, monkeypatch):
    built = []

    async def fake_collect(symbol, llm, **kw):
        built.append(symbol)
        return Dossier(symbol=symbol, name=symbol, built_at=datetime.now(timezone.utc), basis="", sections=[])

    monkeypatch.setattr(dossier, "collect_dossier", fake_collect)
    store = SnapshotStore(tmp_path)
    store.save_dossier("A", {"symbol": "A", "sections": []})  # exists: skipped, not counted
    asyncio.run(dossier._precompute(["A", "B", "C", "D"], store, None, mode="missing", parallel=1, limit=2))
    assert built == ["B", "C"]

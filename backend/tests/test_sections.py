import asyncio
import json
from datetime import date

from finn.llm import LLM
from finn.pull.dossier import build_dossier
from finn.pull.sections import Point, business_pages, drop_uncited
from finn.sources.documents import DocText
from finn.sources.screener import CompanyData, DocLink, Table
from tests.fakes import FakeCompleter

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


def run(llm, c, docs):
    async def collect():
        return [s async for s in build_dossier("ACME", llm, lambda _: c, lambda url: docs[url])]
    return asyncio.run(collect())


def test_missing_sources_give_fixed_reasons(tmp_path):
    bull_bear = {"bull": [{"text": "Revenue up 20% in the latest quarter", "source_ids": ["SCR"]},
                          {"text": "Market leader in adhesives", "source_ids": []}],
                 "bear": [{"text": "Analysts expect a slowdown", "source_ids": ["NEWS:1"]}]}
    llm = LLM(cache_path=tmp_path / "c.sqlite", completer=FakeCompleter([json.dumps(bull_bear)]))
    sections = run(llm, company(), {})
    assert [s.section for s in sections] == ["snapshot", "delivery", "business", "bull_bear"]
    assert sections[0].status == "ready" and sections[0].citations[0].source_id == "SCR"
    assert (sections[1].status, sections[1].reason) == ("unavailable", "No concall transcripts on screener.in")
    assert (sections[2].status, sections[2].reason) == ("unavailable", "No annual report on screener.in")
    assert sections[3].data == {"bull": [bull_bear["bull"][0]], "bear": []}


def test_full_dossier_cites_real_pages(tmp_path):
    transcript = DocLink(label="Transcript Aug 2026", date=date(2026, 8, 1), url="t1")
    report = DocLink(label="Annual Report 2026", date=date(2026, 3, 31), url="ar")
    docs = {"t1": DocText(url="t1", pages=["Opening remarks. " * 20, "",
                                           "For FY27 we expect EBITDA margin of 20% to 24% for the full year."]),
            "ar": DocText(url="ar", pages=["Contents"] * 72 + [
                "Our business segments: adhesives and sealants make up 80% of revenue; the rest is chemicals."])}
    target = {"metric": "ebitda_margin", "raw_metric": "EBITDA margin", "comparison": "between", "value": 20,
              "value_high": 24, "unit": "pct", "period": "FY27", "forward_looking": True,
              "quote": "For FY27 we expect EBITDA margin of 20% to 24%", "source_id": "T:2026-08-01:p3"}
    business = {"what_it_does": "Acme makes adhesives and sealants.", "source_ids": ["AR:2026:p73"],
                "segments": [{"name": "Adhesives", "share_pct": 80, "source_ids": ["AR:2026:p73"]},
                             {"name": "Paints", "share_pct": 35, "source_ids": ["AR:2026:p73"]},
                             {"name": "Exports", "share_pct": None, "source_ids": ["AR:2026:p9"]}]}
    bull_bear = {"bull": [{"text": "Margin above the guided band", "source_ids": ["T:2026-08-01:p3", "SCR"]}],
                 "bear": [{"text": "Concentrated in adhesives", "source_ids": ["AR:2026:p73"]}]}
    replies = [{"targets": [target]}, {"lines": [{"i": 0, "text": "Running at 25% after one quarter."}]},
               business, bull_bear]
    fake = FakeCompleter([json.dumps(r) for r in replies])
    sections = run(LLM(cache_path=tmp_path / "c.sqlite", completer=fake), company([transcript], [report]), docs)
    assert all(s.status == "ready" for s in sections)

    delivery = sections[1]
    [row] = delivery.data["rows"]
    assert (row["verdict"], row["actual"]["value"]) == ("pending", 25.0)  # 30 / 120
    assert {c.source_id: (c.url, c.page) for c in delivery.citations} == {"T:2026-08-01:p3": ("t1", 3)}

    business_data = sections[2].data
    assert [s["name"] for s in business_data["segments"]] == ["Adhesives", "Paints"]  # uncited Exports dropped
    assert business_data["segments"][1]["share_pct"] is None  # 35% is not on the cited page
    assert "[AR:2026:p73]" in fake.calls[2].user

    assert {c.source_id for c in sections[3].citations} == {"T:2026-08-01:p3", "SCR", "AR:2026:p73"}


def test_business_pages_ignore_auditor_report_in_contents():
    pages = (["Contents: Independent Auditor's Report ... 156"] + ["Our business segments and brands"] * 3
             + ["Note"] * 20 + ["Independent Auditor's Report"] + ["Segment information note: segment revenue"] * 5)
    assert business_pages(DocText(url="ar", pages=pages)) == [2, 3, 4]


def test_business_pages_always_include_brsr_activities():
    pages = (["Contents"] * 3 + ["Our business segments and brands"] * 10 + ["Independent Auditor's Report"]
             + ["BRSR: Description of Business Activity | % of turnover"])
    assert business_pages(DocText(url="ar", pages=pages)) == [4, 5, 6, 7, 8, 9, 10, 15]

import json
from datetime import date
from pathlib import Path

import pytest

from finn.llm import LLM, LLMError
from finn.pull.guidance import (Actual, GuidanceTarget, actual_for, assess_delivery, extract_targets, judge,
                                resolve_period)
from finn.sources.documents import DocText
from finn.sources.screener import Table
from tests.fakes import FakeCompleter


def make_llm(tmp_path: Path, responses: list[str]) -> tuple[LLM, FakeCompleter]:
    fake = FakeCompleter(responses)
    return LLM(cache_path=tmp_path / "cache.sqlite", completer=fake), fake


def target(**kw) -> GuidanceTarget:
    base = dict(metric="revenue_growth_yoy", raw_metric="revenue growth", comparison="gte", value=10.0,
                value_high=None, unit="pct", period="FY26", quote="we expect double-digit growth",
                source_id="T:2025-05-01:p3", said_on=date(2025, 5, 1))
    base.update(kw)
    return GuidanceTarget(**base)


# FY25 = Jun 2024 .. Mar 2025; FY26 = Jun 2025 .. Mar 2026
QUARTERS = Table(
    columns=["Jun 2024", "Sep 2024", "Dec 2024", "Mar 2025", "Jun 2025", "Sep 2025", "Dec 2025", "Mar 2026"],
    rows={"Sales": [100, 100, 100, 100, 110, 112, 108, 110],
          "Operating Profit": [20, 20, 20, 20, 22, 24, 22, 22],
          "Net Profit": [10, 10, 10, 10, 12, 12, 12, 12]})


def test_resolve_period():
    assert resolve_period("FY27") == ["Jun 2026", "Sep 2026", "Dec 2026", "Mar 2027"]
    assert resolve_period("Q2FY27") == ["Sep 2026"]
    assert resolve_period("H2FY27") == ["Dec 2026", "Mar 2027"]
    assert resolve_period("Q4 FY2027") == ["Mar 2027"]
    assert resolve_period("next year") is None
    assert resolve_period("Q5FY27") is None


def test_actual_growth_yoy():
    a = actual_for(target(), QUARTERS)
    assert a == Actual(value=10.0, quarters_in=4, quarters_needed=4)  # 440 / 400 - 1
    assert actual_for(target(metric="pat_growth_yoy"), QUARTERS).value == 20.0  # 48 / 40 - 1


def test_actual_margin_and_sums():
    assert actual_for(target(metric="ebitda_margin"), QUARTERS).value == 20.5  # 90 / 440 = 20.45
    assert actual_for(target(metric="revenue", unit="cr", period="H1FY26"), QUARTERS).value == 222.0
    assert actual_for(target(metric="pat", unit="cr", period="Q4FY26"), QUARTERS).value == 12.0


def test_unit_mismatch_is_not_checkable():
    t = target(metric="revenue", unit="pct")
    assert judge(t, actual_for(t, QUARTERS)) == "not_checkable"


def test_pending_reports_tracking_value():
    t = target(period="FY27")
    q = Table(columns=QUARTERS.columns + ["Jun 2026", "Sep 2026"],
              rows={"Sales": QUARTERS.rows["Sales"] + [121, 123.2]})
    a = actual_for(t, q)
    assert a == Actual(value=10.0, quarters_in=2, quarters_needed=4)  # 244.2 / 222 - 1
    assert judge(t, a) == "pending"


def check(value, comparison="gte", v=10.0, vh=None, unit="pct", metric="revenue_growth_yoy", period="FY26",
          quarters_in=4):
    t = target(comparison=comparison, value=v, value_high=vh, unit=unit, metric=metric, period=period)
    return judge(t, Actual(value=value, quarters_in=quarters_in, quarters_needed=4))


@pytest.mark.parametrize("kwargs, verdict", [
    (dict(value=10.0), "met"),
    (dict(value=9.2), "partly"),  # tol = max(1, 1.0) = 1
    (dict(value=8.5), "missed"),
    (dict(value=19.0, comparison="lte", v=20.0), "met"),
    (dict(value=23.0, comparison="lte", v=20.0), "missed"),  # tol = 2
    (dict(value=15.0, comparison="between", v=12.0, vh=15.0), "met"),
    (dict(value=16.5, comparison="between", v=12.0, vh=15.0), "met"),  # beating the range is not a miss
    (dict(value=11.0, comparison="between", v=12.0, vh=15.0), "partly"),  # tol 1.2 from 12
    (dict(value=10.5, comparison="between", v=12.0, vh=15.0), "missed"),
    (dict(value=1040.0, comparison="approx", v=1000.0, unit="cr", metric="revenue"), "met"),  # tol = 50
    (dict(value=1090.0, comparison="approx", v=1000.0, unit="cr", metric="revenue"), "partly"),
    (dict(value=1200.0, comparison="approx", v=1000.0, unit="cr", metric="revenue"), "missed"),
    (dict(value=5.0, quarters_in=2), "pending"),
    (dict(value=5.0, metric="other"), "not_checkable"),
    (dict(value=5.0, period="next year"), "not_checkable"),
])
def test_judge_matrix(kwargs, verdict):
    assert check(**kwargs) == verdict


def test_missing_row_is_not_checkable():
    t = target(metric="pat_growth_yoy")
    no_pat = Table(columns=QUARTERS.columns, rows={"Sales": QUARTERS.rows["Sales"]})
    assert judge(t, actual_for(t, no_pat)) == "not_checkable"


def test_extract_targets_keeps_only_grounded(tmp_path):
    doc = DocText(url="u", pages=["Intro remarks.", "We expect revenue growth of 12 to 14% in FY27 overall."])
    reply = {"targets": [
        {"metric": "revenue_growth_yoy", "raw_metric": "revenue growth", "comparison": "between", "value": 12,
         "value_high": 14, "unit": "pct", "period": "FY27", "forward_looking": True,
         "quote": "We expect revenue growth of 12 to 14% in FY27", "source_id": "T:2026-08-01:p2"},
        {"metric": "pat", "raw_metric": "profit", "comparison": "gte", "value": 500, "value_high": None,
         "unit": "cr", "period": "FY27", "quote": "profit above 500 crore", "source_id": "T:2026-08-01:p9", "forward_looking": True},
        {"metric": "pat", "raw_metric": "profit", "comparison": "gte", "value": 500, "value_high": None,
         "unit": "cr", "period": "FY27", "quote": "profit will cross 500 crore", "source_id": "T:2026-08-01:p2", "forward_looking": True},
        {"metric": "volume_growth", "raw_metric": "volume growth", "comparison": "approx", "value": 9,
         "unit": "pct", "period": "FY27", "quote": "Intro remarks", "source_id": "[T:2026-08-01:p1]"},
    ]}
    llm, fake = make_llm(tmp_path, [json.dumps(reply)])
    targets = extract_targets(doc, date(2026, 8, 1), llm)
    assert [t.metric for t in targets] == ["revenue_growth_yoy"]  # unknown page, unfound quote, past result dropped
    assert targets[0].said_on == date(2026, 8, 1)
    assert "[T:2026-08-01:p2]" in fake.calls[0].user


def test_assess_dedupes_keeping_latest(tmp_path):
    old = target(value=8.0, said_on=date(2025, 5, 1))
    new = target(value=11.0, said_on=date(2025, 8, 1), source_id="T:2025-08-01:p2")
    llm, _ = make_llm(tmp_path, [json.dumps({"lines": [{"i": 0, "text": "Growth came in at 10% against 12%."}]})])
    rows = assess_delivery([old, new], QUARTERS, llm)
    assert len(rows) == 1 and rows[0].target.value == 11.0
    assert rows[0].verdict == "partly"  # 10 vs >= 11, tol 1.1


def test_explain_cannot_change_verdict(tmp_path):
    llm, fake = make_llm(tmp_path, [json.dumps({"lines": [{"i": 0, "text": "Management missed this badly."}]})])
    rows = assess_delivery([target()], QUARTERS, llm)
    assert rows[0].verdict == "met"
    assert "missed" not in rows[0].explanation  # a contradicting line falls back to the template
    assert "verdict: met" in fake.calls[0].user


def test_explain_fallback_on_llm_error(tmp_path):
    llm, _ = make_llm(tmp_path, [])
    llm.complete_json = lambda *a, **k: (_ for _ in ()).throw(LLMError("down"))
    rows = assess_delivery([target()], QUARTERS, llm)
    assert rows[0].verdict == "met"
    assert rows[0].explanation == "Guided revenue growth ≥ 10% for FY26; delivered 10%."


def test_extract_targets_maps_unlisted_metrics_to_other(tmp_path):
    doc = DocText(url="u", pages=["We expect volume growth of about 9% this year."])
    reply = {"targets": [{"metric": "volume_growth", "raw_metric": "volume growth", "comparison": "approx",
                          "value": 9, "unit": "pct", "period": "FY27", "forward_looking": True,
                          "quote": "We expect volume growth of about 9% this year.", "source_id": "[T:2026-08-01:p1]"}]}
    llm, _ = make_llm(tmp_path, [json.dumps(reply)])
    [t] = extract_targets(doc, date(2026, 8, 1), llm)
    assert (t.metric, t.source_id) == ("other", "T:2026-08-01:p1")


def test_not_checkable_rows_skip_the_model(tmp_path):
    llm, fake = make_llm(tmp_path, [])
    rows = assess_delivery([target(metric="other", raw_metric="volume growth")], QUARTERS, llm)
    assert fake.calls == []
    assert rows[0].explanation == "Guided volume growth ≥ 10% for FY26; not checkable from reported financials."
